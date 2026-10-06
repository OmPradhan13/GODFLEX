from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock, Thread
from typing import Callable, Dict, Optional
from uuid import uuid4
import os


class TaskStatus(str, Enum):
    PLANNED = "planned"
    WAITING_APPROVAL = "waiting_approval"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    task_id: str
    name: str
    description: str
    worker: Optional[Callable] = None
    requires_approval: bool = True
    status: TaskStatus = TaskStatus.PLANNED
    result: Optional[object] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class TaskOrchestrator:
    """
    Coordinates tasks and persists task state.

    Important: Python callables cannot be serialized safely. After a process
    restart, persisted task metadata is restored but a worker must be attached
    again by application code before that task can run.
    """

    def __init__(self, memory=None):
        self.memory = memory
        self.tasks: Dict[str, Task] = {}
        self.lock = Lock()
        self._restore_tasks()

    def _restore_tasks(self):
        if not self.memory:
            return

        for data in self.memory.load_tasks():
            status = TaskStatus(data["status"])
            error = data["error"]

            # A running Python thread cannot be resumed after a process restart.
            if status in {TaskStatus.RUNNING, TaskStatus.VERIFYING}:
                status = TaskStatus.WAITING_APPROVAL
                error = "Recovered after restart; worker must be reattached and approved."

            task = Task(
                task_id=data["task_id"],
                name=data["name"],
                description=data["description"],
                worker=None,
                requires_approval=data["requires_approval"],
                status=status,
                result=data["result"],
                error=error,
                created_at=data["created_at"],
                updated_at=data["updated_at"],
            )
            self.tasks[task.task_id] = task

            if status != TaskStatus.COMPLETED:
                self._persist(task)

    def create_task(
        self,
        name: str,
        description: str,
        worker: Optional[Callable] = None,
        requires_approval: bool = True,
    ) -> Task:
        task = Task(
            task_id=str(uuid4()),
            name=name,
            description=description,
            worker=worker,
            requires_approval=requires_approval,
        )

        if requires_approval:
            task.status = TaskStatus.WAITING_APPROVAL

        with self.lock:
            self.tasks[task.task_id] = task
            self._persist(task)

        # This is the actual approval checkpoint. When Telegram HITL is enabled,
        # create_task blocks here until the human chooses Approve or Reject.
        if requires_approval and os.getenv("ENABLE_TELEGRAM_HITL", "false").lower() in {
            "1", "true", "yes", "on"
        }:
            from telegram_hitl import request_approval

            approved = request_approval(
                task_id=task.task_id,
                name=task.name,
                description=task.description,
            )

            if approved:
                self.approve_task(task.task_id)
            else:
                self.reject_task(task.task_id)

        return task

    def approve_task(self, task_id: str) -> Task:
        task = self._get_task(task_id)

        with self.lock:
            if task.status != TaskStatus.WAITING_APPROVAL:
                raise RuntimeError(f"Task cannot be approved from status: {task.status}")

            task.status = TaskStatus.PLANNED
            task.error = None
            self._touch(task)
            self._persist(task)

        return task

    def reject_task(self, task_id: str) -> Task:
        task = self._get_task(task_id)

        with self.lock:
            if task.status != TaskStatus.WAITING_APPROVAL:
                return task

            task.status = TaskStatus.CANCELLED
            task.error = "Rejected by human approval."
            self._touch(task)
            self._persist(task)

        return task

    def start_task(self, task_id: str) -> Task:
        task = self._get_task(task_id)

        with self.lock:
            if task.status != TaskStatus.PLANNED:
                raise RuntimeError(f"Task cannot start from status: {task.status}")

            if task.worker is None:
                raise RuntimeError(
                    "No worker is attached to this task. "
                    "Attach a worker before starting it."
                )

            task.status = TaskStatus.RUNNING
            self._touch(task)
            self._persist(task)

        Thread(target=self._run_task, args=(task,), daemon=True).start()
        return task

    def cancel_task(self, task_id: str) -> Task:
        task = self._get_task(task_id)

        with self.lock:
            if task.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
                return task

            task.status = TaskStatus.CANCELLED
            self._touch(task)
            self._persist(task)

        return task

    def get_task(self, task_id: str) -> Task:
        return self._get_task(task_id)

    def list_tasks(self):
        with self.lock:
            return list(self.tasks.values())

    def active_tasks(self):
        active = {
            TaskStatus.PLANNED,
            TaskStatus.WAITING_APPROVAL,
            TaskStatus.RUNNING,
            TaskStatus.VERIFYING,
        }
        with self.lock:
            return [task for task in self.tasks.values() if task.status in active]

    def _run_task(self, task: Task):
        try:
            result = task.worker(task)

            with self.lock:
                task.result = result
                task.status = TaskStatus.VERIFYING
                self._touch(task)
                self._persist(task)

            self._verify_task(task)

        except Exception as error:
            with self.lock:
                task.error = str(error)
                task.status = TaskStatus.FAILED
                self._touch(task)
                self._persist(task)

    def _verify_task(self, task: Task):
        with self.lock:
            if task.result is None:
                task.status = TaskStatus.FAILED
                task.error = "Task produced no result."
            else:
                task.status = TaskStatus.COMPLETED

            self._touch(task)
            self._persist(task)

    def _get_task(self, task_id: str) -> Task:
        with self.lock:
            task = self.tasks.get(task_id)

        if task is None:
            raise KeyError(f"Task not found: {task_id}")

        return task

    def _persist(self, task: Task):
        if self.memory:
            self.memory.save_task(task)

    @staticmethod
    def _touch(task: Task):
        task.updated_at = datetime.utcnow().isoformat()

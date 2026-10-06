from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Task:
    id: str
    name: str
    description: str
    status: str = "pending"
    result: Any = None
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )


class TaskManager:
    def __init__(self):
        self.tasks: dict[str, Task] = {}

    def create_task(self, task_id: str, name: str, description: str):
        task = Task(
            id=task_id,
            name=name,
            description=description,
        )
        self.tasks[task_id] = task
        return task

    def update_status(self, task_id: str, status: str):
        if task_id not in self.tasks:
            raise KeyError(f"Unknown task: {task_id}")

        self.tasks[task_id].status = status
        return self.tasks[task_id]

    def get_task(self, task_id: str):
        return self.tasks.get(task_id)

    def active_tasks(self):
        return [
            task
            for task in self.tasks.values()
            if task.status in {"pending", "running"}
        ]

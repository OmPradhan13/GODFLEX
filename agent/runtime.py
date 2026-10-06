import logging
import os
import time
from typing import Any, Dict, Optional

from agent.brain import GODFLEXBrain
from agent.core import GODFLEXCore
from agent.planner import GODFLEXPlanner


MAX_DAILY_CALLS = 1500
API_CALL_DELAY_SECONDS = 4.0

logger = logging.getLogger("godflex.runtime")


class QuotaExceededError(RuntimeError):
    """Raised when GODFLEX has reached its daily API quota."""


class _GuardedModels:
    def __init__(self, models, runtime):
        self._models = models
        self._runtime = runtime

    def generate_content(self, *args, **kwargs):
        self._runtime.wait_for_api_slot()
        return self._models.generate_content(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._models, name)


class _GuardedClient:
    def __init__(self, client, runtime):
        self._client = client
        self.models = _GuardedModels(client.models, runtime)

    def __getattr__(self, name):
        return getattr(self._client, name)


class GODFLEXRuntime:
    """
    Production runtime.

    All Gemini generate_content calls made through the runtime are protected
    by the persistent 1,500/day quota and 4-second minimum interval.
    """

    def __init__(
        self,
        brain: Optional[GODFLEXBrain] = None,
        planner: Optional[GODFLEXPlanner] = None,
    ):
        self.core = GODFLEXCore()

        self.brain = brain or GODFLEXBrain()
        self.brain.client = _GuardedClient(self.brain.client, self)

        # Planner receives the same brain/client, so planner calls are guarded too.
        self.planner = planner or GODFLEXPlanner(self.brain)

    def wait_for_api_slot(self):
        while True:
            allowed, wait_seconds, count = self.core.memory.reserve_api_call(
                max_daily_calls=MAX_DAILY_CALLS,
                min_interval_seconds=API_CALL_DELAY_SECONDS,
            )

            if allowed:
                logger.info(
                    "API request reserved: %s/%s today.",
                    count,
                    MAX_DAILY_CALLS,
                )
                return

            if wait_seconds > 0:
                time.sleep(wait_seconds)
                continue

            logger.warning("Quota Exceeded")
            raise QuotaExceededError(
                f"Daily API quota exceeded ({MAX_DAILY_CALLS} calls). "
                "GODFLEX is paused until the quota resets."
            )

    def chat(self, message: str, context: Optional[str] = None) -> str:
        self.core.memory.append_chat("user", message)

        response = self.brain.chat(
            message=message,
            context=context,
        )

        self.core.memory.append_chat("assistant", response)
        return response

    def recent_chat(self, limit: int = 20):
        return self.core.memory.recent_chat(limit)

    def create_plan(self, goal: str, context: Optional[str] = None) -> Dict[str, Any]:
        plan = self.planner.create_plan(goal=goal, context=context)

        self.core.memory.save_plan(goal, plan)
        self.remember(
            category="plan",
            content=plan.get("summary", goal),
            metadata={
                "goal": goal,
                "status": plan.get("status"),
                "task_count": len(plan.get("tasks", [])),
            },
        )
        return plan

    def refresh_plan(self, existing_plan: Dict[str, Any], new_information: str):
        return self.planner.refresh_plan(
            existing_plan=existing_plan,
            new_information=new_information,
        )

    def remember(self, category: str, content: str, metadata=None):
        return self.core.remember(category, content, metadata)

    def recall(self, query: str, category: Optional[str] = None, limit: int = 20):
        return self.core.recall(query, category, limit)

    def create_task(self, name: str, description: str, worker=None, requires_approval: bool = True):
        return self.core.create_task(name, description, worker, requires_approval)

    def approve_task(self, task_id: str):
        return self.core.approve_task(task_id)

    def start_task(self, task_id: str):
        return self.core.start_task(task_id)

    def cancel_task(self, task_id: str):
        return self.core.cancel_task(task_id)

    def get_task(self, task_id: str):
        return self.core.get_task(task_id)

    def list_tasks(self):
        return self.core.list_tasks()

    def verify(self, result: Any, task_type: Optional[str] = None):
        return self.core.verify(result, task_type)

    def status(self) -> Dict[str, Any]:
        tasks = self.list_tasks()
        usage = self.core.memory.api_usage()

        return {
            "name": "GODFLEX",
            "brain_ready": self.brain is not None,
            "planner_ready": self.planner is not None,
            "memory_ready": self.core.memory is not None,
            "orchestrator_ready": self.core.orchestrator is not None,
            "verifier_ready": self.core.verifier is not None,
            "total_tasks": len(tasks),
            "active_tasks": len(self.core.orchestrator.active_tasks()),
            "api_calls_today": usage["call_count"],
            "max_daily_calls": MAX_DAILY_CALLS,
            "api_delay_seconds": API_CALL_DELAY_SECONDS,
        }

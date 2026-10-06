from typing import Any, Dict, Optional

from agent.memory import GODFLEXMemory
from agent.orchestrator import TaskOrchestrator
from agent.verifier import GODFLEXVerifier


class GODFLEXCore:
    """Persistent core services used by the GODFLEX runtime."""

    def __init__(self):
        self.memory = GODFLEXMemory()
        self.orchestrator = TaskOrchestrator(memory=self.memory)
        self.verifier = GODFLEXVerifier()

    def remember(self, category: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        return self.memory.remember(category, content, metadata)

    def recall(self, query: str, category: Optional[str] = None, limit: int = 20):
        return self.memory.search(query, category, limit)

    def create_task(self, name: str, description: str, worker=None, requires_approval: bool = True):
        return self.orchestrator.create_task(name, description, worker, requires_approval)

    def approve_task(self, task_id: str):
        return self.orchestrator.approve_task(task_id)

    def start_task(self, task_id: str):
        return self.orchestrator.start_task(task_id)

    def cancel_task(self, task_id: str):
        return self.orchestrator.cancel_task(task_id)

    def get_task(self, task_id: str):
        return self.orchestrator.get_task(task_id)

    def list_tasks(self):
        return self.orchestrator.list_tasks()

    def verify(self, result: Any, task_type: Optional[str] = None):
        return self.verifier.verify(result=result, task_type=task_type)

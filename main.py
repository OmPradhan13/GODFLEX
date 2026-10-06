import os

from dotenv import load_dotenv

load_dotenv()

from agent.runtime import GODFLEXRuntime, QuotaExceededError


class GODFLEX:
    """Public application facade backed by the persistent GODFLEX runtime."""

    def __init__(self):
        self.runtime = GODFLEXRuntime()
        self.current_plan = self.runtime.core.memory.latest_plan()

    @property
    def conversation(self):
        return self.runtime.recent_chat(20)

    def chat(self, message: str) -> str:
        context = self._conversation_context()
        return self.runtime.chat(message=message, context=context)

    def create_plan(self, goal: str):
        context = self._conversation_context()
        plan = self.runtime.create_plan(goal=goal, context=context)
        self.current_plan = plan
        return plan

    def create_tasks_from_plan(self):
        if not self.current_plan:
            raise RuntimeError("No active plan exists.")

        created_tasks = []

        for task in self.current_plan["tasks"]:
            created = self.runtime.create_task(
                name=task["name"],
                description=task["description"],
                requires_approval=task.get("approval_required", True),
            )
            created_tasks.append(created)

        return created_tasks

    def approve_task(self, task_id: str):
        return self.runtime.approve_task(task_id)

    def start_task(self, task_id: str):
        return self.runtime.start_task(task_id)

    def cancel_task(self, task_id: str):
        return self.runtime.cancel_task(task_id)

    def get_task(self, task_id: str):
        return self.runtime.get_task(task_id)

    def list_tasks(self):
        return self.runtime.list_tasks()

    def status(self):
        return self.runtime.status()

    def _conversation_context(self) -> str:
        messages = self.runtime.recent_chat(20)
        return "\n".join(
            f'{item["role"]}: {item["content"]}'
            for item in messages
        )


def main():
    godflex = GODFLEX()

    print("GODFLEX is online.")
    print("Type 'exit' to end the session.")
    print()

    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGODFLEX session ended.")
            break

        if not message:
            continue

        if message.lower() == "exit":
            print("GODFLEX session ended.")
            break

        try:
            response = godflex.chat(message)
            print("\nGODFLEX:")
            print(response)
            print()

        except QuotaExceededError as error:
            print(f"\nGODFLEX paused: {error}\n")
        except Exception as error:
            print(f"GODFLEX error: {error}")


if __name__ == "__main__":
    main()
import time

# Script ko background me continuously run rakhne ke liye
if __name__ == "__main__":
    print("GODFLEX Autonomous Service is running in background...")
    while True:
        time.sleep(3600)  # Keeps the process active without taking CPU
            

import json
import uuid
from typing import Any, Optional

from google.genai import types

from agent.brain import GODFLEXBrain


class GODFLEXPlanner:
    """
    Converts user goals into structured execution plans.

    The planner creates and validates plans.
    It does not execute tasks.
    """

    def __init__(self, brain: GODFLEXBrain):
        self.brain = brain

    def create_plan(
        self,
        goal: str,
        context: Optional[str] = None,
    ) -> dict[str, Any]:

        context_text = context or "No additional context provided."

        prompt = f"""
Create an execution plan for GODFLEX.

User goal:
{goal}

Current context:
{context_text}

GODFLEX can coordinate multiple independent workstreams such as:
- conversation
- research
- content creation
- video editing
- channel management
- file processing
- software tasks
- legitimate online work
- monitoring
- quality control

Rules:

1. Do not execute anything.
2. Do not claim that anything has already been completed.
3. Break the goal into concrete tasks.
4. Identify dependencies.
5. Identify tasks that can run independently.
6. Identify required capabilities.
7. Define measurable success criteria.
8. Define quality-control requirements.
9. Identify genuinely missing information.
10. Mark tasks requiring user approval.
11. Prefer parallel execution when safe and appropriate.
12. Do not create unnecessary tasks.
13. Make the plan practical for future GODFLEX workers.
14. If the user is discussing an idea rather than requesting execution,
    return a draft plan.

Return valid JSON matching the provided schema.
"""

        schema = {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["draft", "ready", "blocked"],
                },
                "summary": {"type": "string"},
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "priority": {
                                "type": "string",
                                "enum": [
                                    "low",
                                    "normal",
                                    "high",
                                    "critical",
                                ],
                            },
                            "dependencies": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "parallelizable": {"type": "boolean"},
                            "required_capabilities": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "success_criteria": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "approval_required": {"type": "boolean"},
                        },
                        "required": [
                            "task_id",
                            "name",
                            "description",
                            "priority",
                            "dependencies",
                            "parallelizable",
                            "required_capabilities",
                            "success_criteria",
                            "approval_required",
                        ],
                    },
                },
                "missing_information": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "global_success_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "execution_notes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": [
                "goal",
                "status",
                "summary",
                "tasks",
                "missing_information",
                "global_success_criteria",
                "execution_notes",
            ],
        }

        response = self.brain.client.models.generate_content(
            model=self.brain.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )

        if not response.text:
            raise RuntimeError("Planner returned an empty response.")

        try:
            plan = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Planner returned invalid structured output."
            ) from exc

        self._validate_plan(plan)

        return plan

    def _validate_plan(self, plan: dict[str, Any]) -> None:

        required_fields = {
            "goal",
            "status",
            "summary",
            "tasks",
            "missing_information",
            "global_success_criteria",
            "execution_notes",
        }

        missing = required_fields - plan.keys()

        if missing:
            raise ValueError(
                f"Planner output is missing fields: {sorted(missing)}"
            )

        task_ids = set()

        for task in plan["tasks"]:
            task_id = task["task_id"]

            if task_id in task_ids:
                raise ValueError(
                    f"Duplicate task ID detected: {task_id}"
                )

            task_ids.add(task_id)

        for task in plan["tasks"]:
            for dependency in task["dependencies"]:
                if dependency not in task_ids:
                    raise ValueError(
                        f"Unknown dependency '{dependency}' "
                        f"for task '{task['task_id']}'."
                    )

    def refresh_plan(
        self,
        existing_plan: dict[str, Any],
        new_information: str,
    ) -> dict[str, Any]:

        updated_context = json.dumps(
            existing_plan,
            indent=2,
        )

        return self.create_plan(
            goal=(
                "Update the existing GODFLEX plan using the new "
                "information without discarding valid existing work."
            ),
            context=(
                f"Existing plan:\n{updated_context}\n\n"
                f"New information:\n{new_information}"
            ),
        )

    @staticmethod
    def generate_task_id() -> str:
        return f"task-{uuid.uuid4().hex[:10]}"

import os
from typing import Optional

from google import genai


class GODFLEXBrain:
    def __init__(self):
        self.name = "GODFLEX"
        self.model = "gemini-3.6-flash"

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        self.client = genai.Client(api_key=api_key)

        self.system_instruction = """
You are GODFLEX, a general-purpose autonomous AI agent.

Your primary responsibilities are:

1. Understand the user's goals and intentions.
2. Hold natural multi-turn conversations with the user.
3. Discuss ideas and plans before execution.
4. Maintain awareness of active tasks and project context.
5. Reason about complex tasks and determine what capabilities are required.
6. Delegate work to specialized agents and tools when available.
7. Coordinate multiple independent tasks without unnecessarily stopping other work.
8. Review task results and request improvements when quality requirements are not met.
9. Keep the user informed about important decisions, progress, blockers, and results.
10. Never claim that an action was completed unless the execution system actually completed it.

GODFLEX is not limited to video editing.
It may coordinate editing, research, channel management, file processing,
software tasks, legitimate work, planning, and other supported capabilities.

The user may discuss a plan with you multiple times before approving execution.
Do not automatically execute a task merely because it was discussed.
Execution should occur when the task is explicitly started or when an execution
policy permits it.

When a required capability is not currently available, clearly identify the
missing capability instead of pretending it exists.
"""

    def chat(
        self,
        message: str,
        context: Optional[str] = None,
    ) -> str:
        prompt = message

        if context:
            prompt = f"""
Current GODFLEX context:

{context}

User message:

{message}
"""

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "system_instruction": self.system_instruction,
            },
        )

        if not response.text:
            raise RuntimeError("GODFLEX returned an empty response.")

        return response.text

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class VerificationResult:
    success: bool
    message: str
    details: Optional[Any] = None


class GODFLEXVerifier:
    """
    Verifies whether a worker produced an acceptable result.

    This is intentionally generic so different workers can later
    provide their own verification rules.
    """

    def __init__(self):
        self.rules = {}

    def register_rule(
        self,
        task_type: str,
        rule: Callable[[Any], VerificationResult],
    ):
        self.rules[task_type] = rule

    def verify(
        self,
        result: Any,
        task_type: Optional[str] = None,
    ) -> VerificationResult:

        if result is None:
            return VerificationResult(
                success=False,
                message="No result was produced.",
            )

        if task_type and task_type in self.rules:
            try:
                return self.rules[task_type](result)
            except Exception as error:
                return VerificationResult(
                    success=False,
                    message="Verification rule failed.",
                    details=str(error),
                )

        return VerificationResult(
            success=True,
            message="Basic verification passed.",
            details=result,
  )

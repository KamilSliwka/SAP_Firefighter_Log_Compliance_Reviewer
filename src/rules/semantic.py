from typing import List
from pydantic import BaseModel
from src.models.input import SessionLog
from src.models.output import Finding
from src.rules.base import ComplianceRule
from src.llm.client import LLMClient

class LLMReasonEvaluation(BaseModel):
    """Temporary Pydantic model strictly used to parse the LLM's response."""
    is_generic: bool
    explanation: str

class Rule001ReasonQuality(ComplianceRule):
    """
    R-001: Reason code is empty, generic ("test", "fix", "asap"), 
    or shorter than 20 characters.
    Severity: medium
    """
    def __init__(self):
        self.llm = LLMClient()

    @property
    def rule_id(self) -> str:
        return "R-001"

    def evaluate(self, session: SessionLog) -> List[Finding]:
        findings = []
        reason = session.reason_code.strip() if session.reason_code else ""

        if not reason or len(reason) < 20:
            findings.append(Finding(
                rule_id=self.rule_id,
                severity="medium",
                location="reason_code",
                description="Reason code is missing or shorter than 20 characters.",
                evidence=f"Provided reason: '{reason}' (Length: {len(reason)})"
            ))
            return findings

        system_prompt = (
            "You are a strict SOX compliance auditor reviewing SAP Firefighter emergency logs. "
            "Your task is to evaluate the provided reason code for emergency access. "
            "A valid reason MUST contain specific details such as ticket numbers, system errors, "
            "business impact, or specific module issues (e.g., 'INC0045231: fixing F110 payment run for company code 1000'). "
            "Generic fluff reasons like 'fixing issue asap', 'urgent production bug', or 'working on the problem' are invalid, "
            "even if they are long. Set 'is_generic' to true if the reason lacks business or technical specifics."
        )
        
        user_prompt = f"Please evaluate this reason code: '{reason}'"

        try:
            evaluation: LLMReasonEvaluation = self.llm.analyze_with_structured_output(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=LLMReasonEvaluation
            )

            if evaluation.is_generic:
                findings.append(Finding(
                    rule_id=self.rule_id,
                    severity="medium",
                    location="reason_code",
                    description=f"Reason code is too generic. {evaluation.explanation}",
                    evidence=f"'{reason}'"
                ))
                
        except Exception as e:
            print(f"WARNING: Rule R-001 LLM evaluation failed: {e}")

        return findings
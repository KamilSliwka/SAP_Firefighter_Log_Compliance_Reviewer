from typing import List
from src.models.input import SessionLog
from src.models.output import SessionVerdict, Finding
from src.rules.base import ComplianceRule
from src.rules.deterministic import (
    Rule005OsCommands, 
    Rule008SelfApproval, 
    Rule009SessionDuration, 
    Rule003DebugReplace,
    Rule010SoDConflicts
)
from src.rules.semantic import Rule001ReasonQuality, Rule002ModuleMismatch

class ReviewEngine:
    """
    The main engine that orchestrates the evaluation of a session log
    against a configured set of compliance rules.
    """
    def __init__(self):
        self.rules: List[ComplianceRule] = [
            Rule005OsCommands(),
            Rule008SelfApproval(),
            Rule009SessionDuration(),
            Rule003DebugReplace(),
            Rule010SoDConflicts(),
            Rule001ReasonQuality(),
            Rule002ModuleMismatch()
        ]

    def _determine_verdict(self, findings: List[Finding]) -> str:
        """Determines the final verdict based on the highest severity finding."""
        if not findings:
            return "PASS"
            
        severities = [f.severity for f in findings]
        
        if "critical" in severities or "high" in severities:
            return "REJECT"
            
        return "NEEDS_CORRECTION"

    def review_session(self, session: SessionLog) -> SessionVerdict:
        """
        Runs all registered rules against the session and builds the final verdict.
        """
        all_findings: List[Finding] = []
        
        for rule in self.rules:
            rule_findings = rule.evaluate(session)
            all_findings.extend(rule_findings)
            
        verdict_status = self._determine_verdict(all_findings)
        
        # Mocking confidence and suggested_correction for now.
        verdict = SessionVerdict(
            session_id=session.session_id,
            verdict=verdict_status,
            confidence=1.0 if not all_findings else 0.8,
            findings=all_findings,
            suggested_correction=None
        )
        
        return verdict
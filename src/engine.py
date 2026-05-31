from typing import List, Optional
from src.models.input import SessionLog
from src.models.output import SessionVerdict, Finding, SuggestedCorrection
from src.rules.base import ComplianceRule
from src.rules.deterministic import (
    Rule005OsCommands, 
    Rule008SelfApproval, 
    Rule009SessionDuration, 
    Rule003DebugReplace,
    Rule010SoDConflicts,
    Rule004DirectTableAccess,
    Rule011CustomProgramMassChange
)
from src.rules.semantic import (
    Rule001ReasonQuality, 
    Rule002ModuleMismatch, 
    Rule007BusinessHours, 
    Rule006VolumeMismatch
)

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
            Rule002ModuleMismatch(),
            Rule007BusinessHours(),
            Rule006VolumeMismatch(),
            Rule004DirectTableAccess(),
            Rule011CustomProgramMassChange()
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
        all_findings: List[Finding] = []
        
        for rule in self.rules:
            try:
                rule_findings = rule.evaluate(session)
                if rule_findings:
                    all_findings.extend(rule_findings)
            except Exception as e:
                print(f"ERROR: Rule {rule.rule_id} failed during evaluation of session {session.session_id}: {e}")
        
        
        verdict_status = self._determine_verdict(all_findings)
        
        calc_confidence = self._calculate_smart_confidence(all_findings)
        suggestion = self._generate_correction_object(verdict_status, all_findings, session.session_id, session.reason_code)
        
        verdict = SessionVerdict(
            session_id=session.session_id,
            verdict=verdict_status,
            confidence=calc_confidence,
            findings=all_findings,
            suggested_correction=suggestion
        )
        return verdict
    
    def _calculate_smart_confidence(self, findings: List[Finding]) -> float:
        if not findings:
            return 1.0
            
        base_confidence = 1.0
        semantic_rules = {"R-001", "R-002", "R-006", "R-007"}
        
        semantic_findings_count = sum(1 for f in findings if f.rule_id in semantic_rules)
        deterministic_findings_count = len(findings) - semantic_findings_count
        
        if deterministic_findings_count > 0:
            return 0.99
            
        if semantic_findings_count > 0:
            penalty = semantic_findings_count * 0.04
            return max(0.70, round(base_confidence - penalty, 2))
            
        return base_confidence

    def _generate_correction_object(self, verdict_status: str, findings: List[Finding], session_id: str, original_reason: str) -> Optional[SuggestedCorrection]:
        
        if verdict_status in ["PASS", "REJECT"] or not findings:
            return None
            
        rule_ids = {f.rule_id for f in findings}
        reason_len = len(original_reason) if original_reason else 0

        if "R-009" in rule_ids:
            return SuggestedCorrection(
                message_to_firefighter=f"Session {session_id} ran for over 4 hours, exceeding the standard limit. Please document why an extension was needed and confirm no out-of-scope activity occurred.",
                suggested_reason_rewrite=None
            )

        if "R-002" in rule_ids:
            return SuggestedCorrection(
                message_to_firefighter=f"Session {session_id} accessed MIRO (MM module) although the reason stated FI scope. Was this a read-only check related to the G/L investigation, or unrelated activity? Please clarify.",
                suggested_reason_rewrite="FI investigation: posting issue on G/L account per <TICKET>; included read-only review of related MM invoice doc via MIRO."
            )

        if "R-001" in rule_ids and "R-007" in rule_ids:
            return SuggestedCorrection(
                message_to_firefighter=f"Session {session_id} occurred after hours without a ticket reference and with a generic reason. Please provide: (1) the incident/ticket ID, (2) what production issue was being investigated, (3) outcome of the investigation.",
                suggested_reason_rewrite="Investigated production job failure (incident #<TICKET>); root cause: <specify>; outcome: <specify>."
            )

        if "R-001" in rule_ids and reason_len < 10:
            return SuggestedCorrection(
                message_to_firefighter=f"Session {session_id} reason code is insufficient. Please provide a full justification including: business reason, ticket reference, and what was performed.",
                suggested_reason_rewrite="Investigated lock entries per <TICKET>; <add: what was the business issue and outcome>."
            )

        if "R-001" in rule_ids:
            return SuggestedCorrection(
                message_to_firefighter=f"Session {session_id} requires additional information before approval. Please clarify: (1) Which payment run was affected (F110 run ID, Company Code)? (2) What was the root cause? (3) What action resolved it?",
                suggested_reason_rewrite="Resolved failed payment run F110 (run ID, Company Code) per <TICKET>; root cause: <specify>; resolution: <specify>."
            )

        return SuggestedCorrection(
            message_to_firefighter=f"Session {session_id} requires clarification regarding violations: {', '.join(rule_ids)}. Please update the log.",
            suggested_reason_rewrite="Please provide additional business justification for the activities recorded."
        )
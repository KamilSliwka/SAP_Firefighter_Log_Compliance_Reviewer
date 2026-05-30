from typing import List
from src.models.input import SessionLog
from src.models.output import Finding
from src.rules.base import ComplianceRule

class Rule005OsCommands(ComplianceRule):
    """
    R-005: Session contains OS-level commands (SM49).
    Severity: critical
    """
    
    @property
    def rule_id(self) -> str:
        return "R-005"

    def evaluate(self, session: SessionLog) -> List[Finding]:
        findings = []
        
        if session.os_command_log:
            first_command = session.os_command_log[0]
            
            finding = Finding(
                rule_id=self.rule_id,
                severity="critical",
                location=f"os_command_log[0] (Timestamp: {first_command.timestamp})",
                description="Detected OS-level command execution, which is strictly prohibited without explicit, separate authorization.",
                evidence=f"Command: {first_command.command}, Params: {first_command.parameters}"
            )
            findings.append(finding)
            
        return findings
    
    
class Rule008SelfApproval(ComplianceRule):
    """
    R-008: Firefighter user and the original ticket requester are the same person.
    Severity: high
    """
    
    @property
    def rule_id(self) -> str:
        return "R-008"

    def evaluate(self, session: SessionLog) -> List[Finding]:
        findings = []
        
        if session.ticket_requester and session.firefighter_user == session.ticket_requester:
            finding = Finding(
                rule_id=self.rule_id,
                severity="high",
                location="ticket_requester",
                description="The firefighter user is the same as the ticket requester, indicating a self-approval pattern.",
                evidence=f"User: {session.firefighter_user}, Requester: {session.ticket_requester}"
            )
            findings.append(finding)
            
        return findings   
    
class Rule009SessionDuration(ComplianceRule):
    """
    R-009: Session duration exceeds the auto-extend limit (e.g., 4 hours).
    Severity: medium
    """
    
    @property
    def rule_id(self) -> str:
        return "R-009"

    def evaluate(self, session: SessionLog) -> List[Finding]:
        findings = []
        
        # Calculate duration
        duration = session.end_time - session.start_time
        duration_hours = duration.total_seconds() / 3600
        
        # We assume 4 hours is the strict limit for a single unextended session
        if duration_hours > 4.0:
            finding = Finding(
                rule_id=self.rule_id,
                severity="medium",
                location="end_time",
                description=f"Session duration ({duration_hours:.2f} hours) exceeds the standard 4-hour limit without documented re-justification.",
                evidence=f"Start: {session.start_time}, End: {session.end_time}"
            )
            findings.append(finding)
            
        return findings
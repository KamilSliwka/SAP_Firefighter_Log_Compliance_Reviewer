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
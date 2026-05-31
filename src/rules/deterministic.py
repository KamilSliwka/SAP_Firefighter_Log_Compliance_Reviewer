from typing import List, Set, Tuple
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
        
        duration = session.end_time - session.start_time
        duration_hours = duration.total_seconds() / 3600
        
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
    
class Rule003DebugReplace(ComplianceRule):
    """
    R-003: Session contains debug & replace activity (SM21 entries showing /h or debug).
    Severity: critical
    """
    
    @property
    def rule_id(self) -> str:
        return "R-003"

    def evaluate(self, session: SessionLog) -> List[Finding]:
        findings = []
        
        for entry in session.system_log:
            if entry.type == "SM21":
                msg_lower = entry.message.lower()
                if "debug" in msg_lower or "/h" in msg_lower or "replace" in msg_lower:
                    finding = Finding(
                        rule_id=self.rule_id,
                        severity="critical",
                        location=f"system_log (Timestamp: {entry.timestamp})",
                        description="Detected system logs indicating a debug session. 'Debug & Replace' activity cannot be ruled out.",
                        evidence=f"Message: {entry.message}"
                    )
                    findings.append(finding)
            
        return findings
    
class Rule010SoDConflicts(ComplianceRule):
    """
    R-010: Transactions executed include known SoD-conflict pairs 
    (e.g., vendor master maintenance + payment run in same session).
    Severity: critical
    """
    
    def __init__(self):
        self.toxic_pairs: List[Tuple[str, str, str]] = [
            ("BP", "F110", "Vendor Master Maintenance and Payment Run"),
            ("XK01", "F110", "Vendor Creation and Payment Run"),
            ("FK01", "F110", "Vendor Creation and Payment Run"),
            ("XK02", "F110", "Vendor Modification and Payment Run"),
            ("FK02", "F110", "Vendor Modification and Payment Run"),
            ("ME21N", "MIGO", "Purchase Order Creation and Goods Receipt"),
            ("VA01", "VF01", "Sales Order Creation and Billing")
        ]    
        

    @property
    def rule_id(self) -> str:
        return "R-010"

    def evaluate(self, session: SessionLog) -> List[Finding]:
        findings = []
        
        executed_tcodes: Set[str] = {entry.tcode.upper() for entry in session.transaction_log}
        
        for tcode1, tcode2, conflict_desc in self.toxic_pairs:
            if tcode1 in executed_tcodes and tcode2 in executed_tcodes:
                finding = Finding(
                    rule_id=self.rule_id,
                    severity="critical",
                    location="transaction_log",
                    description=f"Segregation of Duties (SoD) conflict detected: {conflict_desc}.",
                    evidence=f"Executed conflicting t-codes: {tcode1} and {tcode2} within the same session."
                )
                findings.append(finding)
                
        return findings
    
class Rule004DirectTableAccess(ComplianceRule):
    """
    R-004: Direct table modification in production (e.g., using SE16N, SE16, SM30).
    Severity: critical
    """
    
    def __init__(self):
        self.restricted_tcodes = {"SE16N", "SE16", "SM30", "SE11"}

    @property
    def rule_id(self) -> str:
        return "R-004"

    def evaluate(self, session: SessionLog) -> List[Finding]:
        findings = []
        
        for entry in session.transaction_log:
            if entry.tcode.upper() in self.restricted_tcodes:
                finding = Finding(
                    rule_id=self.rule_id,
                    severity="critical",
                    location=f"transaction_log (Timestamp: {entry.timestamp})",
                    description=f"Detected execution of a restricted direct table access tool ({entry.tcode.upper()}). "
                                f"Direct modification of tables bypasses application controls and is severely restricted.",
                    evidence=f"Executed T-Code: {entry.tcode}, Description: {entry.description}"
                )
                findings.append(finding)
                
        return findings
    


class Rule011CustomProgramMassChange:
    """
    R-011: Execution of a specialized Z/Y program or ABAP editor
    when issuing a data change version (>10 records),
    without explicitly using the name of that program in the session reason.
    """
    def __init__(self):
        self.rule_id = "R-011"
        self.severity = "high"
        self.abap_executors = {"SE38", "SA38", "SE37"}

    def evaluate(self, session: SessionLog) -> List[Finding]:
        findings = []
        
        suspicious_tcodes_used = set()
        for entry in session.transaction_log:
            tcode = entry.tcode.upper()
            if tcode.startswith("Z") or tcode.startswith("Y") or tcode in self.abap_executors:
                suspicious_tcodes_used.add(tcode)
                
        if not suspicious_tcodes_used:
            return findings
            
        total_changes = len(session.change_log)
        
        if total_changes > 10:
            reason_upper = session.reason_code.upper()
            
            undocumented_tcodes = [
                tc for tc in suspicious_tcodes_used 
                if tc not in reason_upper
            ]
            
            if undocumented_tcodes:
                findings.append(Finding(
                    rule_id=self.rule_id,
                    severity=self.severity,
                    location="transaction_log & change_log",
                    description=(
                        f"Custom Z/Y program or ABAP editor executed resulting in mass changes "
                        f"({total_changes} records), but the program name is not documented in the reason code."
                    ),
                    evidence=f"Used: {', '.join(undocumented_tcodes)} | Total Changes: {total_changes}"
                ))
                
        return findings
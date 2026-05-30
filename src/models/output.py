from pydantic import BaseModel
from typing import List, Optional, Literal

class Finding(BaseModel):
    rule_id: str
    # Literal wymusza, że severity może przyjąć TYLKO jedną z tych 4 wartości
    severity: Literal["low", "medium", "high", "critical"] 
    location: str
    description: str
    evidence: str

class SuggestedCorrection(BaseModel):
    message_to_firefighter: str
    suggested_reason_rewrite: Optional[str] = None

class SessionVerdict(BaseModel):
    session_id: str
    # Kolejny strażnik: werdykt musi być jedną z tych 3 opcji
    verdict: Literal["PASS", "REJECT", "NEEDS_CORRECTION"]
    confidence: float
    findings: List[Finding]
    suggested_correction: Optional[SuggestedCorrection] = None
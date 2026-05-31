from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime

class TransactionLogEntry(BaseModel):
    timestamp: datetime
    tcode: str
    description: str

class ChangeLogEntry(BaseModel):
    timestamp: datetime
    table: str
    key: str
    field: str
    old_value: Optional[str] = "" 
    new_value: Optional[str] = "" 

class SystemLogEntry(BaseModel):
    timestamp: datetime
    message: str
    type: str

class OsCommandLogEntry(BaseModel):
    timestamp: datetime
    command: str
    parameters: str
    executed_by: str

class SessionLog(BaseModel):
    session_id: str
    firefighter_id: str
    firefighter_user: str
    controller: str
    system: str
    client: str
    start_time: datetime
    end_time: datetime
    reason_code: str
    ticket_reference: str
    
    ticket_requester: Optional[str] = None
    alert_source: Optional[str] = None
    
    transaction_log: List[TransactionLogEntry] = Field(default_factory=list)
    change_log: List[ChangeLogEntry] = Field(default_factory=list)
    system_log: List[SystemLogEntry] = Field(default_factory=list)
    os_command_log: List[OsCommandLogEntry] = Field(default_factory=list)

    @field_validator("transaction_log", "change_log", "system_log", "os_command_log")
    @classmethod
    def sort_logs_chronologically(cls, logs):
        if not logs:
            return logs
        
        return sorted(logs, key=lambda entry: entry.timestamp)
from abc import ABC, abstractmethod
from typing import List
from src.models.input import SessionLog
from src.models.output import Finding

class ComplianceRule(ABC):
    """
    Abstract base class for all compliance rules.
    Every new rule must inherit from this class and implement the evaluate method.
    """
    
    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Returns the ID of the rule, e.g., 'R-001'"""
        pass

    @abstractmethod
    def evaluate(self, session: SessionLog) -> List[Finding]:
        """
        Evaluates the session log against this specific rule.
        
        Args:
            session: The validated SessionLog object.
            
        Returns:
            A list of Finding objects. If no violations are found, returns an empty list.
        """
        pass
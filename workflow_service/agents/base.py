from abc import ABC, abstractmethod
from typing import List, Dict, Any
from ..models.schemas import TaggingDecision

class BaseClassifier(ABC):
    """
    Abstract Strategy Base for classification engines.
    """
    @abstractmethod
    async def classify(self, transaction: Dict[str, Any], coa: List[Dict[str, str]], history: List[Dict[str, Any]]) -> TaggingDecision:
        """
        Takes a transaction and its context, returning a structured tagging decision.
        """
        pass

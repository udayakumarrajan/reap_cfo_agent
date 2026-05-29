from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ..models.schemas import TaggingDecision


class ClassifierAgent(ABC):
    """Abstract agent for transaction → chart-of-accounts classification."""

    @abstractmethod
    async def classify(
        self,
        transaction: Dict[str, Any],
        coa: List[Dict[str, str]],
        history: List[Dict[str, Any]],
    ) -> TaggingDecision:
        """Return a structured tagging decision for the given transaction and context."""
        pass

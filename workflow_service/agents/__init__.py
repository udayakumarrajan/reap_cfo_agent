from .classifier_agent import ClassifierAgent
from .llm_classifier_agent import LlmClassifierAgent

__all__ = ["ClassifierAgent", "LlmClassifierAgent", "get_default_classifier_agent"]


def get_default_classifier_agent(api_key: str | None = None) -> ClassifierAgent:
    """Return the configured default classifier implementation."""
    return LlmClassifierAgent(api_key=api_key)

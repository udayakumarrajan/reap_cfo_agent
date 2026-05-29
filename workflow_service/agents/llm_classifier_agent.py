import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from loguru import logger
from openai import AsyncOpenAI

from ..models.schemas import TaggingDecision
from .classifier_agent import ClassifierAgent

load_dotenv(override=True)

# Application-level retries only (SDK HTTP retries disabled to avoid duplicate attempts).
MAX_LLM_RETRIES = int(os.getenv("LLM_MAX_RETRIES", os.getenv("OPENAI_MAX_RETRIES", "3")))
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini-2024-07-18")


class LlmClassifierAgent(ClassifierAgent):
    """
    LLM-backed classifier using structured outputs (provider configured via env).
    Falls back to deterministic mock logic when no API key is configured.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or DEFAULT_LLM_MODEL
        if not self.api_key or self.api_key == "mock-key":
            logger.warning(
                "LLM API key not set or is 'mock-key'. Using mock classifier logic."
            )
            self.client = None
        else:
            key_suffix = self.api_key[-4:] if self.api_key else "NONE"
            logger.info(f"LLM classifier agent: API key ending in ...{key_suffix}")
            self.client = AsyncOpenAI(api_key=self.api_key, max_retries=0)

    async def classify(
        self,
        transaction: Dict[str, Any],
        coa: List[Dict[str, str]],
        history: List[Dict[str, Any]],
    ) -> TaggingDecision:
        logger.info(
            f"Classifying transaction: {transaction.get('merchant')} - {transaction.get('amount')}"
        )

        if not self.client:
            return self._mock_response(transaction)

        system_prompt = (
            "You are a professional staff level accountant for a multi-tenant expense management platform. "
            "Your task is to classify spend transactions into the correct Chart of Accounts (CoA) code based on "
            "merchant names, amounts, and historical context provided. "
            "\n\n"
            "COA OPTIONS:\n"
            f"{json.dumps(coa, indent=2)}\n\n"
            "HISTORICAL CONTEXT (Few-Shot):\n"
            f"{json.dumps(history, indent=2)}\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. If a merchant is rare, long-tail, or ambiguous against historical context, you MUST return a confidence_score < 0.85 and set requires_human_review = True.\n"
            "2. If you are extremely confident (>0.85), set requires_human_review = False.\n"
            "3. Always provide clear reasoning for your decision."
        )

        user_content = json.dumps({"transaction": transaction})
        return await self._call_with_retry(system_prompt, user_content)

    async def _call_with_retry(self, system_prompt: str, user_content: str) -> TaggingDecision:
        last_error: Exception | None = None
        max_attempts = MAX_LLM_RETRIES + 1
        for attempt in range(1, max_attempts + 1):
            try:
                completion = await self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    response_format=TaggingDecision,
                    temperature=0.0,
                )
                decision = completion.choices[0].message.parsed
                logger.info(
                    f"LLM decision: {decision.account_code} (conf: {decision.confidence_score})"
                )
                return decision
            except Exception as e:
                last_error = e
                if attempt < max_attempts:
                    logger.warning(
                        f"LLM API attempt {attempt}/{max_attempts} failed ({e}). Retrying..."
                    )
                else:
                    logger.error(f"LLM API failed after {max_attempts} attempts: {e}")
        return self._fail_safe_decision(last_error)

    @staticmethod
    def _fail_safe_decision(error: Exception | None) -> TaggingDecision:
        detail = str(error) if error else "unknown error"
        return TaggingDecision(
            account_code="7000",
            account_name="Suspense Account",
            confidence_score=0.0,
            reasoning=f"API Error (after {MAX_LLM_RETRIES} retries): {detail}",
            requires_human_review=True,
        )

    def _mock_response(self, transaction: Dict[str, Any]) -> TaggingDecision:
        merchant = (transaction.get("merchant") or "").lower()
        saas_keywords = (
            "amazon web services",
            "aws",
            "google cloud",
            "gcp",
            "azure",
            "slack",
            "github",
            "notion",
            "zoom",
            "microsoft 365",
        )
        marketing_keywords = ("google ads", "facebook ads", "meta ads", "linkedin ads")

        for kw in saas_keywords:
            if kw in merchant:
                return TaggingDecision(
                    account_code="6100",
                    account_name="SaaS tools & Software",
                    confidence_score=0.92,
                    reasoning=f"Mock: matched known SaaS vendor pattern '{kw}'.",
                    requires_human_review=False,
                )
        for kw in marketing_keywords:
            if kw in merchant:
                return TaggingDecision(
                    account_code="6200",
                    account_name="Marketing",
                    confidence_score=0.90,
                    reasoning=f"Mock: matched known marketing vendor pattern '{kw}'.",
                    requires_human_review=False,
                )

        return TaggingDecision(
            account_code="7000",
            account_name="Suspense Account",
            confidence_score=0.45,
            reasoning="Mock: unknown or long-tail merchant. Routing to human review.",
            requires_human_review=True,
        )

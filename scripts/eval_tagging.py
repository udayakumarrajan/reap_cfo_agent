#!/usr/bin/env python3
"""
Offline eval for the tagging classifier (mock mode — no API key required).

    uv run python scripts/eval_tagging.py
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from erp_service.core.seeds import DEFAULT_COA
from workflow_service.agents import LlmClassifierAgent

COA = [{"code": c["code"], "name": c["name"], "type": c["type"]} for c in DEFAULT_COA]
HISTORY: List[dict] = [
    {
        "merchant": "Amazon Web Services",
        "amount": 150.0,
        "account_code": "6100",
        "account_name": "SaaS tools & Software",
    },
    {
        "merchant": "Google Ads",
        "amount": 500.0,
        "account_code": "6200",
        "account_name": "Marketing",
    },
]


@dataclass
class EvalCase:
    merchant: str
    amount: float
    expect_review: bool
    expect_code: str | None  # None = any non-7000 STP code acceptable


CASES = [
    EvalCase("Amazon Web Services", 120.50, False, "6100"),
    EvalCase("AWS", 99.0, False, "6100"),
    EvalCase("Google Ads", 800.0, False, "6200"),
    EvalCase("Slack Technologies", 45.0, False, "6100"),
    EvalCase("Obscure Long Tail Vendor LLC", 250.0, True, "7000"),
    EvalCase("Random Coffee Shop", 12.0, True, "7000"),
    EvalCase("Google Cloud Services", 300.0, False, "6100"),
]


async def run_eval() -> int:
    classifier = LlmClassifierAgent(api_key="mock-key")
    passed = 0
    failed = 0

    print(f"Running {len(CASES)} mock classifier cases...\n")
    for case in CASES:
        decision = await classifier.classify(
            {"merchant": case.merchant, "amount": case.amount},
            COA,
            HISTORY,
        )
        review_ok = decision.requires_human_review == case.expect_review
        if case.expect_code is None:
            code_ok = (
                (case.expect_review and decision.account_code == "7000")
                or (not case.expect_review and decision.account_code != "7000")
            )
        else:
            code_ok = decision.account_code == case.expect_code

        ok = review_ok and code_ok
        status = "PASS" if ok else "FAIL"
        print(
            f"  [{status}] {case.merchant!r}: "
            f"code={decision.account_code} review={decision.requires_human_review} "
            f"conf={decision.confidence_score:.2f}"
        )
        if not ok:
            print(f"         expected review={case.expect_review} code={case.expect_code}")
            failed += 1
        else:
            passed += 1

    print(f"\n{passed}/{len(CASES)} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> None:
    raise SystemExit(asyncio.run(run_eval()))


if __name__ == "__main__":
    main()

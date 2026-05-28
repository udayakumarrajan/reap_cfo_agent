from datetime import timedelta
from typing import Dict, Any, Optional
from temporalio import workflow
from ..models.schemas import TaggingDecision

# Import activities indirectly to avoid circular imports during worker registration
with workflow.unsafe.imports_passed_through():
    from ..activities.transaction_activities import TransactionActivities

@workflow.defn
class TransactionCloseWorkflow:
    """
    Deterministic, replay-safe Temporal State Machine for Transaction Tagging.
    Implements straight-through processing (STP) and Human-in-the-loop (HITL) patterns.
    """
    def __init__(self):
        self.is_human_reviewed = False
        self.human_correction: Optional[Dict[str, Any]] = None
        self.CONFIDENCE_THRESHOLD = 0.85

    @workflow.signal
    def human_override_signal(self, corrected_data: Dict[str, Any]) -> None:
        """
        Signal handler for human accountant manual review.
        """
        self.human_correction = corrected_data
        self.is_human_reviewed = True

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        tx_id = payload["tx_id"]
        tenant_id = payload["tenant_id"]
        
        # 1. Fetch Context (CoA and History)
        context = await workflow.execute_activity(
            "fetch_tenant_context_activity",
            tenant_id,
            start_to_close_timeout=timedelta(seconds=10),
        )
        
        # 2. Run LLM Tagger
        tagger_payload = {
            "transaction": payload["payload"] if "payload" in payload else payload,
            "coa": context["coa"],
            "history": context["history"]
        }
        
        decision_dict = await workflow.execute_activity(
            "run_llm_tagger_activity",
            tagger_payload,
            start_to_close_timeout=timedelta(seconds=30),
        )
        
        decision = TaggingDecision(**decision_dict)
        
        # 3. Decision Logic
        if decision.confidence_score >= self.CONFIDENCE_THRESHOLD and not decision.requires_human_review:
            # Straight-Through Processing (STP)
            await workflow.execute_activity(
                "post_to_accounting_system_activity",
                {
                    "tx_id": tx_id,
                    "status": "AUTO_POSTED",
                    "account_code": decision.account_code,
                    "reasoning": decision.reasoning
                },
                start_to_close_timeout=timedelta(seconds=10),
            )
            return {
                "tx_id": tx_id,
                "workflow_status": "COMPLETED",
                "tagging_status": "AUTO_POSTED",
                "code": decision.account_code,
                "reasoning": decision.reasoning
            }
        
        # 4. Fail-safe: Route to Suspense Account and wait for Human Review
        else:
            # Post to Suspense Account (Code: 7000)
            await workflow.execute_activity(
                "post_to_accounting_system_activity",
                {
                    "tx_id": tx_id,
                    "status": "NEEDS_REVIEW",
                    "account_code": "7000",
                    "reasoning": decision.reasoning
                },
                start_to_close_timeout=timedelta(seconds=10),
            )
            
            # Pause workflow indefinitely until signal is received
            await workflow.wait_condition(lambda: self.is_human_reviewed)
            
            # 5. Handle Human Resolution
            final_code = self.human_correction.get("account_code")
            
            # Update learning loop (Feedback Loop)
            await workflow.execute_activity(
                "update_learning_loop_vectors_activity",
                {
                    "merchant": payload.get("merchant") or payload.get("payload", {}).get("merchant"),
                    "account_code": final_code
                },
                start_to_close_timeout=timedelta(seconds=10),
            )
            
            # Final Post to Accounting System
            await workflow.execute_activity(
                "post_to_accounting_system_activity",
                {
                    "tx_id": tx_id,
                    "status": "HUMAN_RESOLVED",
                    "account_code": final_code,
                    "reasoning": f"Human Resolved. Original LLM Reasoning: {decision.reasoning}"
                },
                start_to_close_timeout=timedelta(seconds=10),
            )
            
            return {
                "tx_id": tx_id,
                "workflow_status": "COMPLETED",
                "tagging_status": "HUMAN_RESOLVED",
                "code": final_code,
                "original_llm_reasoning": decision.reasoning
            }

from temporalio import activity
from loguru import logger
from typing import Dict, Any, List
from ..agents.openai_classifier import OpenAIGpt4oMiniClassifier
from erp_service.api.router import AccountingGatewayRouter

class TransactionActivities:
    """
    Standard, isolated Temporal Activities managing network calls back to ERP service.
    These are the side-effect handlers that maintain SRP.
    """
    def __init__(self, erp_router: AccountingGatewayRouter):
        self.erp_router = erp_router
        self.classifier = OpenAIGpt4oMiniClassifier()

    @activity.defn
    async def fetch_tenant_context_activity(self, tenant_id: str) -> Dict[str, Any]:
        """
        Issues mock network requests to fetch CoA and few-shot vector context.
        """
        logger.info(f"Activity: Fetching context for tenant {tenant_id}")
        coa_res = await self.erp_router.get_tenant_coa(tenant_id)
        history_res = await self.erp_router.get_historical_context(tenant_id)
        
        import json
        coa = json.loads(coa_res.body.decode())
        history = json.loads(history_res.body.decode())
             
        return {"coa": coa, "history": history}

    @activity.defn
    async def run_llm_tagger_activity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes classification via OpenAI Strategy.
        """
        transaction = payload["transaction"]
        coa = payload["coa"]
        history = payload["history"]
        
        logger.info(f"Activity: Running LLM tagger for {transaction.get('merchant')}")
        decision = await self.classifier.classify(transaction, coa, history)
        return decision.model_dump()

    @activity.defn
    async def post_to_accounting_system_activity(self, payload: Dict[str, Any]) -> str:
        """
        Network client adapter that targets ERP Service Router to alter ledger.
        """
        tx_id = payload["tx_id"]
        status = payload["status"]
        account_code = payload.get("account_code")
        reasoning = payload.get("reasoning")
        
        logger.info(f"Activity: Posting to accounting system - {tx_id} -> {status} (Code: {account_code})")
        res = await self.erp_router.update_ledger_status(
            tx_id=tx_id, 
            status=status, 
            account_code=account_code, 
            reasoning=reasoning
        )
        
        import json
        result = json.loads(res.body.decode())
             
        return result.get("status", "unknown")

    @activity.defn
    async def update_learning_loop_vectors_activity(self, payload: Dict[str, Any]) -> str:
        """
        Mocks persisting human-corrected items to local vector space.
        """
        merchant = payload.get("merchant")
        final_code = payload.get("account_code")
        logger.info(f"Activity: Updating learning loop for merchant '{merchant}' with code {final_code}")
        # Mock vector DB update transition
        return "SUCCESS: Persisted feedback vector"

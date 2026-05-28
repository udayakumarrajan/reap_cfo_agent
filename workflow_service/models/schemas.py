from pydantic import BaseModel, Field

class TaggingDecision(BaseModel):
    """
    Structured Pydantic model for AI classification output.
    Enforces strict schemas on the OpenAI parsing layer.
    """
    account_code: str = Field(..., description="The chart of accounts code for the transaction.")
    account_name: str = Field(..., description="A friendly name for the selected account.")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0.")
    reasoning: str = Field(..., description="Step-by-step logic for the classification selection.")
    requires_human_review: bool = Field(..., description="Flag indicating if a human accountant should verify this.")

"""
proposals.py

Trust Boundary: Defines the strict structural output contract for the Probabilistic (LLM) layer.
Responsibility: Enforces that the LLM only categorizes the root cause of the failure and NEVER
proposes a final action (e.g. "RETRY"). The LLM's role is strictly diagnostic.
Invariant: `extra='forbid'` ensures the LLM cannot fabricate ad-hoc fields to bypass the policy engine.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum
import math


class DiagnosisClass(str, Enum):
    BANK_DEGRADATION = "bank_degradation"
    MERCHANT_CHECKOUT_REGRESSION = "merchant_checkout_regression"
    TRANSIENT_TIMEOUT = "transient_timeout"
    INSUFFICIENT_FUNDS = "insufficient_funds"


class DiagnosisProposal(BaseModel):
    """
    A typed, structured boundary for the LLM/Probabilistic layer.
    The LLM may ONLY return this schema and NEVER a direct action.
    """

    model_config = ConfigDict(extra="forbid")

    diagnosis_class: DiagnosisClass = Field(
        ..., description="The categorized failure root cause"
    )
    confidence: float = Field(..., description="Confidence score [0.0, 1.0]")
    evidence_summary: str = Field(
        ..., description="Natural language explanation of the diagnosis"
    )
    evidence_ids: list[str] = Field(
        default_factory=list, description="List of related event IDs forming the cohort"
    )

    @field_validator("confidence")
    def validate_confidence(cls, v):
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Confidence must be a finite number")
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be strictly between 0.0 and 1.0")
        return v

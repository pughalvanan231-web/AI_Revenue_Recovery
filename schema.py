"""
schema.py

Trust Boundary: Defines the core data structures and validation constraints for the system.
Responsibility: Ensures that only valid, well-formed event data enters the orchestration pipeline.
Invariant: All amounts must be strictly positive. Hidden evaluation labels (e.g., is_synthetic_incident)
must never influence the LLM diagnosis or policy decision; they are strictly presentation/evaluation only.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from decimal import Decimal
from enum import Enum


class PaymentStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"


class FailureCode(str, Enum):
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    ISSUER_DOWN = "ISSUER_DOWN"
    TIMEOUT = "TIMEOUT"
    RISK_BLOCKED = "RISK_BLOCKED"
    INVALID_CVV = "INVALID_CVV"


class PaymentEvent(BaseModel):
    event_id: str
    payment_attempt_group_id: str = Field(
        ...,
        description="Stable ID linking multiple attempts of the same checkout workflow",
    )
    timestamp: datetime
    merchant_id: str
    amount: Decimal = Field(..., description="Payment amount in INR")
    currency: str = "INR"

    # Payment context
    payment_method: str = Field(
        ..., description="e.g., UPI, CREDIT_CARD, DEBIT_CARD, NETBANKING"
    )
    issuing_bank: Optional[str] = Field(None, description="e.g., HDFC, ICICI, SBI")
    device_type: str = Field(
        ..., description="e.g., MOBILE_IOS, MOBILE_ANDROID, DESKTOP"
    )

    # State and Failure Context
    status: PaymentStatus = Field(..., description="SUCCESS, FAILED, PENDING")
    failure_code: Optional[FailureCode] = Field(
        None, description="Detailed failure reason if FAILED"
    )
    failure_reason: Optional[str] = Field(None)

    # Hidden Label (for Evaluation Only - must be stripped before giving to Agent)
    is_synthetic_incident: bool = Field(
        False,
        description="True if this failure was artificially injected as an incident",
    )
    incident_type: Optional[str] = Field(
        None, description="e.g., bank_degradation, merchant_checkout_regression, noise"
    )

    @field_validator("amount")
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be a positive value.")
        return v


class RevenueEventType(str, Enum):
    PAYMENT_FAILED = "PAYMENT_FAILED"
    CHECKOUT_ABANDONED = "CHECKOUT_ABANDONED"
    SUBSCRIPTION_FAILED = "SUBSCRIPTION_FAILED"
    INVOICE_OVERDUE = "INVOICE_OVERDUE"


class RevenueEvent(BaseModel):
    id: str = Field(..., description="Unique internal ID for the revenue event record")
    event_id: str = Field(..., description="Original system event ID")
    event_type: RevenueEventType
    customer_id: str
    amount: Decimal
    currency: str = "INR"
    source: str = Field(..., description="Source system generating the event")
    status: str = Field(..., description="Current recovery status")
    created_at: datetime


class RecoveryStrategyType(str, Enum):
    RETRY_PAYMENT = "RETRY_PAYMENT"
    GENERATE_PAYMENT_LINK = "GENERATE_PAYMENT_LINK"
    SEND_EMAIL = "SEND_EMAIL"
    SEND_WHATSAPP = "SEND_WHATSAPP"
    RETRY_THEN_PAYMENT_LINK = "RETRY_THEN_PAYMENT_LINK"
    CUSTOMER_REMINDER = "CUSTOMER_REMINDER"
    REQUEST_PROMISE_TO_PAY = "REQUEST_PROMISE_TO_PAY"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    NO_ACTION = "NO_ACTION"


class RecoveryStrategy(BaseModel):
    id: str
    case_id: str
    strategy: RecoveryStrategyType
    probability: float
    reason: str
    selected_at: datetime


class StrategyResult(BaseModel):
    id: str
    case_id: str
    strategy: RecoveryStrategyType
    result: str
    amount_recovered: Decimal
    execution_time: datetime


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH_VALUE_RECOVERABLE = "HIGH_VALUE_RECOVERABLE"
    HIGH_RISK = "HIGH_RISK"


class RiskScore(BaseModel):
    id: str
    case_id: str
    score: int = Field(..., description="Risk score 1-100")
    recovery_probability: float
    risk_level: RiskLevel
    created_at: datetime


class InvoiceStatus(str, Enum):
    DUE_SOON = "DUE_SOON"
    DUE = "DUE"
    OVERDUE = "OVERDUE"
    PROMISE_TO_PAY = "PROMISE_TO_PAY"
    PAID = "PAID"
    ESCALATED = "ESCALATED"


class Invoice(BaseModel):
    id: str
    customer_id: str
    invoice_number: str
    amount: Decimal
    due_date: datetime
    status: InvoiceStatus


class PromiseToPayStatus(str, Enum):
    PENDING = "PENDING"
    FULFILLED = "FULFILLED"
    MISSED = "MISSED"
    ESCALATED = "ESCALATED"


class PromiseToPay(BaseModel):
    id: str
    invoice_id: str
    amount: Decimal
    promised_date: datetime
    status: PromiseToPayStatus

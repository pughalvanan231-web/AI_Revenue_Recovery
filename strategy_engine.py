"""
strategy_engine.py

Trust Boundary: Recommends the best recovery strategy based on diagnosis and risk score.
Responsibility: Deterministically maps risk/context to a strategy. PolicyEngine will validate it.
"""

from decimal import Decimal
import uuid
from datetime import datetime, timezone
from schema import (
    RevenueEvent,
    RevenueEventType,
    RiskScore,
    RiskLevel,
    RecoveryStrategy,
    RecoveryStrategyType,
)
from proposals import DiagnosisProposal, DiagnosisClass

class StrategyEngine:
    def __init__(self):
        pass

    def select_strategy(
        self,
        event: RevenueEvent,
        risk_score: RiskScore,
        diagnosis: DiagnosisProposal = None,
        customer_history: dict = None
    ) -> RecoveryStrategy:
        if customer_history is None:
            customer_history = {"retry_count": 0}

        strategy_type = RecoveryStrategyType.NO_ACTION
        reason = "Default fallback"
        prob = risk_score.recovery_probability

        if event.event_type == RevenueEventType.PAYMENT_FAILED:
            if diagnosis and diagnosis.diagnosis_class == DiagnosisClass.TRANSIENT_TIMEOUT:
                if customer_history.get("retry_count", 0) < 3:
                    strategy_type = RecoveryStrategyType.RETRY_PAYMENT
                    reason = "Transient timeout detected with retries remaining"
                    prob += 0.1
                else:
                    strategy_type = RecoveryStrategyType.GENERATE_PAYMENT_LINK
                    reason = "Max retries reached, falling back to payment link"
            elif diagnosis and diagnosis.diagnosis_class == DiagnosisClass.INSUFFICIENT_FUNDS:
                strategy_type = RecoveryStrategyType.NO_ACTION
                reason = "Insufficient funds, cannot recover automatically"
            elif risk_score.risk_level == RiskLevel.HIGH_VALUE_RECOVERABLE:
                strategy_type = RecoveryStrategyType.HUMAN_ESCALATION
                reason = "High value transaction requires human approval"
            else:
                strategy_type = RecoveryStrategyType.GENERATE_PAYMENT_LINK
                reason = "Fallback for payment failure"

        elif event.event_type == RevenueEventType.CHECKOUT_ABANDONED:
            if prob > 0.6:
                strategy_type = RecoveryStrategyType.GENERATE_PAYMENT_LINK
                reason = "High probability checkout abandonment, sending link"
            else:
                strategy_type = RecoveryStrategyType.SEND_EMAIL
                reason = "Lower probability abandonment, sending email reminder"

        elif event.event_type == RevenueEventType.INVOICE_OVERDUE:
            if event.amount > Decimal("10000.0"):
                strategy_type = RecoveryStrategyType.HUMAN_ESCALATION
                reason = "Large overdue invoice requires escalation"
            else:
                strategy_type = RecoveryStrategyType.CUSTOMER_REMINDER
                reason = "Standard overdue invoice reminder"
        
        elif event.event_type == RevenueEventType.SUBSCRIPTION_FAILED:
            strategy_type = RecoveryStrategyType.RETRY_THEN_PAYMENT_LINK
            reason = "Subscription standard recovery flow"

        # Hard stop limit
        if risk_score.risk_level == RiskLevel.HIGH_RISK:
            strategy_type = RecoveryStrategyType.NO_ACTION
            reason = "High risk profile, stopping recovery"

        return RecoveryStrategy(
            id=f"strat_{uuid.uuid4().hex[:8]}",
            case_id=event.id,
            strategy=strategy_type,
            probability=min(1.0, prob),
            reason=reason,
            selected_at=datetime.now(timezone.utc)
        )

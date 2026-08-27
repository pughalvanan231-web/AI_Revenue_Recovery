"""
risk_engine.py

Trust Boundary: AI-assisted heuristic layer for scoring revenue risk.
Responsibility: Computes a deterministic + AI-assisted Revenue Risk Score (1-100) 
and assigns a RiskLevel.
"""

from decimal import Decimal
import uuid
from datetime import datetime, timezone
from schema import RevenueEvent, RevenueEventType, RiskScore, RiskLevel

class RevenueRiskEngine:
    def __init__(self):
        pass

    def evaluate_risk(self, event: RevenueEvent, customer_history: dict = None) -> RiskScore:
        """
        Evaluate a RevenueEvent and return a RiskScore.
        """
        if customer_history is None:
            customer_history = {
                "previous_successful_payments": 0,
                "previous_failed_payments": 0,
                "customer_lifetime_value": Decimal("0.0")
            }

        score = 50
        recovery_probability = 0.50
        risk_level = RiskLevel.MEDIUM

        # Base modifiers by event type
        if event.event_type == RevenueEventType.PAYMENT_FAILED:
            score += 10
        elif event.event_type == RevenueEventType.CHECKOUT_ABANDONED:
            score += 20
        elif event.event_type == RevenueEventType.SUBSCRIPTION_FAILED:
            score += 15
        elif event.event_type == RevenueEventType.INVOICE_OVERDUE:
            score += 30

        # Amount modifiers
        if event.amount > Decimal("50000.0"):
            score += 20
            risk_level = RiskLevel.HIGH_VALUE_RECOVERABLE
        elif event.amount < Decimal("100.0"):
            score -= 10
            risk_level = RiskLevel.LOW

        # Customer history modifiers
        if customer_history.get("previous_successful_payments", 0) > 3:
            recovery_probability += 0.20
            score -= 15
        if customer_history.get("previous_failed_payments", 0) > 2:
            recovery_probability -= 0.15
            score += 15

        # Normalize score
        score = max(1, min(100, score))
        recovery_probability = max(0.0, min(1.0, recovery_probability))

        if score > 75 and risk_level != RiskLevel.HIGH_VALUE_RECOVERABLE:
            risk_level = RiskLevel.HIGH_RISK
        elif score < 30 and risk_level != RiskLevel.HIGH_VALUE_RECOVERABLE:
            risk_level = RiskLevel.LOW
        elif risk_level != RiskLevel.HIGH_VALUE_RECOVERABLE:
            risk_level = RiskLevel.MEDIUM

        return RiskScore(
            id=f"risk_{uuid.uuid4().hex[:8]}",
            case_id=event.id,
            score=score,
            recovery_probability=recovery_probability,
            risk_level=risk_level,
            created_at=datetime.now(timezone.utc)
        )

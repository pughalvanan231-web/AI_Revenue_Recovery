"""
policy_engine.py

Trust Boundary: The deterministic, absolute authority for all recovery actions.
Responsibility: Evaluates LLM proposals against hard business constraints (economic value,
confidence floors, retry limits, and idempotency).
Invariant: No LLM output can ever bypass this module. If a proposal fails any gate,
the policy engine safely degrades to "STOP_AND_ESCALATE" or "NO_ACTION".
"""

from typing import Tuple
from decimal import Decimal
from schema import PaymentEvent, PaymentStatus, RevenueEvent, RecoveryStrategy, RecoveryStrategyType
from proposals import DiagnosisProposal, DiagnosisClass
from audit_log import AuditLogger
from state_store import IdempotencyRepository

POLICY_VERSION = "1.1.0"


class PolicyEngine:
    def __init__(self, audit_logger: AuditLogger, state_store: IdempotencyRepository):
        self.audit_logger = audit_logger
        self.state_store = state_store

    def evaluate(
        self, event: PaymentEvent, proposal: DiagnosisProposal
    ) -> Tuple[str, str]:
        """
        Evaluates a payment event against a typed DiagnosisProposal.
        Enforces idempotency and deterministic rules.
        """
        idempotency_key = f"{event.payment_attempt_group_id}:RECOVERY:{POLICY_VERSION}"

        # Rule 0: Event Eligibility Constraint
        if event.status == PaymentStatus.SUCCESS:
            decision, reason = "NO_ACTION", "Payment is already successful."
            self._log(event, proposal, idempotency_key, decision, reason)
            return decision, reason

        # Rule 1: True Idempotency Gate
        is_duplicate, cached_decision = self.state_store.check_and_record(
            idempotency_key, "PENDING", "Evaluating..."
        )
        if is_duplicate:
            decision, reason = cached_decision
            # If decision is PENDING, it means the orchestrator claimed the lock for us. We proceed.
            if decision != "PENDING":
                reason_out = f"Idempotency hit: {reason}"
                self._log(event, proposal, idempotency_key, decision, reason_out)
                return decision, reason_out

        # Track attempt state from durable store, NOT the event payload
        actual_attempt_count = self.state_store.get_attempt_count(
            event.payment_attempt_group_id
        )

        # Rule 2: Bounded Retry Constraint
        if actual_attempt_count >= 1:
            decision, reason = (
                "STOP_AND_ESCALATE",
                f"Retry limit exceeded (attempts: {actual_attempt_count})",
            )
            return self._finalize_decision(
                event, proposal, idempotency_key, decision, reason
            )

        # Rule 3: Low confidence safety gate
        if proposal.confidence < 0.80:
            decision, reason = (
                "NO_ACTION",
                f"Diagnosis confidence too low ({proposal.confidence}), abstaining.",
            )
            return self._finalize_decision(
                event, proposal, idempotency_key, decision, reason
            )

        # Rule 4: Economic/Value Constraint (Strict positive INR Check)
        if event.amount < Decimal("100.0"):
            decision, reason = (
                "NO_ACTION",
                "Transaction amount below intervention threshold (100 INR)",
            )
            return self._finalize_decision(
                event, proposal, idempotency_key, decision, reason
            )

        # Rule 5: Action based on Diagnosis Enum
        if proposal.diagnosis_class == DiagnosisClass.BANK_DEGRADATION:
            decision = "OFFER_ALTERNATE_METHOD"
            reason = f"Bank {event.issuing_bank} is degraded. Offering fallback payment method."

        elif proposal.diagnosis_class == DiagnosisClass.MERCHANT_CHECKOUT_REGRESSION:
            decision = "STOP_AND_ESCALATE"
            reason = f"Checkout regression detected for merchant {event.merchant_id} on {event.device_type}. Escalate to merchant."

        elif proposal.diagnosis_class == DiagnosisClass.TRANSIENT_TIMEOUT:
            decision = "RETRY"
            reason = "Transient timeout detected. Safe to execute 1 bounded retry."

        elif proposal.diagnosis_class == DiagnosisClass.INSUFFICIENT_FUNDS:
            decision = "NO_ACTION"
            reason = "Insufficient funds. Requires user to add funds."

        else:
            decision = "STOP_AND_ESCALATE"
            reason = f"Unhandled diagnosis class. Defaulting to escalate."

        # If we decided to act (RETRY or OFFER_ALTERNATE), increment attempt count
        if decision in ["RETRY", "OFFER_ALTERNATE_METHOD"]:
            self.state_store.increment_attempt_count(event.payment_attempt_group_id)

        return self._finalize_decision(
            event, proposal, idempotency_key, decision, reason
        )

    def _finalize_decision(
        self, event, proposal, idempotency_key, decision, reason
    ) -> Tuple[str, str]:
        # Update the idempotency record with the final decision
        self.state_store.check_and_record(idempotency_key, decision, reason)

        self._log(event, proposal, idempotency_key, decision, reason)
        return decision, reason

    def _log(
        self,
        event: PaymentEvent,
        proposal: DiagnosisProposal,
        idempotency_key: str,
        decision: str,
        reason: str,
    ):
        self.audit_logger.log_decision(
            event_id=event.event_id,
            payment_attempt_group_id=event.payment_attempt_group_id,
            idempotency_key=idempotency_key,
            policy_version=POLICY_VERSION,
            diagnosis_proposal=proposal,
            decision=decision,
            reason=reason,
            metadata={"amount": str(event.amount), "merchant_id": event.merchant_id},
        )

    def evaluate_strategy(
        self,
        event: RevenueEvent,
        strategy: RecoveryStrategy
    ) -> Tuple[str, str]:
        """
        V2 Engine: Evaluates a proposed RecoveryStrategy against strict deterministic rules.
        """
        idempotency_key = f"{event.id}:RECOVERY:{POLICY_VERSION}"
        
        if event.status == "SUCCESS":
            return "NO_ACTION", "Revenue already recovered."
            
        # Economic Floor
        if event.amount < Decimal("100.0"):
            return "NO_ACTION", "Amount below economic threshold."
            
        # High value protection
        if event.amount > Decimal("50000.0") and strategy.strategy != RecoveryStrategyType.HUMAN_ESCALATION:
            return "HUMAN_ESCALATION", "High value transaction overrides strategy to human review."
            
        return strategy.strategy.value, strategy.reason

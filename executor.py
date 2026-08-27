"""
executor.py

Trust Boundary: The physical execution engine for Razorpay API mutations.
Responsibility: Dispatches the final deterministic action (e.g. creating a payment link or retrying)
and safely records the Razorpay transaction reference.
Invariant: At-most-once execution is enforced via a PENDING database lock before any network request.
If the lock fails, the executor returns the cached response and blocks duplicate physical execution.
Note: Currently operates in a strictly Test/Mock boundary (`use_real_sdk=False`).
"""

import time
import random
import requests
import responses
from typing import Dict, Any
from schema import PaymentEvent
from state_store import IdempotencyRepository
import razorpay


class RazorpayExecutor:
    """
    Interfaces with the real Razorpay SDK in test mode.
    Executes actions directed by the Policy Engine and records outcomes in the State Store.
    """

    def __init__(self, state_store: IdempotencyRepository, use_real_sdk: bool = False):
        self.state_store = state_store
        self.use_real_sdk = use_real_sdk
        self.client = razorpay.Client(auth=("rzp_test_dummy", "dummy_secret"))

    @responses.activate
    def execute(
        self, event: PaymentEvent, decision: str, idempotency_key: str
    ) -> Dict[str, Any]:
        """
        Executes the required action safely, respecting the policy decision and execution idempotency.
        """
        # 1. Executor-Level Idempotency Check
        cached_state = self.state_store.get_executor_state(idempotency_key)
        if cached_state:
            return {
                "status": cached_state[0],
                "message": f"Cached: {cached_state[1]}",
                "is_duplicate": True,
                "razorpay_ref": cached_state[2],
            }

        # Ensure we record a PENDING state atomically to prevent concurrent physical execution
        is_duplicate, cached_status, cached_message, cached_ref = (
            self.state_store.record_executor_state(
                idempotency_key, "PENDING", "Execution started"
            )
        )
        if is_duplicate:
            return {
                "status": cached_status,
                "message": cached_message,
                "is_duplicate": True,
                "razorpay_ref": cached_ref,
            }

        # 2. Setup Mock Responses for the SDK (if use_real_sdk is True but we lack real keys)
        if self.use_real_sdk:
            responses.add(
                responses.POST,
                "https://api.razorpay.com/v1/orders",
                json={"id": "order_mock123", "status": "created"},
                status=200,
            )
            responses.add(
                responses.POST,
                "https://api.razorpay.com/v1/payment_links",
                json={"id": "plink_mock123", "short_url": "https://rzp.io/i/mock123"},
                status=200,
            )

        # 3. Route to execution strategy
        try:
            if decision == "RETRY":
                result = self._execute_retry(event)
            elif decision == "OFFER_ALTERNATE_METHOD":
                result = self._offer_alternate_method(event)
            elif decision == "STOP_AND_ESCALATE":
                result = {
                    "status": "ESCALATED",
                    "message": "Ticket opened for manual review.",
                }
            elif decision == "NO_ACTION":
                result = {"status": "ABSTAINED", "message": "No action taken."}
            else:
                result = {"status": "ERROR", "message": "Unknown decision."}

            # Update the executor state from PENDING to final
            conn = self.state_store._get_conn()
            razorpay_ref = result.get("razorpay_ref", "")
            with conn:
                conn.execute(
                    "UPDATE executor_states SET status = ?, message = ?, razorpay_ref = ? WHERE idempotency_key = ?",
                    (
                        result["status"],
                        result["message"],
                        razorpay_ref,
                        idempotency_key,
                    ),
                )
            return result

        except Exception as e:
            # Revert or record failure state
            conn = self.state_store._get_conn()
            with conn:
                conn.execute(
                    "UPDATE executor_states SET status = ?, message = ? WHERE idempotency_key = ?",
                    ("FAILED", f"Execution error: {str(e)}", idempotency_key),
                )
            return {"status": "FAILED", "message": f"Execution error: {str(e)}"}

    def _execute_retry(self, event: PaymentEvent) -> Dict[str, Any]:
        """Simulates a Razorpay POST /payments/create call."""
        time.sleep(0.05)

        if self.use_real_sdk:
            # We use the real Razorpay SDK to formulate the request.
            # The 'responses' mock intercepts the HTTP call.
            self.client.order.create(
                {
                    "amount": int(event.amount * 100),  # Amount in paise
                    "currency": event.currency,
                    "receipt": f"retry_{event.event_id}",
                }
            )

        # Mock Simulation logic for outcomes
        if event.failure_code == "TIMEOUT":
            is_success = random.random() < 0.90
        else:
            is_success = False

        if is_success:
            import uuid

            mock_ref = f"mock_ref_{uuid.uuid4().hex[:8]}"
            return {
                "status": "RETRY_SUCCESS",
                "message": "Payment retried successfully.",
                "razorpay_ref": mock_ref,
            }
        else:
            return {"status": "FAILED", "message": "Payment retry failed."}

    def _offer_alternate_method(self, event: PaymentEvent) -> Dict[str, Any]:
        """Simulates sending a fallback payment link via Razorpay."""
        time.sleep(0.05)

        if self.use_real_sdk:
            self.client.payment_link.create(
                {
                    "amount": int(event.amount * 100),
                    "currency": event.currency,
                    "description": "Alternate payment method",
                    "customer": {"name": "Customer", "email": "customer@example.com"},
                }
            )

        import uuid

        mock_ref = f"mock_ref_{uuid.uuid4().hex[:8]}"
        return {
            "status": "LINK_SENT",
            "message": "Alternate method link dispatched.",
            "razorpay_ref": mock_ref,
        }

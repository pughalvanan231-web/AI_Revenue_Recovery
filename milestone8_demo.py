import os
import uuid
import time
from datetime import datetime, timezone
from decimal import Decimal
from schema import PaymentEvent, PaymentStatus, FailureCode
from policy_engine import PolicyEngine, POLICY_VERSION
from state_store import IdempotencyRepository
from executor import RazorpayExecutor
from llm_agent import RevenueResilienceAgent
from audit_log import AuditLogger
from evaluation_harness import policy_agent


def run_demo():
    print("=" * 60)
    print("  Razorpay Buildathon: Revenue Resilience AI (Demo)  ")
    print("=" * 60)

    # 1. Initialize Core Components
    store = IdempotencyRepository()
    audit_logger = AuditLogger()
    engine = PolicyEngine(audit_logger=audit_logger, state_store=store)

    # Toggle use_real_llm=True if you have Gemini API credentials configured!
    # For safe test-mode execution, we use the simulated LLM here.
    agent = RevenueResilienceAgent(use_real_llm=False)

    # Enable the real Razorpay SDK in test mode (intercepted via 'responses' mock)
    executor = RazorpayExecutor(state_store=store, use_real_sdk=True)

    # 2. Simulate a Bank Degradation Event
    print("\n[1] Detecting Event Anomaly...")
    event = PaymentEvent(
        event_id=str(uuid.uuid4()),
        payment_attempt_group_id=f"group_{uuid.uuid4()}",
        timestamp=datetime.now(timezone.utc),
        merchant_id="M_FLIPKART",
        amount=Decimal("12500.00"),
        currency="INR",
        payment_method="UPI",
        issuing_bank="SBI",
        device_type="MOBILE_ANDROID",
        status=PaymentStatus.FAILED,
        failure_code=FailureCode.ISSUER_DOWN,
        retry_count=0,
    )

    # Seed the agent context with a few SBI failures to trigger the "Bank Degradation" rule
    for _ in range(3):
        agent.recent_failures.append(
            event.model_copy(update={"event_id": str(uuid.uuid4())})
        )

    print(
        f"    New Failed Event: {event.event_id} | Bank: {event.issuing_bank} | Amount: ₹{event.amount}"
    )

    time.sleep(1)

    # 3. Probabilistic Layer (Diagnosis) & Policy Evaluation
    print(
        "\n[2] Running Orchestrator (Idempotency + LLM Diagnosis + Policy Safety Gate)..."
    )
    decision = policy_agent(event, agent=agent, engine=engine)

    print(f"    Orchestrator Decision: {decision}")

    time.sleep(1)

    # 4. Action Execution
    print("\n[3] Executing Action via Razorpay SDK...")
    idempotency_key = f"{event.payment_attempt_group_id}:RECOVERY:{POLICY_VERSION}"
    result = executor.execute(event, decision, idempotency_key)

    print(f"    Executor Result: {result}")

    # 5. Show Audit Log
    print("\n[4] Reconciled Audit Log (Final Immutable State):")
    reservation = store.get_reservation(idempotency_key)
    executor_state = store.get_executor_state(idempotency_key)
    print(f"    Policy Decision: {reservation}")
    print(f"    Executor State: {executor_state}")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()

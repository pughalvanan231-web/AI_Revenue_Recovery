import json
import random
from decimal import Decimal

"""
evaluation_harness.py

Trust Boundary: The offline evaluation and testing sandbox.
Responsibility: Runs the agent and baseline policies over a synthetic test dataset to 
calculate the economic value (Contribution Margin) of the Revenue Resilience system.
Invariant: The `is_synthetic_incident` and `incident_type` labels are STRICTLY HIDDEN 
from the policy engine and agent. They are only used by the simulator to verify if the 
agent's action actually recovered the payment (simulating a held-out reality).
Limitations: Economic results rely on assumed conversion probabilities and fixed 
recovery costs. This module does not perform physical execution.
"""
from typing import List, Dict, Callable, Any
from schema import PaymentEvent, PaymentStatus, FailureCode
from datetime import datetime
from llm_agent import RevenueResilienceAgent
from policy_engine import PolicyEngine
from state_store import IdempotencyRepository

import hashlib

# Define Economics Constants
CONTRIBUTION_MARGIN_PCT = Decimal("0.02")  # 2% of transaction value
COST_PER_RETRY = Decimal("2.0")  # Hard cost of API calls / latency
FRICTION_PENALTY = Decimal(
    "5.0"
)  # Intangible cost of bothering user during degradation
ESCALATION_COST = Decimal("20.0")  # Cost of human support agent
ALT_METHOD_COST = Decimal("1.0")  # Minor UI/UX cost for alternate method flow


def _event_random(event_id: str, salt: str) -> float:
    """Returns a deterministic pseudo-random float [0.0, 1.0) based on event_id."""
    h = hashlib.md5(f"{event_id}_{salt}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


class SimulationResult:
    def __init__(self, policy_name: str):
        self.policy_name = policy_name
        self.total_events = 0
        self.total_retries = 0
        self.successful_recoveries = 0
        self.false_interventions = 0

        # Auditable cost accounting
        self.gross_recovered_contribution = Decimal("0.0")
        self.total_retry_cost = Decimal("0.0")
        self.total_friction_cost = Decimal("0.0")
        self.total_escalation_cost = Decimal("0.0")

    def net_value(self) -> Decimal:
        return (
            self.gross_recovered_contribution
            - self.total_retry_cost
            - self.total_friction_cost
            - self.total_escalation_cost
        )

    def report(self):
        print(f"--- Policy: {self.policy_name} (Held-out Test Set) ---")
        print(f"Total Evaluated Events: {self.total_events}")
        print(f"Total Actions (Retries/Alts): {self.total_retries}")
        print(f"Successful Recoveries: {self.successful_recoveries}")
        print(f"False Interventions (Failed actions): {self.false_interventions}")
        print(
            f"Gross Recovered Contribution (INR): {self.gross_recovered_contribution:,.2f}"
        )
        print(f"(-) Retry/Action Costs (INR): {self.total_retry_cost:,.2f}")
        print(f"(-) Friction Penalties (INR): {self.total_friction_cost:,.2f}")
        print(f"(-) Escalation Costs (INR): {self.total_escalation_cost:,.2f}")
        print(f"Net Recovered Contribution Value (INR): {self.net_value():,.2f}")
        print("-" * 50)


def load_events(filepath: str) -> List[Dict]:
    events = []
    with open(filepath, "r") as f:
        for line in f:
            events.append(json.loads(line))
    return [e for e in events if e.get("status") == "FAILED"]


def simulate_outcome(event_dict: Dict, decision: str) -> Dict[str, Any]:
    """
    Simulates the outcome of a decision against the TRUE state of the event
    (using the hidden synthetic labels).
    """
    amount = Decimal(str(event_dict["amount"]))
    incident_type = event_dict.get("incident_type")
    failure_code = event_dict.get("failure_code")

    metrics = {
        "gross_contribution": Decimal("0.0"),
        "retry_cost": Decimal("0.0"),
        "friction_cost": Decimal("0.0"),
        "escalation_cost": Decimal("0.0"),
        "is_recovered": False,
        "is_false_intervention": False,
    }

    if decision == "NO_ACTION":
        # Organic recovery counterfactual: 5% chance user manually tries again later and succeeds.
        if _event_random(event_dict["event_id"], "organic") < 0.05:
            metrics["gross_contribution"] = amount * CONTRIBUTION_MARGIN_PCT
            metrics["is_recovered"] = True
        return metrics

    if decision == "RETRY":
        metrics["retry_cost"] = COST_PER_RETRY
        # Transient timeout recovers most of the time
        if incident_type is None and failure_code == "TIMEOUT":
            if _event_random(event_dict["event_id"], "retry") < 0.90:
                metrics["gross_contribution"] = amount * CONTRIBUTION_MARGIN_PCT
                metrics["is_recovered"] = True
            else:
                metrics["is_false_intervention"] = True
        else:
            # Retrying a hard failure or degradation fails and causes friction
            metrics["is_false_intervention"] = True
            if incident_type in ["bank_degradation", "merchant_checkout_regression"]:
                metrics["friction_cost"] = FRICTION_PENALTY
        return metrics

    if decision == "OFFER_ALTERNATE_METHOD":
        # Bypasses bank degradation by using another method (e.g. Card instead of UPI)
        metrics["retry_cost"] = ALT_METHOD_COST
        if incident_type == "merchant_checkout_regression":
            # UI is broken, alternate method won't help
            metrics["is_false_intervention"] = True
            metrics["friction_cost"] = FRICTION_PENALTY
        else:
            # 30% conversion rate for alternate methods
            if _event_random(event_dict["event_id"], "alt_method") < 0.30:
                metrics["gross_contribution"] = amount * CONTRIBUTION_MARGIN_PCT
                metrics["is_recovered"] = True
            else:
                metrics["is_false_intervention"] = True
        return metrics

    if decision == "STOP_AND_ESCALATE":
        metrics["escalation_cost"] = ESCALATION_COST
        # 10% chance support agent resolves it and recovers value
        if _event_random(event_dict["event_id"], "escalate") < 0.10:
            metrics["gross_contribution"] = amount * CONTRIBUTION_MARGIN_PCT
            metrics["is_recovered"] = True
        return metrics

    return metrics


# --- BASELINE POLICIES ---


def policy_no_action(event: PaymentEvent, **kwargs) -> str:
    return "NO_ACTION"


def policy_blind_retry(event: PaymentEvent, **kwargs) -> str:
    return "RETRY"


def policy_rule_baseline(event: PaymentEvent, **kwargs) -> str:
    if event.amount > Decimal("500.0") and event.failure_code == FailureCode.TIMEOUT:
        return "RETRY"
    return "NO_ACTION"


def policy_agent(
    event: PaymentEvent,
    agent: RevenueResilienceAgent = None,
    engine: PolicyEngine = None,
    **kwargs,
) -> str:
    from policy_engine import POLICY_VERSION

    idempotency_key = f"{event.payment_attempt_group_id}:RECOVERY:{POLICY_VERSION}"

    # 1. Pre-Diagnosis Deduplication & Lock (Saves LLM tokens/latency & prevents races)
    is_duplicate, cached = engine.state_store.check_and_record(
        idempotency_key, "PENDING", "Diagnosing..."
    )
    if is_duplicate:
        if cached[0] == "PENDING":
            return "STOP_AND_ESCALATE"  # Stale/Concurrent reservation
        return cached[0]  # Return the final cached decision directly

    # 2. Expensive Diagnosis Step
    proposal = agent.diagnose(event)

    # 3. Deterministic Safety Gate & Final Record (UPSERTs the PENDING state)
    decision, _ = engine.evaluate(event, proposal)
    return decision


def evaluate_policy(
    name: str, policy_fn: Callable, held_out_events: List[Dict], **kwargs
) -> SimulationResult:
    result = SimulationResult(name)

    for e_dict in held_out_events:
        result.total_events += 1

        # Strip hidden evaluation labels before passing to policy
        stripped_dict = e_dict.copy()
        stripped_dict["is_synthetic_incident"] = False
        stripped_dict["incident_type"] = None

        event_obj = PaymentEvent(**stripped_dict)
        decision = policy_fn(event_obj, **kwargs)

        if decision in ["RETRY", "OFFER_ALTERNATE_METHOD"]:
            result.total_retries += 1

        metrics = simulate_outcome(e_dict, decision)

        if metrics["is_recovered"]:
            result.successful_recoveries += 1
        if metrics["is_false_intervention"]:
            result.false_interventions += 1

        result.gross_recovered_contribution += metrics["gross_contribution"]
        result.total_retry_cost += metrics["retry_cost"]
        result.total_friction_cost += metrics["friction_cost"]
        result.total_escalation_cost += metrics["escalation_cost"]

    return result


if __name__ == "__main__":
    print("Loading events...")
    all_failed_events = load_events("synthetic_events.jsonl")

    # Chronological Split (70% Calibration, 30% Held-Out Test Set)
    all_failed_events.sort(key=lambda x: datetime.fromisoformat(x["timestamp"]))
    split_idx = int(len(all_failed_events) * 0.7)
    held_out_events = all_failed_events[split_idx:]

    print(f"Loaded {len(all_failed_events)} failed events total.")
    print(
        f"Evaluating policies on the held-out test set of {len(held_out_events)} events.\n"
    )

    res_no_action = evaluate_policy("No Action", policy_no_action, held_out_events)
    res_no_action.report()

    res_blind_retry = evaluate_policy(
        "Blind Retry", policy_blind_retry, held_out_events
    )
    res_blind_retry.report()

    res_rule_baseline = evaluate_policy(
        "Deterministic Rule Baseline", policy_rule_baseline, held_out_events
    )
    res_rule_baseline.report()

    # --- AGENT POLICY SETUP ---
    # Mock Audit Logger for evaluation
    class DummyAuditLogger:
        def log_decision(self, *args, **kwargs):
            pass

    agent = RevenueResilienceAgent(context_window_minutes=60, max_context_events=100)
    engine = PolicyEngine(
        audit_logger=DummyAuditLogger(), state_store=IdempotencyRepository()
    )

    # We must seed the Agent's context window with the calibration events so it doesn't start "blind"
    # at the exact moment the holdout test set begins.
    calibration_events = all_failed_events[:split_idx]
    for e_dict in calibration_events:
        stripped_dict = e_dict.copy()
        stripped_dict["is_synthetic_incident"] = False
        stripped_dict["incident_type"] = None
        agent.recent_failures.append(PaymentEvent(**stripped_dict))

    res_agent = evaluate_policy(
        "Revenue Resilience Agent",
        policy_agent,
        held_out_events,
        agent=agent,
        engine=engine,
    )
    res_agent.report()

    # Sensitivity Reporting (High Friction Cost vs Low Friction Cost)
    print("=== Sensitivity Analysis: Friction Penalty ===")
    original_friction = FRICTION_PENALTY

    # Low Friction
    FRICTION_PENALTY = Decimal("1.0")
    print("\nAssumption: LOW Friction Penalty (1.0 INR)")
    evaluate_policy(
        "Blind Retry (Low Friction)", policy_blind_retry, held_out_events
    ).report()

    # High Friction
    FRICTION_PENALTY = Decimal("10.0")
    print("\nAssumption: HIGH Friction Penalty (10.0 INR)")
    evaluate_policy(
        "Blind Retry (High Friction)", policy_blind_retry, held_out_events
    ).report()

    # Restore
    FRICTION_PENALTY = original_friction

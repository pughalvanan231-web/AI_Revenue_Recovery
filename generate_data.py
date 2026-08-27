import json
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
from schema import PaymentEvent

# Constants
MERCHANTS = ["M_AMAZON", "M_FLIPKART", "M_SWIGGY", "M_ZOMATO", "M_UBER"]
PAYMENT_METHODS = ["UPI", "CREDIT_CARD", "DEBIT_CARD", "NETBANKING"]
ISSUING_BANKS = ["HDFC", "ICICI", "SBI", "AXIS", "KOTAK"]
DEVICE_TYPES = ["MOBILE_IOS", "MOBILE_ANDROID", "DESKTOP"]
FAILURE_CODES = [
    "INSUFFICIENT_FUNDS",
    "ISSUER_DOWN",
    "TIMEOUT",
    "RISK_BLOCKED",
    "INVALID_CVV",
]


def generate_base_event(timestamp: datetime) -> Dict:
    """Generate a random payment event with normal baseline success rates."""
    is_success = random.random() < 0.85  # 85% normal success rate
    status = "SUCCESS" if is_success else "FAILED"

    failure_code = None
    if not is_success:
        failure_code = random.choices(
            FAILURE_CODES,
            weights=[0.4, 0.1, 0.2, 0.05, 0.25],  # Normally, ISSUER_DOWN is rare
            k=1,
        )[0]

    return {
        "event_id": str(uuid.uuid4()),
        "payment_attempt_group_id": f"group_{uuid.uuid4()}",
        "timestamp": timestamp,
        "merchant_id": random.choice(MERCHANTS),
        "amount": round(random.uniform(50.0, 5000.0), 2),
        "currency": "INR",
        "payment_method": random.choice(PAYMENT_METHODS),
        "issuing_bank": random.choice(ISSUING_BANKS),
        "device_type": random.choice(DEVICE_TYPES),
        "status": status,
        "failure_code": failure_code,
        "retry_count": 0,
        "is_synthetic_incident": False,
        "incident_type": None,
    }


def inject_bank_degradation(event: Dict, bank: str, failure_rate: float) -> Dict:
    """Simulate a severe degradation for a specific bank across all merchants."""
    if event["issuing_bank"] == bank:
        if random.random() < failure_rate:
            event["status"] = "FAILED"
            event["failure_code"] = "ISSUER_DOWN"
            event["is_synthetic_incident"] = True
            event["incident_type"] = "bank_degradation"
    return event


def inject_merchant_regression(event: Dict, merchant: str, failure_rate: float) -> Dict:
    """Simulate a checkout regression for a specific merchant."""
    if event["merchant_id"] == merchant and event["device_type"] == "DESKTOP":
        if random.random() < failure_rate:
            event["status"] = "FAILED"
            event["failure_code"] = "TIMEOUT"
            event["is_synthetic_incident"] = True
            event["incident_type"] = "merchant_checkout_regression"
    return event


def generate_dataset(num_events: int = 6000):
    events: List[Dict] = []

    start_time = datetime.now() - timedelta(days=7)

    # Incident parameters
    INCIDENTS = [
        {
            "bank": "HDFC",
            "start": start_time + timedelta(hours=24),  # Day 1
            "end": start_time + timedelta(hours=26),
            "type": "bank_degradation",
            "failure_rate": 0.8,
        },
        {
            "bank": "ICICI",
            "start": start_time + timedelta(hours=130),  # Day 5.4 (hits 30% holdout)
            "end": start_time + timedelta(hours=134),
            "type": "bank_degradation",
            "failure_rate": 0.9,
        },
    ]

    REGRESSIONS = [
        {
            "merchant": "M_SWIGGY",
            "start": start_time + timedelta(hours=140),  # Day 5.8 (hits holdout)
            "end": start_time + timedelta(hours=146),
            "type": "merchant_checkout_regression",
            "failure_rate": 0.8,
        }
    ]

    current_time = start_time
    time_increment = timedelta(days=7) / num_events

    for _ in range(num_events):
        event_dict = generate_base_event(current_time)

        # Inject incidents based on time windows
        for inc in INCIDENTS:
            if inc["start"] <= current_time <= inc["end"]:
                event_dict = inject_bank_degradation(
                    event_dict, inc["bank"], inc["failure_rate"]
                )

        for reg in REGRESSIONS:
            if reg["start"] <= current_time <= reg["end"]:
                event_dict = inject_merchant_regression(
                    event_dict, reg["merchant"], reg["failure_rate"]
                )

        # Validate through Pydantic to ensure schema correctness
        validated_event = PaymentEvent(**event_dict)
        events.append(validated_event.model_dump(mode="json"))

        current_time += time_increment

    return events


if __name__ == "__main__":
    print("Generating synthetic payment events...")
    dataset = generate_dataset(6000)

    output_file = "synthetic_events.jsonl"
    with open(output_file, "w") as f:
        for event in dataset:
            f.write(json.dumps(event) + "\n")

    print(f"Generated {len(dataset)} events and saved to {output_file}")

    df = pd.DataFrame(dataset)
    print("\nDataset Statistics:")
    print(f"Total events: {len(df)}")
    print(f"Overall Success Rate: {(df['status'] == 'SUCCESS').mean():.2%}")
    print("\nIncidents Injected:")
    print(df["incident_type"].value_counts().to_string())

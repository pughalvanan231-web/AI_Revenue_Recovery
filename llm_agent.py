"""
llm_agent.py

Trust Boundary: The probabilistic/heuristic layer of the system.
Responsibility: Uses historical context (recent failures) to diagnose the root cause of a payment failure.
Invariant: This layer outputs ONLY a DiagnosisProposal. It NEVER executes actions, mutates state,
or decides policy. Its `confidence` score (0.0 to 1.0) is a heuristic that the downstream policy
engine uses to gate risk.

Note: Currently operates as a deterministic simulator (use_real_llm=False) for testing/demo purposes.
A real LLM provider integration would enforce the same strict JSON schema boundary.
"""

import time
from typing import List, Dict, Optional
from collections import deque
from datetime import datetime, timedelta

from schema import PaymentEvent
from proposals import DiagnosisProposal, DiagnosisClass

# --- PROMPT TEMPLATE ---
# In a real implementation, this prompt is sent to Gemini or OpenAI along with the JSON context.
SYSTEM_PROMPT = """
You are the Revenue Resilience Agent, an AI diagnosing payment failures in real-time.
You are given a target failed PaymentEvent, along with a sliding window of recent failed events.

Analyze the context for systemic patterns:
1. Bank Degradation: Are there multiple failures for the same issuing_bank across different merchants?
2. Merchant Regression: Are there multiple failures for the same merchant, especially isolated to a specific device_type?
3. Transient Timeout: Is it an isolated timeout?
4. Insufficient Funds: Is the failure explicitly due to lack of user funds?

You MUST output exactly ONE JSON object matching the DiagnosisProposal schema.
Do NOT attempt to execute an action. Your job is ONLY to diagnose the root cause and provide a confidence score [0.0 - 1.0].
"""


class RevenueResilienceAgent:
    """
    Probabilistic Layer (Diagnosis Agent)
    Maintains a sliding window of recent failed events and uses an LLM to detect patterns.
    """

    def __init__(
        self,
        context_window_minutes: int = 60,
        max_context_events: int = 100,
        use_real_llm: bool = False,
    ):
        self.context_window_minutes = context_window_minutes
        self.max_context_events = max_context_events
        self.use_real_llm = use_real_llm
        self.recent_failures: deque = deque(maxlen=max_context_events)

        if self.use_real_llm:
            from google import genai

            self.client = genai.Client()

    def _get_relevant_context(self, current_event: PaymentEvent) -> List[PaymentEvent]:
        # Filter out events older than the context window
        cutoff_time = current_event.timestamp - timedelta(
            minutes=self.context_window_minutes
        )
        return [e for e in self.recent_failures if e.timestamp >= cutoff_time]

    def diagnose(self, event: PaymentEvent) -> DiagnosisProposal:
        """
        Takes a PaymentEvent, analyzes it against the context window, and returns a DiagnosisProposal.
        """
        # Get context BEFORE adding the current event
        context = self._get_relevant_context(event)

        # Add current event to memory for future evaluations
        self.recent_failures.append(event)

        if self.use_real_llm:
            try:
                # Build context block
                context_str = "\n".join(
                    [e.model_dump_json(exclude_none=True) for e in context]
                )
                target_str = event.model_dump_json(exclude_none=True)

                prompt = f"{SYSTEM_PROMPT}\n\nRecent Failures Context:\n{context_str}\n\nTarget Event:\n{target_str}"

                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": DiagnosisProposal.model_json_schema(),
                    },
                )
                return DiagnosisProposal.model_validate_json(response.text)
            except Exception as e:
                return DiagnosisProposal(
                    diagnosis_class=DiagnosisClass.TRANSIENT_TIMEOUT,
                    confidence=0.50,
                    evidence_summary=f"LLM API Error: {str(e)}",
                )

        # ---------------------------------------------------------------------
        # SIMULATED LLM INFERENCE (Fast mode for evaluation harness)
        # ---------------------------------------------------------------------

        # 1. Analyze Context for Bank Degradation
        same_bank_failures = [
            e for e in context if e.issuing_bank == event.issuing_bank
        ]
        if len(same_bank_failures) >= 3:
            return DiagnosisProposal(
                diagnosis_class=DiagnosisClass.BANK_DEGRADATION,
                confidence=0.95,
                evidence_summary=f"Detected {len(same_bank_failures)} recent failures for {event.issuing_bank} across merchants.",
            )

        # 2. Analyze Context for Merchant Checkout Regression
        same_merchant_device_failures = [
            e
            for e in context
            if e.merchant_id == event.merchant_id and e.device_type == event.device_type
        ]
        if len(same_merchant_device_failures) >= 3:
            return DiagnosisProposal(
                diagnosis_class=DiagnosisClass.MERCHANT_CHECKOUT_REGRESSION,
                confidence=0.92,
                evidence_summary=f"Detected {len(same_merchant_device_failures)} recent failures for {event.merchant_id} on {event.device_type}.",
            )

        # 3. Analyze Isolated Event
        if event.failure_code == "INSUFFICIENT_FUNDS":
            return DiagnosisProposal(
                diagnosis_class=DiagnosisClass.INSUFFICIENT_FUNDS,
                confidence=0.99,
                evidence_summary="Explicitly flagged as insufficient funds by the issuer.",
            )

        if event.failure_code == "TIMEOUT":
            return DiagnosisProposal(
                diagnosis_class=DiagnosisClass.TRANSIENT_TIMEOUT,
                confidence=0.85,
                evidence_summary="Isolated timeout with no broader systemic pattern detected in the context window.",
            )

        # Default / Fallback
        return DiagnosisProposal(
            diagnosis_class=DiagnosisClass.TRANSIENT_TIMEOUT,
            confidence=0.50,  # Low confidence, will be caught by Policy Engine Rule 3
            evidence_summary="Unknown failure code. Guessing transient timeout with low confidence.",
        )

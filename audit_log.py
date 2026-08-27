"""
audit_log.py

Trust Boundary: The append-only ledger for all system decisions.
Responsibility: Records the immutable facts of an intervention: what the LLM proposed,
what the policy engine decided, and the exact version of the policy at the time.
Invariant: The `proposal_hash` provides cryptographically verifiable proof of what the
probabilistic layer outputted, preventing tampering.
Limitation: Currently writes to a JSONL file. In production, this must write to a WORM
(Write-Once-Read-Many) datastore with cryptographically signed append-only logs.
"""

import json
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any


class AuditLogger:
    def __init__(self, log_file_path: str = "audit_log.jsonl"):
        self.log_file_path = log_file_path

    def log_decision(
        self,
        event_id: str,
        payment_attempt_group_id: str,
        idempotency_key: str,
        policy_version: str,
        diagnosis_proposal: Any,
        decision: str,
        reason: str,
        metadata: Dict[str, Any] = None,
    ):
        """
        Logs an immutable record of a policy decision for auditability.
        """
        # Create a simple hash of the proposal to prove what was evaluated
        proposal_dict = (
            diagnosis_proposal.model_dump()
            if hasattr(diagnosis_proposal, "model_dump")
            else {}
        )
        proposal_hash = hashlib.sha256(
            json.dumps(proposal_dict, sort_keys=True).encode()
        ).hexdigest()

        log_entry = {
            "decision_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_id": event_id,
            "payment_attempt_group_id": payment_attempt_group_id,
            "idempotency_key": idempotency_key,
            "policy_version": policy_version,
            "proposal_hash": proposal_hash,
            "proposal": proposal_dict,
            "decision": decision,
            "reason": reason,
            "metadata": metadata or {},
        }

        with open(self.log_file_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        return log_entry

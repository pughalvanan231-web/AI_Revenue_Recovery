"""
state_store.py

Trust Boundary: The system of record for at-most-once execution.
Responsibility: Ensures durable, concurrent-safe tracking of policy decisions and physical
executor states.
Invariant: All mutations must use SQLite atomic transactions (`with conn:`). Uses WAL mode
for safe concurrent reads/writes. If a PENDING reservation is stale or concurrent threads hit
an IntegrityError, they safely fallback to the cached final state.
Note on Migration: Currently uses a 'CREATE TABLE IF NOT EXISTS' strategy. Future production
iterations require a strict versioned migration script (e.g. Alembic).
"""

import sqlite3
import threading
from typing import Tuple, Optional
from datetime import datetime, timezone


class IdempotencyRepository:
    """
    A durable state store for tracking workflow attempts and preventing duplicate executions.
    Backed by SQLite to provide true atomicity and durability across restarts.
    """

    def __init__(self, db_path: str = "idempotency.db"):
        self.db_path = db_path
        self._init_db()
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            # Enable foreign keys and use Write-Ahead Logging for better concurrency
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS action_reservations (
                    idempotency_key TEXT PRIMARY KEY,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_attempts (
                    payment_attempt_group_id TEXT PRIMARY KEY,
                    attempt_count INTEGER NOT NULL DEFAULT 0
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS executor_states (
                    idempotency_key TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    razorpay_ref TEXT,
                    amount_paise INTEGER,
                    latency_ms INTEGER,
                    created_at TEXT NOT NULL
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS revenue_events (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    customer_id TEXT NOT NULL,
                    amount DECIMAL NOT NULL,
                    currency TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recovery_strategies (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    probability REAL NOT NULL,
                    reason TEXT NOT NULL,
                    selected_at TEXT NOT NULL
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_results (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    result TEXT NOT NULL,
                    amount_recovered DECIMAL NOT NULL,
                    execution_time TEXT NOT NULL
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS risk_scores (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    recovery_probability REAL NOT NULL,
                    risk_level TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS invoices (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    invoice_number TEXT NOT NULL,
                    amount DECIMAL NOT NULL,
                    due_date TEXT NOT NULL,
                    status TEXT NOT NULL
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS promise_to_pay (
                    id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL,
                    amount DECIMAL NOT NULL,
                    promised_date TEXT NOT NULL,
                    status TEXT NOT NULL
                )
            """
            )
        conn.close()

    def get_reservation(self, idempotency_key: str) -> Optional[Tuple[str, str]]:
        """Checks if a reservation exists without attempting to write."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT decision, reason FROM action_reservations WHERE idempotency_key = ?",
            (idempotency_key,),
        )
        row = cursor.fetchone()
        if row:
            return (row[0], row[1])
        return None

    def check_and_record(
        self, idempotency_key: str, decision: str, reason: str
    ) -> Tuple[bool, Tuple[str, str]]:
        """
        Atomically checks if the idempotency_key exists.
        If it does, returns (True, cached_decision).
        If it doesn't, records the new decision and returns (False, new_decision).

        To support updating from PENDING to final, we use an UPSERT (ON CONFLICT DO UPDATE).
        """
        conn = self._get_conn()

        try:
            with conn:
                # First check if it exists and what state it's in
                cursor = conn.execute(
                    "SELECT decision, reason FROM action_reservations WHERE idempotency_key = ?",
                    (idempotency_key,),
                )
                existing = cursor.fetchone()

                if existing:
                    # If we are trying to overwrite PENDING with a final decision, do an update.
                    if existing[0] == "PENDING" and decision != "PENDING":
                        conn.execute(
                            "UPDATE action_reservations SET decision = ?, reason = ?, timestamp = ? WHERE idempotency_key = ?",
                            (
                                decision,
                                reason,
                                datetime.now(timezone.utc).isoformat(),
                                idempotency_key,
                            ),
                        )
                        return False, (decision, reason)
                    else:
                        # Standard Idempotency Hit
                        return True, (existing[0], existing[1])

                # Insert new record
                conn.execute(
                    "INSERT INTO action_reservations (idempotency_key, decision, reason, timestamp) VALUES (?, ?, ?, ?)",
                    (
                        idempotency_key,
                        decision,
                        reason,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                return False, (decision, reason)
        except sqlite3.IntegrityError:
            # Race condition caught by SQLite PRIMARY KEY
            cursor = conn.execute(
                "SELECT decision, reason FROM action_reservations WHERE idempotency_key = ?",
                (idempotency_key,),
            )
            existing = cursor.fetchone()
            if existing:
                return True, (existing[0], existing[1])
            return True, ("UNKNOWN", "Race condition prevented row retrieval")

    def get_attempt_count(self, payment_attempt_group_id: str) -> int:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT attempt_count FROM workflow_attempts WHERE payment_attempt_group_id = ?",
            (payment_attempt_group_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else 0

    def increment_attempt_count(self, payment_attempt_group_id: str):
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                INSERT INTO workflow_attempts (payment_attempt_group_id, attempt_count)
                VALUES (?, 1)
                ON CONFLICT(payment_attempt_group_id) DO UPDATE SET attempt_count = attempt_count + 1
            """,
                (payment_attempt_group_id,),
            )

    def get_executor_state(
        self, idempotency_key: str
    ) -> Optional[Tuple[str, str, str]]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT status, message, razorpay_ref FROM executor_states WHERE idempotency_key = ?",
            (idempotency_key,),
        )
        row = cursor.fetchone()
        return (row[0], row[1], row[2]) if row else None

    def record_executor_state(
        self,
        idempotency_key: str,
        status: str,
        message: str,
        razorpay_ref: str = "",
        amount_paise: int = 0,
        latency_ms: int = 0,
    ) -> Tuple[bool, str, str, str]:
        """Records executor state atomically. Returns (is_duplicate, status, message, razorpay_ref)."""
        conn = self._get_conn()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO executor_states (idempotency_key, status, message, razorpay_ref, amount_paise, latency_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        idempotency_key,
                        status,
                        message,
                        razorpay_ref,
                        amount_paise,
                        latency_ms,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                return False, status, message, razorpay_ref
        except sqlite3.IntegrityError:
            cached = self.get_executor_state(idempotency_key)
            if cached:
                return True, cached[0], cached[1], cached[2]
            return True, "UNKNOWN", "Race condition fetching executor state", ""

    def close(self):
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn

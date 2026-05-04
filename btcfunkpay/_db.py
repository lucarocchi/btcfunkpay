from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from ._models import Invoice, PaymentStatus

_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS payments (
    id            TEXT PRIMARY KEY,
    address       TEXT NOT NULL UNIQUE,
    xpub_index    INTEGER NOT NULL,
    amount_sat    INTEGER,
    label         TEXT,
    status        TEXT NOT NULL DEFAULT 'pending',
    created_at    INTEGER NOT NULL,
    expires_at    INTEGER,
    txid          TEXT,
    received_sat  INTEGER NOT NULL DEFAULT 0,
    confirmations INTEGER NOT NULL DEFAULT 0,
    confirmed_at  INTEGER,
    updated_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS address_index (
    xpub        TEXT PRIMARY KEY,
    next_index  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS monitor_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _ts_to_dt(ts: Optional[int]) -> Optional[datetime]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _row_to_invoice(row: sqlite3.Row) -> Invoice:
    return Invoice(
        payment_id=row["id"],
        address=row["address"],
        xpub_index=row["xpub_index"],
        amount_sat=row["amount_sat"],
        label=row["label"],
        status=PaymentStatus(row["status"]),
        created_at=_ts_to_dt(row["created_at"]),
        expires_at=_ts_to_dt(row["expires_at"]),
        txid=row["txid"],
        received_sat=row["received_sat"],
        confirmations=row["confirmations"],
        confirmed_at=_ts_to_dt(row["confirmed_at"]),
    )


class PaymentStore:
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(
            db_path, check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._conn.executescript(_SCHEMA)

    def get_next_index(self, xpub: str) -> int:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._conn.execute(
                "SELECT next_index FROM address_index WHERE xpub = ?", (xpub,)
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO address_index (xpub, next_index) VALUES (?, 1)", (xpub,)
                )
                idx = 0
            else:
                idx = row["next_index"]
                self._conn.execute(
                    "UPDATE address_index SET next_index = ? WHERE xpub = ?",
                    (idx + 1, xpub),
                )
            self._conn.execute("COMMIT")
        return idx

    def create_payment(
        self,
        address: str,
        xpub_index: int,
        amount_sat: Optional[int],
        label: Optional[str],
        expires_at: Optional[datetime],
    ) -> Invoice:
        payment_id = str(uuid.uuid4())
        now = _now_ts()
        exp_ts = int(expires_at.timestamp()) if expires_at else None
        with self._lock:
            self._conn.execute(
                """INSERT INTO payments
                   (id, address, xpub_index, amount_sat, label, status,
                    created_at, expires_at, received_sat, confirmations, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,0,0,?)""",
                (payment_id, address, xpub_index, amount_sat, label,
                 PaymentStatus.PENDING.value, now, exp_ts, now),
            )
        return self.get_payment(payment_id)

    def get_payment(self, payment_id: str) -> Optional[Invoice]:
        row = self._conn.execute(
            "SELECT * FROM payments WHERE id = ?", (payment_id,)
        ).fetchone()
        return _row_to_invoice(row) if row else None

    def get_payment_by_address(self, address: str) -> Optional[Invoice]:
        row = self._conn.execute(
            "SELECT * FROM payments WHERE address = ?", (address,)
        ).fetchone()
        return _row_to_invoice(row) if row else None

    _ALLOWED_UPDATE_FIELDS = frozenset({
        "txid", "received_sat", "confirmations", "status", "confirmed_at",
    })

    def update_payment(self, payment_id: str, **fields) -> None:
        if not fields:
            return
        unknown = set(fields) - self._ALLOWED_UPDATE_FIELDS
        if unknown:
            raise ValueError(f"update_payment: campi non permessi: {unknown}")
        fields["updated_at"] = _now_ts()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [payment_id]
        with self._lock:
            self._conn.execute(
                f"UPDATE payments SET {set_clause} WHERE id = ?", values
            )

    def list_payments(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Invoice]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM payments WHERE status = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM payments ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_row_to_invoice(r) for r in rows]

    def list_pending(self) -> list[Invoice]:
        rows = self._conn.execute(
            "SELECT * FROM payments WHERE status IN ('pending', 'detected')"
        ).fetchall()
        return [_row_to_invoice(r) for r in rows]

    def list_expired(self) -> list[Invoice]:
        now = _now_ts()
        rows = self._conn.execute(
            "SELECT * FROM payments WHERE status = 'pending' "
            "AND expires_at IS NOT NULL AND expires_at < ?",
            (now,),
        ).fetchall()
        return [_row_to_invoice(r) for r in rows]

    def get_watched_addresses(self) -> dict[str, str]:
        rows = self._conn.execute(
            "SELECT address, id FROM payments WHERE status IN ('pending', 'detected')"
        ).fetchall()
        return {r["address"]: r["id"] for r in rows}

    def get_monitor_state(self, key: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT value FROM monitor_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set_monitor_state(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO monitor_state (key, value) VALUES (?, ?)",
                (key, value),
            )

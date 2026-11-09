"""Реализации PaymentRepository. Взаимозаменяемы (LSP)."""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from decimal import Decimal

from app.domain.models import Money, Payment, PaymentStatus
from app.interfaces.ports import PaymentRepository


class InMemoryPaymentRepository(PaymentRepository):
    def __init__(self) -> None:
        self._data: dict[str, Payment] = {}

    def add(self, payment: Payment) -> None:
        self._data[payment.id] = payment

    def get(self, payment_id: str) -> Payment | None:
        return self._data.get(payment_id)

    def update(self, payment: Payment) -> None:
        self._data[payment.id] = payment

    def list_all(self) -> list[Payment]:
        return sorted(self._data.values(), key=lambda p: p.created_at, reverse=True)

    def find_by_tx_hash(self, tx_hash: str) -> Payment | None:
        return next((p for p in self._data.values() if p.tx_hash == tx_hash.lower()), None)


class SQLitePaymentRepository(PaymentRepository):
    def __init__(self, path: str = "cryptopay.db") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS payments (
                    id TEXT PRIMARY KEY,
                    merchant_address TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    tx_hash TEXT,
                    payer_address TEXT,
                    fee_wei TEXT NOT NULL DEFAULT '0',
                    confirmations INTEGER NOT NULL DEFAULT 0
                )"""
            )
            self._conn.commit()

    @staticmethod
    def _row_to_payment(r: sqlite3.Row) -> Payment:
        return Payment(
            id=r["id"],
            merchant_address=r["merchant_address"],
            amount=Money(Decimal(r["amount"]), r["currency"]),
            description=r["description"] or "",
            status=PaymentStatus(r["status"]),
            created_at=datetime.fromisoformat(r["created_at"]),
            expires_at=datetime.fromisoformat(r["expires_at"]),
            tx_hash=r["tx_hash"],
            payer_address=r["payer_address"],
            fee_wei=int(r["fee_wei"]),
            confirmations=r["confirmations"],
        )

    def add(self, p: Payment) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (p.id, p.merchant_address, str(p.amount.amount), p.amount.currency, p.description,
                 p.status.value, p.created_at.isoformat(), p.expires_at.isoformat(),
                 p.tx_hash, p.payer_address, str(p.fee_wei), p.confirmations),
            )
            self._conn.commit()

    def get(self, payment_id: str) -> Payment | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
        return self._row_to_payment(r) if r else None

    def update(self, p: Payment) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE payments SET status=?, tx_hash=?, payer_address=?, fee_wei=?, confirmations=?, expires_at=? WHERE id=?",
                (p.status.value, p.tx_hash, p.payer_address, str(p.fee_wei), p.confirmations,
                 p.expires_at.isoformat(), p.id),
            )
            self._conn.commit()

    def list_all(self) -> list[Payment]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM payments ORDER BY created_at DESC").fetchall()
        return [self._row_to_payment(r) for r in rows]

    def find_by_tx_hash(self, tx_hash: str) -> Payment | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM payments WHERE tx_hash=?", (tx_hash.lower(),)).fetchone()
        return self._row_to_payment(r) if r else None

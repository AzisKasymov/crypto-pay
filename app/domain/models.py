"""Доменные сущности. Не зависят ни от FastAPI, ни от блокчейна, ни от БД (DIP)."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")


class PaymentStatus(str, Enum):
    PENDING = "PENDING"        # счёт создан, ждём оплату
    CONFIRMING = "CONFIRMING"  # tx найдена, ждём подтверждений
    PAID = "PAID"              # оплачено
    FAILED = "FAILED"          # tx отклонена / не совпала с заказом
    EXPIRED = "EXPIRED"        # время жизни счёта истекло


class DomainError(Exception):
    """Базовая ошибка предметной области."""


class InvalidAddressError(DomainError):
    pass


class InvalidTransitionError(DomainError):
    pass


def validate_address(address: str) -> str:
    if not ADDRESS_RE.match(address or ""):
        raise InvalidAddressError(f"Некорректный адрес кошелька: {address!r}")
    return address.lower()


@dataclass(frozen=True)
class Money:
    """Value object: сумма в ETH (Decimal, не float!)."""
    amount: Decimal
    currency: str = "ETH"

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise DomainError("Сумма должна быть положительной")

    @property
    def wei(self) -> int:
        return int(self.amount * Decimal(10) ** 18)


@dataclass
class OnChainTx:
    """Снимок транзакции, полученный из блокчейна."""
    tx_hash: str
    sender: str
    recipient: str
    value_wei: int
    confirmations: int
    success: bool


@dataclass
class Payment:
    merchant_address: str
    amount: Money
    description: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=30))
    tx_hash: str | None = None
    payer_address: str | None = None
    fee_wei: int = 0
    confirmations: int = 0

    _ALLOWED = {
        PaymentStatus.PENDING: {PaymentStatus.CONFIRMING, PaymentStatus.PAID, PaymentStatus.FAILED, PaymentStatus.EXPIRED},
        PaymentStatus.CONFIRMING: {PaymentStatus.CONFIRMING, PaymentStatus.PAID, PaymentStatus.FAILED},
        PaymentStatus.PAID: set(),
        PaymentStatus.FAILED: set(),
        PaymentStatus.EXPIRED: set(),
    }

    def transition(self, new_status: PaymentStatus) -> None:
        if new_status not in self._ALLOWED[self.status]:
            raise InvalidTransitionError(f"{self.status.value} -> {new_status.value} запрещён")
        self.status = new_status

    def is_expired(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return self.status == PaymentStatus.PENDING and now > self.expires_at

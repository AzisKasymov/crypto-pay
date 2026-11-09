"""Абстракции (порты). Сервисы зависят от них, а не от конкретных реализаций (DIP).
Интерфейсы узкие и целевые (ISP): репозиторий, блокчейн, комиссия, уведомления — отдельно."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import OnChainTx, Payment


class PaymentRepository(ABC):
    @abstractmethod
    def add(self, payment: Payment) -> None: ...

    @abstractmethod
    def get(self, payment_id: str) -> Payment | None: ...

    @abstractmethod
    def update(self, payment: Payment) -> None: ...

    @abstractmethod
    def list_all(self) -> list[Payment]: ...

    @abstractmethod
    def find_by_tx_hash(self, tx_hash: str) -> Payment | None: ...


class BlockchainGateway(ABC):
    """Доступ к блокчейну только на чтение (проверка транзакций)."""

    @abstractmethod
    def get_transaction(self, tx_hash: str) -> OnChainTx | None: ...


class FeeCalculator(ABC):
    @abstractmethod
    def fee_wei(self, amount_wei: int) -> int: ...


class Notifier(ABC):
    @abstractmethod
    def notify(self, event: str, payload: dict) -> None: ...

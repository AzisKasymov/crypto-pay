"""Бизнес-логика платежей. Зависит только от абстракций (DIP) и отвечает только за
оркестрацию платежа (SRP): хранение, блокчейн, комиссия и уведомления вынесены."""
from __future__ import annotations

from decimal import Decimal

from app.domain.models import (
    TX_HASH_RE, DomainError, Money, Payment, PaymentStatus, validate_address,
)
from app.interfaces.ports import BlockchainGateway, FeeCalculator, Notifier, PaymentRepository


class PaymentNotFound(DomainError):
    pass


class PaymentService:
    def __init__(
        self,
        repo: PaymentRepository,
        chain: BlockchainGateway,
        fee: FeeCalculator,
        notifier: Notifier,
        required_confirmations: int = 1,
    ) -> None:
        self._repo = repo
        self._chain = chain
        self._fee = fee
        self._notifier = notifier
        self._required = required_confirmations

    # --- создание счёта -------------------------------------------------
    def create_payment(self, merchant_address: str, amount: Decimal, description: str = "") -> Payment:
        payment = Payment(
            merchant_address=validate_address(merchant_address),
            amount=Money(amount),
            description=description,
        )
        payment.fee_wei = self._fee.fee_wei(payment.amount.wei)
        self._repo.add(payment)
        self._notifier.notify("payment.created", {"id": payment.id, "amount": str(amount)})
        return payment

    # --- чтение ----------------------------------------------------------
    def get(self, payment_id: str) -> Payment:
        payment = self._repo.get(payment_id)
        if payment is None:
            raise PaymentNotFound(f"Платёж {payment_id} не найден")
        if payment.is_expired():
            payment.transition(PaymentStatus.EXPIRED)
            self._repo.update(payment)
            self._notifier.notify("payment.expired", {"id": payment.id})
        return payment

    def list_all(self) -> list[Payment]:
        return self._repo.list_all()

    # --- привязка транзакции и проверка ---------------------------------
    def submit_transaction(self, payment_id: str, tx_hash: str) -> Payment:
        if not TX_HASH_RE.match(tx_hash or ""):
            raise DomainError("Некорректный хэш транзакции")
        tx_hash = tx_hash.lower()
        payment = self.get(payment_id)

        if payment.status in (PaymentStatus.PAID, PaymentStatus.EXPIRED, PaymentStatus.FAILED):
            raise DomainError(f"Платёж в статусе {payment.status.value}, повторная отправка невозможна")

        existing = self._repo.find_by_tx_hash(tx_hash)
        if existing is not None and existing.id != payment.id:
            raise DomainError("Эта транзакция уже привязана к другому платежу")

        payment.tx_hash = tx_hash
        return self._verify(payment)

    def refresh(self, payment_id: str) -> Payment:
        """Повторная проверка (для статуса CONFIRMING)."""
        payment = self.get(payment_id)
        if payment.tx_hash and payment.status in (PaymentStatus.PENDING, PaymentStatus.CONFIRMING):
            return self._verify(payment)
        return payment

    def _verify(self, payment: Payment) -> Payment:
        tx = self._chain.get_transaction(payment.tx_hash)
        if tx is None:
            payment.confirmations = 0
            self._repo.update(payment)
            return payment  # tx ещё не видна в сети — остаёмся PENDING

        payment.payer_address = tx.sender
        payment.confirmations = tx.confirmations

        valid = (
            tx.success
            and tx.recipient == payment.merchant_address
            and tx.value_wei >= payment.amount.wei
        )
        if not valid:
            payment.transition(PaymentStatus.FAILED)
            self._notifier.notify("payment.failed", {"id": payment.id, "tx": payment.tx_hash})
        elif tx.confirmations >= self._required:
            payment.transition(PaymentStatus.PAID)
            self._notifier.notify("payment.paid", {"id": payment.id, "tx": payment.tx_hash})
        else:
            payment.transition(PaymentStatus.CONFIRMING)

        self._repo.update(payment)
        return payment

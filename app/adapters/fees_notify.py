"""Стратегии комиссии (OCP: новая стратегия — новый класс, без правки PaymentService)
и уведомления."""
from __future__ import annotations

import logging

from app.interfaces.ports import FeeCalculator, Notifier

log = logging.getLogger("cryptopay")


class PercentFee(FeeCalculator):
    def __init__(self, percent: float = 1.0) -> None:
        self._bp = int(percent * 100)  # базисные пункты

    def fee_wei(self, amount_wei: int) -> int:
        return amount_wei * self._bp // 10_000


class FlatFee(FeeCalculator):
    def __init__(self, flat_wei: int) -> None:
        self._flat = flat_wei

    def fee_wei(self, amount_wei: int) -> int:
        return self._flat


class NoFee(FeeCalculator):
    def fee_wei(self, amount_wei: int) -> int:
        return 0


class LogNotifier(Notifier):
    def notify(self, event: str, payload: dict) -> None:
        log.info("EVENT %s %s", event, payload)


class CompositeNotifier(Notifier):
    """Паттерн Composite: несколько получателей уведомлений как один."""

    def __init__(self, *notifiers: Notifier) -> None:
        self._n = notifiers

    def notify(self, event: str, payload: dict) -> None:
        for n in self._n:
            n.notify(event, payload)

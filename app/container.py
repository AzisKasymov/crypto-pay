"""Composition Root: единственное место, где выбираются конкретные реализации (DIP).
Чтобы заменить БД, сеть или комиссию, достаточно изменить только этот файл."""
from __future__ import annotations

from app.adapters.blockchain import EthereumRpcGateway, MockBlockchainGateway
from app.adapters.fees_notify import LogNotifier, PercentFee
from app.adapters.repositories import SQLitePaymentRepository
from app.config import Settings
from app.interfaces.ports import BlockchainGateway
from app.services.payment_service import PaymentService


def build_chain(settings: Settings) -> BlockchainGateway:
    if settings.chain_mode == "ethereum":
        return EthereumRpcGateway(settings.rpc_url)
    return MockBlockchainGateway()


def build_service(settings: Settings, chain: BlockchainGateway | None = None) -> PaymentService:
    return PaymentService(
        repo=SQLitePaymentRepository(settings.db_path),
        chain=chain or build_chain(settings),
        fee=PercentFee(settings.fee_percent),
        notifier=LogNotifier(),
        required_confirmations=settings.required_confirmations,
    )

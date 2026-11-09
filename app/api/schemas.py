from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CreatePaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0, description="Сумма в ETH")
    merchant_address: str | None = Field(default=None, description="Адрес получателя (0x...)")
    description: str = ""


class SubmitTxRequest(BaseModel):
    tx_hash: str


class PaymentOut(BaseModel):
    id: str
    merchant_address: str
    amount: str
    amount_wei: str
    currency: str
    description: str
    status: str
    created_at: datetime
    expires_at: datetime
    tx_hash: str | None
    payer_address: str | None
    fee_wei: str
    confirmations: int


class MockTxRequest(BaseModel):
    """Только для демо-режима (CHAIN_MODE=mock): имитирует перевод в блокчейне."""
    payment_id: str
    sender: str = "0x1111111111111111111111111111111111111111"
    confirmations: int = 3

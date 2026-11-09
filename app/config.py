"""Конфигурация из переменных окружения (12-factor), чтобы запускать на любом облаке."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    chain_mode: str = os.getenv("CHAIN_MODE", "mock")            # mock | ethereum
    rpc_url: str = os.getenv("RPC_URL", "https://ethereum-sepolia-rpc.publicnode.com")
    chain_id: int = int(os.getenv("CHAIN_ID", "11155111"))        # Sepolia
    chain_name: str = os.getenv("CHAIN_NAME", "Sepolia Testnet")
    db_path: str = os.getenv("DB_PATH", "cryptopay.db")
    fee_percent: float = float(os.getenv("FEE_PERCENT", "1.0"))
    required_confirmations: int = int(os.getenv("REQUIRED_CONFIRMATIONS", "1"))
    default_merchant: str = os.getenv("MERCHANT_ADDRESS", "0x000000000000000000000000000000000000dEaD")

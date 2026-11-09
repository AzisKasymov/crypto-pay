"""Реализации BlockchainGateway.

EthereumRpcGateway — реальная проверка транзакций через JSON-RPC (Sepolia/Mainnet/любая EVM-сеть).
MockBlockchainGateway — для тестов и демонстрации без интернета.
"""
from __future__ import annotations

import httpx

from app.domain.models import OnChainTx
from app.interfaces.ports import BlockchainGateway


class EthereumRpcGateway(BlockchainGateway):
    def __init__(self, rpc_url: str, timeout: float = 10.0) -> None:
        self._url = rpc_url
        self._client = httpx.Client(timeout=timeout)
        self._id = 0

    def _call(self, method: str, params: list):
        self._id += 1
        resp = self._client.post(self._url, json={"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"RPC error: {data['error']}")
        return data["result"]

    def get_transaction(self, tx_hash: str) -> OnChainTx | None:
        tx = self._call("eth_getTransactionByHash", [tx_hash])
        if tx is None:
            return None
        receipt = self._call("eth_getTransactionReceipt", [tx_hash])
        if receipt is None or tx.get("blockNumber") is None:
            # tx в mempool, ещё не включена в блок
            return OnChainTx(tx_hash, tx["from"].lower(), (tx.get("to") or "").lower(),
                             int(tx["value"], 16), 0, True)
        latest = int(self._call("eth_blockNumber", []), 16)
        confirmations = max(0, latest - int(receipt["blockNumber"], 16) + 1)
        return OnChainTx(
            tx_hash=tx_hash,
            sender=tx["from"].lower(),
            recipient=(tx.get("to") or "").lower(),
            value_wei=int(tx["value"], 16),
            confirmations=confirmations,
            success=receipt.get("status") == "0x1",
        )


class MockBlockchainGateway(BlockchainGateway):
    """Эмулятор блокчейна: транзакции добавляются вручную (в тестах и демо-режиме)."""

    def __init__(self) -> None:
        self._txs: dict[str, OnChainTx] = {}

    def register(self, tx: OnChainTx) -> None:
        self._txs[tx.tx_hash.lower()] = tx

    def get_transaction(self, tx_hash: str) -> OnChainTx | None:
        return self._txs.get(tx_hash.lower())

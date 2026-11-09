"""HTTP-слой (FastAPI). Только трансляция запросов в вызовы сервиса (SRP)."""
from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.adapters.blockchain import MockBlockchainGateway
from app.api.schemas import CreatePaymentRequest, MockTxRequest, PaymentOut, SubmitTxRequest
from app.config import Settings
from app.container import build_chain, build_service
from app.domain.models import DomainError, OnChainTx, Payment
from app.services.payment_service import PaymentNotFound, PaymentService

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def to_out(p: Payment) -> PaymentOut:
    return PaymentOut(
        id=p.id, merchant_address=p.merchant_address, amount=str(p.amount.amount),
        amount_wei=str(p.amount.wei), currency=p.amount.currency, description=p.description,
        status=p.status.value, created_at=p.created_at, expires_at=p.expires_at,
        tx_hash=p.tx_hash, payer_address=p.payer_address, fee_wei=str(p.fee_wei),
        confirmations=p.confirmations,
    )


def create_app(settings: Settings | None = None, service: PaymentService | None = None,
               chain=None) -> FastAPI:
    settings = settings or Settings()
    chain = chain or build_chain(settings)
    service = service or build_service(settings, chain)

    app = FastAPI(title="CryptoPay", version="1.0.0",
                  description="Платёжная система с интеграцией криптокошелька (MetaMask / Ethereum)")

    @app.exception_handler(PaymentNotFound)
    async def _nf(_, exc: PaymentNotFound):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def _de(_, exc: DomainError):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "chain_mode": settings.chain_mode}

    @app.get("/api/config")
    def config():
        return {
            "chain_mode": settings.chain_mode,
            "chain_id": settings.chain_id,
            "chain_id_hex": hex(settings.chain_id),
            "chain_name": settings.chain_name,
            "rpc_url": settings.rpc_url,
            "default_merchant": settings.default_merchant,
            "fee_percent": settings.fee_percent,
        }

    @app.post("/api/payments", response_model=PaymentOut, status_code=201)
    def create_payment(req: CreatePaymentRequest):
        merchant = req.merchant_address or settings.default_merchant
        return to_out(service.create_payment(merchant, req.amount, req.description))

    @app.get("/api/payments", response_model=list[PaymentOut])
    def list_payments():
        return [to_out(p) for p in service.list_all()]

    @app.get("/api/payments/{payment_id}", response_model=PaymentOut)
    def get_payment(payment_id: str):
        return to_out(service.get(payment_id))

    @app.post("/api/payments/{payment_id}/tx", response_model=PaymentOut)
    def submit_tx(payment_id: str, req: SubmitTxRequest):
        return to_out(service.submit_transaction(payment_id, req.tx_hash))

    @app.post("/api/payments/{payment_id}/refresh", response_model=PaymentOut)
    def refresh(payment_id: str):
        return to_out(service.refresh(payment_id))

    # --- демо-режим: имитация перевода без реального кошелька ---------
    if isinstance(chain, MockBlockchainGateway):
        @app.post("/api/dev/mock-tx")
        def mock_tx(req: MockTxRequest):
            p = service.get(req.payment_id)
            tx_hash = "0x" + secrets.token_hex(32)
            chain.register(OnChainTx(tx_hash, req.sender.lower(), p.merchant_address,
                                     p.amount.wei, req.confirmations, True))
            return {"tx_hash": tx_hash}

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(WEB_DIR / "index.html")

    return app


app = create_app()

"""
FastAPI integration example — btcfunkpay backend.

Usage:
  pip install fastapi uvicorn httpx
  uvicorn server:app --reload
"""

import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from btcfunkpay import PaymentProcessor, PaymentEvent, load_config

cfg = load_config()

_STATIC_DIR = Path(__file__).parent / "static"

_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

def _safe_webhook_url(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        host = p.hostname or ""
        if host in _BLOCKED_HOSTS:
            return False
        if host.startswith("169.254.") or host.startswith("10.") or host.startswith("192.168."):
            return False
        return True
    except Exception:
        return False

# --------------------------------------------------------------------------- #
#  Lifespan                                                                    #
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    proc = PaymentProcessor(
        xpub=cfg.xpub,
        rpc_url=cfg.rpc_url,
        db_path=cfg.db_path,
        required_confirmations=cfg.required_confirmations,
        poll_interval=cfg.poll_interval,
        expiry_seconds=cfg.expiry_seconds,
        mainnet=cfg.mainnet,
        wallet_name=cfg.wallet_name,
    )
    proc.setup()

    @proc.on_payment
    async def handle(event: PaymentEvent):
        import logging
        logger = logging.getLogger("btcfunkpay")
        status = event.status.value if hasattr(event.status, "value") else str(event.status)
        logger.info(
            f"payment {event.payment_id}: {status} "
            f"— {event.received_sat} sat label={event.label}"
        )
        if cfg.webhook_url and _safe_webhook_url(cfg.webhook_url) and (event.is_first_detection or event.is_first_confirmation):
            payload = {
                "payment_id":    event.payment_id,
                "label":         event.label,
                "status":        status,
                "received_sat":  event.received_sat,
                "txid":          event.txid,
                "address":       event.address,
                "confirmations": event.confirmations,
            }
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    await c.post(cfg.webhook_url, json=payload)
            except Exception as e:
                logger.warning(f"webhook POST failed: {e}")

    app.state.proc = proc
    # price cache: {"prices": {...}, "ts": float}
    app.state.price_cache = None
    await proc.astart()
    yield
    await proc.astop()


# --------------------------------------------------------------------------- #
#  App                                                                         #
# --------------------------------------------------------------------------- #

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


# --------------------------------------------------------------------------- #
#  Routes                                                                      #
# --------------------------------------------------------------------------- #

@app.get("/")
def root():
    return {"service": "btcfunkpay", "version": "1.0"}


@app.get("/funkpay.js")
def funkpay_js():
    path = _STATIC_DIR / "funkpay.js"
    return Response(
        content=path.read_text(),
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/prices")
async def prices(request: Request):
    cache = request.app.state.price_cache
    now = time.time()
    if cache and now - cache["ts"] < 120:
        return cache["prices"]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://mempool.space/api/v1/prices",
                headers={"User-Agent": "btcfunkpay/1.0"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        if cache:
            return cache["prices"]
        raise HTTPException(status_code=502, detail=f"price fetch failed: {exc}")

    # mempool returns { USD, EUR, GBP, CAD, CHF, AUD, JPY }
    request.app.state.price_cache = {"prices": data, "ts": now}
    return data


class InvoiceRequest(BaseModel):
    amount_sat: int | None = None
    label: str | None = None


@app.post("/invoices")
def create_invoice(req: InvoiceRequest, request: Request):
    inv = request.app.state.proc.create_invoice(
        amount_sat=req.amount_sat, label=req.label
    )
    return {
        "payment_id": inv.payment_id,
        "address":    inv.address,
        "bip21_uri":  inv.bip21_uri,
        "amount_sat": inv.amount_sat,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
    }


@app.get("/invoices")
def list_invoices(
    request: Request,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    invoices = request.app.state.proc.list_invoices(
        status=status, limit=min(limit, 500), offset=offset
    )
    return [
        {
            "payment_id":    inv.payment_id,
            "address":       inv.address,
            "label":         inv.label,
            "amount_sat":    inv.amount_sat,
            "status":        inv.status.value,
            "received_sat":  inv.received_sat,
            "confirmations": inv.confirmations,
            "txid":          inv.txid,
            "created_at":    inv.created_at.isoformat() if inv.created_at else None,
            "confirmed_at":  inv.confirmed_at.isoformat() if inv.confirmed_at else None,
        }
        for inv in invoices
    ]


@app.get("/invoices/{payment_id}")
def get_invoice(payment_id: str, request: Request):
    inv = request.app.state.proc.get_invoice(payment_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "payment_id":    inv.payment_id,
        "address":       inv.address,
        "status":        inv.status.value,
        "received_sat":  inv.received_sat,
        "confirmations": inv.confirmations,
        "txid":          inv.txid,
    }

"""
FastAPI integration example — btcfunkpay backend.

Usage:
  pip install fastapi uvicorn httpx
  uvicorn server:app --reload
"""

import logging
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

# Prevent urllib3/requests from logging HTTP bodies at DEBUG level.
# importdescriptors RPC payloads contain the full xpub — keep them out of logs.
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

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
            f"payment {event.payment_id}: {status} — {event.received_sat} sat"
        )
        if cfg.webhook_url and _safe_webhook_url(cfg.webhook_url) and (event.is_first_detection or event.is_first_confirmation):
            inv = proc.get_invoice(event.payment_id)
            payload = {
                "payment_id":    event.payment_id,
                "label":         event.label,
                "status":        status,
                "received_sat":  event.received_sat,
                "txid":          event.txid,
                "address":       event.address,
                "confirmations": event.confirmations,
            }
            if inv and inv.shipping:
                payload["shipping"] = inv.shipping
            if inv and inv.billing:
                payload["billing"] = inv.billing
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

_limiter = Limiter(key_func=get_remote_address)
app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.state.limiter = _limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_http_basic = HTTPBasic()

def _require_admin(credentials: HTTPBasicCredentials = Depends(_http_basic)):
    pw = cfg.admin_password
    if not pw:
        raise HTTPException(status_code=503, detail="Admin password not configured")
    ok_user = secrets.compare_digest(credentials.username.encode(), cfg.admin_username.encode())
    ok_pass = secrets.compare_digest(credentials.password.encode(), pw.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )

_origins = [o.strip() for o in cfg.allowed_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


# --------------------------------------------------------------------------- #
#  Routes                                                                      #
# --------------------------------------------------------------------------- #

@app.get("/")
def root(request: Request):
    host = request.headers.get("host", "").split(":")[0]
    if host == "funkpay.dev":
        from fastapi.responses import HTMLResponse
        path = _STATIC_DIR / "funkpay-landing.html"
        return HTMLResponse(path.read_text())
    return {"service": "btcfunkpay", "version": "1.0"}


@app.get("/.well-known/funkpay.json")
def well_known():
    """FunkPay service discovery — lets AI agents auto-discover this server from a domain."""
    server = cfg.public_url.rstrip("/") if cfg.public_url else ""
    name = cfg.name or (cfg.public_url.split("//")[-1].split("/")[0] if cfg.public_url else "btcfunkpay")
    return {"server": server, "name": name, "version": "1.0"}


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


class ShippingInfo(BaseModel):
    firstName: str = Field("", max_length=128)
    lastName: str = Field("", max_length=128)
    email: str = Field("", max_length=256)
    phone: str = Field("", max_length=64)
    address1: str = Field("", max_length=256)
    address2: str = Field("", max_length=256)
    city: str = Field("", max_length=128)
    state: str = Field("", max_length=128)
    zip: str = Field("", max_length=32)
    country: str = Field("", max_length=64)


class BillingInfo(BaseModel):
    sameAsShipping: bool = True
    company: str = Field("", max_length=256)
    vatId: str = Field("", max_length=64)
    firstName: str = Field("", max_length=128)
    lastName: str = Field("", max_length=128)
    email: str = Field("", max_length=256)
    address1: str = Field("", max_length=256)
    city: str = Field("", max_length=128)
    zip: str = Field("", max_length=32)
    country: str = Field("", max_length=64)


class InvoiceRequest(BaseModel):
    amount_sat: int | None = Field(None, ge=1000, le=2_100_000_000_000_000)
    label: str | None = Field(None, max_length=256)
    shipping: ShippingInfo | None = None
    billing: BillingInfo | None = None


@app.post("/invoices")
@_limiter.limit("20/minute")
def create_invoice(req: InvoiceRequest, request: Request):
    inv = request.app.state.proc.create_invoice(
        amount_sat=req.amount_sat,
        label=req.label,
        shipping=req.shipping.model_dump() if req.shipping else None,
        billing=req.billing.model_dump() if req.billing else None,
    )
    return {
        "payment_id": inv.payment_id,
        "address":    inv.address,
        "bip21_uri":  inv.bip21_uri,
        "amount_sat": inv.amount_sat,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
    }


_STATUS_PATTERN = "^(pending|detected|confirmed|expired|overpaid)$"

@app.get("/invoices")
def list_invoices(
    request: Request,
    status: str | None = Query(None, pattern=_STATUS_PATTERN),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: HTTPBasicCredentials = Depends(_require_admin),
):
    invoices = request.app.state.proc.list_invoices(
        status=status, limit=limit, offset=offset
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

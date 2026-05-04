# FunkPay — Integration Guide

This document explains how to integrate FunkPay into any web application.
Pass this file to Claude as context when working on integrations.

---

## What is FunkPay

FunkPay is a Bitcoin on-chain payment library. It:
- Derives receive addresses from an **xpub** (BIP84, no private keys)
- Monitors transactions via a **Bitcoin Core node** (your own, no third party)
- Fires callbacks when payment status changes (detected → confirmed)
- Exposes an **embeddable JS widget** (`funkpay.js`)

The demo is live at: **https://btcfunk.com/#support**

---

## Architecture

```
Your website
  └── <div id="funkpay">        ← place this div anywhere
  └── <script src="https://btcfunk.com/pay/funkpay.js"></script>
        └── Shadow DOM injected into #funkpay
              ├── POST /pay/invoices        (create invoice)
              ├── GET  /pay/invoices/:id    (poll status)
              └── FunkPay.on() callbacks → parent page
```

The payment UI runs inside a **Shadow DOM** for CSS isolation — your page styles never leak in, and the widget works on any website. No iframe, no cross-origin restrictions.

Want a modal/popup? Style the div yourself with `position:fixed` — FunkPay doesn't care where the div is.

---

## Embedding funkpay.js

### Minimal

```html
<div id="funkpay" data-server="https://pay.example.com"></div>
<script src="https://btcfunk.com/pay/funkpay.js"></script>
```

`data-server` is required — without it the widget will not render. Replace `https://pay.example.com` with the base URL of your running btcfunkpay backend.

### With options (data attributes)

```html
<div id="funkpay"
     data-server="https://pay.example.com"
     data-currency="EUR"
     data-label="user-42"
     data-theme="auto">
</div>
<script src="https://btcfunk.com/pay/funkpay.js"></script>
```

### With payment callbacks

```html
<div id="funkpay" data-server="https://pay.example.com" data-currency="EUR"></div>
<script src="https://btcfunk.com/pay/funkpay.js"></script>
<script>
  FunkPay.on('detected', function(payment) {
    // Transaction seen in mempool (0-conf) — do not release goods yet
    console.log('in mempool', payment.payment_id);
  });

  FunkPay.on('confirmed', function(payment) {
    // payment.payment_id   — invoice ID
    // payment.received_sat — satoshis received
    // payment.status       — 'confirmed' or 'overpaid'
    activateSubscription(payment.label);
  });

  FunkPay.on('expired', function(payment) {
    console.log('expired', payment.payment_id);
  });
</script>
```

> **Note:** JS callbacks only fire while the user is on the page. For reliable server-side notifications use the [webhook](#webhook).

Callbacks registered before or after the script loads both work — no postMessage needed, the widget calls them directly.

### FunkPay API

| | |
|---|---|
| `FunkPay.on(event, cb)` | Register event callback |

**`data-*` attributes on `#funkpay`:**

| Attribute | Default | Description |
|-----------|---------|-------------|
| `data-server` | **Required** | Base URL of your self-hosted backend (e.g. `https://pay.example.com`). Without this the widget displays a configuration error. |
| `data-currency` | `USD` | Fiat display currency: `USD` `EUR` `GBP` `JPY` `CAD` `CHF` `AUD` |
| `data-amount` | — | Pre-fill amount in satoshis (always satoshis, regardless of `data-currency`) |
| `data-label` | — | Fixed order/user identifier stored with the invoice. If omitted, the widget shows a free "Reference" field for the user to fill in. |
| `data-theme` | `auto` | Color theme: `light`, `dark`, or `auto` (follows system `prefers-color-scheme`) |
| `data-success-url` | `/` | URL the browser navigates to when the user clicks "Done" after payment. Use for post-payment redirect (e.g. `/order-confirmed`). This is a browser-side redirect only — not a webhook. |

**Events:**

| Event | Payload | When |
|-------|---------|------|
| `detected` | `{ payment_id, received_sat, txid, status }` | Transaction seen in mempool (0-conf). Do **not** release goods — use only for optimistic UI updates. |
| `confirmed` | `{ payment_id, received_sat, txid, status }` | Required confirmations reached on-chain. Safe to release goods/services. |
| `expired` | `{ payment_id }` | Invoice expired without payment |

---

## REST API

Base URL: `https://btcfunk.com/pay`

### Create invoice

```
POST /invoices
Content-Type: application/json

{
  "amount_sat": 50000,   // optional — null means "any amount"
  "label": "user-42"    // optional — stored for your reference
}
```

Response:
```json
{
  "payment_id": "7509006e-...",
  "address": "bc1q...",
  "bip21_uri": "bitcoin:bc1q...?amount=0.00050000&label=user-42",
  "amount_sat": 50000,
  "expires_at": "2026-05-03T10:00:00+00:00"
}
```

### Poll invoice status

```
GET /invoices/{payment_id}
```

Response:
```json
{
  "payment_id": "7509006e-...",
  "address": "bc1q...",
  "status": "confirmed",
  "received_sat": 50000,
  "confirmations": 1,
  "txid": "abc123..."
}
```

### List invoices

```
GET /invoices
GET /invoices?status=confirmed
GET /invoices?limit=50&offset=0
```

Response:
```json
[
  {
    "payment_id": "7509006e-...",
    "address": "bc1q...",
    "label": "user-42",
    "amount_sat": 50000,
    "status": "confirmed",
    "received_sat": 50000,
    "confirmations": 1,
    "txid": "abc123...",
    "created_at": "2026-05-03T10:00:00+00:00",
    "confirmed_at": "2026-05-03T10:05:00+00:00"
  }
]
```

`status` filter is optional. `limit` defaults to 100, max 500.

**Status values:**

| Status | Meaning |
|--------|---------|
| `pending` | Waiting for payment |
| `detected` | Transaction in mempool (0 conf) |
| `confirmed` | Required confirmations reached |
| `overpaid` | Confirmed but received more than expected |
| `expired` | Invoice expired without payment |

---

## Webhook

The webhook is the **reliable** way to receive payment notifications server-side — it fires regardless of whether the user is still on the page.

### Configuration

Set in `btcfunkpay.conf`:

```ini
[notifications]
webhook_url = https://your-backend.com/api/payment-webhook
```

Or via environment variable:

```bash
BTCFUNKPAY_WEBHOOK_URL=https://your-backend.com/api/payment-webhook
```

### When it fires

Two POST requests are sent per successful payment:

| Call | `status` | `confirmations` | When |
|------|----------|-----------------|------|
| 1st | `detected` | `0` | Transaction appears in mempool |
| 2nd | `confirmed` | `≥ 1` | Required confirmations reached on-chain |

### Payload

```json
{
  "payment_id":    "7509006e-...",
  "label":         "user-42",
  "status":        "confirmed",
  "received_sat":  50000,
  "txid":          "abc123...",
  "address":       "bc1q...",
  "confirmations": 1
}
```

### Example receiver (FastAPI)

```python
@app.post("/api/payment-webhook")
async def payment_webhook(request: Request):
    data = await request.json()
    payment_id = data["payment_id"]
    status     = data["status"]
    received   = data["received_sat"]

    if status == "detected":
        # Optimistic: show "payment incoming" to the user
        pass

    if status == "confirmed":
        # Safe: release the order / activate the account
        activate_order(payment_id, received)

    return {"ok": True}
```

> **Security note:** the webhook has no signature — anyone who knows the URL can POST to it. Add a secret token in the URL (`/api/payment-webhook?token=...`) or validate the `payment_id` against your own database before acting on it.

---

## Server setup (self-hosted)

### Requirements

- Python 3.11+
- Bitcoin Core node (pruned is fine, txindex not required)
- Linux server with systemd

### Installation

```bash
git clone https://github.com/lucarocchi/btcfunkpay.git
cd btcfunkpay
python3 -m venv venv
source venv/bin/activate
pip install -e ".[demo]"
```

### Configuration

Copy and edit the config file:

```bash
cp btcfunkpay.conf.example btcfunkpay.conf
nano btcfunkpay.conf
```

Minimum required settings:

```ini
[bitcoin]
xpub = xpub6...          # your BIP84 xpub (from Ledger, Coldcard, etc.)
rpc_url = http://user:pass@127.0.0.1:8332
mainnet = true

[payments]
required_confirmations = 1   # 0 = mempool only (instant, less secure)
```

Environment variables override the config file (useful for Docker):

| Env var | Config key |
|---------|-----------|
| `BTCFUNKPAY_XPUB` | `bitcoin.xpub` |
| `BTCFUNKPAY_RPC_URL` | `bitcoin.rpc_url` |
| `BTCFUNKPAY_REQUIRED_CONFIRMATIONS` | `payments.required_confirmations` |
| `BTCFUNKPAY_WEBHOOK_URL` | `notifications.webhook_url` |
| `BTCFUNKPAY_ALLOWED_ORIGINS` | `cors.allowed_origins` |
| `BTCFUNKPAY_ADMIN_USERNAME` | `admin.username` (default: `admin`) |
| `BTCFUNKPAY_ADMIN_PASSWORD` | `admin.password` — required to access `GET /invoices` |
| `BTCFUNKPAY_CONFIG` | path to config file |

### Run

```bash
uvicorn server:app --host 127.0.0.1 --port 8001
```

### Point the widget to your server

Once your server is running, embed the widget with `data-server` pointing to your backend:

```html
<div id="funkpay" data-server="https://pay.example.com" data-currency="EUR"></div>
<script src="https://btcfunk.com/pay/funkpay.js"></script>
```

The widget script stays on `btcfunk.com` — only the API calls go to your server.

### CORS

The server enables CORS by default (`allowed_origins = *`). To restrict to specific domains, set in `btcfunkpay.conf`:

```ini
[cors]
allowed_origins = https://mysite.com,https://shop.mysite.com
```

Or via environment variable:

```bash
export BTCFUNKPAY_ALLOWED_ORIGINS=https://mysite.com
```

### Nginx proxy (serve at /pay/)

```nginx
location /pay/ {
    proxy_pass http://127.0.0.1:8001/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### systemd service

```ini
[Unit]
Description=FunkPay demo
After=network.target bitcoind.service

[Service]
WorkingDirectory=/opt/btcfunkpay
EnvironmentFile=/opt/btcfunkpay/.env
ExecStart=/opt/btcfunkpay/venv/bin/uvicorn server:app \
          --host 127.0.0.1 --port 8001
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Using the Python library directly

```python
from btcfunkpay import PaymentProcessor, PaymentEvent, load_config

cfg = load_config()  # reads btcfunkpay.conf

proc = PaymentProcessor(
    xpub=cfg.xpub,
    rpc_url=cfg.rpc_url,
    required_confirmations=cfg.required_confirmations,
)

@proc.on_payment
def handle(event: PaymentEvent):
    if event.is_first_confirmation:
        print(f"PAID: {event.received_sat} sat — label={event.label}")
        # activate subscription, send email, etc.

proc.setup()   # creates Bitcoin Core watch-only wallet
inv = proc.create_invoice(amount_sat=50_000, label="user-42")
print(inv.bip21_uri)   # bitcoin:bc1q...?amount=0.00050000

proc.start()       # background thread
proc.run_forever() # block until stop()
```

### Inside FastAPI (async)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    proc = PaymentProcessor(xpub=..., rpc_url=...)
    proc.setup()
    app.state.proc = proc
    await proc.astart()   # returns asyncio.Task
    yield
    await proc.astop()

app = FastAPI(lifespan=lifespan)
```

---

## Notes

- **No custody**: funds go directly to your wallet. FunkPay never touches private keys.
- **Pruned node**: historical rescan will fail — only new transactions are monitored. This is expected.
- **required_confirmations=0**: instant detection (mempool), fine for digital goods / subscriptions.
- **Fiat conversion**: uses mempool.space public API, updated on page load.
- **Reorg handling**: if a block is orphaned, confirmed payments revert to `detected` automatically.
- **Invoice expiry**: default 1 hour, configurable. Expired invoices fire the `expired` callback.

# FunkPay — Integration Guide

This document explains how to integrate FunkPay into any web application.
Pass this file to Claude as context when working on integrations.

---

## What is FunkPay

FunkPay is a Bitcoin on-chain payment library. It:
- Derives receive addresses from an **xpub** (BIP84, no private keys)
- Monitors transactions via a **Bitcoin Core node** (your own, no third party)
- Fires callbacks when payment status changes (detected → confirmed)
- Exposes a **payment page** and an **embeddable JS widget** (`funkpay.js`)

The demo is live at: **https://btcfunk.com/pay/**

---

## Architecture

```
Your website
  └── <script src="https://btcfunk.com/pay/funkpay.js">
        └── FunkPay.open() → modal iframe
              └── https://btcfunk.com/pay/   (payment page)
                    ├── POST /invoices        (create invoice)
                    ├── GET  /invoices/:id    (poll status)
                    └── postMessage → parent  (confirmed / expired)
```

---

## Embedding funkpay.js

### Minimal

```html
<script src="https://btcfunk.com/pay/funkpay.js"></script>
<button onclick="FunkPay.open()">Pay with Bitcoin</button>
```

### With amount and callback

```html
<script src="https://btcfunk.com/pay/funkpay.js"></script>

<script>
  // Register callback BEFORE open()
  FunkPay.on('confirmed', function(payment) {
    console.log('Payment confirmed!', payment);
    // payment.payment_id  — invoice ID
    // payment.received_sat — amount received in satoshis
    // payment.status      — 'confirmed' or 'overpaid'
  });

  FunkPay.on('expired', function(payment) {
    console.log('Invoice expired', payment.payment_id);
  });
</script>

<!-- Open with pre-filled amount and a label to identify the user/order -->
<button onclick="FunkPay.open({ amount_sat: 50000, label: 'user-42', currency: 'EUR' })">
  Pay €xx in Bitcoin
</button>
```

### FunkPay API

| Method | Description |
|--------|-------------|
| `FunkPay.open(opts)` | Open the payment modal |
| `FunkPay.close()` | Close the modal programmatically |
| `FunkPay.on(event, cb)` | Register event callback |

**`open(opts)` options:**

| Option | Type | Description |
|--------|------|-------------|
| `amount_sat` | number | Amount in satoshis (pre-fills BTC field) |
| `label` | string | Order or user identifier stored with the invoice |
| `currency` | string | Default fiat currency: `USD`, `EUR`, `GBP`, `JPY`, `CAD`, `CHF`, `AUD` |

**Events:**

| Event | Payload | When |
|-------|---------|------|
| `confirmed` | `{ payment_id, received_sat, status }` | Payment confirmed on-chain |
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

**Status values:**

| Status | Meaning |
|--------|---------|
| `pending` | Waiting for payment |
| `detected` | Transaction in mempool (0 conf) |
| `confirmed` | Required confirmations reached |
| `overpaid` | Confirmed but received more than expected |
| `expired` | Invoice expired without payment |

---

## Server setup (self-hosted)

### Requirements

- Python 3.11+
- Bitcoin Core node (pruned is fine, txindex not required)
- Linux server with systemd

### Installation

```bash
git clone root@178.104.206.139:/opt/btcfunkpay.git
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
| `BTCFUNKPAY_CONFIG` | path to config file |

### Run

```bash
uvicorn examples.fastapi_integration:app --host 127.0.0.1 --port 8001
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
ExecStart=/opt/btcfunkpay/venv/bin/uvicorn examples.fastapi_integration:app \
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

<p align="center">
  <img src="static/logo.png" alt="FunkPay" width="220">
</p>

<p align="center">
  <strong>Bitcoin on-chain payments — self-custodial, no middlemen.</strong><br>
  Your keys. Your coins.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-orange.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Bitcoin-on--chain-f7931a.svg" alt="Bitcoin">
  <img src="https://img.shields.io/badge/no_custody-✓-green.svg" alt="No custody">
</p>

---

## Philosophy

Bitcoin confirmations can take up to an hour. FunkPay doesn't make you wait.

The moment a transaction hits the mempool, the UX unlocks. For most use cases — digital goods, donations, subscriptions — that's enough. Double-spend attacks on small amounts are economically irrational: the cost of executing one far exceeds the value of any typical transaction.

FunkPay gives you two signals, and lets you decide what to do with each:

- **`detected`** (mempool) — transaction is visible on the network. Unlock the UX, start a timed trial, show a thank-you screen.
- **`confirmed`** (N confirmations) — transaction is settled. Ship the physical good, activate the account permanently, fire the webhook.

Never ship an irreversible good before `confirmed`. For everything else, the mempool is your friend.

This isn't a workaround — it's the same logic behind every contactless payment terminal in the world. The merchant accepts a calculated risk because the friction of waiting costs more than the fraud it prevents.

**Live demo → [btcfunk.com/#support](https://btcfunk.com/#support)**

---

## Overview

FunkPay is a Python library for accepting Bitcoin on-chain payments. It derives receive addresses from your **xpub** (no private keys), monitors transactions via your own **Bitcoin Core node**, and fires callbacks when payments arrive.

It also ships an **embeddable JS widget** — drop one `<script>` tag on any page and a payment widget appears inline.

```html
<div id="funkpay" data-server="https://pay.example.com" data-currency="EUR" data-label="user-42"></div>
<script src="https://btcfunk.com/pay/funkpay.js"></script>
<script>
  FunkPay.on('confirmed', (payment) => activateSubscription(payment.label));
</script>
```

> **Note:** the widget includes an "I've paid" button that the user can click at any time, even without sending any amount. It only shows a thank-you screen on the user's side — if no transaction arrives on-chain, no success callback or webhook call will ever be triggered.

---

## Features

- **Self-custodial** — funds go directly to your wallet, FunkPay never touches private keys
- **No third party** — your node, your database, your data
- **BIP84 address derivation** — pure Python stdlib, no external crypto libraries
- **Embeddable widget** — one `<script>` tag, Shadow DOM isolation, works on any website
- **Multi-currency** — fiat display in USD, EUR, GBP, JPY, CAD, CHF, AUD
- **Reorg-safe** — handles chain reorganizations automatically
- **Async + sync** — works standalone or inside FastAPI / asyncio apps
- **SQLite storage** — no external database required

---

## Installation

```bash
pip install btcfunkpay
```

Or from source:

```bash
git clone https://github.com/lucarocchi/btcfunkpay.git
cd btcfunkpay
pip install -e ".[demo]"
```

**Requirements:** Python 3.11+ · Bitcoin Core node (pruned is fine)

---

## Quick start

### 1. Configure

```bash
cp btcfunkpay.conf.example btcfunkpay.conf
```

```ini
[bitcoin]
xpub    = xpub6...          # from Ledger, Coldcard, etc.
rpc_url = http://user:pass@127.0.0.1:8332
mainnet = true

[payments]
required_confirmations = 1  # 0 = mempool only (instant)
min_sat = 1000
```

### 2. Use in Python

```python
from btcfunkpay import PaymentProcessor, PaymentEvent, load_config

cfg = load_config()

proc = PaymentProcessor(
    xpub=cfg.xpub,
    rpc_url=cfg.rpc_url,
    required_confirmations=cfg.required_confirmations,
)

@proc.on_payment
def handle(event: PaymentEvent):
    if event.is_first_confirmation:
        print(f"Paid: {event.received_sat} sat — {event.label}")

proc.setup()
inv = proc.create_invoice(amount_sat=50_000, label="order-123")
print(inv.bip21_uri)  # bitcoin:bc1q...?amount=0.00050000

proc.start()
proc.run_forever()
```

### 3. Or run the terminal monitor

No web server needed — run this script, enter an amount, share the address with your customer, and wait:

```bash
python3 examples/standalone.py
```

```
=== FunkPay — new invoice ===
Amount in satoshis (leave blank for open amount): 50000
Label (customer email, order ID, ...): mario@gmail.com

  Address : bc1q...
  BIP21   : bitcoin:bc1q...?amount=0.00050000&label=mario%40gmail.com
  Expires : 14:32:00

Waiting for payment... (Ctrl+C to cancel)
[mempool] Transaction detected — 50000 sat (txid: abc123...)
Waiting for confirmation...
[confirmed] Payment confirmed — 50000 sat  label=mario@gmail.com
```

### 4. Or run the web widget server

```bash
uvicorn server:app --port 8001
# then embed the widget on your page pointing to http://localhost:8001
```

---

## Embed on your website

> **The widget alone is not enough.** `funkpay.js` is a UI — it needs a backend to derive Bitcoin addresses, monitor the blockchain, and fire payment callbacks. You must run your own backend (see [INTEGRATION.md](INTEGRATION.md)) and set `data-server` to point to it. Without `data-server` the widget displays a configuration error.

```html
<!-- 1. Place the div -->
<div id="funkpay" data-server="https://pay.example.com" data-currency="EUR"></div>

<!-- 2. Load the widget — auto-mounts into the div above -->
<script src="https://btcfunk.com/pay/funkpay.js"></script>

<!-- 3. Handle events (optional) -->
<script>
  FunkPay.on('confirmed', function(payment) {
    // payment.payment_id, payment.received_sat, payment.status
    console.log('Confirmed!', payment);
  });
</script>
```

`data-*` attributes on `#funkpay`:

| Attribute | Description |
|-----------|-------------|
| `data-server` | **Required.** Base URL of your self-hosted backend (e.g. `https://pay.example.com`). Without this the widget will not render. |
| `data-currency` | Fiat currency: `USD` `EUR` `GBP` `JPY` `CAD` `CHF` `AUD` |
| `data-amount` | Pre-fill amount in satoshis (always satoshis, regardless of `data-currency`) |
| `data-label` | Order / user identifier |
| `data-theme` | `light` \| `dark` \| `auto` (default: auto-detect) |

> **CORS:** the widget runs on your domain and calls your backend — your server must allow cross-origin requests. CORS is enabled by default (`allowed_origins = *`). To restrict it, set `allowed_origins` in `btcfunkpay.conf` or via `BTCFUNKPAY_ALLOWED_ORIGINS`.

---

## Payment status

| Status | Meaning |
|--------|---------|
| `pending` | Waiting for payment |
| `detected` | Transaction in mempool |
| `confirmed` | Required confirmations reached |
| `overpaid` | Confirmed, received more than expected |
| `expired` | Invoice expired without payment |

---

## Full integration guide

See **[INTEGRATION.md](INTEGRATION.md)** for:
- Complete REST API reference
- Nginx + systemd setup
- FastAPI async integration
- Self-hosting instructions

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.

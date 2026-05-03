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

FunkPay is a Python library for accepting Bitcoin on-chain payments. It derives receive addresses from your **xpub** (no private keys), monitors transactions via your own **Bitcoin Core node**, and fires callbacks when payments arrive.

It also ships an **embeddable JS widget** — drop one `<script>` tag on any page and a payment modal appears, like Stripe but Bitcoin.

```html
<script src="https://btcfunk.com/pay/funkpay.js"></script>
<script>
  FunkPay.on('confirmed', (payment) => activateSubscription(payment.label));
  FunkPay.open({ amount_sat: 50000, label: 'user-42', currency: 'EUR' });
</script>
```

**Live demo → [btcfunk.com/pay](https://btcfunk.com/pay/)**

---

## Features

- **Self-custodial** — funds go directly to your wallet, FunkPay never touches private keys
- **No third party** — your node, your database, your data
- **BIP84 address derivation** — pure Python stdlib, no external crypto libraries
- **Embeddable widget** — one `<script>` tag, works on any website
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

### 3. Or run the demo server

```bash
uvicorn examples.fastapi_integration:app --port 8001
# open http://localhost:8001
```

---

## Embed on your website

```html
<!-- 1. Load the widget -->
<script src="https://btcfunk.com/pay/funkpay.js"></script>

<!-- 2. Open on button click -->
<button onclick="FunkPay.open()">Pay with Bitcoin</button>

<!-- 3. Handle events -->
<script>
  FunkPay.on('confirmed', function(payment) {
    // payment.payment_id, payment.received_sat, payment.status
    console.log('Confirmed!', payment);
  });
</script>
```

`FunkPay.open(opts)` options:

| Option | Type | Description |
|--------|------|-------------|
| `amount_sat` | number | Pre-fill amount in satoshis |
| `label` | string | Order / user identifier |
| `currency` | string | Fiat currency: `USD` `EUR` `GBP` `JPY` `CAD` `CHF` `AUD` |

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

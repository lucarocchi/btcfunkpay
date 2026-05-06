# btcfunkpay — Claude Code Context

## Cos'è questo progetto

**btcfunkpay** è una libreria Python + server FastAPI per accettare pagamenti Bitcoin on-chain.

- Deriva indirizzi da **xpub** (BIP84, nessuna chiave privata sul server)
- Monitora transazioni via **Bitcoin Core RPC** (nodo proprio, nessun third party)
- Espone **REST API** e widget JS embeddable (`funkpay.js`)
- Invia webhook quando un pagamento è `detected` e `confirmed`

È il componente **lato merchant** dell'ecosistema FunkPay.

---

## Ecosistema FunkPay — 3 progetti

| Repo | Ruolo | Path locale |
|------|-------|-------------|
| `btcfunkpay` (questo) | Merchant payment server | `../btcfunkpay` |
| `funkpayai` | Agent wallet + MCP server (Electron) | `../funkpayai` |
| `btcfunk` | Website btcfunk.com (analytics + serve funkpay.js) | `../btcfunk` |

### Flusso completo
```
Claude Code
  └─[MCP]→ funkpayai → firma tx → broadcast via bitcoind
                                        │
                                   Bitcoin network
                                        │
              btcfunkpay (questo) ←────┘ rileva on-chain
                └── webhook → attiva ordine → notifica agent
```

---

## Stack tecnico

- **Python 3.11+** + FastAPI + uvicorn
- **SQLite** (via `_db.py`) — storage invoice
- **Bitcoin Core RPC** (`_rpc.py`) — monitoring transazioni
- **BIP32/BIP84** (`_bip32.py`) — derivazione indirizzi da xpub
- **funkpay.js** (`static/funkpay.js`) — widget embeddable con Shadow DOM

## Struttura

```
btcfunkpay/
  server.py              — FastAPI app: API REST + serve widget
  btcfunkpay/
    __init__.py          — exports pubblici: PaymentProcessor, PaymentEvent, load_config
    _config.py           — carica btcfunkpay.conf + env vars
    _models.py           — Invoice, PaymentEvent, PaymentStatus
    _db.py               — SQLite CRUD invoice
    _monitor.py          — polling Bitcoin Core per nuove tx
    _rpc.py              — client JSON-RPC Bitcoin Core
    _bip32.py            — derivazione BIP84 da xpub
    processor.py         — PaymentProcessor: orchestration
  static/
    funkpay.js           — widget embeddabile (Shadow DOM)
  btcfunkpay.conf.example
```

## Comandi

```bash
pip install -e .
uvicorn server:app --reload --host 127.0.0.1 --port 8001
```

Config minima (`btcfunkpay.conf`):
```ini
[bitcoin]
xpub = xpub6...
rpc_url = http://user:pass@127.0.0.1:8332
mainnet = true
[payments]
required_confirmations = 1
```

## REST API

```
POST /pay/invoices        { amount_sat?, label? }
GET  /pay/invoices/:id
GET  /pay/invoices?status=confirmed&limit=50
```

**Invoice status:** `pending → detected → confirmed | overpaid | expired`

**Webhook** (POST a `webhook_url` configurato):
```json
{ "payment_id": "...", "label": "...", "status": "confirmed",
  "received_sat": 50000, "txid": "...", "confirmations": 1 }
```

## Modelli chiave (_models.py)

```python
class PaymentStatus(str, Enum):
    PENDING = "pending" | DETECTED = "detected" | CONFIRMED = "confirmed"
    EXPIRED = "expired" | OVERPAID = "overpaid"

@dataclass
class Invoice:
    payment_id, address, xpub_index, amount_sat, label, status,
    created_at, expires_at, txid, received_sat, confirmations, confirmed_at

@dataclass
class PaymentEvent:
    payment_id, address, txid, amount_sat, received_sat, confirmations,
    status, label, created_at, confirmed_at,
    is_first_detection, is_first_confirmation
```

## Uso come libreria Python

```python
from btcfunkpay import PaymentProcessor, PaymentEvent, load_config

proc = PaymentProcessor(xpub=..., rpc_url=...)
proc.setup()

@proc.on_payment
def handle(event: PaymentEvent):
    if event.is_first_confirmation:
        activate_order(event.label, event.received_sat)

inv = proc.create_invoice(amount_sat=50_000, label="order-42")
proc.run_forever()
```

## Embedding widget

```html
<div id="funkpay" data-server="https://pay.example.com" data-currency="USD"></div>
<script src="https://btcfunk.com/pay/funkpay.js"></script>
<script>
  FunkPay.on('confirmed', (p) => activateOrder(p.label))
</script>
```

## Stato corrente (2026-05-06)

- ✅ Libreria funzionante, testata
- ✅ Server FastAPI con REST API + widget
- ✅ Demo live su btcfunk.com/#support
- 🔲 Estendere Invoice per supportare `shipping` e `billing` metadata (per beni fisici acquistati da agent via funkpayai)
- 🔲 Notifica agent dopo conferma pagamento (callback URL o polling)

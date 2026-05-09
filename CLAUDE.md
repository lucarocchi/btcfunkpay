# btcfunkpay — Claude Code Context

## Cos'è questo progetto

**btcfunkpay** è una libreria Python + server FastAPI per accettare pagamenti Bitcoin on-chain.

- Deriva indirizzi da **xpub/tpub** (BIP84, nessuna chiave privata sul server)
- Monitora transazioni via **Bitcoin Core RPC** (nodo proprio, nessun third party)
- Espone **REST API** e widget JS embeddable (`funkpay.js`)
- Invia webhook quando un pagamento è `detected` e `confirmed`
- Supporta **acquisti per SKU** — risolve il prezzo chiamando il catalog adapter del merchant

È il componente **lato merchant** dell'ecosistema FunkPay.

---

## Ecosistema FunkPay — 3 progetti

| Repo | Ruolo | Path locale |
|------|-------|-------------|
| `btcfunkpay` (questo) | Merchant payment engine | `../btcfunkpay` |
| `funkpayai` | Agent wallet + MCP server (Electron) | `../funkpayai` |
| `btcfunk` | Website btcfunk.com (analytics + serve funkpay.js) | `../btcfunk` |

### Flusso acquisto via SKU

```
AI Agent
  │  create_invoice(merchant_url, sku="FUNK-002")
  ▼
btcfunkpay (server.py)
  │  GET {catalog_url}/funkpay/product?sku=FUNK-002   ← contratto standard
  ▼
Merchant catalog adapter (shop.py)
  │  legge products.sqlite → { price_sat: 50000, name: "..." }
  ▼
btcfunkpay crea invoice con amount_sat risolto
  │
  ▼
Agent: send_payment → wait_for_payment → ricevuta
```

### Flusso pagamento completo

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
- **BIP32/BIP84** (`_bip32.py`) — derivazione indirizzi da xpub/tpub (mainnet + testnet)
- **funkpay.js** (`static/funkpay.js`) — widget embeddable con Shadow DOM
- **python-multipart** — upload immagini prodotti (shop.py)

## Struttura

```
btcfunkpay/
  server.py              — motore pagamento: API REST + widget + SKU resolver
  shop.py                — layer merchant shop.funkpay.dev: catalogo prodotti + admin UI
  btcfunkpay/
    __init__.py          — exports pubblici: PaymentProcessor, PaymentEvent, load_config
    _config.py           — carica btcfunkpay.conf + env vars (incl. catalog_url)
    _models.py           — Invoice, PaymentEvent, PaymentStatus
    _db.py               — SQLite CRUD invoice
    _monitor.py          — polling Bitcoin Core per nuove tx
    _rpc.py              — client JSON-RPC Bitcoin Core
    _bip32.py            — derivazione BIP84 da xpub/tpub/zpub/vpub
    processor.py         — PaymentProcessor: orchestration
  static/
    funkpay.js           — widget embeddabile (Shadow DOM)
  btcfunkpay.conf.example
```

## Comandi

```bash
pip install -e .
# motore pagamento
uvicorn server:app --host 127.0.0.1 --port 8001

# catalog merchant (shop.funkpay.dev)
SHOP_DB_PATH=products.sqlite SHOP_ADMIN_PASS=secret \
uvicorn shop:app --host 127.0.0.1 --port 8003
```

Config minima (`btcfunkpay.conf`):
```ini
[bitcoin]
xpub = xpub6...        # oppure tpub per testnet
rpc_url = http://user:pass@127.0.0.1:8332
mainnet = true

[payments]
required_confirmations = 1

[server]
catalog_url = https://shop.example.com  # merchant catalog adapter (opzionale)
```

---

## REST API — motore pagamento (server.py)

```
POST /invoices        { amount_sat?, label?, sku?, shipping?, billing?, amount_fiat?, currency? }
GET  /invoices/:id
GET  /invoices?status=confirmed&limit=50   (admin auth)
POST /invoices        { sku: "FUNK-002" }  → risolve prezzo da catalog_url
```

**Invoice status:** `pending → detected → confirmed | overpaid | expired`

**Fiscal fields:** `amount_fiat`, `currency`, `exchange_rate` — salvati sull'invoice per contabilità.

**Webhook** (POST a `webhook_url` configurato):
```json
{ "payment_id": "...", "label": "...", "status": "confirmed",
  "received_sat": 50000, "txid": "...", "confirmations": 1 }
```

---

## Contratto standard FunkPay — catalog adapter

Qualsiasi merchant che vuole supportare acquisti via SKU deve implementare:

```
GET {catalog_url}/funkpay/product?sku={SKU}
→ { sku, name, description, price_sat, type, image, active }
```

`server.py` chiama questo endpoint quando riceve `POST /invoices { sku: "..." }`.
Il merchant implementa il suo adapter come vuole (DB, CMS, JSON…) — `shop.py` è
l'implementazione per shop.funkpay.dev.

---

## REST API — catalog merchant (shop.py)

```
GET  /products                          → lista prodotti attivi (pubblico)
GET  /products/{sku}                    → dettaglio prodotto (pubblico)
GET  /funkpay/product?sku={sku}         → contratto standard FunkPay
GET  /admin/products                    → pagina admin CRUD (auth)
POST /admin/products                    → crea prodotto (auth)
POST /admin/products/{sku}              → aggiorna prodotto (auth)
POST /admin/products/{sku}/delete       → elimina prodotto (auth)
```

**Products SQLite schema:**
```sql
products (sku TEXT PK, name, description, price_sat, type, image, active, created_at)
```

**Variabili d'ambiente shop.py:**
```
SHOP_DB_PATH       path products.sqlite
SHOP_IMAGES_DIR    path cartella immagini
SHOP_STATIC_DIR    path cartella static
SHOP_ADMIN_USER    username admin (default: admin)
SHOP_ADMIN_PASS    password admin
```

---

## Modelli chiave (_models.py)

```python
class PaymentStatus(str, Enum):
    PENDING | DETECTED | CONFIRMED | EXPIRED | OVERPAID

@dataclass
class Invoice:
    payment_id, address, xpub_index, amount_sat, label, status,
    created_at, expires_at, txid, received_sat, confirmations, confirmed_at,
    shipping, billing, amount_fiat, currency, exchange_rate
```

---

## VPS (shop.funkpay.dev — testnet)

| Servizio | Path | Porta |
|---------|------|-------|
| btcfunkpay-testnet | `/opt/btcfunkpay-testnet/` | 8002 |
| btcfunkpay-shop | `/opt/btcfunkpay-testnet/` | 8003 |

**nginx routing shop.funkpay.dev:**
- `/products`, `/admin/products`, `/funkpay`, `/static/product-images` → 8003 (shop.py)
- tutto il resto → 8002 (server.py)

**btcfunkpay.conf testnet:**
```ini
catalog_url = https://shop.funkpay.dev
```

---

## Stato corrente (2026-05-09)

- ✅ Libreria funzionante, testata
- ✅ Server FastAPI con REST API + widget
- ✅ Demo live su btcfunk.com/#support (mainnet)
- ✅ Demo live su shop.funkpay.dev (testnet)
- ✅ Invoice con `shipping`, `billing`, `amount_fiat`, `currency`, `exchange_rate`
- ✅ Acquisti via SKU — contratto `GET /funkpay/product?sku=`
- ✅ shop.py — catalog adapter con SQLite + admin CRUD + upload immagini
- ✅ Pagina admin `/invoice` (invoice list) e `/admin/products` (catalog)
- ✅ xpub + tpub (mainnet + testnet) supportati in _bip32.py
- 🔲 MCP tool `list_products` in funkpayai
- 🔲 MCP tool `create_invoice` con parametro `sku`

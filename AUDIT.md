# BTCFunkPay — Security & Quality Audit

**Data audit originale:** 2026-05-03  
**Ultimo aggiornamento:** 2026-05-04  
**Revisore:** Claude Sonnet 4.6 (audit commissionato da Luca Rocchi)  
**Scope:** tutti i file del progetto — `server.py`, `btcfunkpay/`, `static/funkpay.js`, `examples/`, `btcfunkpay.conf.example`, `pyproject.toml`, `README.md`, `INTEGRATION.md`

---

## Stato complessivo

| Categoria | Conteggio |
|-----------|-----------|
| ✅ Risolti | 20 |
| ⚠️ Rischio accettato (motivato) | 3 |
| 🔲 Aperti / da fare | 3 |

---

## ✅ Finding risolti

### F1 — Zero autenticazione su GET /invoices
**Severità originale:** BLOCCANTE  
**Risolto in:** commit `8ff1df5` (2026-05-04)

`GET /invoices` protetto con HTTP Basic Auth tramite FastAPI `HTTPBasic`. Username e password configurabili via env `BTCFUNKPAY_ADMIN_USERNAME` / `BTCFUNKPAY_ADMIN_PASSWORD` o sezione `[admin]` nel config file. Usa `secrets.compare_digest` per prevenire timing attacks. Restituisce 503 se la password non è configurata, 401 con header `WWW-Authenticate: Basic` in caso di credenziali errate.

Anche `btcfunk.com/invoices` (la pagina HTML admin) è protetta con le stesse credenziali — il browser mostra il popup di login nativo.

`POST /invoices` e `GET /invoices/{id}` restano pubblici per design (il widget ne ha bisogno).

---

### F2 — Script QR caricato da CDN senza SRI
**Severità originale:** BLOCCANTE  
**Risolto in:** commit `286503b` (2026-05-04)

`qrcode.min.js` rimosso dal CDN jsDelivr e copiato in `static/qrcode.min.js`. Il widget lo carica ora via `_base + '/static/qrcode.min.js'` dallo stesso server che serve `funkpay.js`. Nessuna dipendenza da CDN di terze parti.

---

### F3 — CORS wildcard hardcoded, configurazione ignorata
**Severità originale:** BLOCCANTE  
**Risolto in:** commit `286503b` (2026-05-04)

`server.py` ora legge `cfg.allowed_origins` e costruisce la lista di origini consentite:
```python
_origins = [o.strip() for o in cfg.allowed_origins.split(",") if o.strip()] or ["*"]
```
Configurabile via `BTCFUNKPAY_ALLOWED_ORIGINS` o `[cors] allowed_origins` nel config file.

---

### F4 — Conversione BTC→satoshi con virgola mobile
**Severità originale:** CRITICO  
**Risolto in:** sessione precedente

Sostituita la conversione `round(tx["amount"] * 1e8)` con `Decimal`:
```python
from decimal import Decimal, ROUND_DOWN
amount_sat = int((Decimal(str(raw)) * Decimal("1e8")).to_integral_value(rounding=ROUND_DOWN))
```

---

### F5 — SQL injection potenziale in `update_payment`
**Severità originale:** CRITICO  
**Risolto in:** sessione precedente

Aggiunta whitelist esplicita in `_db.py`:
```python
_ALLOWED_UPDATE_FIELDS = frozenset({
    "txid", "received_sat", "confirmations", "status", "confirmed_at",
})
```
Il metodo lancia `ValueError` se viene passato un campo non in whitelist.

---

### F6 — GET /invoices espone l'intero database
**Severità originale:** CRITICO  
**Risolto tramite:** F1 (Basic Auth)

Il finding era la conseguenza diretta dell'assenza di autenticazione. Risolto con la Basic Auth di F1.

---

### F8 — SSRF via webhook_url non validata
**Severità originale:** CRITICO  
**Risolto in:** sessione precedente

Aggiunta funzione `_safe_webhook_url()` in `server.py` che blocca:
- Schemi non HTTP/HTTPS
- Hostname localhost / 127.0.0.1 / ::1 / 0.0.0.0
- Range link-local 169.254.x.x
- Range privati 10.x.x.x e 192.168.x.x

Il webhook viene inviato solo se la URL passa la validazione.

---

### F10 — Nessuna validazione su `amount_sat` e `label`
**Severità originale:** GRAVE  
**Risolto in:** commit `286503b` (2026-05-04)

```python
class InvoiceRequest(BaseModel):
    amount_sat: int | None = Field(None, ge=1000, le=2_100_000_000_000_000)
    label: str | None = Field(None, max_length=256)
```

---

### F11 — `status` filter e query params non validati
**Severità originale:** GRAVE  
**Risolto in:** commit `286503b` (2026-05-04)

```python
status: str | None = Query(None, pattern="^(pending|detected|confirmed|expired|overpaid)$"),
limit: int = Query(100, ge=1, le=500),
offset: int = Query(0, ge=0),
```

---

### F12 — Credenziali RPC in chiaro nei traceback
**Severità originale:** GRAVE  
**Risolto in:** commit `286503b` (2026-05-04)

Aggiunta funzione `_redact_url()` in `_rpc.py` che rimuove `user:password` dall'URL prima che compaia in eccezioni rilanciate. `self._safe_url` viene usata al posto di `self._url` nei messaggi di errore.

---

### F13 — Dati server riflessi nel DOM senza whitelist
**Severità originale:** GRAVE  
**Risolto in:** commit `286503b` (2026-05-04)

Prima di scrivere in `className`, il valore viene validato contro una whitelist:
```javascript
var _VALID_STATUSES = {pending:1, detected:1, confirmed:1, expired:1, overpaid:1};
var safeStatus = _VALID_STATUSES[data.status] ? data.status : 'pending';
row.className = 'status-row status-' + safeStatus;
```

---

### F14 — `window.location.href = '/'` hardcoded
**Severità originale:** GRAVE  
**Risolto in:** commit `286503b` (2026-05-04)

Il pulsante "Done" ora rispetta il nuovo attributo `data-success-url`. La destinazione è validata (deve essere path `/...` o URL `http(s)://...`):
```javascript
var dest = opts.successUrl || '/';
if (/^https?:\/\//.test(dest) || dest.startsWith('/')) {
    window.location.href = dest;
}
```

---

### F17 — `asyncio.get_event_loop()` deprecato in Python 3.10+
**Severità originale:** MEDIO  
**Risolto in:** commit `286503b` (2026-05-04)

Tutte le occorrenze di `asyncio.get_event_loop().run_in_executor(...)` sostituite con `asyncio.get_running_loop().run_in_executor(...)`.

---

### F18 — Label utente loggate in chiaro
**Severità originale:** MEDIO  
**Risolto in:** commit `286503b` (2026-05-04)

Rimosso `label={event.label}` dal log INFO. Il payment ID e lo status sono sufficienti per il tracciamento operativo.

---

### F20 — `alphabet.index(c)` lancia ValueError generica
**Severità originale:** MEDIO  
**Risolto in:** commit `286503b` (2026-05-04)

Sostituito `alphabet.index(c)` con `alphabet.find(c)` e check esplicito:
```python
idx = alphabet.find(c)
if idx < 0:
    raise ValueError(f"Invalid Base58 character: {c!r}")
```

---

### F21 — FastAPI espone OpenAPI schema in produzione
**Severità originale:** BASSO  
**Risolto in:** commit `286503b` (2026-05-04)

```python
app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
```

---

### F22 — Widget chiama `confirmed` callback su `detected` (0 conf)
**Severità originale:** BASSO  
**Risolto in:** commit `c72f641` (2026-05-04)

Separati i due stati con schermate e comportamenti distinti:

| Status | Schermata | Polling | Callback |
|--------|-----------|---------|----------|
| `detected` | "Payment detected! Waiting for confirmation..." | continua | `FunkPay.on('detected', ...)` |
| `confirmed` / `overpaid` | "Payment confirmed!" | si ferma | `FunkPay.on('confirmed', ...)` |

Webhook già corretto: il server invia due POST separati — uno su `is_first_detection` e uno su `is_first_confirmation` — così il backend del merchant riceve entrambi gli eventi indipendentemente dal browser dell'utente.

---

### F24 — `tx["amount"]` non verificato come tipo numerico
**Severità originale:** BASSO  
**Risolto insieme a F4**

Il refactoring per F4 ha aggiunto il check esplicito:
```python
raw = tx.get("amount")
if raw is None:
    log.warning("tx %s: amount mancante, skip", tx.get("txid"))
    continue
```

---

### F25 — `httpx` dipendenza implicita, `requests` senza pin
**Severità originale:** BASSO  
**Risolto in:** commit `286503b` (2026-05-04)

```toml
dependencies = ["requests>=2.28,<3", "httpx>=0.27,<1", "fastapi>=0.111,<1", "uvicorn[standard]>=0.29,<1"]
```

---

## ⚠️ Rischio accettato

### F7 — Replace-By-Fee (RBF) non gestito
**Severità originale:** CRITICO  
**Decisione:** rischio accettato per il caso d'uso attuale

**Scenario di attacco:** un mittente invia una tx verso l'indirizzo monitorato (`detected`), poi la sostituisce con una nuova tx RBF verso un indirizzo diverso (double-spend). Il monitor non rileva la sparizione della tx originale — l'invoice rimane bloccata in `detected` fino alla scadenza.

**Perché è accettabile:**
1. F22 è risolto: il widget non chiama più `callbacks.confirmed` su `detected`. Chi segue le best practice (agisce solo su `confirmed`) non è vulnerabile.
2. Il webhook distingue `detected` e `confirmed` — il backend del merchant deve rilasciare beni solo su `confirmed`.
3. L'expiry (default 3600s) gestisce l'invoice bloccata: dopo la scadenza il webhook notifica `expired`.
4. Per le donazioni su btcfunk.com il mittente non ha incentivo economico al double-spend.

**Fix necessario se:** si implementa fulfillment automatico su `detected` (beni digitali ad alta velocità). In quel caso aggiungere un check per ogni invoice `detected` ogni poll cycle: `gettransaction(inv.txid)` → se risponde con codice -5 (not found), la tx è sparita → rimettere l'invoice a `pending`.

---

### F19 — Reorg handling incompleto
**Severità originale:** MEDIO  
**Decisione:** rischio accettato per il caso d'uso attuale

Il monitor gestisce i `removed[]` di `listsinceblock` (reorg che riportano `CONFIRMED → DETECTED`), ma non il caso in cui una tx `DETECTED` sparisca per una reorg profonda. In pratica, una reorg che invalida transazioni con 0 conferme è un evento rarissimo sulla mainnet Bitcoin.

Accettabile per una singola istanza che processa pagamenti non critici. Se il sistema gestisse volumi elevati o pagamenti ad alto valore, si dovrebbe aggiungere il controllo delle conferme in decrescita per transazioni in stato `DETECTED`.

---

### F23 — Credenziali RPC in URL (pattern http://user:pass@host)
**Severità originale:** BASSO  
**Decisione:** rischio residuo accettato, parzialmente mitigato da F12

**Situazione attuale:** le credenziali RPC sono nella URL in chiaro nel file `.env` / config. F12 ha eliminato la fuoriuscita nei log e nei traceback Python.

**Perché è accettabile:** Bitcoin Core RPC ascolta solo su `127.0.0.1`. Per sfruttare le credenziali serve già accesso locale root al server — a quel punto il file `.env` è comunque leggibile in qualsiasi formato. Separare user/pass in tre variabili distinte non riduce la superficie di attacco reale.

**Alternativa non implementata:** `BTCFUNKPAY_RPC_USER` + `BTCFUNKPAY_RPC_PASSWORD` separati, con `requests.auth.HTTPBasicAuth`. Migliore ergonomia, stessa sicurezza effettiva.

---

## 🔲 Aperti — da fare

### F9 — Race condition tra `get_next_index` e `create_payment`
**Severità originale:** GRAVE  
**Stato:** non corretto

**Problema:** `get_next_index` usa `BEGIN IMMEDIATE` per incrementare l'indice in modo atomico, ma `create_payment` avviene subito dopo in una transazione separata. Con più worker uvicorn (`--workers N`) ogni processo ha la propria connessione SQLite: il lock della prima transazione non protegge la seconda.

**Rischio concreto:** due invoice create quasi simultaneamente potrebbero ricevere lo stesso `xpub_index` → stesso indirizzo Bitcoin → ambiguità su quale cliente ha pagato.

**Impatto attuale:** basso — il server gira con un singolo worker. Il GIL Python protegge il caso single-process.

**Fix:** rendere index-increment + INSERT un'unica transazione `BEGIN IMMEDIATE ... COMMIT` in `create_payment`, eliminando `get_next_index` come metodo separato.

---

### F15 — xpub exposure indiretta nei log di setup
**Severità originale:** MEDIO  
**Stato:** non corretto

Durante il setup del wallet (`processor.py`), il descrittore BIP84 che contiene la xpub completa viene costruito come stringa e passato a `importdescriptors`. Se il logger `requests` o `urllib3` è in livello DEBUG, la richiesta RPC completa — inclusa la xpub — compare nei log.

La xpub non è una chiave privata ma permette di derivare tutti gli indirizzi presenti e futuri del wallet, abilitando chain analysis completa.

**Fix:** assicurarsi che `logging.getLogger("urllib3").setLevel(logging.WARNING)` e `logging.getLogger("requests").setLevel(logging.WARNING)` in produzione. Non loggare il descrittore completo.

---

### F16 — Nessun rate limiting su POST /invoices
**Severità originale:** MEDIO  
**Stato:** non corretto

`POST /invoices` è pubblico e crea un record SQLite + incrementa `next_index` + chiama Bitcoin Core RPC ad ogni richiesta. Un attaccante può:
- Esaurire lo spazio disco con invoice spazzatura
- Consumare indirizzi xpub (il range di descriptor default è 1000 indirizzi)
- Sovraccaricare Bitcoin Core RPC

**Fix:** aggiungere `slowapi` (già usato in btcfunk):
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/invoices")
@limiter.limit("10/minute")
def create_invoice(request: Request, req: InvoiceRequest): ...
```

---

## Note architetturali

Il progetto ha un design concettualmente corretto: nessuna custodia di chiavi private, derivazione BIP84 pura, SQLite locale, Shadow DOM per CSS isolation. I problemi trovati erano tipici di un progetto in fase alpha esposto in produzione.

I tre finding BLOCCANTI originali (auth assente, CDN senza SRI, CORS ignorato) sono tutti risolti. I due finding CRITICI Bitcoin (floating point sat, callback confirmed su detected) sono risolti. Il progetto è ora deployabile in produzione per il caso d'uso attuale (donazioni, pagamenti singoli non ad alto volume).

Le tre voci aperte (F9 race condition, F15 xpub in log, F16 rate limiting) diventano prioritarie se il volume di richieste cresce o se si passa a un deployment multi-worker.

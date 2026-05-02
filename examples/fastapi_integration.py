"""
FastAPI integration example with demo UI.

Usage:
  pip install fastapi uvicorn
  uvicorn examples.fastapi_integration:app --reload
  open http://localhost:8000
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from btcfunkpay import PaymentProcessor, PaymentEvent, PaymentStatus

import os

XPUB = os.environ["BTCFUNKPAY_XPUB"]
RPC_URL = os.environ["BTCFUNKPAY_RPC_URL"]

DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>btcfunkpay — demo</title>
  <script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f5f5;
      color: #111;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }

    .card {
      background: #fff;
      border: 1px solid #e0e0e0;
      border-radius: 12px;
      padding: 40px;
      width: 100%;
      max-width: 320px;
    }

    h1 {
      font-size: 18px;
      font-weight: 600;
      letter-spacing: -0.3px;
      margin-bottom: 4px;
    }

    .subtitle {
      font-size: 13px;
      color: #888;
      margin-bottom: 32px;
    }

    .field-wrap {
      position: relative;
      margin-bottom: 12px;
    }

    .field-icon {
      position: absolute;
      left: 12px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 15px;
      font-weight: 700;
      pointer-events: none;
      line-height: 1;
    }

    .field-icon.btc { color: #f7931a; }
    .field-icon.usd { color: #22a55a; }

    input {
      width: 100%;
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 10px 12px 10px 32px;
      font-size: 14px;
      color: #111;
      outline: none;
      transition: border-color 0.15s;
    }
    input:focus { border-color: #f7931a; }
    input[type=number]::-webkit-inner-spin-button,
    input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }

    .field-sep {
      text-align: center;
      font-size: 16px;
      color: #ccc;
      margin: 2px 0 10px;
      line-height: 1;
    }

    button {
      width: 100%;
      background: #f7931a;
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 11px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
    }
    button:hover { background: #e8840f; }
    button:disabled { background: #ccc; cursor: default; }

    /* ---- invoice panel ---- */
    #invoice { display: none; margin-top: 32px; }

    .divider {
      border: none;
      border-top: 1px solid #eee;
      margin-bottom: 28px;
    }

    .qr-wrap {
      display: flex;
      justify-content: center;
      margin-bottom: 24px;
    }

    #qrcode canvas, #qrcode img { border-radius: 8px; }

    .address-box {
      background: #f9f9f9;
      border: 1px solid #eee;
      border-radius: 8px;
      padding: 12px 14px;
      font-family: monospace;
      font-size: 12px;
      word-break: break-all;
      color: #333;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .address-box span { flex: 1; }

    .copy-btn {
      background: none;
      border: 1px solid #ddd;
      color: #555;
      border-radius: 6px;
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 500;
      cursor: pointer;
      width: auto;
      white-space: nowrap;
      transition: border-color 0.15s, color 0.15s;
    }
    .copy-btn:hover { border-color: #f7931a; color: #f7931a; background: none; }

    .meta-row {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: #888;
      margin-bottom: 24px;
    }

    /* ---- status badge ---- */
    .status-row {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 14px;
      border-radius: 8px;
      border: 1px solid #eee;
      font-size: 13px;
      font-weight: 500;
    }

    .dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }

    .status-pending   { border-color: #eee; color: #888; }
    .status-pending .dot { background: #ccc; }

    .status-detected  { border-color: #ffe0a0; background: #fff8ee; color: #b06000; }
    .status-detected .dot { background: #f7931a; animation: pulse 1.2s infinite; }

    .status-confirmed { border-color: #b8ebc8; background: #f0fbf4; color: #1a7a3a; }
    .status-confirmed .dot { background: #22c55e; }

    .status-expired   { border-color: #fdd; background: #fff5f5; color: #b00; }
    .status-expired .dot { background: #ef4444; }

    .status-overpaid  { border-color: #b8ebc8; background: #f0fbf4; color: #1a7a3a; }
    .status-overpaid .dot { background: #22c55e; }

    .txid {
      font-size: 11px;
      font-family: monospace;
      color: #999;
      margin-top: 8px;
      word-break: break-all;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.35; }
    }

    .new-btn {
      margin-top: 20px;
      background: none;
      border: 1px solid #ddd;
      color: #555;
      border-radius: 8px;
      padding: 9px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      width: 100%;
      transition: border-color 0.15s;
    }
    .new-btn:hover { border-color: #f7931a; color: #f7931a; background: none; }
  </style>
</head>
<body>
<div class="card">
  <h1>BTCFunk Payment</h1>
  <p class="subtitle">Direct to wallet.</p>

  <form id="form">
    <div class="field-wrap">
      <span class="field-icon btc">₿</span>
      <input id="amount-sat" type="number" placeholder="satoshis" min="1">
    </div>
    <div class="field-sep">⇅</div>
    <div class="field-wrap">
      <span class="field-icon usd">$</span>
      <input id="amount-usd" type="number" placeholder="USD" min="0" step="0.01">
    </div>

    <button type="submit" id="submit-btn">Pay</button>
  </form>

  <div id="invoice">
    <hr class="divider">

    <div class="qr-wrap">
      <div id="qrcode"></div>
    </div>

    <div class="address-box">
      <span id="address-text"></span>
      <button class="copy-btn" onclick="copyAddress()">Copy</button>
    </div>

    <div class="meta-row">
      <span id="amount-label"></span>
      <span id="expires-label"></span>
    </div>

    <div class="status-row status-pending" id="status-row">
      <div class="dot"></div>
      <span id="status-text">Waiting for payment...</span>
    </div>
    <div class="txid" id="txid-row"></div>

    <button class="new-btn" id="cancel-btn" onclick="reset()">Cancel</button>
  </div>
</div>

<script>
  let paymentId = null;
  let pollTimer = null;
  let currentAddress = '';
  let btcPriceUsd = null;
  let updatingFrom = null;

  const STATUS_LABELS = {
    pending:   'Waiting for payment...',
    detected:  'Transaction detected in mempool',
    confirmed: 'Payment confirmed',
    expired:   'Invoice expired',
    overpaid:  'Payment confirmed (overpaid)',
  };

  // fetch BTC price once on load
  async function fetchPrice() {
    try {
      const r = await fetch('https://mempool.space/api/v1/prices');
      const d = await r.json();
      btcPriceUsd = d.USD;
    } catch (_) {}
  }
  fetchPrice();

  // sat → USD
  document.getElementById('amount-sat').addEventListener('input', () => {
    if (updatingFrom === 'usd') return;
    updatingFrom = 'sat';
    const sat = parseFloat(document.getElementById('amount-sat').value);
    if (btcPriceUsd && sat >= 0) {
      const usd = (sat / 1e8) * btcPriceUsd;
      document.getElementById('amount-usd').value = usd.toFixed(2);
    } else {
      document.getElementById('amount-usd').value = '';
    }
    updatingFrom = null;
  });

  // USD → sat
  document.getElementById('amount-usd').addEventListener('input', () => {
    if (updatingFrom === 'sat') return;
    updatingFrom = 'usd';
    const usd = parseFloat(document.getElementById('amount-usd').value);
    if (btcPriceUsd && usd >= 0) {
      const sat = Math.round((usd / btcPriceUsd) * 1e8);
      document.getElementById('amount-sat').value = sat;
    } else {
      document.getElementById('amount-sat').value = '';
    }
    updatingFrom = null;
  });

  document.getElementById('form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.textContent = 'Creating...';

    const satRaw = document.getElementById('amount-sat').value;
    const amount_sat = satRaw ? parseInt(satRaw) : null;

    try {
      const base = location.pathname.replace(/\/?$/, '/');
      const res = await fetch(base + 'invoices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount_sat }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      showInvoice(data);
    } catch (err) {
      alert('Error: ' + err.message);
      btn.disabled = false;
      btn.textContent = 'Pay';
    }
  });

  function showInvoice(data) {
    paymentId = data.payment_id;
    currentAddress = data.address;

    document.getElementById('address-text').textContent = data.address;
    document.getElementById('invoice').style.display = 'block';
    document.getElementById('form').style.display = 'none';

    const amountLabel = data.amount_sat
      ? (data.amount_sat / 1e8).toFixed(8) + ' BTC'
      : 'Any amount';
    document.getElementById('amount-label').textContent = amountLabel;

    if (data.expires_at) {
      const exp = new Date(data.expires_at);
      document.getElementById('expires-label').textContent =
        'Expires ' + exp.toLocaleTimeString();
    }

    document.getElementById('qrcode').innerHTML = '';
    new QRCode(document.getElementById('qrcode'), {
      text: data.bip21_uri,
      width: 200,
      height: 200,
      colorDark: '#111',
      colorLight: '#fff',
      correctLevel: QRCode.CorrectLevel.M,
    });

    startPolling();
  }

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(poll, 5000);
    poll();
  }

  async function poll() {
    if (!paymentId) return;
    try {
      const base = location.pathname.replace(/\/?$/, '/');
      const res = await fetch(base + 'invoices/' + paymentId);
      if (!res.ok) return;
      const data = await res.json();
      updateStatus(data);
      if (['confirmed', 'expired', 'overpaid'].includes(data.status)) {
        clearInterval(pollTimer);
      }
    } catch (_) {}
  }

  function updateStatus(data) {
    const row = document.getElementById('status-row');
    row.className = 'status-row status-' + data.status;
    document.getElementById('status-text').textContent =
      STATUS_LABELS[data.status] || data.status;

    const txidRow = document.getElementById('txid-row');
    if (data.txid) {
      txidRow.textContent = 'txid: ' + data.txid;
    }

    // hide cancel once payment is done
    const cancelBtn = document.getElementById('cancel-btn');
    if (['confirmed', 'overpaid'].includes(data.status)) {
      cancelBtn.style.display = 'none';
    }
  }

  function copyAddress() {
    navigator.clipboard.writeText(currentAddress).then(() => {
      const btn = document.querySelector('.copy-btn');
      btn.textContent = 'Copied';
      setTimeout(() => btn.textContent = 'Copy', 1500);
    });
  }

  function reset() {
    clearInterval(pollTimer);
    paymentId = null;
    currentAddress = '';
    document.getElementById('invoice').style.display = 'none';
    document.getElementById('form').style.display = 'block';
    document.getElementById('amount-sat').value = '';
    document.getElementById('amount-usd').value = '';
    document.getElementById('submit-btn').disabled = false;
    document.getElementById('submit-btn').textContent = 'Pay';
    document.getElementById('txid-row').textContent = '';
    document.getElementById('cancel-btn').style.display = '';
  }
</script>
</body>
</html>"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    proc = PaymentProcessor(xpub=XPUB, rpc_url=RPC_URL, required_confirmations=1)
    proc.setup()

    @proc.on_payment
    async def handle(event: PaymentEvent):
        if event.is_first_confirmation:
            print(f"CONFIRMED: {event.received_sat} sat for label={event.label}")

    app.state.proc = proc
    await proc.astart()
    yield
    await proc.astop()


app = FastAPI(lifespan=lifespan)


class InvoiceRequest(BaseModel):
    amount_sat: int | None = None
    label: str | None = None


@app.get("/", response_class=HTMLResponse)
def demo_page():
    return DEMO_HTML


@app.post("/invoices")
def create_invoice(req: InvoiceRequest):
    inv = app.state.proc.create_invoice(amount_sat=req.amount_sat, label=req.label)
    return {
        "payment_id": inv.payment_id,
        "address": inv.address,
        "bip21_uri": inv.bip21_uri,
        "amount_sat": inv.amount_sat,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
    }


@app.get("/invoices/{payment_id}")
def get_invoice(payment_id: str):
    inv = app.state.proc.get_invoice(payment_id)
    if inv is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "payment_id": inv.payment_id,
        "address": inv.address,
        "status": inv.status.value,
        "received_sat": inv.received_sat,
        "confirmations": inv.confirmations,
        "txid": inv.txid,
    }

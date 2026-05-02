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

    .input-group { margin-bottom: 16px; }

    .input-label {
      display: block;
      font-size: 11px;
      font-weight: 500;
      color: #999;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      margin-bottom: 6px;
    }

    .field-wrap {
      position: relative;
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

    #currency-select {
      width: 100%;
      border: 1px solid #ddd;
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 14px;
      color: #111;
      background: #fff;
      outline: none;
      cursor: pointer;
    }
    #currency-select:focus { border-color: #f7931a; }

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
    #submit-btn { transition: background 0.15s, opacity 0.15s; }

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
    <div class="input-group">
      <label class="input-label" for="currency-select">Currency</label>
      <select id="currency-select">
        <option value="USD">USD — US Dollar</option>
        <option value="EUR">EUR — Euro</option>
        <option value="GBP">GBP — British Pound</option>
        <option value="JPY">JPY — Japanese Yen</option>
        <option value="CAD">CAD — Canadian Dollar</option>
        <option value="CHF">CHF — Swiss Franc</option>
        <option value="AUD">AUD — Australian Dollar</option>
      </select>
    </div>

    <div class="input-group">
      <label class="input-label" for="amount-fiat">Amount</label>
      <div class="field-wrap">
        <span class="field-icon usd" id="fiat-icon">$</span>
        <input id="amount-fiat" type="number" placeholder="0.00" min="0" step="0.01">
      </div>
    </div>

    <div class="input-group">
      <label class="input-label" for="amount-btc">Bitcoin</label>
      <div class="field-wrap">
        <span class="field-icon btc">₿</span>
        <input id="amount-btc" type="number" placeholder="0.00000000" min="0" step="0.00000001">
      </div>
    </div>

    <button type="submit" id="submit-btn" disabled>Pay</button>
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
  const MIN_SAT = 1000;  // configurable minimum

  const CURRENCY_SYMBOLS = {
    USD: '$', EUR: '€', GBP: '£', JPY: '¥', CAD: 'C$', CHF: 'Fr', AUD: 'A$',
  };
  const FIAT_DECIMALS = { JPY: 0 };

  let paymentId = null;
  let pollTimer = null;
  let currentAddress = '';
  let allPrices = {};
  let updatingFrom = null;

  function selectedCurrency() {
    return document.getElementById('currency-select').value;
  }

  function selectedPrice() {
    return allPrices[selectedCurrency()] || null;
  }

  function updateFiatIcon() {
    const sym = CURRENCY_SYMBOLS[selectedCurrency()] || selectedCurrency();
    document.getElementById('fiat-icon').textContent = sym;
  }

  function satFromBtcField() {
    return Math.round((parseFloat(document.getElementById('amount-btc').value) || 0) * 1e8);
  }

  function updatePayBtn() {
    document.getElementById('submit-btn').disabled = satFromBtcField() < MIN_SAT;
  }

  const STATUS_LABELS = {
    pending:   'Waiting for payment...',
    detected:  'Transaction detected in mempool',
    confirmed: 'Payment confirmed',
    expired:   'Invoice expired',
    overpaid:  'Payment confirmed (overpaid)',
  };

  // fetch all BTC prices once on load
  async function fetchPrice() {
    try {
      const r = await fetch('https://mempool.space/api/v1/prices');
      allPrices = await r.json();
    } catch (_) {}
  }
  fetchPrice();

  // currency change: re-convert from BTC side
  document.getElementById('currency-select').addEventListener('change', () => {
    updateFiatIcon();
    const btc = parseFloat(document.getElementById('amount-btc').value);
    const price = selectedPrice();
    if (price && !isNaN(btc) && document.getElementById('amount-btc').value !== '') {
      const decimals = FIAT_DECIMALS[selectedCurrency()] ?? 2;
      document.getElementById('amount-fiat').value = (btc * price).toFixed(decimals);
    } else {
      document.getElementById('amount-fiat').value = '';
    }
  });

  // fiat → BTC
  document.getElementById('amount-fiat').addEventListener('input', () => {
    if (updatingFrom === 'btc') return;
    updatingFrom = 'fiat';
    const fiat = parseFloat(document.getElementById('amount-fiat').value);
    const price = selectedPrice();
    if (price && fiat >= 0) {
      document.getElementById('amount-btc').value = (fiat / price).toFixed(8);
    } else {
      document.getElementById('amount-btc').value = '';
    }
    updatingFrom = null;
    updatePayBtn();
  });

  // BTC → fiat
  document.getElementById('amount-btc').addEventListener('input', () => {
    if (updatingFrom === 'fiat') return;
    updatingFrom = 'btc';
    const btc = parseFloat(document.getElementById('amount-btc').value);
    const price = selectedPrice();
    if (price && btc >= 0) {
      const decimals = FIAT_DECIMALS[selectedCurrency()] ?? 2;
      document.getElementById('amount-fiat').value = (btc * price).toFixed(decimals);
    } else {
      document.getElementById('amount-fiat').value = '';
    }
    updatingFrom = null;
    updatePayBtn();
  });

  document.getElementById('form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.textContent = 'Creating...';

    const amount_sat = satFromBtcField() || null;

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
    document.getElementById('amount-btc').value = '';
    document.getElementById('amount-fiat').value = '';
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

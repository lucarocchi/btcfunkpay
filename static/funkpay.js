/**
 * FunkPay Widget — embeddable Bitcoin payment widget (Shadow DOM edition)
 *
 * Drop a div and the script — that's it:
 *
 *   <div id="funkpay" data-currency="EUR"></div>
 *   <script src="https://btcfunk.com/pay/funkpay.js"></script>
 *
 * Optional data attributes on the div:
 *   data-currency   USD | EUR | GBP | JPY | CAD | CHF | AUD
 *   data-amount     amount in satoshis (pre-fills the field)
 *   data-label      order / user identifier
 *   data-theme      light | dark | auto (default: auto)
 *
 * Listen for payment events (optional):
 *   <script>
 *     FunkPay.on('confirmed', function(p) { console.log('paid!', p); });
 *     FunkPay.on('expired',   function(p) { console.log('expired', p); });
 *   </script>
 */
(function (global) {
  'use strict';

  var _base = (function () {
    var scripts = document.querySelectorAll('script[src]');
    for (var i = 0; i < scripts.length; i++) {
      var s = scripts[i].src;
      if (s.indexOf('funkpay.js') !== -1) {
        try {
          var u = new URL(s);
          return u.origin + u.pathname.replace(/\/funkpay\.js$/, '');
        } catch (_) {
          return s.replace(/\/funkpay\.js(\?.*)?$/, '');
        }
      }
    }
    return '';
  })();

  var _callbacks = {};

  var _CSS = `
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :host {
      display: block;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #111111;
    }

    .card {
      background: #ffffff;
      border: 1px solid #e0e0e0;
      border-radius: 12px;
      padding: 16px 20px;
      width: 100%;
      height: 480px;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
    }

    [data-theme="dark"] .card {
      background: #1a1a1a;
      border-color: #2e2e2e;
      color: #f0f0f0;
    }

    .card-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
    }

    .funky-logo {
      display: block;
      width: 68px;
      height: auto;
      margin: 0;
      flex-shrink: 0;
    }

    .header-title {
      font-size: 15px;
      font-weight: 700;
      color: #111111;
      margin-bottom: 2px;
    }

    [data-theme="dark"] .header-title { color: #f0f0f0; }

    .header-sub {
      font-size: 12px;
      color: #555555;
      margin: 0;
    }

    [data-theme="dark"] .header-sub { color: #aaaaaa; }

    #payment-success {
      display: none;
      flex: 1;
      flex-direction: column;
    }
    #success-content { flex: 1; display: flex; flex-direction: column; justify-content: center; }
    #payment-success .ok-title { font-size: 1.1rem; font-weight: 700; color: #22c55e; margin-bottom: 8px; }
    #payment-success .ok-amount { font-size: 0.85rem; color: #555555; margin-bottom: 8px; }
    [data-theme="dark"] #payment-success .ok-amount { color: #aaaaaa; }
    #payment-success .ok-txid { font-size: 10px; font-family: monospace; color: #999999; word-break: break-all; cursor: pointer; }
    [data-theme="dark"] #payment-success .ok-txid { color: #666666; }

    .input-group { margin-bottom: 10px; }

    .input-label {
      display: block;
      font-size: 11px;
      font-weight: 500;
      color: #999999;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      margin-bottom: 6px;
    }

    [data-theme="dark"] .input-label { color: #666666; }

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
      border: 1px solid #dddddd;
      border-radius: 8px;
      padding: 10px 12px 10px 32px;
      font-size: 14px;
      color: #111111;
      background: #ffffff;
      outline: none;
      transition: border-color 0.15s;
    }
    [data-theme="dark"] input {
      border-color: #3a3a3a;
      color: #f0f0f0;
      background: #242424;
    }
    input:focus { border-color: #f7931a; }
    input[type=number]::-webkit-inner-spin-button,
    input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }

    select {
      width: 100%;
      border: 1px solid #dddddd;
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 14px;
      color: #111111;
      background: #ffffff;
      outline: none;
      cursor: pointer;
    }
    [data-theme="dark"] select {
      border-color: #3a3a3a;
      color: #f0f0f0;
      background: #242424;
    }
    select:focus { border-color: #f7931a; }

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
    button:disabled { background: #cccccc; cursor: default; }
    [data-theme="dark"] button:disabled { background: #333333; }
    #submit-btn { transition: background 0.15s, opacity 0.15s; }

    #form { flex: 1; display: flex; flex-direction: column; }

    .pay-hint {
      margin-top: 14px;
      margin-bottom: 0;
      font-size: 12px;
      color: #888888;
      line-height: 1.6;
    }
    [data-theme="dark"] .pay-hint { color: #888888; }
    .pay-hint b { color: #555555; font-weight: 600; }
    [data-theme="dark"] .pay-hint b { color: #bbbbbb; }

    /* ---- invoice panel ---- */
    #invoice { display: none; flex: 1; margin-top: 14px; flex-direction: column; }

    .divider {
      border: none;
      border-top: 1px solid #eeeeee;
      margin-bottom: 12px;
    }
    [data-theme="dark"] .divider { border-top-color: #2e2e2e; }

    .qr-wrap {
      display: flex;
      justify-content: center;
      margin-bottom: 10px;
    }

    #qrcode canvas, #qrcode img { border-radius: 8px; }

    .address-box {
      background: #f9f9f9;
      border: 1px solid #eeeeee;
      border-radius: 8px;
      padding: 12px 14px;
      font-family: monospace;
      font-size: 12px;
      word-break: break-all;
      color: #333333;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    [data-theme="dark"] .address-box {
      background: #242424;
      border-color: #333333;
      color: #cccccc;
    }

    .address-box span { flex: 1; }

    .copy-btn {
      background: none;
      border: 1px solid #dddddd;
      color: #555555;
      border-radius: 6px;
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 500;
      cursor: pointer;
      width: auto;
      white-space: nowrap;
      transition: border-color 0.15s, color 0.15s;
    }
    [data-theme="dark"] .copy-btn {
      border-color: #3a3a3a;
      color: #888888;
    }
    .copy-btn:hover { border-color: #f7931a; color: #f7931a; background: none; }

    .meta-row {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: #888888;
      margin-bottom: 10px;
    }
    [data-theme="dark"] .meta-row { color: #666666; }

    /* ---- status badge ---- */
    .status-row {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      font-weight: 500;
      margin-top: 4px;
    }

    .dot {
      width: 7px; height: 7px;
      border-radius: 50%;
      flex-shrink: 0;
    }

    .status-pending   { color: #999999; }
    [data-theme="dark"] .status-pending { color: #666666; }
    .status-pending .dot { background: #22c55e; animation: pulse 1.4s infinite; }
    [data-theme="dark"] .status-pending .dot { background: #22c55e; }

    .status-detected  { color: #b06000; }
    .status-detected .dot { background: #f7931a; animation: pulse 1.2s infinite; }

    .status-confirmed { color: #15803d; }
    .status-confirmed .dot { background: #22c55e; }

    .status-overpaid  { color: #15803d; }
    .status-overpaid .dot  { background: #22c55e; }

    .status-expired   { color: #b91c1c; }
    .status-expired .dot  { background: #ef4444; }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.3; }
    }

    .txid {
      font-size: 10px;
      font-family: monospace;
      color: #888888;
      word-break: break-all;
      margin-top: 8px;
    }
    [data-theme="dark"] .txid { color: #666666; }
  `;

  var _LOGO_SRC = 'data:image/png;base64,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';

  var _HTML = `
    <div class="card">
      <div class="card-header">
        <img class="funky-logo" src="${_LOGO_SRC}" alt="FunkPay">
        <div>
          <div class="header-title">Pay with Bitcoin</div>
          <p class="header-sub">Your keys. Your coins.</p>
        </div>
      </div>

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
            <input id="amount-fiat" type="number" placeholder="0.00" min="0">
          </div>
        </div>

        <div class="input-group">
          <label class="input-label" for="amount-btc">Bitcoin</label>
          <div class="field-wrap">
            <span class="field-icon btc">₿</span>
            <input id="amount-btc" type="text" inputmode="decimal" placeholder="0.00000000" pattern="[0-9]*\\.?[0-9]*">
          </div>
        </div>

        <div class="pay-hint">
          Enter fiat or BTC amount.<br>Click <b>Pay</b>, scan the QR with your Bitcoin wallet and<br>Send.<br><a href="https://github.com/lucarocchi/btcfunkpay" target="_blank" rel="noopener" style="color:inherit;text-decoration:underline;text-underline-offset:2px;">Open source · MIT</a>
        </div>
        <button type="submit" id="submit-btn" style="margin-top:auto;" disabled>Pay</button>
      </form>

      <div id="invoice">
        <hr class="divider">

        <div class="qr-wrap">
          <div id="qrcode"></div>
        </div>

        <div class="address-box">
          <span id="address-text"></span>
          <button class="copy-btn" id="copy-btn">Copy</button>
        </div>

        <div class="meta-row">
          <span id="amount-label"></span>
        </div>

        <div class="status-row status-pending" id="status-row">
          <div class="dot"></div>
          <span id="status-text">Waiting for payment...</span>
        </div>
        <div class="txid" id="txid-row"></div>

        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:auto;padding-top:10px;">
          <span id="cancel-btn" style="font-size:13px;color:#aaaaaa;cursor:pointer;">Cancel</span>
          <span id="paid-btn" style="font-size:13px;color:#22c55e;cursor:pointer;">I’ve paid</span>
        </div>
      </div>

      <div id="payment-success">
        <div id="success-content">
          <div class="ok-title" id="ok-title">Payment received!</div>
          <div class="ok-sub" id="ok-sub" style="display:none;font-size:12px;color:#999999;margin-bottom:12px;line-height:1.6;"></div>
          <div class="ok-amount" id="ok-amount"></div>
          <div class="ok-txid" id="ok-txid" title="Click to copy txid"></div>
        </div>
        <button id="thankyou-btn" style="background:#22c55e;margin-top:auto;">Thank you</button>
      </div>
    </div>
  `;

  var MIN_SAT = 1000;

  var CURRENCY_SYMBOLS = {
    USD: '$', EUR: '€', GBP: '£', JPY: '¥', CAD: 'C$', CHF: 'Fr', AUD: 'A$',
  };
  var FIAT_DECIMALS = { JPY: 0 };

  var STATUS_LABELS = {
    pending:   'Waiting for payment...',
    detected:  'Transaction detected in mempool',
    confirmed: 'Payment confirmed',
    expired:   'Invoice expired',
    overpaid:  'Payment confirmed (overpaid)',
  };

  function on(event, cb) {
    _callbacks[event] = cb;
  }

  function _loadQR(cb) {
    if (window.QRCode) { cb(); return; }
    var s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js';
    s.onload = cb;
    document.head.appendChild(s);
  }

  function _initWidget(root, opts) {
    var paymentId     = null;
    var pollTimer     = null;
    var currentAddress = '';
    var allPrices     = {};
    var updatingFrom  = null;
    var base          = opts.server || _base;

    // --- apply theme ---
    var wrapper = root.querySelector('.card').parentElement;
    var theme = opts.theme || 'auto';
    if (theme === 'auto') {
      theme = (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches)
        ? 'dark' : 'light';
    }
    wrapper.setAttribute('data-theme', theme);

    // --- pre-fill currency ---
    if (opts.currency) {
      var sel = root.getElementById('currency-select');
      if (sel) { sel.value = opts.currency; updateFiatIcon(); }
    }

    // --- pre-fill amount ---
    if (opts.amount) {
      var sat = parseInt(opts.amount);
      if (sat > 0) {
        root.getElementById('amount-btc').value = (sat / 1e8).toFixed(8);
      }
    }

    function selectedCurrency() {
      return root.getElementById('currency-select').value;
    }

    function selectedPrice() {
      return allPrices[selectedCurrency()] || null;
    }

    function updateFiatIcon() {
      var sym = CURRENCY_SYMBOLS[selectedCurrency()] || selectedCurrency();
      root.getElementById('fiat-icon').textContent = sym;
    }

    function satFromBtcField() {
      return Math.round((parseFloat(root.getElementById('amount-btc').value) || 0) * 1e8);
    }

    function updatePayBtn() {
      root.getElementById('submit-btn').disabled = satFromBtcField() < MIN_SAT;
    }

    async function fetchPrice() {
      try {
        var r = await fetch(base + '/prices');
        allPrices = await r.json();
        var price = selectedPrice();
        if (price) {
          var btc  = parseFloat(root.getElementById('amount-btc').value);
          var fiat = parseFloat(root.getElementById('amount-fiat').value);
          var decimals = (FIAT_DECIMALS[selectedCurrency()] !== undefined)
            ? FIAT_DECIMALS[selectedCurrency()] : 2;
          if (btc > 0) {
            root.getElementById('amount-fiat').value = (btc * price).toFixed(decimals);
          } else if (fiat > 0) {
            root.getElementById('amount-btc').value = (fiat / price).toFixed(8);
          }
        }
        updatePayBtn();
      } catch (_) {}
    }

    fetchPrice();

    // currency change
    root.getElementById('currency-select').addEventListener('change', function() {
      updateFiatIcon();
      var btc = parseFloat(root.getElementById('amount-btc').value);
      var price = selectedPrice();
      if (price && !isNaN(btc) && root.getElementById('amount-btc').value !== '') {
        var decimals = (FIAT_DECIMALS[selectedCurrency()] !== undefined)
          ? FIAT_DECIMALS[selectedCurrency()] : 2;
        root.getElementById('amount-fiat').value = (btc * price).toFixed(decimals);
      } else {
        root.getElementById('amount-fiat').value = '';
      }
    });

    // fiat → BTC
    root.getElementById('amount-fiat').addEventListener('input', function() {
      if (updatingFrom === 'btc') return;
      updatingFrom = 'fiat';
      var fiat  = parseFloat(root.getElementById('amount-fiat').value);
      var price = selectedPrice();
      if (price && fiat >= 0) {
        root.getElementById('amount-btc').value = (fiat / price).toFixed(8);
      } else {
        root.getElementById('amount-btc').value = '';
      }
      updatingFrom = null;
      updatePayBtn();
    });

    // BTC → fiat
    root.getElementById('amount-btc').addEventListener('input', function() {
      if (updatingFrom === 'fiat') return;
      updatingFrom = 'btc';
      var btc   = parseFloat(root.getElementById('amount-btc').value);
      var price = selectedPrice();
      if (price && btc >= 0) {
        var decimals = (FIAT_DECIMALS[selectedCurrency()] !== undefined)
          ? FIAT_DECIMALS[selectedCurrency()] : 2;
        root.getElementById('amount-fiat').value = (btc * price).toFixed(decimals);
      } else {
        root.getElementById('amount-fiat').value = '';
      }
      updatingFrom = null;
      updatePayBtn();
    });

    // form submit
    root.getElementById('form').addEventListener('submit', async function(e) {
      e.preventDefault();
      var btn = root.getElementById('submit-btn');
      btn.disabled = true;
      btn.textContent = 'Creating...';

      var amount_sat = satFromBtcField() || null;
      var label = opts.label || null;

      try {
        var res = await fetch(base + '/invoices', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount_sat: amount_sat, label: label }),
        });
        if (!res.ok) throw new Error(await res.text());
        var data = await res.json();
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

      root.getElementById('address-text').textContent = data.address;
      root.getElementById('invoice').style.display = 'flex';
      root.getElementById('form').style.display = 'none';

      var amountLabel = data.amount_sat
        ? (data.amount_sat / 1e8).toFixed(8) + ' BTC'
        : 'Any amount';
      root.getElementById('amount-label').textContent = amountLabel;

      root.getElementById('qrcode').innerHTML = '';
      var isDark = wrapper.getAttribute('data-theme') === 'dark';
      new QRCode(root.getElementById('qrcode'), {
        text: data.bip21_uri,
        width: 160,
        height: 160,
        colorDark:  isDark ? '#f0f0f0' : '#111111',
        colorLight: isDark ? '#1a1a1a' : '#ffffff',
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
        var res = await fetch(base + '/invoices/' + paymentId);
        if (!res.ok) return;
        var data = await res.json();
        updateStatus(data);
        if (['confirmed', 'expired', 'overpaid'].includes(data.status)) {
          clearInterval(pollTimer);
        }
      } catch (_) {}
    }

    function updateStatus(data) {
      var row = root.getElementById('status-row');
      row.className = 'status-row status-' + data.status;
      root.getElementById('status-text').textContent =
        STATUS_LABELS[data.status] || data.status;

      var txidRow = root.getElementById('txid-row');
      if (data.txid) {
        var txid = data.txid;
        txidRow.innerHTML = '';
        var txidSpan = document.createElement('span');
        txidSpan.style.cssText = 'cursor:pointer;text-decoration:underline;text-underline-offset:2px';
        txidSpan.title = 'Copy txid';
        txidSpan.textContent = 'txid: ' + txid;
        txidSpan.addEventListener('click', function() {
          navigator.clipboard.writeText(txid).then(function() {
            var prev = txidRow.style.color;
            txidRow.style.color = '#22c55e';
            setTimeout(function() { txidRow.style.color = prev; }, 800);
          });
        });
        txidRow.appendChild(txidSpan);
      }

      if (['detected', 'confirmed', 'overpaid'].includes(data.status)) {
        clearInterval(pollTimer);
        root.getElementById('invoice').style.display = 'none';
        root.getElementById('form').style.display = 'none';
        var s = root.getElementById('payment-success');
        s.style.display = 'flex';
        root.getElementById('ok-title').textContent = 'Payment received!';
        var okSubConfirmed = root.getElementById('ok-sub');
        okSubConfirmed.textContent = 'Your payment has been confirmed on the Bitcoin network. Thank you for paying with Bitcoin!';
        okSubConfirmed.style.display = 'block';
        var sat = data.received_sat || 0;
        root.getElementById('ok-amount').textContent = (sat / 1e8).toFixed(8) + ' BTC received';
        if (data.txid) {
          var okTxid = root.getElementById('ok-txid');
          okTxid.textContent = 'txid: ' + data.txid;
          okTxid.onclick = (function(t) {
            return function() {
              navigator.clipboard.writeText(t).then(function() {
                okTxid.style.color = '#22c55e';
                setTimeout(function() { okTxid.style.color = ''; }, 800);
              });
            };
          })(data.txid);
        }

        if (_callbacks.confirmed) _callbacks.confirmed(data);
      }

      if (data.status === 'expired') {
        if (_callbacks.expired) _callbacks.expired(data);
      }
    }

    // copy address button
    root.getElementById('copy-btn').addEventListener('click', function() {
      navigator.clipboard.writeText(currentAddress).then(function() {
        var btn = root.getElementById('copy-btn');
        btn.textContent = 'Copied';
        setTimeout(function() { btn.textContent = 'Copy'; }, 1500);
      });
    });

    // "I've paid" button
    root.getElementById('paid-btn').addEventListener('click', function() {
      showThankYou();
    });

    // cancel button
    root.getElementById('cancel-btn').addEventListener('click', function() {
      reset();
    });

    // thank you button
    root.getElementById('thankyou-btn').addEventListener('click', function() {
      window.location.href = '/';
    });

    function showThankYou() {
      clearInterval(pollTimer);
      root.getElementById('invoice').style.display = 'none';
      root.getElementById('form').style.display = 'none';
      var s = root.getElementById('payment-success');
      s.style.display = 'flex';
      root.getElementById('ok-title').textContent = 'Thank you!';
      var okSub = root.getElementById('ok-sub');
      okSub.textContent = 'Your payment is on its way. Bitcoin transactions typically confirm within 10–60 minutes. You can close this page.';
      okSub.style.display = 'block';
      root.getElementById('ok-amount').textContent = '';
      root.getElementById('ok-txid').textContent = '';
    }

    function reset() {
      clearInterval(pollTimer);
      paymentId = null;
      currentAddress = '';
      root.getElementById('invoice').style.display = 'none';
      root.getElementById('form').style.display = 'block';
      root.getElementById('amount-btc').value = '';
      root.getElementById('amount-fiat').value = '';
      root.getElementById('submit-btn').disabled = false;
      root.getElementById('submit-btn').textContent = 'Pay';
      root.getElementById('txid-row').textContent = '';
    }
  }

  function _mount(el, opts) {
    var shadow = el.attachShadow({ mode: 'open' });
    var style = document.createElement('style');
    style.textContent = _CSS;
    shadow.appendChild(style);
    var wrap = document.createElement('div');
    wrap.innerHTML = _HTML;
    shadow.appendChild(wrap);
    _loadQR(function() { _initWidget(shadow, opts); });
  }

  function _auto() {
    var el = document.getElementById('funkpay');
    if (!el) return;
    var server = (el.getAttribute('data-server') || '').replace(/\/$/, '');
    _mount(el, {
      currency: el.getAttribute('data-currency') || '',
      theme:    el.getAttribute('data-theme')    || 'auto',
      label:    el.getAttribute('data-label')    || '',
      amount:   el.getAttribute('data-amount')   || '',
      server:   server,
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _auto);
  } else {
    _auto();
  }

  global.FunkPay = { on: on };

})(window);

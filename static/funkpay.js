/**
 * FunkPay Widget — embeddable Bitcoin payment modal
 * Usage:
 *   <script src="https://btcfunk.com/pay/widget.js"></script>
 *   <script>
 *     FunkPay.on('confirmed', function(payment) { ... });
 *     FunkPay.open({ amount_sat: 50000, label: 'user-42' });
 *   </script>
 */
(function (global) {
  'use strict';

  // Auto-detect base URL from this script's src attribute
  var _base = (function () {
    var scripts = document.querySelectorAll('script[src]');
    for (var i = 0; i < scripts.length; i++) {
      var s = scripts[i].src;
      if (s.indexOf('funkpay.js') !== -1) return s.replace('/funkpay.js', '');
    }
    return '';
  })();

  var _callbacks = {};
  var _overlay = null;

  function _injectStyles() {
    if (document.getElementById('funkpay-styles')) return;
    var style = document.createElement('style');
    style.id = 'funkpay-styles';
    style.textContent =
      '#funkpay-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.55);' +
      'display:flex;align-items:center;justify-content:center;z-index:2147483647;' +
      'backdrop-filter:blur(6px);animation:fp-fade-in 0.2s ease}' +
      '#funkpay-iframe{border:none;border-radius:16px;width:380px;height:680px;' +
      'max-width:95vw;max-height:92vh;box-shadow:0 24px 80px rgba(0,0,0,0.35);' +
      'animation:fp-slide-up 0.25s ease}' +
      '@keyframes fp-fade-in{from{opacity:0}to{opacity:1}}' +
      '@keyframes fp-slide-up{from{transform:translateY(24px);opacity:0}to{transform:translateY(0);opacity:1}}';
    document.head.appendChild(style);
  }

  function _close() {
    if (_overlay) { _overlay.remove(); _overlay = null; }
    window.removeEventListener('message', _onMessage);
  }

  function _onMessage(e) {
    if (!e.data || typeof e.data.type !== 'string') return;
    if (e.data.type === 'funkpay:confirmed') {
      if (_callbacks.onConfirmed) _callbacks.onConfirmed(e.data.payment);
    }
    if (e.data.type === 'funkpay:expired') {
      if (_callbacks.onExpired) _callbacks.onExpired(e.data.payment);
    }
    if (e.data.type === 'funkpay:close') {
      _close();
    }
  }

  /**
   * Open the payment modal.
   * @param {Object} opts
   * @param {number}  [opts.amount_sat]  - Amount in satoshis (pre-fills the BTC field)
   * @param {string}  [opts.label]       - Order/user label stored with the invoice
   * @param {string}  [opts.currency]    - Default fiat currency, e.g. 'EUR' (default: 'USD')
   */
  function open(opts) {
    opts = opts || {};
    _close();
    _injectStyles();

    _overlay = document.createElement('div');
    _overlay.id = 'funkpay-overlay';

    var iframe = document.createElement('iframe');
    iframe.id = 'funkpay-iframe';
    iframe.setAttribute('allow', 'clipboard-write');

    var params = [];
    if (opts.amount_sat) params.push('amount='    + encodeURIComponent(opts.amount_sat));
    if (opts.label)      params.push('label='     + encodeURIComponent(opts.label));
    if (opts.currency)   params.push('currency='  + encodeURIComponent(opts.currency));
    iframe.src = _base + '/' + (params.length ? '?' + params.join('&') : '');

    _overlay.appendChild(iframe);
    document.body.appendChild(_overlay);

    // close on backdrop click
    _overlay.addEventListener('click', function (e) {
      if (e.target === _overlay) _close();
    });

    // close on Escape key
    document.addEventListener('keydown', function _esc(e) {
      if (e.key === 'Escape') { _close(); document.removeEventListener('keydown', _esc); }
    });

    window.addEventListener('message', _onMessage);
  }

  /**
   * Register an event callback.
   * @param {'confirmed'|'expired'|'close'} event
   * @param {Function} cb
   */
  function on(event, cb) {
    _callbacks['on' + event.charAt(0).toUpperCase() + event.slice(1)] = cb;
  }

  global.FunkPay = { open: open, close: _close, on: on };

})(window);

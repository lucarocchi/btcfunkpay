/**
 * FunkPay Widget — embeddable Bitcoin payment widget
 *
 * Inline (recommended):
 *   <div id="funkpay"></div>
 *   <script src="https://btcfunk.com/pay/funkpay.js"></script>
 *   <script>
 *     FunkPay.on('confirmed', (p) => console.log('paid!', p));
 *     FunkPay.mount('#funkpay', { currency: 'EUR' });
 *   </script>
 *
 * Modal (alternative):
 *   FunkPay.open({ amount_sat: 50000, label: 'user-42' });
 */
(function (global) {
  'use strict';

  var _base = (function () {
    var scripts = document.querySelectorAll('script[src]');
    for (var i = 0; i < scripts.length; i++) {
      var s = scripts[i].src;
      if (s.indexOf('funkpay.js') !== -1) return s.replace('/funkpay.js', '');
    }
    return '';
  })();

  var _callbacks = {};
  var _overlay   = null;

  function _detectTheme() {
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
    return 'light';
  }

  function _buildSrc(opts) {
    var params = [];
    if (opts.amount_sat) params.push('amount='   + encodeURIComponent(opts.amount_sat));
    if (opts.label)      params.push('label='    + encodeURIComponent(opts.label));
    if (opts.currency)   params.push('currency=' + encodeURIComponent(opts.currency));
    params.push('theme=' + (opts.theme || _detectTheme()));
    return _base + '/?' + params.join('&');
  }

  function _makeIframe(src, extraStyle) {
    var iframe = document.createElement('iframe');
    iframe.setAttribute('allow', 'clipboard-write');
    iframe.style.cssText = 'border:none;width:100%;' + (extraStyle || '');
    iframe.src = src;
    return iframe;
  }

  function _onMessage(e) {
    if (!e.data || typeof e.data.type !== 'string') return;
    if (e.data.type === 'funkpay:confirmed') {
      if (_callbacks.onConfirmed) _callbacks.onConfirmed(e.data.payment);
    }
    if (e.data.type === 'funkpay:expired') {
      if (_callbacks.onExpired) _callbacks.onExpired(e.data.payment);
    }
    if (e.data.type === 'funkpay:close') { _close(); }
  }

  function _close() {
    if (_overlay) { _overlay.remove(); _overlay = null; }
    window.removeEventListener('message', _onMessage);
  }

  /**
   * Mount the widget inline inside a container element.
   * @param {string|Element} selector  - CSS selector or DOM element
   * @param {Object}         opts
   * @param {number} [opts.amount_sat]
   * @param {string} [opts.label]
   * @param {string} [opts.currency]   'USD'|'EUR'|'GBP'|'JPY'|'CAD'|'CHF'|'AUD'
   * @param {string} [opts.theme]      'light'|'dark'|'auto' (default: auto-detect)
   */
  function mount(selector, opts) {
    opts = opts || {};
    var container = typeof selector === 'string' ? document.querySelector(selector) : selector;
    if (!container) { console.error('FunkPay.mount: element not found:', selector); return; }
    container.innerHTML = '';
    var iframe = _makeIframe(_buildSrc(opts), 'height:640px;border-radius:12px;');
    container.appendChild(iframe);
    window.addEventListener('message', _onMessage);
  }

  /**
   * Open as a modal overlay.
   * @param {Object} opts  - same as mount()
   */
  function open(opts) {
    opts = opts || {};
    _close();

    if (!document.getElementById('funkpay-styles')) {
      var style = document.createElement('style');
      style.id = 'funkpay-styles';
      style.textContent =
        '#fp-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.55);' +
        'display:flex;align-items:center;justify-content:center;z-index:2147483647;' +
        'backdrop-filter:blur(6px);animation:fp-in 0.2s ease}' +
        '#fp-overlay iframe{border:none;border-radius:16px;width:380px;height:680px;' +
        'max-width:95vw;max-height:92vh;box-shadow:0 24px 80px rgba(0,0,0,0.35);' +
        'animation:fp-up 0.25s ease}' +
        '@keyframes fp-in{from{opacity:0}to{opacity:1}}' +
        '@keyframes fp-up{from{transform:translateY(24px);opacity:0}to{transform:translateY(0);opacity:1}}';
      document.head.appendChild(style);
    }

    _overlay = document.createElement('div');
    _overlay.id = 'fp-overlay';
    _overlay.appendChild(_makeIframe(_buildSrc(opts)));
    document.body.appendChild(_overlay);

    _overlay.addEventListener('click', function (e) { if (e.target === _overlay) _close(); });
    document.addEventListener('keydown', function _esc(e) {
      if (e.key === 'Escape') { _close(); document.removeEventListener('keydown', _esc); }
    });
    window.addEventListener('message', _onMessage);
  }

  function on(event, cb) {
    _callbacks['on' + event.charAt(0).toUpperCase() + event.slice(1)] = cb;
  }

  global.FunkPay = { mount: mount, open: open, close: _close, on: on };

})(window);

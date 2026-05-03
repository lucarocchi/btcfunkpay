/**
 * FunkPay Widget — embeddable Bitcoin payment widget
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
      if (s.indexOf('funkpay.js') !== -1) return s.replace('/funkpay.js', '');
    }
    return '';
  })();

  var _callbacks = {};

  function _detectTheme() {
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
    return 'light';
  }

  function _buildSrc(opts) {
    var params = [];
    if (opts.amount)   params.push('amount='   + encodeURIComponent(opts.amount));
    if (opts.label)    params.push('label='    + encodeURIComponent(opts.label));
    if (opts.currency) params.push('currency=' + encodeURIComponent(opts.currency));
    var theme = opts.theme || 'auto';
    if (theme === 'auto') theme = _detectTheme();
    params.push('theme=' + theme);
    return _base + '/?' + params.join('&');
  }

  function _onMessage(e) {
    if (!e.data || typeof e.data.type !== 'string') return;
    if (e.data.type === 'funkpay:confirmed' && _callbacks.confirmed) _callbacks.confirmed(e.data.payment);
    if (e.data.type === 'funkpay:expired'   && _callbacks.expired)   _callbacks.expired(e.data.payment);
  }

  function _mount(container, opts) {
    container.innerHTML = '';
    var iframe = document.createElement('iframe');
    iframe.setAttribute('allow', 'clipboard-write');
    iframe.style.cssText = 'border:none;width:100%;height:640px;border-radius:12px;';
    iframe.src = _buildSrc(opts);
    container.appendChild(iframe);
    window.addEventListener('message', _onMessage);
  }

  function _auto() {
    var el = document.getElementById('funkpay');
    if (!el) return;
    _mount(el, {
      amount:   el.getAttribute('data-amount')   || '',
      label:    el.getAttribute('data-label')    || '',
      currency: el.getAttribute('data-currency') || '',
      theme:    el.getAttribute('data-theme')    || 'auto',
    });
  }

  function on(event, cb) {
    _callbacks[event] = cb;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _auto);
  } else {
    _auto();
  }

  global.FunkPay = { on: on };

})(window);

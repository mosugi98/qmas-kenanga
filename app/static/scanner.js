/* Scanner USB (mode keyboard / "wedge"): scanner mengetik kode dengan sangat cepat lalu menekan Enter.
   UsbScan.attach(cb)          tangkap scan di mana saja pada halaman (kecuali saat mengetik di kolom isian lain)
   UsbScan.bindInput(el, cb)   kolom khusus scan: Enter = kirim kode, kolom dikosongkan, fokus dijaga
   UsbScan.beep('ok'|'dup'|'err') bunyi umpan balik (kasir tidak perlu melihat layar) */
(function () {
  var ctx = null;
  function audio() {
    try { ctx = ctx || new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { ctx = null; }
    return ctx;
  }
  function nada(freqs, dur) {
    var c = audio(); if (!c) return;
    if (c.state === 'suspended') c.resume();
    var t = c.currentTime;
    freqs.forEach(function (f, i) {
      var o = c.createOscillator(), g = c.createGain();
      o.frequency.value = f; o.type = 'sine';
      g.gain.setValueAtTime(0.15, t + i * dur);
      g.gain.exponentialRampToValueAtTime(0.001, t + (i + 1) * dur);
      o.connect(g); g.connect(c.destination);
      o.start(t + i * dur); o.stop(t + (i + 1) * dur);
    });
  }
  function beep(jenis) {
    if (jenis === 'ok') nada([1100], 0.09);
    else if (jenis === 'dup') nada([700, 700], 0.09);
    else nada([220, 180], 0.18);
  }

  var MAKS_JEDA = 60;   // ms antar ketukan; ketikan manusia jauh lebih lambat
  var MIN_PANJANG = 3;

  function attach(cb) {
    var buf = '', last = 0, cepat = 0;
    document.addEventListener('keydown', function (e) {
      var el = e.target, tag = el && el.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (el && el.isContentEditable)) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      var now = Date.now();
      if (now - last > MAKS_JEDA) { buf = ''; cepat = 0; }
      else cepat++;
      last = now;
      if (e.key === 'Enter') {
        if (buf.length >= MIN_PANJANG && cepat >= MIN_PANJANG - 1) {
          e.preventDefault();
          var k = buf; buf = ''; cepat = 0;
          cb(k.toUpperCase());
        }
        buf = ''; cepat = 0;
      } else if (e.key.length === 1) {
        buf += e.key;
      }
    }, true);
  }

  function bindInput(el, cb) {
    function kirim() {
      var v = el.value.trim();
      el.value = '';
      if (v) cb(v.toUpperCase());
      el.focus();
    }
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); kirim(); }
    });
    // jaga fokus agar scan berikutnya selalu masuk (kecuali sedang mengisi kolom lain)
    document.addEventListener('click', function (e) {
      var t = e.target.tagName;
      if (t !== 'INPUT' && t !== 'TEXTAREA' && t !== 'SELECT' && t !== 'A' && t !== 'BUTTON') el.focus();
    });
    el.focus();
  }

  window.UsbScan = { attach: attach, bindInput: bindInput, beep: beep };
})();

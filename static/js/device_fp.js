/* Device fingerprint for Zero Trust EMR
   Builds a stable device ID from browser signals that websites CAN see
   (MAC addresses never travel over HTTP, so they cannot be read here). */
(function () {
  function fnv1a(str) {
    var h = 0x811c9dc5;
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    return (h >>> 0).toString(16);
  }

  function canvasHash() {
    try {
      var c = document.createElement('canvas');
      c.width = 220; c.height = 60;
      var ctx = c.getContext('2d');
      ctx.textBaseline = 'top';
      ctx.font = '14px Arial';
      ctx.fillStyle = '#6366f1';
      ctx.fillRect(0, 0, 220, 60);
      ctx.fillStyle = '#ffffff';
      ctx.fillText('ZeroTrustEMR-FP-7f3a', 8, 12);
      ctx.fillStyle = '#0f172a';
      ctx.font = '16px serif';
      ctx.fillText('MBEYA@2025', 30, 30);
      var data = c.toDataURL().slice(0, 2048);
      return fnv1a(data);
    } catch (e) { return 'nocanvas'; }
  }

  var signals = [
    navigator.userAgent,
    navigator.language || '',
    (navigator.languages || []).join(','),
    navigator.platform || '',
    screen.width + 'x' + screen.height,
    screen.availWidth + 'x' + screen.availHeight,
    screen.colorDepth || '',
    (new Date().getTimezoneOffset()) || '',
    navigator.hardwareConcurrency || '',
    navigator.deviceMemory || '',
    navigator.maxTouchPoints || '',
    canvasHash()
  ];

  var fp = fnv1a(signals.join('||'));

  // Keep the fingerprint available across pages (e.g. login -> OTP verify)
  try {
    sessionStorage.setItem('zt_device_fp', fp);
  } catch (e) {}

  // Drop it into any form field named device_fp
  window.addEventListener('DOMContentLoaded', function () {
    var inputs = document.querySelectorAll('input[name="device_fp"]');
    for (var i = 0; i < inputs.length; i++) inputs[i].value = fp;
  });

  window.__ztDeviceFp = fp;
})();

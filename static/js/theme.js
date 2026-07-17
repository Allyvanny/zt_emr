/* Zero Trust EMR — Theme toggle (dark/light) */
(function () {
  var toggle = document.getElementById('theme-toggle');
  var knob   = document.getElementById('theme-knob');
  if (!toggle) return; // not logged in / no topbar on this page

  function applyIcon() {
    var current = document.documentElement.getAttribute('data-theme') || 'light';
    knob.textContent = current === 'dark' ? '🌙' : '☀️';
  }

  applyIcon();

  toggle.addEventListener('click', function () {
    var current = document.documentElement.getAttribute('data-theme') || 'light';
    var next    = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('zt-theme', next);
    applyIcon();
  });
})();

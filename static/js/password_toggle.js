/* Zero Trust EMR — Password visibility toggle (eye button) */
(function(){
  function toggleType(input, btn){
    var show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    btn.textContent = show ? '🙈' : '👁';
    btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  }

  function init(){
    document.querySelectorAll('input[type="password"]').forEach(function(input){
      if (input.dataset.pwWrapped) return;
      input.dataset.pwWrapped = '1';

      // Wrap in a relative-positioned container
      var wrap = document.createElement('div');
      wrap.className = 'password-wrap';
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);

      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'password-toggle';
      btn.textContent = '👁';
      btn.setAttribute('aria-label', 'Show password');
      btn.addEventListener('click', function(){ toggleType(input, btn); });
      wrap.appendChild(btn);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

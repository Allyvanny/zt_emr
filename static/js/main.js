document.addEventListener('DOMContentLoaded', function() {
  // Password show/hide eye toggle
  (function(){
    document.querySelectorAll('input[type="password"]').forEach(function(input){
      if (input.dataset.pwWrapped) return;
      input.dataset.pwWrapped = '1';
      var wrap = document.createElement('div');
      wrap.className = 'password-wrap';
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'password-toggle';
      btn.textContent = '👁';
      btn.setAttribute('aria-label', 'Show password');
      btn.addEventListener('click', function(){
        var show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        btn.textContent = show ? '🙈' : '👁';
      });
      wrap.appendChild(btn);
    });
  })();

  // Live clock — East African Time (UTC+3)
  const cl = document.getElementById('live-clock');
  if(cl){ const tick=()=>{const n=new Date();cl.textContent=n.toLocaleTimeString('en-GB',{timeZone:'Africa/Nairobi',hour:'2-digit',minute:'2-digit',second:'2-digit'})};tick();setInterval(tick,1000); }
  // Auto-dismiss alerts
  document.querySelectorAll('.alert').forEach(a=>{setTimeout(()=>{a.style.transition='opacity .5s';a.style.opacity='0';setTimeout(()=>a.remove(),500)},7000)});
  // OTP input
  const otp=document.querySelector('.otp-input');
  if(otp){otp.addEventListener('input',function(){this.value=this.value.replace(/[^0-9]/g,'').slice(0,6)});otp.focus();}
  // Confirms
  document.querySelectorAll('form[action*="toggle-lock"]').forEach(f=>f.addEventListener('submit',e=>{if(!confirm('Change lock status for this user?'))e.preventDefault()}));
  document.querySelectorAll('form[action*="force-mfa"]').forEach(f=>f.addEventListener('submit',e=>{if(!confirm('Force MFA on next login?'))e.preventDefault()}));
  document.querySelectorAll('form[action*="cancel"]').forEach(f=>f.addEventListener('submit',e=>{if(!confirm('Cancel this item?'))e.preventDefault()}));
});

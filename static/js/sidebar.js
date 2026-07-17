/* Zero Trust EMR — Mobile sidebar drawer */
(function(){
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const openBtn = document.getElementById('sidebar-toggle');
  const closeBtn = document.getElementById('sidebar-close');
  if(!sidebar) return; // not authenticated / no sidebar on this page

  function openSidebar(){ sidebar.classList.add('open'); overlay.classList.add('show'); document.body.style.overflow='hidden'; }
  function closeSidebar(){ sidebar.classList.remove('open'); overlay.classList.remove('show'); document.body.style.overflow=''; }

  if(openBtn) openBtn.addEventListener('click', openSidebar);
  if(closeBtn) closeBtn.addEventListener('click', closeSidebar);
  if(overlay) overlay.addEventListener('click', closeSidebar);

  // Auto-close the drawer once a nav link is tapped (mobile UX)
  document.querySelectorAll('.sidebar .sidebar-nav a, .sidebar .sidebar-logout').forEach(function(link){
    link.addEventListener('click', closeSidebar);
  });

  // Clear mobile-only open state if the window is resized up to desktop width
  window.addEventListener('resize', function(){
    if(window.innerWidth >= 960) closeSidebar();
  });
})();

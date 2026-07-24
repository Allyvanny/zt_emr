/* Zero Trust EMR — Sidebar: mobile drawer + desktop collapse */
(function(){
  var sidebar    = document.getElementById('sidebar');
  var overlay    = document.getElementById('sidebar-overlay');
  var openBtn    = document.getElementById('sidebar-toggle');
  var closeBtn   = document.getElementById('sidebar-close');
  var collapseBtn= document.getElementById('sidebar-collapse-toggle');
  if(!sidebar) return;

  function openSidebar(){ sidebar.classList.add('open'); overlay.classList.add('show'); document.body.style.overflow='hidden'; }
  function closeSidebar(){ sidebar.classList.remove('open'); overlay.classList.remove('show'); document.body.style.overflow=''; }

  if(openBtn)  openBtn.addEventListener('click', openSidebar);
  if(closeBtn) closeBtn.addEventListener('click', closeSidebar);
  if(overlay)  overlay.addEventListener('click', closeSidebar);

  document.querySelectorAll('.sidebar .sidebar-nav a, .sidebar .sidebar-logout').forEach(function(link){
    link.addEventListener('click', closeSidebar);
  });

  window.addEventListener('resize', function(){
    if(window.innerWidth >= 960){ closeSidebar(); }
  });

  /* Desktop collapse/expand toggle */
  var collapsed = localStorage.getItem('zt-sidebar-collapsed') === '1';
  if(collapsed && window.innerWidth >= 960) sidebar.classList.add('collapsed');
  updateCollapseIcon();

  if(collapseBtn){
    collapseBtn.addEventListener('click', function(){
      sidebar.classList.toggle('collapsed');
      var isCollapsed = sidebar.classList.contains('collapsed');
      localStorage.setItem('zt-sidebar-collapsed', isCollapsed ? '1' : '0');
      updateCollapseIcon();
    });
  }

  function updateCollapseIcon(){
    if(!collapseBtn) return;
    collapseBtn.textContent = sidebar.classList.contains('collapsed') ? '▶' : '◀';
    collapseBtn.title = sidebar.classList.contains('collapsed') ? 'Expand sidebar' : 'Collapse sidebar';
  }
})();

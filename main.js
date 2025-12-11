(function(){
  const btn = document.getElementById('toggle-theme');
  if(!btn) return;
  const body = document.body;
  const stored = localStorage.getItem('theme');
  if(stored) body.className = stored;
  btn.addEventListener('click', ()=>{
    if(body.classList.contains('theme-light')){
      body.className = 'theme-navy';
      localStorage.setItem('theme','theme-navy');
    } else {
      body.className = 'theme-light';
      localStorage.setItem('theme','theme-light');
    }
  });
  document.querySelectorAll('.flash').forEach(el=>{
    setTimeout(()=>{
      el.style.transition = 'opacity 400ms ease, transform 400ms ease';
      el.style.opacity = '0';
      el.style.transform = 'translateY(-8px)';
    }, 4000);
  });
})();

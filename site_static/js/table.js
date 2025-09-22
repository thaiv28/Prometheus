(function(){
  const S = window.Prometheus.state;
  S.sort = { col: 'score', dir: 'desc' };

  function qs(s){ return document.querySelector(s); }
  function qsa(s){ return Array.from(document.querySelectorAll(s)); }

  function getRows(){ const el=document.querySelector('#metric-data'); if(!el) return []; try { return JSON.parse(el.textContent); } catch(e){ return []; } }

  function sortRows(rows){
    const { col, dir } = S.sort;
    return rows.slice().sort((a,b)=>{
      let av=a[col], bv=b[col];
      if(typeof av==='string') av=av.toLowerCase(); if(typeof bv==='string') bv=bv.toLowerCase();
      if(av < bv) return dir==='asc'?-1:1;
      if(av > bv) return dir==='asc'?1:-1;
      return 0;
    });
  }

  function rerender(){
    const body = qs('#rankings-body'); if(!body) return;
    const raw = getRows();
    const filtered = Array.from(document.querySelectorAll('#rankings-body tr')).map(tr=>({
      teamname: tr.children[1]?.textContent,
      score: parseFloat(tr.children[2]?.textContent) || 0,
      league: tr.children[3]?.textContent.trim(),
      year: tr.children[4]?.textContent.trim()
    }));
    const sorted = sortRows(filtered);
    body.innerHTML = sorted.map((r,i)=>`
      <tr data-year="${r.year}" data-league="${r.league}">
        <td class="rank-col">${i+1}</td>
        <td class="team-col">${r.teamname}</td>
        <td class="score-col">${Number(r.score).toFixed(2)}</td>
        <td>${r.league}</td>
        <td>${r.year}</td>
      </tr>`).join('');
  }

  function bindSort(){
    document.addEventListener('click', e=>{
      const th = e.target.closest('[data-sort]');
      if(!th) return;
      const col = th.getAttribute('data-sort');
      if(S.sort.col===col) S.sort.dir = S.sort.dir==='asc'?'desc':'asc'; else { S.sort.col=col; S.sort.dir='desc'; }
      qsa('thead th').forEach(h=>h.classList.remove('active-asc','active-desc'));
      th.classList.add(S.sort.dir==='asc'?'active-asc':'active-desc');
      rerender();
    });
  }

  window.addEventListener('prometheus:rows-updated', rerender);
  document.addEventListener('DOMContentLoaded', bindSort);
})();

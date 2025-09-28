(function(){
  const S = window.Prometheus.state;
  S.sort = { col: 'score', dir: 'desc' };

  function qs(s){ return document.querySelector(s); }
  function qsa(s){ return Array.from(document.querySelectorAll(s)); }

  function getRaw(){
    if(S.raw && S.raw.rows) return S.raw.rows; // populated by filters.js
    const el=document.querySelector('#metric-data'); if(!el) return []; try { return JSON.parse(el.textContent); } catch(e){ return []; }
  }

  function applyActiveFilters(rows){
    if(!S.filters) return rows;
    return rows.filter(r=>{
      if(S.filters.years?.size && !S.filters.years.has(String(r.year))) return false;
      if(S.filters.leagues?.size && !S.filters.leagues.has(String(r.league))) return false;
      if(S.filters.search){
        const s = S.filters.search.toLowerCase();
        if(!String(r.teamname).toLowerCase().includes(s)) return false;
      }
      return true;
    });
  }

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

  function format(num){ return typeof num==='number' ? num.toFixed(2) : ''; }

  function rerender(){
    const body = qs('#rankings-body'); if(!body) return;
    const base = getRaw();
    const filtered = applyActiveFilters(base);
    const sorted = sortRows(filtered);
    body.innerHTML = sorted.map((r,i)=>{
      const teamCell = r.slug ? `<a href="teams/${r.slug}.html" class="team-link">${r.teamname}</a>` : r.teamname;
      return `
      <tr data-year="${r.year}" data-league="${r.league}">
        <td class="rank-col">${i+1}</td>
        <td class="team-col">${teamCell}</td>
        <td class="score-col"><span class="tooltip" data-tooltip="Score: Composite metric 0-100">${format(Number(r.score))}</span></td>
        <td><span class="tooltip" data-tooltip="Era Z: Dominance vs global field">${format(Number(r.era_score))}</span></td>
        <td><span class="tooltip" data-tooltip="League Z: Dominance vs league field">${format(Number(r.league_score))}</span></td>
        <td><span class="badge league-${String(r.league).replace(/\s+/g,'')} tooltip" data-tooltip="League">${r.league}</span></td>
        <td><span class="tooltip" data-tooltip="Season Year">${r.year}</span></td>
      </tr>`;
    }).join('');
    if(!sorted.length){ body.innerHTML = '<tr><td colspan="7" class="empty-state">No results</td></tr>'; }
  }

  function bindSort(){
    document.addEventListener('click', e=>{
      const th = e.target.closest('[data-sort]');
      if(!th) return;
      const col = th.getAttribute('data-sort');
      if(!col) return;
      if(S.sort.col===col) S.sort.dir = S.sort.dir==='asc'?'desc':'asc'; else { S.sort.col=col; S.sort.dir='desc'; }
      qsa('thead th').forEach(h=>h.classList.remove('active-asc','active-desc'));
      th.classList.add(S.sort.dir==='asc'?'active-asc':'active-desc');
      rerender();
    });
  }

  window.addEventListener('prometheus:rows-updated', rerender);
  document.addEventListener('DOMContentLoaded', ()=>{ bindSort(); rerender(); });
})();

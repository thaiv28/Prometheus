 (function(){
  const S = window.Prometheus.state;
  S.filters = { years: new Set(), leagues: new Set(), search: '' };
  S.raw = {};
  let suppressUrl = false;

  function qs(sel){ return document.querySelector(sel); }
  function qsa(sel){ return Array.from(document.querySelectorAll(sel)); }

  function readData(){
    const el = qs('#metric-data');
    if(!el) return;
    try { S.raw.rows = JSON.parse(el.textContent); } catch(e){ S.raw.rows = []; }
  }

  function renderChips(){
    const wrap = qs('#active-filters'); if(!wrap) return;
    const chips = [];
    S.filters.years.forEach(y=>chips.push(`<span class="filter-chip" data-chip-year="${y}">${y}<button aria-label="Remove year ${y}" data-remove-year="${y}">×</button></span>`));
    S.filters.leagues.forEach(l=>chips.push(`<span class="filter-chip" data-chip-league="${l}">${l}<button aria-label="Remove league ${l}" data-remove-league="${l}">×</button></span>`));
    if(S.filters.search) chips.push(`<span class="filter-chip" data-chip-search>“${S.filters.search}”<button aria-label="Clear search" data-clear-search>×</button></span>`);
    wrap.innerHTML = chips.join('');
  }

  function serializeState(){
    if(suppressUrl) return;
    const params = new URLSearchParams();
    if(S.filters.years.size) params.set('years', Array.from(S.filters.years).join(','));
    if(S.filters.leagues.size) params.set('leagues', Array.from(S.filters.leagues).join(','));
    if(S.filters.search) params.set('search', S.filters.search);
    const newUrl = window.location.pathname + (params.toString()? ('?'+params.toString()):'');
    history.replaceState(null,'',newUrl);
  }

  function hydrateFromUrl(){
    const q = new URLSearchParams(window.location.search);
    const years = q.get('years');
    const leagues = q.get('leagues');
    const searchVal = q.get('search');
    if(years){ years.split(',').filter(Boolean).forEach(y=>S.filters.years.add(y)); }
    if(leagues){ leagues.split(',').filter(Boolean).forEach(l=>S.filters.leagues.add(l)); }
    if(searchVal){ S.filters.search = searchVal; const si=qs('#team-search'); if(si) si.value=searchVal; }
    // attempt to set selects to single value if only one selected
    const yearSel = qs('#year-filter');
    if(yearSel && S.filters.years.size===1){ yearSel.value=Array.from(S.filters.years)[0]; }
    const leagueSel = qs('#league-filter');
    if(leagueSel && S.filters.leagues.size===1){ leagueSel.value=Array.from(S.filters.leagues)[0]; }
  }

  // Update trigger text based on current selections
  function updateTriggerLabels(){
    const yearsTrigger = qs('#years-trigger');
    if(yearsTrigger){
      yearsTrigger.textContent = 'Years: ' + (S.filters.years.size ? Array.from(S.filters.years).sort().join(', ') : 'All');
    }
    const leaguesTrigger = qs('#leagues-trigger');
    if(leaguesTrigger){
      leaguesTrigger.textContent = 'Leagues: ' + (S.filters.leagues.size ? Array.from(S.filters.leagues).sort().join(', ') : 'All');
    }
  }

  // Sync checkboxes in custom dropdowns with filter state
  function syncCheckboxes(){
    qsa('[data-year-option]').forEach(cb=>{ cb.checked = S.filters.years.has(cb.value); });
    qsa('[data-league-option]').forEach(cb=>{ cb.checked = S.filters.leagues.has(cb.value); });
    updateTriggerLabels();
  }

  function applyFilters(){
    const rows = S.raw.rows || [];
    const years = S.filters.years; const leagues = S.filters.leagues; const search = S.filters.search.toLowerCase();
    const tbody = qs('#rankings-body'); if(!tbody) return;
    const filtered = rows.filter(r => {
      if(years.size && !years.has(String(r.year))) return false;
      if(leagues.size && !leagues.has(String(r.league))) return false;
      if(search && !String(r.teamname).toLowerCase().includes(search)) return false;
      return true;
    });
    tbody.innerHTML = filtered.map((r,i)=>`
      <tr data-year="${r.year}" data-league="${r.league}">
        <td class="rank-col">${i+1}</td>
        <td class="team-col">${r.teamname}</td>
        <td class="score-col"><span class="tooltip" data-tooltip="Score: Composite metric 0-100">${Number(r.score).toFixed(2)}</span></td>
        <td><span class="tooltip" data-tooltip="Era Z: Dominance vs global field">${Number(r.era_score).toFixed(2)}</span></td>
        <td><span class="tooltip" data-tooltip="League Z: Dominance vs league field">${Number(r.league_score).toFixed(2)}</span></td>
        <td><span class="badge league-${r.league.replace(/\s+/g,'')} tooltip" data-tooltip="League">${r.league}</span></td>
        <td><span class="tooltip" data-tooltip="Season Year">${r.year}</span></td>
      </tr>`).join('');
  qs('#results-count').textContent = filtered.length + ' rows';
    if(!filtered.length){ tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No results</td></tr>'; }
    window.dispatchEvent(new CustomEvent('prometheus:rows-updated',{detail:{count:filtered.length}}));
  renderChips();
  serializeState();
  }

  function replaceSetFromArray(set, arr){ set.clear(); arr.forEach(v=> set.add(v)); }

  function bindChips(){
    document.addEventListener('click', e=>{
      const yr = e.target.getAttribute('data-remove-year');
  if(yr){ S.filters.years.delete(yr); applyFilters(); syncCheckboxes(); return; }
      const lg = e.target.getAttribute('data-remove-league');
  if(lg){ S.filters.leagues.delete(lg); applyFilters(); syncCheckboxes(); return; }
  if(e.target.hasAttribute('data-clear-search')){ S.filters.search=''; const si=qs('#team-search'); if(si) si.value=''; applyFilters(); syncCheckboxes(); return; }
    });
  }

  function bindFilters(){
    const yearSel = qs('#year-filter');
    const leagueSel = qs('#league-filter');
    const search = qs('#team-search');
    const reset = qs('#reset-filters');
  // (helpers hoisted above)

  function togglePanel(trigger){
    const wrap = trigger.closest('.multi-select');
    const expanded = trigger.getAttribute('aria-expanded') === 'true';
    // close any other open panels first
    qsa('.multi-select .multi-trigger[aria-expanded="true"]').forEach(t=>{ if(t!==trigger){ t.setAttribute('aria-expanded','false'); t.closest('.multi-select').classList.remove('open'); }});
    if(!expanded){
      trigger.setAttribute('aria-expanded','true');
      wrap.classList.add('open');
    } else {
      trigger.setAttribute('aria-expanded','false');
      wrap.classList.remove('open');
    }
  }

  document.addEventListener('click', e=>{
    const trig = e.target.closest('.multi-trigger');
    if(trig){ togglePanel(trig); return; }
    // outside click close
    if(!e.target.closest('.multi-select')){
      qsa('.multi-select.open').forEach(ms=>{ ms.classList.remove('open'); const btn = ms.querySelector('.multi-trigger'); if(btn) btn.setAttribute('aria-expanded','false'); });
    }
  });

  document.addEventListener('change', e=>{
    if(e.target.matches('[data-year-option]')){
      if(e.target.checked) S.filters.years.add(e.target.value); else S.filters.years.delete(e.target.value);
      applyFilters(); syncCheckboxes();
    } else if(e.target.matches('[data-league-option]')){
      if(e.target.checked) S.filters.leagues.add(e.target.value); else S.filters.leagues.delete(e.target.value);
      applyFilters(); syncCheckboxes();
    }
  });

  document.addEventListener('click', e=>{
    const act = e.target.getAttribute('data-action');
    const target = e.target.getAttribute('data-target');
    if(act && target){
      if(act === 'select-all'){
        if(target==='years') { qsa('[data-year-option]').forEach(cb=> S.filters.years.add(cb.value)); }
        if(target==='leagues') { qsa('[data-league-option]').forEach(cb=> S.filters.leagues.add(cb.value)); }
      } else if(act === 'clear-all') {
        if(target==='years') S.filters.years.clear();
        if(target==='leagues') S.filters.leagues.clear();
      }
      applyFilters(); syncCheckboxes();
    }
  });

  function selectedValues(sel){ return Array.from(sel.selectedOptions).map(o=>o.value).filter(v=>v!=='ALL'); }
  if(yearSel){ yearSel.addEventListener('change', ()=>{ const vals = selectedValues(yearSel); if(vals.length===0){ S.filters.years.clear(); } else { replaceSetFromArray(S.filters.years, vals); } applyFilters(); }); }
  if(leagueSel){ leagueSel.addEventListener('change', ()=>{ const vals = selectedValues(leagueSel); if(vals.length===0){ S.filters.leagues.clear(); } else { replaceSetFromArray(S.filters.leagues, vals); } applyFilters(); }); }
    if(search){ search.addEventListener('input', e=>{ S.filters.search = e.target.value; applyFilters(); }); }
  if(reset){ reset.addEventListener('click', ()=>{ S.filters.years.clear(); S.filters.leagues.clear(); S.filters.search=''; if(search) search.value=''; if(yearSel){ Array.from(yearSel.options).forEach(o=>o.selected = false); } if(leagueSel){ Array.from(leagueSel.options).forEach(o=>o.selected = false); } applyFilters(); syncCheckboxes(); }); }
    bindChips();
  // initial sync for custom UI after URL hydration
  syncCheckboxes();
  }

  document.addEventListener('DOMContentLoaded', ()=>{ readData(); hydrateFromUrl(); bindFilters(); applyFilters(); });
})();

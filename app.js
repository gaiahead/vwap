'use strict';
const DATA_VERSION = 'data-etf-20260913-v4';
const LINES = Object.freeze([
  { label: '1일', window: 1, color: '#eab308' },
  { label: '20일', window: 20, color: '#dc2626' },
  { label: '60일', window: 60, color: '#16a34a' },
  { label: '240일', window: 240, color: '#2563eb' }
]);
const COLUMNS = [
  ['name','ETF 이름 / 티커'], ['category','분류'], ['issuer','운용사'],
  ['aum_krw','순자산, 억원'], ['avg_trading_value_20d_krw','20일 평균 거래대금, 억원 (추정)'],
  ['avg_volume_20d','20일 평균 거래량, 주']
];
function format(value, digits=2) {
  return value === null || value === undefined || value === '' || (typeof value === 'number' && !Number.isFinite(value))
    ? '-' : typeof value === 'number' ? value.toLocaleString('ko-KR',{maximumFractionDigits:digits}) : String(value);
}
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function selectEtfs(etfs, {query='',category='',issuer='',sort='name',dir='asc',minVolume=0}={}) {
  const terms=query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return etfs.filter(e=> {
    const text=[e.name,e.ticker,e.category,e.issuer,e.benchmark,e.exposure,e.holdings_text].filter(Boolean).join(' ').toLocaleLowerCase();
    return terms.every(t=>text.includes(t)) && (!category || (category==='__missing' ? !e.category : e.category===category)) &&
      (!issuer || (issuer==='__missing' ? !e.issuer : e.issuer===issuer)) &&
      (!(Number(minVolume)>0) || (e.avg_volume_20d!=null && e.avg_volume_20d>=Number(minVolume)));
  }).sort((a,b)=> {
    const av=a[sort],bv=b[sort];
    if(av==null || bv==null) return av==null && bv==null ? a.name.localeCompare(b.name,'ko') : av==null ? 1 : -1;
    const comparison=typeof av==='number' && typeof bv==='number' ? av-bv : String(av).localeCompare(String(bv),'ko');
    return comparison*(dir==='asc'?1:-1) || a.name.localeCompare(b.name,'ko');
  });
}
function sliceRange(rows, years=1) {
  if(!rows.length) return [];
  const end=new Date(rows.at(-1).date+'T00:00:00Z');
  const month=end.getUTCMonth();
  end.setUTCFullYear(end.getUTCFullYear()-years);
  if(end.getUTCMonth()!==month) end.setUTCDate(0);
  const cutoff=end.toISOString().slice(0,10);
  return rows.filter(row=>row.date>=cutoff);
}
function segmentWidth(values, start, end) {
  return Number.isFinite(values[start]) && Number.isFinite(values[end]) && values[end]<values[start] ? 1 : 2;
}
function chartData(rows) {
  return {labels:rows.map(r=>r.date),datasets:LINES.map(line=> {
    const data=rows.map(r=> { const value=r[`vwap_${line.window}d`]; return Number.isFinite(value) && value>0 ? value : null; });
    return {label:line.label,data,borderColor:line.color,backgroundColor:line.color,
      borderWidth:2,pointRadius:0,pointHitRadius:8,spanGaps:false,tension:0,
      segment:{borderWidth:ctx=>segmentWidth(data,ctx.p0DataIndex,ctx.p1DataIndex)}};
  })};
}
function updateRange(chart, rows, years) {
  chart.data=chartData(sliceRange(rows,years));
  chart.update();
}
if(typeof module!=='undefined') module.exports={COLUMNS,LINES,format,selectEtfs,sliceRange,segmentWidth,updateRange,chartData};

if(typeof document!=='undefined') {
  let etfs=[], selected=null, priceChart=null, profileChart=null, requestId=0;
  let sort='name',dir='asc';
  const cache=new Map();
  const el=id=>document.getElementById(id);
  const sourceLink=source=> {
    if(!source) return '-';
    const text=`기준 ${format(source.as_of)}${source.retrieved_at ? ', 수집 '+source.retrieved_at : ''}${source.note ? ', '+source.note : ''}`;
    return /^https:\/\//.test(source.url || '') ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(text)}</a>` : escapeHtml(text);
  };
  function cellValue(e,key) {
    const value=e[key];
    return format(value!=null && ['aum_krw','avg_trading_value_20d_krw'].includes(key) ? value/1e8 : value, key.includes('cost') || key.includes('expense') ? 4 : 2);
  }
  function renderTable() {
    const rows=selectEtfs(etfs,{query:el('search').value,category:el('category').value,issuer:el('issuer').value,
      minVolume:el('min-volume').value,sort,dir});
    el('count').textContent=`${rows.length} / ${etfs.length} ETFs`;
    el('etf-body').innerHTML=rows.map(e=>`<tr${e.ticker===selected?' class="selected"':''}>`+COLUMNS.map(([key])=>
      key==='name' ? `<td><button class="etf-link" data-ticker="${escapeHtml(e.ticker)}">${escapeHtml(e.name)}</button><small>${escapeHtml(e.ticker)}, 기준 ${escapeHtml(format(e.history_source.as_of))}</small></td>` :
      `<td>${escapeHtml(cellValue(e,key))}</td>`).join('')+'</tr>').join('') || `<tr><td colspan="${COLUMNS.length}">검색 결과가 없습니다.</td></tr>`;
    document.querySelectorAll('th[data-sort]').forEach(th=> {
      th.setAttribute('aria-sort',th.dataset.sort===sort ? dir==='asc'?'ascending':'descending':'none');
    });
  }
  function destroyCharts() {
    priceChart?.destroy(); profileChart?.destroy(); priceChart=null; profileChart=null;
  }
  async function showDetail(ticker) {
    const id=++requestId; selected=ticker; destroyCharts(); renderTable();
    el('detail-section').hidden=false; el('detail-title').textContent=etfs.find(e=>e.ticker===ticker).name;
    el('detail-content').textContent='ETF 상세 정보를 불러오는 중…';
    try {
      let detail=cache.get(ticker);
      if(!detail) {
        const response=await fetch(`detail_data/${encodeURIComponent(ticker)}.json?v=${DATA_VERSION}`);
        if(!response.ok) throw new Error('상세 데이터를 불러올 수 없습니다.');
        detail=await response.json(); cache.set(ticker,detail);
      }
      if(id!==requestId) return;
      renderDetail(detail);
      el('detail-section').scrollIntoView({behavior:'smooth',block:'start'});
      el('detail-title').focus({preventScroll:true});
    } catch(error) { if(id===requestId) el('detail-content').textContent=error.message; }
  }
  function renderDetail(detail) {
    const f=detail.facts, meta=detail._meta;
    const fields=[...COLUMNS.slice(1),['benchmark','기초지수'],['exposure','투자대상']];
    const sourceFor=key=> f.sources[key] || (['aum_krw','premium_discount_pct'].includes(key)?f.sources.market:
      key.startsWith('avg_')?f.sources.liquidity:['holdings_summary','top10_weight_pct'].includes(key)?f.sources.holdings:null);
    el('detail-content').innerHTML=`<p class="muted">${escapeHtml(detail.ticker)}, 가격 기준 ${escapeHtml(format(meta.as_of))}, ${meta.rows} 거래일, ${sourceLink(meta)}</p>
      ${meta.complete_history===false?'<p class="notice">캐시 데이터: 이전 이력이 누락될 수 있습니다. 전체 이력 다운로드가 필요합니다.</p>':''}
      <div class="facts">${fields.map(([key,label])=>`<div><dt>${label}</dt><dd>${escapeHtml(cellValue(f,key))}</dd><small>${sourceLink(sourceFor(key))}</small></div>`).join('')}</div>
      <h3>보유자산 분석</h3>
      <p class="muted">상위 10개 직접 주식 기준이며 ETF 전체 밸류에이션과 다를 수 있습니다. 유효한 양수 값의 보유비중을 재정규화한 가중 조화평균입니다. 비중은 ETF 전체 대비이며, 기준일은 보유자산 기준입니다.</p>
      <div class="facts">${['per','pbr'].map(key=> {
        const v=f.valuation?.[key];
        return `<div><dt>상위 10개 기준 ${key.toUpperCase()}</dt><dd>${escapeHtml(format(v?.value))} <small>유효 ${v?.valid_count??0}/${v?.top10_count??0}, 비중 ${format(v?.covered_weight_pct)}%</small></dd><small>${escapeHtml((v?.basis??[]).join(', ') || '-')}</small></div>`;
      }).join('')}</div><p class="muted">${sourceLink(f.sources.holdings)}</p>
      <div class="holdings">${f.holdings.length?'<ol>'+f.holdings.map(h=>`<li>${escapeHtml(h.name)} (${escapeHtml(format(h.symbol || h.ticker))}) <strong>${escapeHtml(format(h.weight_pct))}%</strong>, PER ${format(h.per?.value)}, PBR ${format(h.pbr?.value)}<small>PER ${escapeHtml(h.per?.basis || '-')} ${escapeHtml(h.per?.period || '')}, PBR ${escapeHtml(h.pbr?.basis || '-')} ${escapeHtml(h.pbr?.period || '')}, ${sourceLink(h.source)}</small></li>`).join('')+'</ol>':'-'}</div>
      <h3>VWAP 가격 차트, 로그 스케일</h3><div id="range-controls" class="controls" role="group" aria-label="차트 범위">${[1,5,10].map(y=>`<button data-years="${y}" aria-pressed="${y===1}">${y}년</button>`).join('')}</div>
      <p id="chart-dates" class="muted" aria-live="polite"></p><div class="chart-wrap"><canvas id="price-chart" role="img" aria-label="ETF VWAP 가격 차트"></canvas></div>
      <p class="muted">일봉 대표가격 (고가 + 저가 + 종가) / 3의 거래량 가중평균입니다. 기간별 준비구간과 거래량이 없는 구간은 비어 있습니다.</p>
      <h3>Volume Profile</h3><p class="muted">최근 거래일 기준 일봉에서 추정한 가격대별 거래량입니다.</p>
      <div id="vp-controls" class="controls" role="group" aria-label="Volume Profile 기간">${LINES.map(l=>`<button data-period="${l.window}" aria-pressed="${l.window===1}">${l.label}</button>`).join('')}</div>
      <p id="vp-status" class="muted"></p><div class="chart-wrap profile"><canvas id="profile-chart" role="img" aria-label="가격대별 추정 거래량"></canvas></div>`;
    function dates(years) {
      const rows=sliceRange(detail.ohlcv,years);
      el('chart-dates').textContent=rows.length?`${rows[0].date} ~ ${rows.at(-1).date}, ${rows.length} 거래일`:'가격 데이터가 없습니다.';
    }
    dates(1);
    if(typeof Chart==='undefined') { el('chart-dates').textContent+=' 차트 라이브러리를 불러오지 못했습니다.'; return; }
    priceChart=new Chart(el('price-chart'),{type:'line',data:chartData(sliceRange(detail.ohlcv,1)),options:{responsive:true,maintainAspectRatio:false,animation:false,
      interaction:{mode:'index',axis:'x',intersect:false},scales:{x:{ticks:{maxTicksLimit:8}},y:{type: 'logarithmic',ticks:{callback:value=>format(value)}}}}});
    el('range-controls').addEventListener('click',event=> {
      const button=event.target.closest('[data-years]'); if(!button) return;
      const years=Number(button.dataset.years); updateRange(priceChart,detail.ohlcv,years); dates(years);
      el('range-controls').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
    });
    function profile(period) {
      profileChart?.destroy(); profileChart=null;
      const p=detail.volume_profile[`${period}d`];
      el('vp-status').textContent=p?'':'해당 기간의 데이터가 부족합니다.';
      if(!p) return;
      profileChart=new Chart(el('profile-chart'),{type:'bar',data:{labels:p.buckets.map(b=>format(b.price)),datasets:[{label:'추정 거래량',data:p.buckets.map(b=>b.volume),backgroundColor:LINES.find(l=>l.window===period).color}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false}}}});
    }
    profile(1);
    el('vp-controls').addEventListener('click',event=> {
      const b=event.target.closest('[data-period]'); if(!b) return;
      profile(Number(b.dataset.period)); el('vp-controls').querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
    });
  }
  el('etf-head').innerHTML=COLUMNS.map(([key,label])=>`<th data-sort="${key}" scope="col" aria-sort="none"><button>${label} ↕</button></th>`).join('');
  el('etf-head').addEventListener('click',event=> {
    const th=event.target.closest('th[data-sort]'); if(!th) return;
    dir=sort===th.dataset.sort && dir==='asc'?'desc':'asc'; sort=th.dataset.sort; renderTable();
  });
  el('etf-body').addEventListener('click',event=> {
    const b=event.target.closest('[data-ticker]'); if(b) showDetail(b.dataset.ticker);
  });
  ['search','category','issuer','min-volume'].forEach(id=>el(id).addEventListener('input',renderTable));
  el('reset').addEventListener('click',()=> { ['search','category','issuer','min-volume'].forEach(id=>el(id).value=''); renderTable(); });
  el('detail-close').addEventListener('click',()=> {
    const previous=selected; ++requestId; selected=null; destroyCharts(); el('detail-section').hidden=true; renderTable();
    document.querySelector(`[data-ticker="${previous}"]`)?.focus();
  });
  fetch(`trend_data.json?v=${DATA_VERSION}`).then(response=> {if(!response.ok) throw new Error('ETF 목록을 불러올 수 없습니다.');return response.json();}).then(data=> {
    etfs=data.etfs;
    el('updated').textContent=`생성 ${data._meta.updated_at}`;
    el('status').textContent=`시장 정보: ${data._meta.market_status==='available'?'수집됨':'미수집'}, 전체 이력 미확인 ${data._meta.incomplete_history_count} ETFs`;
    ['category','issuer'].forEach(key=> {
      [...new Set(etfs.map(e=>e[key]).filter(Boolean))].sort().forEach(value=> {
        const option=document.createElement('option'); option.value=value; option.textContent=value; el(key).append(option);
      });
      const missing=document.createElement('option');missing.value='__missing';missing.textContent='정보 없음';el(key).append(missing);
    });
    renderTable();
  }).catch(error=> {el('status').textContent=error.message;});
}

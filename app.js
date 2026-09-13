'use strict';
const DATA_VERSION = 'data-etf-20260913-v9';
const LINES = Object.freeze([
  { label: '1일', window: 1, color: '#eab308' },
  { label: '20일', window: 20, color: '#dc2626' },
  { label: '60일', window: 60, color: '#16a34a' },
  { label: '240일', window: 240, color: '#2563eb' }
]);
const COLUMNS = [
  ['name','ETF 이름 / 티커'], ['category','분류'],
  ['aum_krw','순자산, 억원'], ['avg_trading_value_20d_krw','20일 평균 거래대금, 억원 (추정)'],
  ['avg_volume_20d','20일 평균 거래량, 주']
];
function format(value, digits=2) {
  return value === null || value === undefined || value === '' || (typeof value === 'number' && !Number.isFinite(value))
    ? '-' : typeof value === 'number' ? value.toLocaleString('ko-KR',{maximumFractionDigits:digits}) : String(value);
}
function cellValue(e,key) {
  const value=e[key];
  const scaled=value!=null && ['aum_krw','avg_trading_value_20d_krw'].includes(key) ? value/1e8 : value;
  const digits=['avg_trading_value_20d_krw','avg_volume_20d'].includes(key) ? 0 :
    key.includes('cost') || key.includes('expense') ? 4 : 2;
  return format(scaled,digits);
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
function xTickLabel(value,index,ticks) {
  const last=ticks.length-1;
  const step=Math.max(1,Math.ceil(last/7));
  return index===0 || index===last || index%step===0 ? this.getLabelForValue(value) : '';
}
function xTickIndexes(length,maxTicks=8) {
  if(length<=0) return [];
  if(length<=maxTicks) return Array.from({length},(_,index)=>index);
  return [...new Set(Array.from({length:maxTicks},(_,index)=>Math.round(index*(length-1)/(maxTicks-1))))];
}
function selectedValues(rows,index) {
  const row=rows[index];
  if(!row) return null;
  return {date:row.date,values:LINES.map(line=>[line.label,format(row[`vwap_${line.window}d`],0),line.color])};
}
const selectedDateLine={
  id:'selected-date-line',
  afterDatasetsDraw(chart) {
    if(!Number.isInteger(chart.$selectedIndex)) return;
    const {left,right,top,bottom}=chart.chartArea;
    const x=Math.max(left+0.75,Math.min(right-0.75,chart.scales.x.getPixelForValue(chart.$selectedIndex)));
    chart.ctx.save(); chart.ctx.beginPath(); chart.ctx.moveTo(x,top); chart.ctx.lineTo(x,bottom);
    chart.ctx.lineWidth=1.5; chart.ctx.strokeStyle='#111827'; chart.ctx.stroke(); chart.ctx.restore();
  }
};
function updateRange(chart, rows, years) {
  chart.$rows=sliceRange(rows,years);
  chart.$selectedIndex=null;
  chart.data=chartData(chart.$rows);
  chart.update();
}
if(typeof module!=='undefined') module.exports={COLUMNS,LINES,format,cellValue,selectEtfs,sliceRange,segmentWidth,updateRange,chartData,xTickLabel,xTickIndexes,selectedValues};

if(typeof document!=='undefined') {
  let etfs=[], selected=null, priceChart=null, requestId=0, cleanupChartInteractions=null;
  let sort='name',dir='asc';
  const cache=new Map();
  const el=id=>document.getElementById(id);


  function renderTable() {
    const rows=selectEtfs(etfs,{query:el('search').value,category:el('category').value,issuer:el('issuer').value,
      minVolume:el('min-volume').value,sort,dir});
    el('count').textContent=`${rows.length} / ${etfs.length} ETFs`;
    el('etf-body').innerHTML=rows.map(e=>`<tr${e.ticker===selected?' class="selected"':''}>`+COLUMNS.map(([key])=>
      key==='name' ? `<td><button class="etf-link" data-ticker="${escapeHtml(e.ticker)}">${escapeHtml(e.name)}</button><small>${escapeHtml(e.ticker)}</small></td>` :
      `<td>${escapeHtml(cellValue(e,key))}</td>`).join('')+'</tr>').join('') || `<tr><td colspan="${COLUMNS.length}">검색 결과가 없습니다.</td></tr>`;
    document.querySelectorAll('th[data-sort]').forEach(th=> {
      th.setAttribute('aria-sort',th.dataset.sort===sort ? dir==='asc'?'ascending':'descending':'none');
    });
  }
  function destroyCharts() {
    cleanupChartInteractions?.(); cleanupChartInteractions=null;
    priceChart?.destroy(); priceChart=null;
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
    const fields=[COLUMNS[1],['issuer','운용사'],...COLUMNS.slice(2),['benchmark','기초지수'],['exposure','투자대상']];
    el('detail-content').innerHTML=`<p class="muted">${escapeHtml(detail.ticker)}, ${escapeHtml(format(meta.as_of))}, ${meta.rows} 거래일</p>
      ${meta.complete_history===false?'<p class="notice">캐시 데이터: 이전 이력이 누락될 수 있습니다. 전체 이력 다운로드가 필요합니다.</p>':''}
      <div class="facts">${fields.map(([key,label])=>`<div><dt>${label}</dt><dd>${escapeHtml(cellValue(f,key))}</dd></div>`).join('')}</div>
      <h3>보유자산 분석</h3>
      <p class="muted">상위 10개 직접 주식의 보유비중 가중 조화평균입니다. 0 이하와 미확인 값은 제외합니다.</p>
      <div class="facts valuation">${['pbr','per'].map(key=> {
        const v=f.valuation?.[key];
        return `<div><dt>${key.toUpperCase()}</dt><dd>${escapeHtml(format(v?.value))}</dd><small>유효 ${v?.valid_count??0}/${v?.top10_count??0}</small></div>`;
      }).join('')}</div>
      <div class="holdings">${f.holdings.length?'<ol>'+f.holdings.map(h=>`<li>${escapeHtml(h.name)} (${escapeHtml(format(h.symbol || h.ticker))}) <strong>${escapeHtml(format(h.weight_pct))}%</strong>, PBR ${format(h.pbr?.value)}, PER ${format(h.per?.value)}</li>`).join('')+'</ol>':'-'}</div>
      <h3>VWAP 가격 차트, 로그 스케일</h3><div id="range-controls" class="controls" role="group" aria-label="차트 범위">${[1,5,10].map(y=>`<button data-years="${y}" aria-pressed="${y===1}">${y}년</button>`).join('')}</div>
      <p id="chart-dates" class="muted" aria-live="polite"></p><div class="chart-wrap"><canvas id="price-chart" role="img" aria-label="ETF VWAP 가격 차트"></canvas></div>
      <div id="chart-selection" class="chart-selection" aria-live="polite">차트에서 날짜를 선택하세요.</div>
      <p class="muted">일봉 대표가격 (고가 + 저가 + 종가) / 3의 거래량 가중평균입니다. 기간별 준비구간과 거래량이 없는 구간은 비어 있습니다.</p>`;
    function dates(years) {
      const rows=sliceRange(detail.ohlcv,years);
      el('chart-dates').textContent=rows.length?`${rows[0].date} ~ ${rows.at(-1).date}, ${rows.length} 거래일`:'가격 데이터가 없습니다.';
    }
    dates(1);
    if(typeof Chart==='undefined') { el('chart-dates').textContent+=' 차트 라이브러리를 불러오지 못했습니다.'; return; }
    const initialRows=sliceRange(detail.ohlcv,1);
    const selectChartIndex=(chart,index)=> {
      if(!Number.isInteger(index) || index<0 || index>=chart.$rows.length) return;
      chart.$selectedIndex=index;
      const selection=selectedValues(chart.$rows,index);
      el('chart-selection').innerHTML=`<strong>선택일 ${escapeHtml(selection.date)}</strong>${selection.values.map(([label,value,color])=>`<span><i style="background:${color}"></i>${label} ${escapeHtml(value)}원</span>`).join('')}`;
      chart.draw();
    };
    priceChart=new Chart(el('price-chart'),{type:'line',data:chartData(initialRows),plugins:[selectedDateLine],options:{responsive:true,maintainAspectRatio:false,animation:false,
      interaction:{mode:'index',axis:'x',intersect:false},plugins:{tooltip:{enabled:false}},
      scales:{x:{afterBuildTicks:axis=> { const maxTicks=axis.chart.width<600?3:8; axis.ticks=xTickIndexes(axis.chart.data.labels.length,maxTicks).map(value=>({value})); },ticks:{autoSkip:false,callback:xTickLabel,maxRotation:0}},y:{type: 'logarithmic',ticks:{callback:value=>format(value)}}}}});
    priceChart.$rows=initialRows;
    const chart=priceChart, canvas=chart.canvas, controls=el('range-controls');
    let activePointer=null;
    const selectChartClientX=clientX=> {
      const rect=canvas.getBoundingClientRect();
      if(!chart.$rows.length || rect.width<=0) return;
      const pixel=(clientX-rect.left)*(chart.width/rect.width);
      const index=Math.round(chart.scales.x.getValueForPixel(pixel));
      if(!Number.isFinite(index)) return;
      selectChartIndex(chart,Math.max(0,Math.min(chart.$rows.length-1,index)));
    };
    const cancelDrag=()=> {
      const pointer=activePointer;
      activePointer=null;
      if(pointer!==null && canvas.hasPointerCapture(pointer)) canvas.releasePointerCapture(pointer);
    };
    const handlers={
      pointerdown:event=> {
        if(activePointer!==null || event.isPrimary===false || event.button!==0) return;
        activePointer=event.pointerId;
        canvas.setPointerCapture(activePointer);
        selectChartClientX(event.clientX);
      },
      pointermove:event=> {
        if(event.pointerId===activePointer) selectChartClientX(event.clientX);
      },
      pointerup:event=> {
        if(event.pointerId!==activePointer) return;
        selectChartClientX(event.clientX);
        cancelDrag();
      },
      pointercancel:event=> { if(event.pointerId===activePointer) cancelDrag(); },
      lostpointercapture:event=> { if(event.pointerId===activePointer) cancelDrag(); }
    };
    Object.entries(handlers).forEach(([type,handler])=>canvas.addEventListener(type,handler));
    const changeRange=event=> {
      const button=event.target.closest('[data-years]'); if(!button) return;
      cancelDrag();
      const years=Number(button.dataset.years); updateRange(chart,detail.ohlcv,years); dates(years);
      el('chart-selection').textContent='차트에서 날짜를 선택하세요.';
      controls.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
    };
    controls.addEventListener('click',changeRange);
    cleanupChartInteractions=()=> {
      cancelDrag();
      Object.entries(handlers).forEach(([type,handler])=>canvas.removeEventListener(type,handler));
      controls.removeEventListener('click',changeRange);
    };
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
    el('status').textContent=data._meta.incomplete_history_count ? `전체 이력 확인 필요 ${data._meta.incomplete_history_count} ETFs` : '';
    ['category','issuer'].forEach(key=> {
      [...new Set(etfs.map(e=>e[key]).filter(Boolean))].sort().forEach(value=> {
        const option=document.createElement('option'); option.value=value; option.textContent=value; el(key).append(option);
      });
      const missing=document.createElement('option');missing.value='__missing';missing.textContent='정보 없음';el(key).append(missing);
    });
    renderTable();
  }).catch(error=> {el('status').textContent=error.message;});
}

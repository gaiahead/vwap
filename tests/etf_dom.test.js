// Minimal DOM boundary harness: executes production event handlers without a browser.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const nodes=new Map();
class Element {
  constructor(id='') { this.id=id;this.value='';this.checked=false;this.hidden=false;this.dataset={};this.attrs={};this.listeners={};this.children=[]; }
  addEventListener(type,fn) { assert.equal(this.listeners[type],undefined,`duplicate ${type} listener`);this.listeners[type]=fn; }
  removeEventListener(type,fn) { if(this.listeners[type]===fn) delete this.listeners[type]; }
  setPointerCapture(id) { this.captured=id; }
  hasPointerCapture(id) { return this.captured===id; }
  releasePointerCapture(id) { assert.equal(this.captured,id);this.captured=null;this.listeners.lostpointercapture?.({pointerId:id}); }
  dispatch(type,event={}) { this.listeners[type]?.(event); }
  setAttribute(key,value) { this.attrs[key]=value; }
  append(child) { this.children.push(child); }
  focus() { this.focused=true; }
  scrollIntoView() {}
  closest() { return this; }
  getBoundingClientRect() { return this.rect || {left:0,width:100}; }
  querySelectorAll() { return this.children; }
  set innerHTML(html) {
    this.html=html;this.children=[];
    for(const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) nodes.set(match[1],new Element(match[1]));
    for(const match of html.matchAll(/<th data-sort="([^"]+)"[^>]*>/g)) {
      const th=new Element();th.dataset.sort=match[1];this.children.push(th);
    }
    for(const [id,key] of [['range-controls','years']]) {
      if(!html.includes(`id="${id}"`)) continue;
      const group=nodes.get(id);
      for(const match of html.matchAll(new RegExp(`<button data-${key}="([^"]+)" aria-pressed="([^"]+)"`,'g'))) {
        const button=new Element();button.dataset[key]=match[1];button.attrs['aria-pressed']=match[2];group.children.push(button);
      }
    }
  }
  get innerHTML() { return this.html; }
}
for(const id of ['search','category','issuer','min-volume','count','etf-head','etf-body','reset','detail-close','detail-section','detail-content','detail-title','updated','status']) nodes.set(id,new Element(id));
const document={getElementById:id=>nodes.get(id),createElement:()=>new Element(),
  querySelectorAll:()=>nodes.get('etf-head').children,querySelector:()=>null};
const trend=JSON.parse(fs.readFileSync('trend_data.json'));
const requests=[];const charts=[];
class Chart {
  constructor(canvas,config) {
    this.canvas=canvas;this.config=config;this.data=config.data;this.updates=0;this.width=100;
    this.chartArea={left:10,right:90,top:5,bottom:80};
    this.scales={x:{
      getValueForPixel:pixel=>(pixel-10)/80*(this.data.labels.length-1),
      getPixelForValue:index=>10+80*index/Math.max(1,this.data.labels.length-1)
    }};
    this.strokes=[];
    this.ctx={save(){},restore(){},beginPath(){},
      moveTo:(x,y)=>{this.start=[x,y];},lineTo:(x,y)=>{this.end=[x,y];},
      stroke:()=>this.strokes.push({start:this.start,end:this.end,width:this.ctx.lineWidth,color:this.ctx.strokeStyle})};
    charts.push(this);
  }
  update() { this.updates++; }
  draw() { this.draws=(this.draws||0)+1;this.config.plugins.forEach(plugin=>plugin.afterDatasetsDraw?.(this)); }
  getElementsAtEventForMode() { return [{index:2}]; }
  destroy() { this.destroyed=true; }
}
const fetch=async url=> {
  requests.push(url);
  return {ok:true,json:async()=>JSON.parse(fs.readFileSync(url.split('?')[0]))};
};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const click=(id,target)=>nodes.get(id).listeners.click({target});
(async()=> {
  vm.runInNewContext(fs.readFileSync('app.js','utf8'),{document,Chart,fetch,console});
  await flush();await flush();
  assert.equal(nodes.get('count').textContent,'55 / 55 ETFs');
  nodes.get('search').value='Nvidia';nodes.get('search').listeners.input();
  assert.equal(nodes.get('count').textContent,`${trend.etfs.filter(e=>(e.holdings_text||'').toLowerCase().includes('nvidia')).length} / 55 ETFs`);
  click('reset');
  const sortHeader=nodes.get('etf-head').children.find(th=>th.dataset.sort==='avg_volume_20d');
  click('etf-head',sortHeader);
  assert.equal(sortHeader.attrs['aria-sort'],'ascending');
  click('etf-head',sortHeader);
  assert.equal(sortHeader.attrs['aria-sort'],'descending');
  const button=new Element();button.dataset.ticker='069500.KS';
  click('etf-body',button);await flush();await flush();
  assert.equal(nodes.get('detail-section').hidden,false);
  assert.equal(nodes.get('detail-title').focused,true);
  const price=charts.find(c=>c.canvas.id==='price-chart');
  assert.equal(price.config.options.scales.y.type,'logarithmic');
  assert.equal(price.config.options.plugins.tooltip.enabled,false);
  assert.equal(price.config.options.scales.x.ticks.autoSkip,false);
  assert.ok(price.config.plugins.some(plugin=>plugin.id==='selected-date-line'));
  const canvas=price.canvas;
  canvas.rect={left:40,width:200}; // CSS width differs from Chart.js logical width.
  const pointer=(type,x,id=1,pointerType='mouse',button=0)=>canvas.dispatch(type,{clientX:x,pointerId:id,pointerType,button,isPrimary:true});
  const expectSelection=index=> {
    assert.equal(price.$selectedIndex,index);
    const row=price.$rows[index];
    assert.ok(nodes.get('chart-selection').innerHTML.includes(row.date));
    for(const key of ['vwap_1d','vwap_20d','vwap_60d','vwap_240d']) {
      const value=row[key];
      const formatted=value==null?'-':value.toLocaleString('ko-KR',{maximumFractionDigits:0});
      assert.ok(nodes.get('chart-selection').innerHTML.includes(`${formatted}원`));
    }
    const stroke=price.strokes.at(-1);
    assert.equal(stroke.color,'#111827');
    assert.ok(stroke.start[0]-stroke.width/2>=price.chartArea.left,'whole edge marker inside plot');
    assert.ok(stroke.start[0]+stroke.width/2<=price.chartArea.right,'whole edge marker inside plot');
    assert.deepEqual([stroke.start[1],stroke.end[1]],[5,80]);
  };
  pointer('pointermove',140);
  assert.equal(price.$selectedIndex,undefined,'hover does not select');
  for(const kind of ['mouse','touch']) {
    pointer('pointerdown',60,1,kind);
    assert.equal(canvas.captured,1,'drag captures pointer');
    expectSelection(0);
    pointer('pointermove',140,2,kind);
    expectSelection(0); // Another pointer cannot hijack the drag.
    pointer('pointermove',140,1,kind);
    expectSelection(Math.round((price.$rows.length-1)/2));
    pointer('pointermove',220,1,kind);
    expectSelection(price.$rows.length-1);
    pointer('pointermove',1000,1,kind);
    expectSelection(price.$rows.length-1);
    pointer('pointermove',-1000,1,kind);
    expectSelection(0);
    pointer('pointerup',220,1,kind);
    expectSelection(price.$rows.length-1);
    assert.equal(canvas.captured,null);
    const draws=price.draws;
    pointer('pointermove',60,1,kind);
    assert.equal(price.draws,draws,'selection persists after release');
  }
  for(const end of ['pointercancel','lostpointercapture']) {
    pointer('pointerdown',140);
    if(end==='lostpointercapture') canvas.captured=null;
    pointer(end,140);
    const draws=price.draws;
    pointer('pointermove',60);
    pointer('pointerup',60);
    assert.equal(price.draws,draws,`${end} stops selection`);
    assert.equal(canvas.captured,null);
  }
  const draws=price.draws;
  pointer('pointerdown',60,1,'mouse',2);
  assert.equal(price.draws,draws,'ignore secondary mouse button');
  const savedRows=price.$rows,savedData=price.data;
  price.$rows=[];price.data={labels:[]};price.$selectedIndex=null;
  pointer('pointerdown',140);pointer('pointermove',1000);pointer('pointerup',60);
  assert.equal(price.$selectedIndex,null,'empty data cannot select');
  price.$rows=[savedRows[0]];price.data={labels:[savedRows[0].date]};
  pointer('pointerdown',-1000);expectSelection(0);
  pointer('pointermove',1000);expectSelection(0);pointer('pointerup',1000);
  price.$rows=savedRows;price.data=savedData;
  canvas.rect.width=0;
  const beforeZeroWidth=price.draws;
  pointer('pointerdown',140);pointer('pointerup',140);
  assert.equal(price.draws,beforeZeroWidth,'ignore zero-width canvas');
  canvas.rect.width=200;
  assert.match(fs.readFileSync('style.css','utf8'),/#price-chart\s*\{[^}]*touch-action:\s*none/);
  assert.ok(nodes.get('detail-content').innerHTML.includes('보유자산 분석'));
  assert.ok(nodes.get('detail-content').innerHTML.includes('운용사'));
  const controls=nodes.get('range-controls');
  assert.deepEqual(controls.children.map(b=>b.dataset.years),['1','5','10']);
  assert.deepEqual(controls.children.map(b=>b.attrs['aria-pressed']),['true','false','false']);
  const original=price.data.labels.length;
  pointer('pointerdown',140);
  click('range-controls',controls.children[1]);
  assert.equal(canvas.captured,null,'range change releases capture');
  assert.equal(price.$selectedIndex,null);
  const rangeDraws=price.draws;pointer('pointermove',60);pointer('pointerup',60);
  assert.equal(price.draws,rangeDraws,'old drag cannot select after range change');
  assert.equal(price.updates,1);
  assert.ok(price.data.labels.length>original);
  assert.equal(controls.children[1].attrs['aria-pressed'],'true');
  assert.equal(controls.children[0].attrs['aria-pressed'],'false');
  assert.deepEqual(Array.from(price.data.datasets,d=>d.label),['1일','20일','60일','240일']);
  pointer('pointerdown',140);
  click('detail-close');
  assert.equal(canvas.captured,null,'close releases capture');
  assert.deepEqual(Object.keys(canvas.listeners),[],'close removes chart handlers');
  assert.deepEqual(Object.keys(controls.listeners),[],'close removes range handler');
  assert.equal(nodes.get('detail-section').hidden,true);
  assert.equal(price.destroyed,true);
  click('etf-body',button);await flush();
  assert.equal(requests.filter(url=>url.startsWith('detail_data/')).length,1);
  const reopened=charts.filter(c=>c.canvas.id==='price-chart').at(-1);
  assert.equal(reopened.data.labels.length,original);
  const reopenDraws=reopened.draws;
  pointer('pointermove',60);pointer('pointerup',60);
  controls.dispatch('click',{target:controls.children[2]});
  assert.equal(reopened.draws,reopenDraws,'detached handlers cannot affect reopened chart');
  reopened.canvas.dispatch('pointerdown',{clientX:50,pointerId:3,button:0,isPrimary:true});
  assert.equal(reopened.draws,1,'reopened chart selects once');
  click('detail-close');
  assert.equal(reopened.canvas.captured,null);
  assert.deepEqual(Object.keys(reopened.canvas.listeners),[]);
  assert.equal(trend.etfs.length,55);
  console.log('Production DOM handlers: search, sorting, detail, ranges, close and cache passed');
})().catch(error=>{console.error(error);process.exitCode=1;});

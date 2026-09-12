// Minimal DOM boundary harness: executes production event handlers without a browser.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const nodes=new Map();
class Element {
  constructor(id='') { this.id=id;this.value='';this.checked=false;this.hidden=false;this.dataset={};this.attrs={};this.listeners={};this.children=[]; }
  addEventListener(type,fn) { this.listeners[type]=fn; }
  setAttribute(key,value) { this.attrs[key]=value; }
  append(child) { this.children.push(child); }
  focus() { this.focused=true; }
  scrollIntoView() {}
  closest() { return this; }
  querySelectorAll() { return this.children; }
  set innerHTML(html) {
    this.html=html;this.children=[];
    for(const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) nodes.set(match[1],new Element(match[1]));
    for(const match of html.matchAll(/<th data-sort="([^"]+)"[^>]*>/g)) {
      const th=new Element();th.dataset.sort=match[1];this.children.push(th);
    }
    for(const [id,key] of [['range-controls','years'],['vp-controls','period']]) {
      if(!html.includes(`id="${id}"`)) continue;
      const group=nodes.get(id);
      for(const match of html.matchAll(new RegExp(`<button data-${key}="([^"]+)" aria-pressed="([^"]+)"`,'g'))) {
        const button=new Element();button.dataset[key]=match[1];button.attrs['aria-pressed']=match[2];group.children.push(button);
      }
    }
  }
  get innerHTML() { return this.html; }
}
for(const id of ['search','category','issuer','has-fees','min-volume','count','etf-head','etf-body','reset','detail-close','detail-section','detail-content','detail-title','updated','status']) nodes.set(id,new Element(id));
const document={getElementById:id=>nodes.get(id),createElement:()=>new Element(),
  querySelectorAll:()=>nodes.get('etf-head').children,querySelector:()=>null};
const trend=JSON.parse(fs.readFileSync('trend_data.json'));
const requests=[];const charts=[];
class Chart {
  constructor(canvas,config) { this.canvas=canvas;this.data=config.data;this.updates=0;charts.push(this); }
  update() { this.updates++; }
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
  assert.equal(nodes.get('count').textContent,'1 / 55 ETFs');
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
  const controls=nodes.get('range-controls');
  assert.deepEqual(controls.children.map(b=>b.dataset.years),['1','5','10']);
  assert.deepEqual(controls.children.map(b=>b.attrs['aria-pressed']),['true','false','false']);
  const original=price.data.labels.length;
  click('range-controls',controls.children[1]);
  assert.equal(price.updates,1);
  assert.ok(price.data.labels.length>original);
  assert.equal(controls.children[1].attrs['aria-pressed'],'true');
  assert.equal(controls.children[0].attrs['aria-pressed'],'false');
  assert.deepEqual(Array.from(price.data.datasets,d=>d.label),['1일','20일','60일','240일']);
  click('detail-close');
  assert.equal(nodes.get('detail-section').hidden,true);
  assert.equal(price.destroyed,true);
  click('etf-body',button);await flush();
  assert.equal(requests.filter(url=>url.startsWith('detail_data/')).length,1);
  const reopened=charts.filter(c=>c.canvas.id==='price-chart').at(-1);
  assert.equal(reopened.data.labels.length,original);
  assert.equal(trend.etfs.length,55);
  console.log('Production DOM handlers: search, sorting, detail, ranges, close and cache passed');
})().catch(error=>{console.error(error);process.exitCode=1;});

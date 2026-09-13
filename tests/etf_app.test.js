const assert = require('node:assert/strict');
const api = require('../app.js');
assert.deepEqual(api.LINES.map(x=>[x.label,x.color]), [['1일','#eab308'],['20일','#dc2626'],['60일','#16a34a'],['240일','#2563eb']]);
const rows=['2015-09-11','2016-09-12','2021-09-11','2021-09-12','2025-09-11','2025-09-12','2026-09-12'].map(date=>({date}));
assert.equal(api.sliceRange(rows,1).length,2);
assert.equal(api.sliceRange(rows,5).length,4);
assert.equal(api.sliceRange(rows,10).length,6);
assert.equal(api.sliceRange(rows.slice(-1),10).length,1);
assert.equal(api.sliceRange([],1).length,0);
assert.equal(api.sliceRange([{date:'2023-02-28'},{date:'2024-02-29'}],1).length,2);
const funds=[{name:'Alpha',ticker:'123.KS',category:'국내',issuer:'Issuer',benchmark:'Index',exposure:'Semiconductor',holdings_text:'Example Corp',aum_krw:20},{name:'Beta',ticker:'456.KS',category:'해외',aum_krw:10},{name:'Missing',ticker:'789.KS',aum_krw:null}];
for (const q of ['alpha','123','국내','issuer','index','semiconductor','example corp']) assert.equal(api.selectEtfs(funds,{query:q}).length,1,q);
assert.equal(api.selectEtfs(funds,{category:'해외'})[0].name,'Beta');
assert.equal(api.selectEtfs(funds,{issuer:'Issuer'})[0].name,'Alpha');
assert.equal(api.selectEtfs(funds,{query:'absent'}).length,0);
for(const dir of ['asc','desc']) {
 const sorted=api.selectEtfs(funds,{sort:'aum_krw',dir});
 assert.equal(sorted.at(-1).name,'Missing');
 assert.equal(sorted[0].name,dir==='asc'?'Beta':'Alpha');
}
assert.equal(api.format(null),'-');
assert.equal(api.cellValue({avg_volume_20d:1234.56},'avg_volume_20d'),'1,235');
assert.equal(api.cellValue({avg_trading_value_20d_krw:123456789.0},'avg_trading_value_20d_krw'),'1');
assert.equal(api.selectEtfs([{name:'Liquid',avg_volume_20d:1000},{name:'Thin',avg_volume_20d:5},{name:'Missing'}],{minVolume:100}).length,1);
assert.equal(api.segmentWidth([1,1.0001],0,1),2);
assert.equal(api.segmentWidth([1.0001,1],0,1),1);
assert.equal(api.segmentWidth([null,1],0,1),2);
let updates=0;
const chart={data:{},update(){updates++;}};
api.updateRange(chart,rows,1);
assert.equal(chart.data.labels.length,2);
api.updateRange(chart,rows,10);
assert.equal(chart.data.labels.length,6);
assert.equal(chart.data.datasets.length,4);
assert.equal(updates,2);
console.log('ETF search/filter/sort, calendar ranges, chart updates and colors passed');

assert.deepEqual(api.chartData([-2,0,null,Infinity,NaN,3].map(v=>({vwap_1d:v}))).datasets[0].data,[null,null,null,null,null,3]);
const ticks=Array.from({length:244},(_,i)=>({value:i}));
assert.equal(api.xTickLabel.call({getLabelForValue:i=>`D${i}`},243,243,ticks),'D243');
assert.equal(api.xTickLabel.call({getLabelForValue:i=>`D${i}`},242,242,ticks),'');
assert.deepEqual(api.selectedValues([{date:'2026-09-11',vwap_1d:1234.6,vwap_20d:1100.4}],0),
  {date:'2026-09-11',values:[['1일','1,235','#eab308'],['20일','1,100','#dc2626'],['60일','-','#16a34a'],['240일','-','#2563eb']]});
assert.deepEqual(api.xTickIndexes(244),[0,35,69,104,139,174,208,243]);
assert.deepEqual(api.xTickIndexes(244,3),[0,122,243]);
assert.deepEqual(api.xTickIndexes(1),[0]);

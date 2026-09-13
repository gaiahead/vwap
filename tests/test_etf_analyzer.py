import json
import subprocess
from pathlib import Path
from unittest.mock import Mock
import numpy as np
import pandas as pd
import pytest
import gen_trend_data as gen

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {'0060H0','379800','379810','458730','453650','453640','203780','481190','456600','381180','390390','446770','487230','486450','491010','069500','122630','229200','233740','091160','395160','471990','469150','475300','475310','455850','487240','0117V0','396500','434730','474800','497780','0036Z0','415920','457990','091180','091170','305720','117680','266420','0115D0','0080G0','117700','140710','498410','102970','140700','157490','266370','228810','445290','0177X0','0148J0','228790','266410'}

def frame(n=800):
    return pd.DataFrame({'open':100.,'high':110.,'low':90.,'close':105.,'volume':np.arange(n)+1},index=pd.bdate_range('2020-01-01',periods=n))

def test_registry_exact_etfs():
    assert {t for _,t in gen.ASSETS} == {t+'.KS' for t in EXPECTED}
    assert len(gen.ASSETS) == len(EXPECTED)
    derived = [gen.derive_registry_facts(name) for name, _ in gen.ASSETS]
    assert all(item.get('category') and item.get('issuer') and item.get('exposure') for item in derived)
    assert gen.derive_registry_facts('KODEX 반도체')['category'] == '국내 주식, 반도체'
    assert gen.derive_registry_facts('TIGER 미국나스닥바이오')['category'] == '해외 주식, 헬스케어 및 바이오'

def test_full_history_and_warmup():
    work=gen.prepare_storage_frame(frame(1000))
    assert len(work)==1000
    assert work.vwap_240d.iloc[:239].isna().all()
    assert work.vwap_240d.iloc[239:].notna().all()
    assert gen.WINDOWS == [1,20,60,240]

def test_download_calendar_cap(monkeypatch):
    raw=frame(); raw.columns=[c.title() for c in raw.columns]
    fetch=Mock(return_value=raw)
    monkeypatch.setattr(gen.yf,'download',fetch)
    monkeypatch.setattr(gen,'maybe_patch_krx_today',lambda df,*a:df)
    result=gen.download_ohlcv('069500.KS','2024-02-29')
    assert fetch.call_args.kwargs['start']=='2004-02-29'
    assert fetch.call_args.kwargs['end']=='2024-03-01'
    assert len(result)==800

def test_market_and_missing(monkeypatch):
    market={'marketSum':100,'quant':20,'amonut':2000,'nowVal':102,'nav':100}
    facts=gen.build_facts('069500.KS',frame(20),market,'2026-09-12')
    assert facts['aum_krw']==100*100_000_000
    assert facts['premium_discount_pct']==pytest.approx(2)
    assert facts['avg_volume_20d']==10.5
    assert facts['avg_trading_value_20d_krw']==1102.5
    assert facts['total_expense_ratio_pct'] is None
    assert facts['holdings']==[]
    assert facts['sources']['market']['url']==gen.NAVER_ETF_URL
    assert gen.build_facts('069500.KS',frame(3),{},'x')['avg_volume_20d'] is None
    monkeypatch.setattr(gen.requests,'get',Mock(side_effect=gen.requests.Timeout))
    assert gen.fetch_naver_etf_list()=={}
    assert gen.safe_round(float('inf')) is None

def test_schema():
    brief,detail=gen.build_asset_outputs('KODEX 200','069500.KS',frame())
    assert 'strategy_signal' not in brief and 'strategy_signal' not in detail
    assert 'ohlcv' not in brief and 'holdings' not in brief
    assert len(detail['ohlcv'])==800
    assert 'volume_profile' not in detail
    json.dumps(detail,allow_nan=False)

def test_generated_parity():
    trend=json.loads((ROOT/'trend_data.json').read_text())
    assert {x['ticker'] for x in trend['etfs']}=={t for _,t in gen.ASSETS}
    assert {p.stem for p in (ROOT/'detail_data').glob('*.json')}=={t for _,t in gen.ASSETS}
    for brief in trend['etfs']:
        detail=json.loads((ROOT/'detail_data'/f"{brief['ticker']}.json").read_text())
        assert detail['_meta']==brief['history_source']
        assert brief['aum_krw']==detail['facts']['aum_krw']
        rows=detail['ohlcv']
        if rows:
            assert rows[0]['date']>=trend['_meta']['history_start']
            assert rows[-1]['vwap_1d'] is not None
        assert not {'strategy_signal','strategies'} & detail.keys()

def test_js_behavior():
    subprocess.run(['node','tests/etf_app.test.js'],cwd=ROOT,check=True)

def test_active_contract():
    html=(ROOT/'index.html').read_text(); app=(ROOT/'app.js').read_text()
    assert not (ROOT/'detail.html').exists()
    for word in ['BUY','SELL','WAIT','종목','alignment_','vwap_5d','vwap_120d']:
        assert word not in html+app
    assert 'aria-live' in html
    assert 'Volume Profile' not in html+app
    assert 'volume_profile' not in app
    assert "['pbr','per']" in app
    assert 'id="chart-selection"' in app
    assert 'selected-date-line' in app
    assert 'autoSkip:false' in app
    assert 'tooltip:{enabled:false}' in app
    assert '시장 정보:' not in app
    assert '생성 ${' not in html+app
    import re
    assert re.search(r'style.css\?v=([^"\']+)',html)[1] == re.search(r"DATA_VERSION = '([^']+)'",app)[1]

@pytest.mark.parametrize('encoding',['utf-8','cp949'])
def test_naver_response_encodings_and_timeout(monkeypatch,encoding):
    payload={'result':{'etfItemList':[{'itemcode':'069500','itemname':'한글 ETF','marketSum':100}]}}
    response=Mock(content=json.dumps(payload,ensure_ascii=False).encode(encoding))
    get=Mock(return_value=response); monkeypatch.setattr(gen.requests,'get',get)
    assert gen.fetch_naver_etf_list()['069500']['itemname']=='한글 ETF'
    assert get.call_args.kwargs['timeout']==15

@pytest.mark.parametrize('payload',[b'not json',b'{}',b'{"result":null}',b'{"result":{"etfItemList":null}}'])
def test_naver_invalid_payload_missing(monkeypatch,payload):
    monkeypatch.setattr(gen.requests,'get',Mock(return_value=Mock(content=payload)))
    assert gen.fetch_naver_etf_list()=={}


def test_market_invalid_numbers_and_zero_volume():
    data=frame(260);data['volume']=0
    brief,detail=gen.build_asset_outputs('ETF','069500.KS',data,{'nav':0,'nowVal':100,'marketSum':'garbage'})
    assert brief['aum_krw'] is None and brief['premium_discount_pct'] is None
    assert all(row['vwap_240d'] is None for row in detail['ohlcv'])
    assert 'volume_profile' not in detail
    json.dumps(detail,allow_nan=False)


def test_cap_cleaning_and_normal_warmup():
    data=frame(6000); data.index=pd.bdate_range('2000-01-01',periods=6000)
    cleaned=gen.clean_frame(data,'2023-01-01')
    assert cleaned.index[0]>=pd.Timestamp('2003-01-01')
    assert cleaned.index[-1]<=pd.Timestamp('2023-01-01')
    assert len(cleaned)>4800
    assert gen.history_start('2024-02-29')=='2004-02-29'


def test_optional_sources_and_holdings_validation(tmp_path):
    path=tmp_path/'facts.json'
    def write(fields):
        path.write_text(json.dumps({'etfs':{'069500.KS':fields}}))
    write({'total_expense_ratio_pct':{'value':.15}})
    with pytest.raises(ValueError):gen.load_optional_facts(path)
    record={'value':.15,'source_url':'https://example.com/report','as_of':'2026-03-31'}
    write({'total_expense_ratio_pct':record})
    assert gen.load_optional_facts(path)['069500.KS']['total_expense_ratio_pct']==record
    write({'holdings':{**record,'value':[{'name':'Example','weight_pct':101}]}})
    with pytest.raises(ValueError):gen.load_optional_facts(path)
    optional=gen.load_optional_facts()
    facts=gen.build_facts('069500.KS',frame(),optional=optional['069500.KS'])
    assert len(facts['holdings'])==10
    assert facts['top10_weight_pct']==pytest.approx(63.4)
    assert facts['sources']['holdings']['as_of']=='2026-03-31'


def test_strict_write_does_not_truncate(tmp_path):
    path=tmp_path/'test.json';path.write_text('{}')
    with pytest.raises(ValueError):gen.write_json_file(path,{'value':float('inf')})
    assert path.read_text()=='{}'


def test_cached_history_missing_and_empty(tmp_path,monkeypatch):
    monkeypatch.setattr(gen,'DETAIL_DIR',str(tmp_path))
    assert gen.cached_history('069500.KS','2026-09-12').empty
    (tmp_path/'069500.KS.json').write_text('{"ohlcv":[],"_meta":{}}')
    assert gen.cached_history('069500.KS','2026-09-12').empty


def test_default_failed_run_leaves_artifacts(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path/'trend_data.json').write_text('{}')
    monkeypatch.setattr(gen,'ASSETS',[('ETF','069500.KS')])
    monkeypatch.setattr(gen,'fetch_naver_etf_list',lambda:{})
    monkeypatch.setattr(gen,'load_optional_facts',lambda:{})
    monkeypatch.setattr(gen,'download_ohlcv',Mock(side_effect=ValueError('offline')))
    monkeypatch.setattr('sys.argv',['gen_trend_data.py','--end','2026-09-12'])
    with pytest.raises(SystemExit):gen.main()
    assert (tmp_path/'trend_data.json').read_text()=='{}'


def test_production_dom_handlers():
    subprocess.run(['node','tests/etf_dom.test.js'],cwd=ROOT,check=True)


def test_generated_rolling_series_and_liquidity_recompute():
    trend=json.loads((ROOT/'trend_data.json').read_text())
    for brief in trend['etfs']:
        detail=json.loads((ROOT/'detail_data'/f"{brief['ticker']}.json").read_text())
        if not detail['ohlcv']:
            continue
        df=pd.DataFrame(detail['ohlcv'])
        price=(df.high+df.low+df.close)/3
        for window in [1,20,60,240]:
            expected=(price*df.volume).rolling(window).sum()/df.volume.rolling(window).sum().replace(0,np.nan)
            # OHLCV and VWAP are serialized independently to four decimals.
            assert np.allclose(df[f'vwap_{window}d'].astype(float),expected,atol=.0002,rtol=0,equal_nan=True)
        if len(df)>=20:
            assert brief['avg_volume_20d']==pytest.approx(df.volume.tail(20).mean(),abs=.0001)
            # Stored closes are rounded to four decimals after this estimate is computed.
            assert brief['avg_trading_value_20d_krw']==pytest.approx(
                (df.close*df.volume).tail(20).mean(), rel=1e-8, abs=1000
            )
        assert not any('strategy' in key or 'signal' in key for key in brief)

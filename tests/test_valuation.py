import json
from pathlib import Path
from unittest.mock import Mock
import pytest
import gen_trend_data as gen


def test_ui_contract():
    app = Path('app.js').read_text()
    columns = app.split('const COLUMNS = [')[1].split('];')[0]
    assert columns.rstrip().endswith("['avg_volume_20d','20일 평균 거래량, 주']")
    assert all(x not in columns for x in ['cost', 'expense', 'premium', 'holdings', 'top10'])
    assert 'has-fees' not in Path('index.html').read_text() + app
    assert "type: 'logarithmic'" in app
    assert '로그 스케일' in app


def test_normalize_direct_stocks():
    rows = [{'holding_isin':f'US{i:010d}', 'holding_name':str(i), 'weight':i,
             'asset_type':'equity', 'instrument_type':'stock'} for i in range(1,13)]
    rows += [dict(rows[-1], instrument_type=t, weight=99) for t in ['etf','future','swap','bond','cash']]
    result = gen.normalize_holdings({'asof':'2026-09-11','holdings':rows})
    assert len(result['holdings']) == 10
    assert [h['weight_pct'] for h in result['holdings']] == list(range(12,2,-1))
    assert result['as_of'] == '2026-09-11'


def test_naver_period_selection():
    payload={'financeInfo':{'trTitleList':[{'key':'2024','title':'2024','isConsensus':'N'}, {'key':'2025','title':'2025','isConsensus':'N'}, {'key':'2026','title':'2026(E)','isConsensus':'Y'}],
      'rowList':[{'title':'PER','columns':{'2024':{'value':'8'},'2025':{'value':'10'},'2026':{'value':'20'}}},
                 {'title':'PBR','columns':{'2025':{'value':'2'},'2026':{'value':'-'}}}]}}
    result=gen.parse_naver_valuation(payload)
    assert result['per']['value']==20 and result['per']['basis']=='consensus'
    assert result['pbr']['value']==2 and result['pbr']['basis']=='actual'
    assert result['pbr']['period']=='2025'


def test_yahoo_preference():
    result=gen.parse_yahoo_valuation({'forwardPE':20,'trailingPE':30,'priceToBook':2})
    assert result['per']['value']==20 and result['per']['basis']=='forward'
    result=gen.parse_yahoo_valuation({'forwardPE':-2,'trailingPE':30,'priceToBook':float('inf')})
    assert result['per']['value']==30 and result['per']['basis']=='trailing'
    assert result['pbr']['value'] is None


def test_harmonic_coverage():
    rows=[{'weight_pct':20,'per':{'value':10,'basis':'consensus'}},
          {'weight_pct':10,'per':{'value':20,'basis':'forward'}},
          {'weight_pct':5,'per':{'value':-1}}, {'weight_pct':2,'per':{'value':float('nan')}}]
    r=gen.aggregate_multiple(rows,'per','2026-09-11')
    assert r['value']==pytest.approx(12)
    assert (r['valid_count'],r['top10_count'],r['covered_weight_pct'],r['top10_weight_pct'])==(2,4,30,37)
    assert r['basis']==['consensus','forward']
    assert gen.aggregate_multiple(rows,'pbr',None)['value'] is None
    json.dumps(r,allow_nan=False)


def test_offline_no_network(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    fail=Mock(side_effect=AssertionError('network called'))
    monkeypatch.setattr(gen.requests,'get',fail)
    monkeypatch.setattr(gen.yf,'Ticker',fail)
    monkeypatch.setattr(gen.yf,'download',fail)
    monkeypatch.setattr(gen,'ASSETS',[('ETF','069500.KS')])
    monkeypatch.setattr(gen,'load_optional_facts',lambda:{})
    monkeypatch.setattr('sys.argv',['gen_trend_data.py','--offline'])
    gen.main()
    fail.assert_not_called()
    result=json.loads(Path('detail_data/069500.KS.json').read_text())
    assert result['facts']['valuation']['per']['value'] is None


def test_cache_fresh_stale_and_failure(tmp_path,monkeypatch):
    from datetime import timedelta
    c=gen.ValuationCollector(path=tmp_path/'cache.json')
    record={**gen.parse_yahoo_valuation({'forwardPE':12,'priceToBook':2}), 'retrieved_at':c.now.isoformat()}
    c.cache['stocks']['US123']=record
    fetch=Mock(return_value=record)
    monkeypatch.setattr(gen,'fetch_valuation',fetch)
    assert c.stock('US123')['per']['value']==12
    fetch.assert_not_called()
    c.cache['stocks']['US123']['retrieved_at']=(c.now-timedelta(days=8)).isoformat()
    assert c.stock('US123')['status']=='live'
    fetch.assert_called_once()
    c.cache['stocks']['US456']={**record,'retrieved_at':(c.now-timedelta(days=8)).isoformat()}
    fetch.side_effect=ValueError('failed refresh')
    assert c.stock('US456').get('per',{}).get('value') is None
    assert c.stock('US456').get('per',{}).get('value') is None
    assert fetch.call_count==2


def test_holdings_fallback_and_cached_offline(tmp_path,monkeypatch):
    c=gen.ValuationCollector(path=tmp_path/'cache.json')
    c.cache['holdings']['069500']={'holdings':[{'isin':'KR7005930003','name':'삼성전자','weight_pct':20}],
                                  'as_of':'2026-09-11','url':'https://www.k-etf.com/etf/069500'}
    c.cache['stocks']['KR7005930003']={**gen.parse_naver_valuation({'financeInfo':{'trTitleList':[], 'rowList':[]}}),
                                      'retrieved_at':c.now.isoformat()}
    fail=Mock(side_effect=ValueError('holdings down'))
    monkeypatch.setattr(gen,'fetch_json',fail)
    facts={'sources':{},'holdings':[]}
    c.enrich('069500.KS',facts)
    assert facts['sources']['holdings']['status']=='cached_after_failure'
    assert facts['valuation']['per']['top10_count']==1
    c.save()
    fail.reset_mock()
    c=gen.ValuationCollector(offline=True,path=tmp_path/'cache.json')
    c.enrich('069500.KS',facts)
    fail.assert_not_called()
    assert facts['sources']['holdings']['status']=='cached'


def test_reviewed_holdings_fallback_tolerates_unknown_weight(tmp_path, monkeypatch):
    collector = gen.ValuationCollector(path=tmp_path/'cache.json')
    monkeypatch.setattr(gen, 'fetch_json', Mock(side_effect=ValueError('holdings down')))
    facts = {
        'sources': {'holdings': {'as_of': '2026-03-31', 'url': 'https://example.com/report'}},
        'holdings': [{'name': 'Example', 'weight_pct': None}],
    }
    collector.enrich('069500.KS', facts)
    assert facts['top10_weight_pct'] == 0
    assert facts['valuation']['per']['value'] is None
    assert facts['sources']['holdings']['status'] == 'verified_after_failure'


def test_korean_isin_and_foreign_equity_search(monkeypatch, foreign_ratios):
    get=Mock(return_value={'financeInfo':{'trTitleList':[],'rowList':[]}})
    monkeypatch.setattr(gen,'fetch_json',get)
    assert gen.fetch_valuation('KR7005930003', '삼성전자')['symbol']=='005930'
    assert get.call_args.args[0] == 'https://m.stock.naver.com/api/stock/005930/finance/annual'
    get.reset_mock()
    get.side_effect = [
        {'result': {'items': [{'name': '엔비디아', 'category': 'stock',
                              'reutersCode': 'NVDA.O', 'nationCode': 'USA'}]}},
        foreign_ratios,
    ]
    ticker=Mock(side_effect=AssertionError('Yahoo must not be called'))
    monkeypatch.setattr(gen.yf,'Ticker',ticker)
    result = gen.fetch_valuation('US67066G1040', '엔비디아')
    assert result['per']['value'] == 25
    assert result['symbol'] == 'NVDA.O'
    assert result['url'] == 'https://stock.naver.com/worldstock/stock/NVDA.O/total'
    assert get.call_args_list[0].args[0] == 'https://stock.naver.com/api/autocomplete/search/autoComplete'
    assert get.call_args_list[0].kwargs['params'] == {'query': '엔비디아', 'target': 'stock'}
    assert get.call_args_list[1].args[0] == 'https://stock.naver.com/api/securityService/stock/finance/ratios/annual'
    assert get.call_args_list[1].kwargs['params'] == {'reutersCode': 'NVDA.O'}
    ticker.assert_not_called()


def test_generated_valuation_strict_json():
    from tests.check_json import reject_constant, unique_keys
    for path in [Path('trend_data.json'),Path(gen.CACHE_FILE),*Path('detail_data').glob('*.json')]:
        payload=json.loads(path.read_text(),parse_constant=reject_constant,object_pairs_hook=unique_keys)
        if 'facts' not in payload:
            continue
        facts=payload['facts']
        assert len(facts['holdings'])<=10
        for key in ('per','pbr'):
            ratio=facts['valuation'][key]
            expected=gen.aggregate_multiple(facts['holdings'],key,facts['sources']['holdings']['as_of'])
            assert ratio==expected
            assert ratio['value'] is None or ratio['value']>0


@pytest.fixture
def foreign_ratios():
    return {
        'trTitleList': [
            {'key': 'last12month', 'title': '2026.07.31'},
            {'key': '2025', 'title': '2025.01.31'},
            {'key': '2026', 'title': '2026.01.31'},
        ],
        'rowList': [
            {'title': 'PER Growth', 'columns': {'last12month': {'value': '999'}}},
            {'title': 'PER', 'columns': {'2025': {'value': '40'}, '2026': {'value': '30'},
                                       'last12month': {'value': '25'}}},
            {'title': 'PBR', 'columns': {'2025': {'value': '10'}, '2026': {'value': '12'},
                                       'last12month': {'value': '-'}}},
        ],
    }


def test_foreign_naver_latest_valid_period_per_metric(foreign_ratios):
    result = gen.parse_naver_foreign_valuation(foreign_ratios)
    assert result['per'] == {'value': 25, 'period': '2026.07.31',
                             'basis': 'actual', 'is_consensus': False}
    assert result['pbr'] == {'value': 12, 'period': '2026.01.31',
                             'basis': 'actual', 'is_consensus': False}


@pytest.mark.parametrize('invalid', ['-', '0', '-2', 'NaN', 'Infinity', True, None])
def test_foreign_naver_invalid_latest_falls_back(foreign_ratios, invalid):
    foreign_ratios['rowList'][1]['columns']['last12month']['value'] = invalid
    assert gen.parse_naver_foreign_valuation(foreign_ratios)['per']['value'] == 30


def test_foreign_search_exact_name_priority():
    candidates = [
        {'name': '엔비디아', 'category': 'etf', 'reutersCode': 'ETF.O', 'nationCode': 'USA'},
        {'name': '엔비디아 ADR', 'category': 'stock', 'reutersCode': 'OTHER.O', 'nationCode': 'USA'},
        {'name': '엔비디아', 'category': 'stock', 'reutersCode': 'NVDA.O', 'nationCode': 'USA'},
    ]
    assert gen.select_naver_foreign_stock({'result': {'items': candidates}}, '엔비디아')['reutersCode'] == 'NVDA.O'


def test_foreign_search_rejects_ambiguous_candidates():
    candidates = [
        {'name': 'Apple', 'category': 'stock', 'reutersCode': 'AAPL.O', 'nationCode': 'USA'},
        {'name': 'Apple ADR', 'category': 'stock', 'reutersCode': 'OTHER.O', 'nationCode': 'USA'},
    ]
    with pytest.raises(ValueError, match='Ambiguous'):
        gen.select_naver_foreign_stock({'result': {'items': candidates}}, '애플')


def test_foreign_search_single_foreign_stock_only():
    candidates = [
        {'name': '국내', 'category': 'stock', 'reutersCode': '005930.KS', 'nationCode': 'KOR'},
        {'name': '애플', 'category': 'stock', 'nationCode': 'USA'},
        {'name': 'Apple', 'category': 'stock', 'reutersCode': 'AAPL.O', 'nationCode': 'USA'},
    ]
    assert gen.select_naver_foreign_stock({'result': {'items': candidates}}, '애플')['reutersCode'] == 'AAPL.O'
    with pytest.raises(ValueError):
        gen.select_naver_foreign_stock({'result': {'items': candidates[:2]}}, '애플')


def test_foreign_search_uses_isin_and_primary_market():
    candidates = [
        {'name': '마이크로소프트', 'category': 'stock', 'reutersCode': 'MSFT.O', 'nationCode': 'USA'},
        {'name': '마이크로소프트', 'category': 'stock', 'reutersCode': '4338.HK', 'nationCode': 'HKG'},
    ]
    selected = gen.select_naver_foreign_stock(
        {'result': {'items': candidates}}, '마이크로소프트', 'US5949181045',
        lambda item: {'isinCode': 'US5949181045'},
    )
    assert selected['reutersCode'] == 'MSFT.O'


def test_foreign_search_disambiguates_share_class_by_isin():
    candidates = [
        {'name': '알파벳 Class A', 'category': 'stock', 'reutersCode': 'GOOGL.O', 'nationCode': 'USA'},
        {'name': '알파벳 Class C', 'category': 'stock', 'reutersCode': 'GOOG.O', 'nationCode': 'USA'},
    ]
    isins = {'GOOGL.O': 'US02079K3059', 'GOOG.O': 'US02079K1079'}
    selected = gen.select_naver_foreign_stock(
        {'result': {'items': candidates}}, '알파벳', 'US02079K1079',
        lambda item: {'isinCode': isins[item['reutersCode']]},
    )
    assert selected['reutersCode'] == 'GOOG.O'


@pytest.mark.parametrize('stage', ['search', 'ratios', 'empty_ratios'])
def test_foreign_failure_preserves_cache_and_retries_next_run(tmp_path, monkeypatch, capsys, stage):
    from datetime import timedelta
    path = tmp_path / 'cache.json'
    c = gen.ValuationCollector(path=path)
    isin = 'US67066G1040'
    old = {**gen.parse_yahoo_valuation({'forwardPE': 12}),
           'retrieved_at': (c.now - timedelta(days=8)).isoformat()}
    c.cache['stocks'][isin] = old
    search = {'result': {'items': [{'name': '엔비디아', 'category': 'stock',
                                  'reutersCode': 'NVDA.O', 'nationCode': 'USA'}]}}
    responses = [ValueError('HTTP 429')] if stage == 'search' else [
        search, ValueError('HTTP 429') if stage == 'ratios' else {'trTitleList': [], 'rowList': []}]
    get = Mock(side_effect=responses)
    yahoo = Mock(side_effect=AssertionError('Yahoo must not be called'))
    monkeypatch.setattr(gen, 'fetch_json', get)
    monkeypatch.setattr(gen.yf, 'Ticker', yahoo)
    facts = {'sources': {}, 'holdings': []}
    c.cache['holdings']['123456'] = {'as_of': '2026-09-11', 'holdings': [
        {'isin': isin, 'name': '엔비디아', 'weight_pct': 20}]}
    # Keep holdings retrieval separate from the valuation HTTP failures.
    monkeypatch.setattr(gen, 'normalize_holdings', lambda payload: c.cache['holdings']['123456'])
    get.side_effect = [{}, *responses]
    c.enrich('123456.KS', facts)
    assert facts['holdings'][0]['per']['value'] is None
    assert facts['holdings'][0]['source']['status'] == 'failed'
    assert c.stock(isin, '엔비디아')['status'] == 'failed'
    assert get.call_count == len(responses) + 1
    assert get.call_args_list[1].kwargs['params']['query'] == '엔비디아'
    assert '[WARN] Valuation' in capsys.readouterr().out
    yahoo.assert_not_called()
    c.save()
    assert json.loads(path.read_text())['stocks'][isin] == old
    retry = Mock(return_value=gen.parse_yahoo_valuation({'forwardPE': 24}))
    monkeypatch.setattr(gen, 'fetch_valuation', retry)
    assert gen.ValuationCollector(path=path).stock(isin, '엔비디아')['status'] == 'live'
    retry.assert_called_once_with(isin, '엔비디아')


def test_foreign_failure_without_cache_is_not_saved(tmp_path, monkeypatch):
    path = tmp_path / 'cache.json'
    fetch = Mock(side_effect=ValueError('missing stock'))
    monkeypatch.setattr(gen, 'fetch_valuation', fetch)
    c = gen.ValuationCollector(path=path)
    assert c.stock('US123', 'Unknown')['status'] == 'failed'
    c.save()
    assert json.loads(path.read_text())['stocks'] == {}
    assert gen.ValuationCollector(path=path).stock('US123', 'Unknown')['status'] == 'failed'
    assert fetch.call_count == 2

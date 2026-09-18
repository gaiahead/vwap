import json
import re
from pathlib import Path
from unittest.mock import Mock

import gen_trend_data as gen


def assert_no_valuation_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            assert str(key).lower() not in {'valuation', 'pbr', 'per', 'stocks'}
            assert_no_valuation_keys(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_valuation_keys(child)


def test_ui_contract_chart_first_and_no_valuation():
    app = Path('app.js').read_text()
    columns = app.split('const COLUMNS = [')[1].split('];')[0]
    assert columns.rstrip().endswith("['avg_volume_20d','20일 평균 거래량, 주']")
    assert all(x not in columns for x in ['issuer', 'cost', 'expense', 'premium', 'holdings', 'top10'])
    assert 'has-fees' not in Path('index.html').read_text() + app
    assert "type: 'logarithmic'" in app
    assert '로그 스케일' in app
    detail_markup = app.split('el(\'detail-content\').innerHTML=`', 1)[1].split('`;', 1)[0]
    assert detail_markup.index('VWAP 가격 차트') < detail_markup.index('<div class="facts">')
    assert not re.search(r'\b(?:PBR|PER|pbr|per|valuation)\b', detail_markup)
    assert 'pointRadius:0' in app
    assert 'pointHoverRadius:0' in app


def test_normalize_direct_stocks():
    rows = [{'holding_isin': f'US{i:010d}', 'holding_name': str(i), 'weight': i,
             'asset_type': 'equity', 'instrument_type': 'stock'} for i in range(1, 13)]
    rows += [dict(rows[-1], instrument_type=t, weight=99) for t in ['etf', 'future', 'swap', 'bond', 'cash']]
    result = gen.normalize_holdings({'asof': '2026-09-11', 'holdings': rows})
    assert len(result['holdings']) == 10
    assert [h['weight_pct'] for h in result['holdings']] == list(range(12, 2, -1))
    assert result['as_of'] == '2026-09-11'
    assert_no_valuation_keys(result)


def test_offline_no_network_or_valuation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fail = Mock(side_effect=AssertionError('network called'))
    monkeypatch.setattr(gen.requests, 'get', fail)
    monkeypatch.setattr(gen.yf, 'Ticker', fail)
    monkeypatch.setattr(gen.yf, 'download', fail)
    monkeypatch.setattr(gen, 'ASSETS', [('ETF', '069500.KS')])
    monkeypatch.setattr(gen, 'load_optional_facts', lambda: {})
    monkeypatch.setattr('sys.argv', ['gen_trend_data.py', '--offline'])
    gen.main()
    fail.assert_not_called()
    result = json.loads(Path('detail_data/069500.KS.json').read_text())
    assert_no_valuation_keys(result)
    cache = json.loads(Path(gen.CACHE_FILE).read_text())
    assert set(cache) == {'holdings'}


def test_holdings_fallback_and_cached_offline(tmp_path, monkeypatch):
    c = gen.HoldingsCollector(path=tmp_path/'cache.json')
    c.cache['holdings']['069500'] = {
        'holdings': [{'isin': 'KR7005930003', 'name': '삼성전자', 'weight_pct': 20}],
        'as_of': '2026-09-11', 'url': 'https://www.k-etf.com/etf/069500'}
    fail = Mock(side_effect=ValueError('holdings down'))
    monkeypatch.setattr(gen, 'fetch_json', fail)
    facts = {'sources': {}, 'holdings': []}
    c.enrich('069500.KS', facts)
    assert facts['sources']['holdings']['status'] == 'cached_after_failure'
    assert facts['holdings'] == [{'isin': 'KR7005930003', 'name': '삼성전자', 'weight_pct': 20}]
    assert_no_valuation_keys(facts)
    c.save()
    fail.reset_mock()
    c = gen.HoldingsCollector(offline=True, path=tmp_path/'cache.json')
    c.enrich('069500.KS', facts)
    fail.assert_not_called()
    assert facts['sources']['holdings']['status'] == 'cached'


def test_reviewed_holdings_fallback_tolerates_unknown_weight(tmp_path, monkeypatch):
    collector = gen.HoldingsCollector(path=tmp_path/'cache.json')
    monkeypatch.setattr(gen, 'fetch_json', Mock(side_effect=ValueError('holdings down')))
    facts = {
        'sources': {'holdings': {'as_of': '2026-03-31', 'url': 'https://example.com/report'}},
        'holdings': [{'name': 'Example', 'weight_pct': None}],
    }
    collector.enrich('069500.KS', facts)
    assert facts['top10_weight_pct'] == 0
    assert facts['sources']['holdings']['status'] == 'verified_after_failure'
    assert_no_valuation_keys(facts)


def test_generated_holdings_strict_json_without_valuation():
    paths = [Path('trend_data.json'), Path(gen.CACHE_FILE), *Path('detail_data').glob('*.json')]
    assert Path(gen.CACHE_FILE).name == 'holdings_cache.json'
    assert not Path('valuation_cache.json').exists()
    for path in paths:
        payload = json.loads(path.read_text())
        assert_no_valuation_keys(payload)
        if 'facts' in payload:
            assert len(payload['facts']['holdings']) <= 10

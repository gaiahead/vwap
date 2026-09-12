# ETF data pipeline, schema v2

Run from repository root:

```sh
.venv/bin/python gen_trend_data.py --end 2026-09-12
```

Without `--end`, use today's Korean calendar date. yfinance receives an explicit start exactly 20 calendar years before that date and an exclusive end one day later. Newly listed ETFs naturally return only since listing. Store every valid returned daily row within those inclusive bounds, sorted and deduplicated. There is no trading-row truncation and no historical date exclusion list. Download prices use `auto_adjust=True`. Yahoo cache files are kept in the ignored repo-local `.local-run/yfinance` directory.

Preserve the Naver same-day KRX patch: after 15:30 KST, fetch the target day's row using the bounded siseJson request and overwrite/append it, including when Yahoo already supplied the same date. Do not patch unconfirmed intraday data. Patch source/date survive in detail metadata and the list's `history_source`. Naver failure leaves the Yahoo snapshot intact.

Calculate rolling VWAP for [1, 20, 60, 240] using `(high + low + close) / 3`, weighted by volume. Require the full window; VWAP240 has exactly 239 warmup rows. Zero-volume windows are null. Profile buckets are a normal-distribution approximation of daily volume, not observed intraday trades. Its VWAP uses the exact same rolling formula.

## Market source

Fetch https://finance.naver.com/api/sise/etfItemList.nhn once per run with a 15-second timeout. Parse UTF-8 or CP949 JSON and the `result.etfItemList` envelope. Missing, malformed or failed responses yield missing metadata without aborting OHLCV generation.

- `marketSum` is converted from 억원 to KRW as the Naver ETF size/AUM proxy. It is not a separately audited accounting NAV total.
- Premium/discount percent = `(nowVal / nav - 1) * 100`, only for finite price and positive NAV.
- Preserve marketSum, quant, amonut, nowVal and nav in source metadata. `amonut` is retained raw; no unverified currency scaling is applied.
- Average daily volume = mean of the latest 20 trading rows' volumes.
- Average daily trading value = mean of adjusted close × volume over those same rows, explicitly labeled an estimate. Fewer than 20 rows yields null, not a shorter-period average. This is distinct from the single-day Naver amount.

Each market source records URL, retrieval timestamp and quote as-of separately. The endpoint does not guarantee a quote date, so as-of remains null unless supplied explicitly; never label retrieval time as the quote date. Liquidity records first/last trading dates and formula. Historical cache dates are never updated to the regeneration date.

## Fees, classification and holdings

`derive_registry_facts` assigns every registered ETF a search taxonomy and issuer from the registered product-name prefix. The taxonomy is an internal discovery aid, not an issuer classification. It also keeps the full product name as broad exposure text. Do not infer fees, constituents or precise benchmark identities from product names.

`etf_facts.json` is a reviewed optional input, not generated output. Every populated sourced field needs `value`, `source_url` (HTTPS), and ISO `as_of`. Optional `note` preserves cost definitions. Unknown ETF tickers/fields, negative or nonfinite fees, invalid dates and invalid holdings weights fail validation. Sourced category, issuer and exposure values override the registry-derived discovery values.

Supported fields: category, issuer, benchmark, exposure, total_expense_ratio_pct (issuer's annual 총보수), synthetic_total_expense_ratio_pct (합성총보수), trading_cost_pct (증권거래비용), actual_total_cost_pct (only explicitly disclosed comparable 실부담비용), other_cost_pct, and holdings (name, optional ticker, optional weight_pct). Percentages are percentage points: 0.15 means 0.15% annually. These overlapping cost figures must not be added blindly. The current snapshots leave actual/other costs null.

Source investigation on 2026-09-12:

- [Naver legacy detail](https://finance.naver.com/item/main.naver?code=069500) redirected to a client-rendered stock page without a reliably extractable fee/holdings table in the fetched response.
- [Naver mobile integration API](https://m.stock.naver.com/api/stock/069500/integration) could not be verified in this environment; no assumed schema is shipped.
- [Samsung product page](https://www.samsungfund.com/etf/product/view.do?id=2ETF01) yielded dynamic/variable content; a cross-issuer automatic parser was not established.
- [Samsung's dated quarterly issuer PDF](https://www.samsungfund.com/upload/kodex/newsroom/20260416171916907.pdf), PDF pages 14–15, provides explicitly dated 2026-03-31 fee/holdings snapshots for KODEX 200 and KODEX 미국S&P500. Only those two verified snapshots are seeded. Facts remain dated March, not represented as September holdings. Publication URLs/page layouts are not stable discovery APIs, so automatic PDF scraping is not enabled.

To maintain facts: obtain the latest issuer report or a verified documented feed, confirm the registered ticker and date, distinguish annual management fee from synthetic expense and trading costs, update the relevant field records and citation, then run generator and tests. Leave unsupported fields absent. Add fixture-backed provider parsers only when response structure, units and dates can be verified. No comprehensive cross-issuer automation is claimed.

## Artifacts and failure handling

`trend_data.json` contains run `_meta` and compact ETF list facts/search text/sources; never OHLCV, profile buckets or strategies. `detail_data/<ticker>.json` contains full available OHLCV, facts/holdings, profiles and `_meta`, identical to that ETF's list `history_source`. All generated JSON comes from this script with `allow_nan=False`; serialization occurs before opening output files. Unregistered detail files are removed by the generator.

Default download failures stop before replacing artifacts. `--allow-cache` explicitly permits cached fallback after a live failure; `--offline` regenerates from cached OHLCV without network. Both mark histories incomplete and preserve their real dates. Missing caches still produce ETF rows with null metrics and empty detail history. These modes cannot recover old truncated data and do not fulfill a full-history backfill.

The checked-in redesign regeneration used the strict network mode:

```sh
.venv/bin/python gen_trend_data.py --end 2026-09-12
```

The run downloaded all 55 ETF histories successfully, fetched current Naver ETF market metadata and produced zero incomplete histories. The stored window begins no earlier than 2006-09-12; each ETF begins at the first row Yahoo returned after its own listing date. The longest current history is KODEX 200 with 4,266 rows from 2007-01-29 through 2026-09-11.

GitHub generation timeout is 45 minutes for all-history requests. Workflow runs the default strict mode and will not publish a partially downloaded run. No workflow was dispatched during this redesign.

# ETF data pipeline, schema v2

Run from repository root:

```sh
.venv/bin/python gen_trend_data.py --end 2026-09-12
```

Without `--end`, use today's Korean calendar date. yfinance receives an explicit start exactly 20 calendar years before that date and an exclusive end one day later. Newly listed ETFs naturally return only since listing. Store every valid returned daily row within those inclusive bounds, sorted and deduplicated. There is no trading-row truncation and no historical date exclusion list. Download prices use `auto_adjust=True`. Yahoo cache files are kept in the ignored repo-local `.local-run/yfinance` directory.

Preserve the Naver same-day KRX patch: after 15:30 KST, fetch the target day's row using the bounded siseJson request and overwrite/append it, including when Yahoo already supplied the same date. Do not patch unconfirmed intraday data. Patch source/date survive in detail metadata and the list's `history_source`. Naver failure leaves the Yahoo snapshot intact.

Calculate rolling VWAP for [1, 20, 60, 240] using `(high + low + close) / 3`, weighted by volume. Require the full window; VWAP240 has exactly 239 warmup rows. Zero-volume windows are null. Volume Profile and its bucket approximation are not generated.

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

Supported reviewed fields include category, issuer, benchmark, exposure, optional historical fee/cost snapshots and holdings. Percentages are percentage points: 0.15 means 0.15% annually. Overlapping cost figures must not be added blindly.

The online collector requests K-ETF's `tax-fee` endpoint for every registered ETF and uses only `data.total_fee` as `total_expense_ratio_pct`. It does not ingest component fees, taxes, synthetic total expense, trading cost, other cost or actual total cost. The UI labels this value as the advertised annual total fee and explicitly excludes other costs, trading costs and taxes. `fees_cache.json` stores the last valid value, K-ETF page/API URLs and retrieval time. Transient 429/502/503/504 responses are retried up to three times; a failed live request uses the cache without changing its original retrieval time.

## Artifacts and failure handling

`trend_data.json` contains run `_meta` and compact ETF list facts/search text/sources; never OHLCV, profile buckets or strategies. `detail_data/<ticker>.json` contains full available OHLCV, facts/holdings and `_meta`, identical to that ETF's list `history_source`. All generated JSON comes from this script with `allow_nan=False`; serialization occurs before opening output files. Unregistered detail files are removed by the generator.

Default download failures stop before replacing artifacts. `--allow-cache` explicitly permits cached fallback after a live failure; `--offline` regenerates from cached OHLCV without network. Both mark histories incomplete and preserve their real dates. Missing caches still produce ETF rows with null metrics and empty detail history. These modes cannot recover old truncated data and do not fulfill a full-history backfill.

The checked-in redesign regeneration used the strict network mode:

```sh
.venv/bin/python gen_trend_data.py --end 2026-09-12
```

The run downloaded all 55 ETF histories successfully, fetched current Naver ETF market metadata and produced zero incomplete histories. The stored window begins no earlier than 2006-09-12; each ETF begins at the first row Yahoo returned after its own listing date. The longest current history is KODEX 200 with 4,266 rows from 2007-01-29 through 2026-09-11.

GitHub generation timeout is 45 minutes for all-history requests. Workflow runs the default strict mode and will not publish a partially downloaded run. No workflow was dispatched during this redesign.


## Direct-stock holdings

`holdings_cache.json` stores holdings by ETF code. The online collector requests the latest K-ETF holdings for every ETF. It selects at most ten direct stocks by descending original percentage weight, using `instrument_type == stock` or `asset_type == equity`, excluding cash, derivatives, bonds and funds/ETFs. API URL, original K-ETF page URL, holdings date and retrieval time are recorded.

PBR and PER collection, stock-level valuation matching, ratio aggregation and valuation cache entries are not part of the pipeline. Generated list and detail JSON must not contain `valuation`, `pbr`, `per` or `stocks` keys.

Holdings failures use a cached snapshot or the reviewed input, retaining its real date and marking failure/cache provenance in sources. Reviewed fallback snapshots are saved to the holdings cache. Empty successful portfolios are distinct from failed API calls.

`--offline` never requests any network resource and uses the holdings and fee caches along with cached OHLCV. Missing caches produce no holdings or current total fee unless a reviewed optional snapshot exists. `--allow-cache` attempts online collection while allowing existing prices on download failure. GitHub Actions stages both caches together with generated ETF data.

# Static integration and validation

`index.html` loads pinned Chart.js 4.4.8, `style.css` and `app.js` using deferred scripts. CSS, app and JSON fetches share the cache token `data-etf-20260913-v4`. No standalone detail page remains. Serve from any static HTTP host; ETF details are fetched on demand from `detail_data/`.

Native labels, buttons, `aria-sort`, range `aria-pressed`, result announcements, visible focus outlines and a labeled horizontal-scroll region support keyboard use. Detail opening focuses its heading; closing restores the ETF button when still visible. Dynamic text and URLs are escaped before HTML insertion. Source links accept HTTPS only. Chart library failure keeps facts visible and reports the chart error.

Validation commands from repository root:

```sh
.venv/bin/python -m pytest -q
node tests/etf_app.test.js
node tests/etf_dom.test.js
node --check app.js
.venv/bin/python -m py_compile gen_trend_data.py
.venv/bin/python tests/check_json.py
git diff --check
```

Pytest scratch files are kept in ignored repo-local `.test-tmp`. Tests fix the ETF registry independently, check full-history download dates, rolling warmup, Naver encodings/timeouts/malformed payloads, metadata fallbacks, sourced optional values, preserved KRX patch behavior, strict JSON and generated list/detail parity. The old pairwise contract tests were retired because the ETF analyzer requirements explicitly supersede them.

Initial focused RED: eight failures against the old implementation. Additional malformed-cache coverage also observed RED before the fix. A minimal DOM boundary harness also executes production search, sort, detail/cache and range event handlers. It does not validate layout. Browser visual checks could not run because Chromium failed to launch in this sandbox; Node behavioral tests and source checks are not substitutes for screenshot inspection.

Follow-up RED: six new tests failed before implementation. Cache-refresh and generated valuation tests added two further observed failures. Coverage includes API normalization, direct-stock filtering, Naver consensus/actual selection, Yahoo forward/trailing selection, harmonic coverage, cache expiration and offline network isolation. Strict validation includes valuation_cache.json and recomputes generated multiples.

# ETF analyzer behavior

`trend_data.json` schema v2 supplies a compact `etfs` array. There is no comparison signal, strategy or score schema. The exact 55 ETFs retained from the original registry are fixed by an independent test set; no individual equities are discovery rows.

One case-insensitive free-text search checks name, ticker, category, issuer, benchmark, exposure, and holdings names/tickers. Whitespace-separated terms must all match somewhere in that combined text. Category/issuer dropdowns include an explicit missing-information option. A minimum 20-day average volume input filters liquidity and excludes missing volumes when a positive threshold is set. Reset clears all filters.

Every displayed column sorts in both directions through a native button. Missing values sort last in either direction; name resolves ties. Headers expose `aria-sort`. Results count and loading/errors are announced. The ETF name is a keyboard-accessible detail button. Detail responses are cached, with request IDs preventing late responses from replacing the current selection or reopening a closed detail.

The list ends with 20-day average volume. It shows name/ticker, category, issuer, AUM, average trading value and average volume. Detail basic facts add only benchmark and exposure. Fees, premium/discount and holdings summaries are not basic-fact columns. Holdings analysis separately shows top-ten direct stocks, individual PER/PBR and symbols, aggregate multiples, valid N/M coverage and ETF weight coverage, basis, dates and source links. Fewer than ten eligible stocks use the actual count. Missing values display a dash. These multiples are not whole-ETF valuations.

Chart range buttons are exactly `1년`, `5년`, `10년`, default `1년`, with `aria-pressed`. Bounds are measured backwards from the last available trading date by calendar years, clamping leap day to February 28 when needed. Shorter histories show all available rows. Switching ranges updates chart data, visible date bounds and row counts. VWAP calculations occur before display slicing. Volume Profile controls are exactly `1일`, `20일`, `60일`, `240일`, independently anchored to the latest stored date.

`tests/etf_app.test.js` exercises exported production search/filter/sort, date slicing, exact colors, segment widths and chart update functions under Node. Browser visual validation is separate; passing Node tests does not establish rendered layout correctness.

The VWAP price y-axis uses Chart.js `type: logarithmic`, visibly labeled 로그 스케일. Nonfinite, zero and negative VWAP values become null before reaching the chart. Volume Profile retains its existing axes.

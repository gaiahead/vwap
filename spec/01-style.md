# ETF dashboard style

Keep the light blue/white dashboard, restrained borders, rounded panels and readable Korean type. The main panel is ETF discovery; detail expands below it. Active UI uses ETF wording.

The wide comparison table scrolls inside its own labeled, keyboard-focusable region. Headers stay visible; desktop ETF names stay fixed on horizontal scroll. On mobile the name column is not sticky so it cannot consume the viewport. Filters wrap; search occupies a full mobile row. Controls have visible focus indicators and approximately 40px touch targets. Facts use responsive cards; charts have bounded responsive heights.

Missing text or numbers render as `-`, never zero. Cost percentages preserve up to four decimal places. Market dates and dated facts remain visible; incomplete cached history gets a visible notice. Source links open safely with `noopener noreferrer`.

VWAP colors are fixed: 1일 `#eab308`, 20일 `#dc2626`, 60일 `#16a34a`, 240일 `#2563eb`. Adjacent falling segments use width 1; rising/equal/missing segments use width 2. Colors do not change with direction. No smoothed curves or bridges over missing values.

# HTML 구조 + 통합 명세 — `index.html`

> 99% 재현을 위한 DOM 구조, 데이터 연결, 렌더링 순서, 색상 팔레트, 타이포그래피 상세 기술

---

## 1. 문서 선언 및 `<html>`

```html
<!DOCTYPE html>
<html lang="ko">
```

- HTML5 문서
- 언어: 한국어 (`ko`)

---

## 2. `<head>`

```html
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>VWAP 추세 모니터</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3"></script>
  <link rel="stylesheet" href="style.css"/>
</head>
```

| 요소 | 내용 |
|------|------|
| `charset` | `UTF-8` |
| `viewport` | `width=device-width, initial-scale=1.0` — 모바일 반응형 |
| `title` | `VWAP 추세 모니터` |
| CDN 1 | Chart.js v4 (`chart.js@4`) |
| CDN 2 | chartjs-plugin-annotation v3 (`chartjs-plugin-annotation@3`) |
| CSS | `style.css` (로컬 파일) |

### CDN URL 정확한 형태

- `https://cdn.jsdelivr.net/npm/chart.js@4` — 최신 v4.x 자동 리졸브
- `https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3` — 최신 v3.x 자동 리졸브

### 로드 순서

1. Chart.js (동기 스크립트, head에서 로드)
2. chartjs-plugin-annotation (동기 스크립트, Chart.js 이후)
3. style.css (병렬 로드)

> `app.js`는 `<body>` 끝에서 로드 → Chart.js가 이미 준비된 상태

---

## 3. `<body>` 전체 구조

```
<body>
  ├── <header>
  │   ├── <h1>📊 VWAP 추세 모니터</h1>
  │   └── <p>Volume Weighted Average Price · <span#updated></span></p>
  ├── <div.chart-section>
  │   └── <div.chart-wrap>
  │       └── <canvas#chart-structure>
  ├── <div.groups#groups>
  │   └── (JS로 동적 생성)
  ├── <div.sci-section#sci-section> (초기 display:none)
  │   ├── <div.sci-title>📐 SCI (Slope Consistency Index)</div>
  │   └── <table.sci-table>
  │       ├── <thead> (12열 헤더)
  │       └── <tbody#sci-body> (JS로 동적 생성)
  ├── <div> (SCI 가중치 설명, 인라인 스타일)
  │   ├── 제목 div
  │   ├── 수식 설명 div
  │   ├── 비교 기준 설명 div
  │   └── <table> (인라인 스타일)
  │       ├── <thead> (4열 헤더)
  │       └── <tbody#sci-weight-table> (JS IIFE로 동적 생성)
  └── <script src="app.js">
```

---

## 4. 섹션별 상세

### 4-1. `<header>`

```html
<header>
  <h1>📊 VWAP 추세 모니터</h1>
  <p>Volume Weighted Average Price · <span id="updated"></span></p>
</header>
```

| 요소 | id | JS 연결 |
|------|----|---------|
| `<span>` | `updated` | `data._meta.updated_at + ' 기준'` |

**렌더링 결과 예시**: `Volume Weighted Average Price · 2026-03-27 07:00 기준`

### 4-2. 차트 영역

```html
<div class="chart-section">
  <div class="chart-wrap">
    <canvas id="chart-structure"></canvas>
  </div>
</div>
```

| 요소 | id/class | JS 연결 |
|------|---------|---------|
| `<canvas>` | `chart-structure` | `new Chart(document.getElementById('chart-structure'), ...)` |
| `.chart-wrap` | — | `resizeChart()`에서 `querySelector('.chart-wrap')` → `style.height` 설정 |

### 4-3. 종목 그룹 영역

```html
<div class="groups" id="groups"></div>
```

- **초기 상태**: 비어있음
- **JS `renderCards()`에서 동적 생성**:

```
<div.groups#groups>
  ├── <div.group>              (g1)
  │   ├── <div.asset-btn [active]>
  │   │   ├── <div.indicator>
  │   │   ├── <div.name>TLT</div>
  │   │   ├── <div.val style="color:rgb(...)">102.34</div>
  │   │   └── <div.sci>SCI 0.850</div>
  │   ├── <div.asset-btn>
  │   │   └── ...
  │   └── ...
  ├── <div.group>              (g2)
  │   └── ...
  └── <div.group>              (g3)
      └── ...
```

### 4-4. SCI 테이블 섹션

```html
<div class="sci-section" id="sci-section" style="display:none">
```

- **초기 `display:none`** — `renderSCI()`에서 조건 충족 시 `display: ''`로 변경

#### 테이블 헤더

```html
<thead>
  <tr>
    <th>종목</th>
    <th>SCI</th>
    <th>10d</th><th>20d</th><th>30d</th><th>40d</th><th>50d</th>
    <th>60d</th><th>70d</th><th>80d</th><th>90d</th><th>100d</th>
  </tr>
</thead>
```

- 총 12열: 종목명 + SCI + 10개 기간별 점수

#### 테이블 바디

```html
<tbody id="sci-body"></tbody>
```

- JS `renderSCI()`에서 동적 생성
- 각 행의 HTML 구조:

```html
<tr>
  <td>삼성전자</td>
  <td style="color:#4ade80;font-weight:700">0.850</td>
  <td style="color:#4ade80">8/10</td>
  <td style="color:#94a3b8">6/10</td>
  ...
</tr>
```

### 4-5. SCI 가중치 설명 섹션 (인라인 스타일)

이 섹션은 CSS 클래스 없이 전체 인라인 스타일로 구성:

```html
<div style="padding:16px 28px 32px;border-top:1px solid #1e2535;margin-top:8px">
```

#### 제목

```html
<div style="font-size:0.72rem;font-weight:700;color:#334155;letter-spacing:.08em;text-transform:uppercase;margin-bottom:12px">
  📐 SCI — Slope Consistency Index
</div>
```

#### 수식 설명

```html
<div style="font-size:0.75rem;color:#475569;margin-bottom:10px">
  투자금 = 기준값 × SCI  |  SCI = Σ(가중치 × 행 점수) / Σ(가중치)  |  지수 감소 0.75
</div>
```

- `&nbsp;|&nbsp;` — 구분자 양쪽에 non-breaking space

#### 비교 기준 설명

```html
<div style="font-size:0.73rem;color:#334155;margin-bottom:10px">
  비교 기준: slope &gt; endpoint × 1% (10d당 ≈ 주간 0.5% = 연 30%)  |
  행 점수 = 100개 슬로프 중 기준 초과 비율 (가중 평균)
</div>
```

- `&gt;` = `>` (HTML 엔티티)

#### 가중치 테이블

```html
<table style="border-collapse:collapse;font-size:0.72rem;width:100%;max-width:700px">
```

##### 헤더

```html
<thead>
  <tr>
    <th style="padding:4px 12px;text-align:left;color:#334155;border-bottom:1px solid #1e2535">Endpoint</th>
    <th style="padding:4px 12px;text-align:right;color:#334155;border-bottom:1px solid #1e2535">가중치</th>
    <th style="padding:4px 12px;text-align:right;color:#334155;border-bottom:1px solid #1e2535">비중</th>
    <th style="padding:4px 12px;text-align:left;color:#1e2535;border-bottom:1px solid #1e2535;padding-left:16px">시작점 범위</th>
  </tr>
</thead>
```

| 열 | 정렬 | 색상 |
|----|------|------|
| Endpoint | left | `#334155` |
| 가중치 | right | `#334155` |
| 비중 | right | `#334155` |
| 시작점 범위 | left | `#1e2535` (매우 어두움) |

##### 바디 (`#sci-weight-table`)

JS IIFE에서 동적 생성. 상세 스타일은 `02-app.md` 섹션 13 참조.

---

## 5. `<script src="app.js">` 위치

```html
  ...
  </div>  <!-- SCI 가중치 설명 끝 -->
  <script src="app.js"></script>
</body>
```

- `<body>` 마지막에 위치 → 모든 DOM 요소가 이미 파싱된 상태에서 실행
- `defer` 속성 없음 (body 끝이라 불필요)

---

## 6. 데이터 연결 (JSON → DOM)

### 6-1. 정적 바인딩 (페이지 로드 시 1회)

| JSON 경로 | DOM 요소 | 값 형식 |
|-----------|---------|---------|
| `_meta.updated_at` | `#updated` textContent | `"2026-03-27 07:00 기준"` |

### 6-2. 동적 바인딩 (renderCards, 클릭 시 재실행)

| JSON 경로 | DOM 요소 | 값 형식 |
|-----------|---------|---------|
| `[name].group` | 그룹 분류 | `g1`/`g2`/`g3` |
| `[name].vwap_structure[0].norm` | `.asset-btn .val` | `102.34` 또는 `–` |
| `calcSCI()` 결과 | `.asset-btn .sci` | `SCI 0.850` 또는 빈 문자열 |
| `calcColors()` 결과 | `.asset-btn` style `--c`, `.val` color | `rgb(R, G, B)` |

### 6-3. 차트 바인딩

| JSON 경로 | Chart.js 매핑 |
|-----------|--------------|
| `[name].vwap_structure[*].norm` (reversed) | `datasets[*].data` (20개 포인트) |
| `[name].vwap_structure[*].vwap` (reversed) | `datasets[*].rawVwap` (툴팁용) |

### 6-4. SCI 테이블 바인딩

| JSON 경로 | DOM 요소 |
|-----------|---------|
| `calcSCI()` → `sci` | SCI 열 |
| `calcSCI()` → `rowScores[0..9]` | 10d~100d 열 |

---

## 7. 렌더링 순서 (타임라인)

```
[브라우저 파싱]
  1. DOCTYPE, <html>, <head> 파싱
  2. Chart.js CDN 로드 (동기, 블로킹)
  3. chartjs-plugin-annotation CDN 로드 (동기, 블로킹)
  4. style.css 로드
  5. <body> 파싱 시작 → 정적 HTML 요소 생성
  6. <script src="app.js"> 만남 → 다운로드 + 실행

[app.js 실행]
  7. 전역 상수/변수 선언
  8. 함수 선언 (rankColor, calcColors)
  9. fetch('trend_data.json') 시작 (비동기, non-blocking)
  10. IIFE 실행 → #sci-weight-table에 가중치 행 10개 + 합계 행 즉시 삽입

[fetch 완료 (비동기)]
  11. allNames, namesByGroup 구성
  12. #updated 텍스트 설정
  13. 내부 함수 정의
  14. renderCards() → #groups에 종목 카드 생성 (각 카드에 클릭 이벤트 등록)
  15. renderSCI() → #sci-body에 SCI 테이블 행 생성 (조건 충족 시)
  16. new Chart() → 차트 렌더링 (300ms 애니메이션)
  17. resizeChart() → .chart-wrap 높이 설정 + 차트 리사이즈
  18. window resize 이벤트 리스너 등록

[사용자 인터랙션]
  19. 카드 클릭 → activeSet 토글 → renderCards() + updateChart()
  20. 창 크기 변경 → resizeChart()
```

---

## 8. 색상 팔레트 (전체 통합)

### 8-1. 배경 계층

| 계층 | 색상 | 용도 |
|------|------|------|
| L0 (가장 어두운) | `#0f1117` | body 배경 |
| L1 | `#161b27` | 카드, 차트 배경, td border-top |
| L2 | `#1a2030` | 호버/활성 카드 배경 |
| L3 | `#1e2535` | 테두리, 그리드선, 구분선 |

### 8-2. 텍스트 계층

| 계층 | 색상 | 용도 |
|------|------|------|
| T1 (가장 밝은) | `#f8fafc` | 제목 (h1) |
| T2 | `#e2e8f0` | body 기본 텍스트 |
| T3 | `#cbd5e1` | 테이블 데이터 |
| T4 | `#94a3b8` | 종목명, 라벨 |
| T5 | `#64748b` | 활성 SCI 텍스트 |
| T6 | `#475569` | 부제목, 비활성 텍스트, 틱 라벨 |
| T7 (가장 어두운) | `#334155` | 테이블 헤더, 설명 텍스트 |

### 8-3. 시맨틱 색상

| 의미 | 색상 | 용도 |
|------|------|------|
| 양호/긍정 | `#4ade80` | SCI ≥ 0.8, rowScore ≥ 0.8 |
| 중립 | `#94a3b8` | SCI 0.6~0.8, rowScore 0.5~0.8 |
| 부정/경고 | `#f87171` | SCI < 0.6 |
| 정보 (파란) | `#60a5fa` | 가중치 비중 퍼센트 |
| 막대 배경 | `#1e3a5f` | SCI 가중치 바 차트 |

### 8-4. 동적 색상 (rankColor)

| t 값 | RGB | 의미 |
|------|-----|------|
| 0.0 | `rgb(239, 68, 68)` | 최하위 (빨강) |
| 0.25 | `rgb(173, 91, 98)` | 하위 |
| 0.5 | `rgb(107, 114, 128)` | 중간 (회색) |
| 0.75 | `rgb(70, 155, 111)` | 상위 |
| 1.0 | `rgb(34, 197, 94)` | 최상위 (녹색) |

### 8-5. Chart.js 전용

| 용도 | 색상 |
|------|------|
| 그리드선 | `#1e2535` (= GRID) |
| 틱 라벨 | `#475569` (= TICK) |
| 기준선 (y=100) | `#475569` |
| 라벨 배경 | `rgba(15,17,23,0.85)` |

---

## 9. 타이포그래피

### 9-1. 폰트 패밀리

```
'Apple SD Gothic Neo', 'Pretendard', sans-serif
```

- **Apple SD Gothic Neo**: macOS/iOS 기본 한글 폰트
- **Pretendard**: 크로스 플랫폼 한글 폰트 (CDN 미포함, 시스템 설치 의존)
- **sans-serif**: 최종 폴백

> 웹폰트 CDN 없음. 로컬 시스템 폰트에 의존.

### 9-2. 폰트 크기 체계

| 크기 | 용도 |
|------|------|
| `1.2rem` | h1 제목, `.val` (10d norm 값) |
| `0.8rem` | `.sci-table` 기본 |
| `0.78rem` | `.asset-btn .name` (종목명) |
| `0.75rem` | SCI 수식 설명 (인라인) |
| `0.74rem` | `header p` (부제목) |
| `0.73rem` | SCI 비교 기준 설명 (인라인) |
| `0.72rem` | `.sci-title`, SCI 가중치 테이블, 가중치 제목 |
| `0.68rem` | `.asset-btn .sci` (SCI 값) |
| `0.65rem` | `.sci-table th` (테이블 헤더) |
| `10px` | Chart.js 틱 라벨, 어노테이션 라벨 |
| `8px` | SCI 가중치 바 차트 높이 |

### 9-3. 폰트 굵기

| 굵기 | 용도 |
|------|------|
| `800` | `.val` (10d norm 값, 가장 굵음) |
| `700` | h1, `.name`, `.sci-title`, `.sci-table td:first-child`, SCI 값, 가중치 제목 |
| `600` | `.sci-table th`, 합계 행 |
| 기본 (400) | 그 외 모든 텍스트 |

### 9-4. letter-spacing

| 값 | 용도 |
|----|------|
| `.08em` | SCI 가중치 제목 (인라인) |
| `.06em` | `.sci-title` |
| `.04em` | `.sci-table th` |

---

## 10. 반응형 동작

### 10-1. CSS 반응형

- `min-height: 100vh` — body가 뷰포트 전체 채움
- `flex-wrap: wrap` — `.group` 내 카드가 너비 부족 시 줄바꿈
- `width: 100%` — `.chart-wrap`, `.sci-table` 전체 너비
- `max-width: 700px` — SCI 가중치 테이블 최대 너비

### 10-2. JS 반응형

```js
h = Math.max(300, Math.min(420, window.innerHeight * 0.45))
```

| 뷰포트 높이 | 차트 높이 |
|-------------|----------|
| < 667px | 300px (최소) |
| 667~933px | 뷰포트 × 45% |
| > 933px | 420px (최대) |

### 10-3. 미디어 쿼리

없음. 모든 반응형 처리는 flex-wrap과 JS 리사이즈로 수행.

---

## 11. 접근성·SEO

| 항목 | 상태 |
|------|------|
| `lang="ko"` | 있음 |
| `charset="UTF-8"` | 있음 |
| `viewport` meta | 있음 |
| `title` | 있음 (`VWAP 추세 모니터`) |
| `alt` 속성 | 해당 없음 (이미지 없음) |
| ARIA 속성 | 없음 |
| 시맨틱 태그 | `<header>` 사용, `<main>` 미사용 |
| 키보드 탐색 | `.asset-btn`에 `cursor: pointer`만 있고 `tabindex`/`role` 없음 |
| 색상 대비 | 다크 모드 기반, 최소 텍스트 `#334155` on `#0f1117` (낮은 대비) |

---

## 12. 외부 의존성 요약

| 의존성 | 버전 | 로드 방식 | 용도 |
|--------|------|----------|------|
| Chart.js | @4 (latest v4.x) | CDN script (동기) | 라인 차트 렌더링 |
| chartjs-plugin-annotation | @3 (latest v3.x) | CDN script (동기) | 기준선 + 라벨 어노테이션 |
| style.css | — | 로컬 link | 스타일시트 |
| app.js | — | 로컬 script (body 끝) | 애플리케이션 로직 |
| trend_data.json | — | fetch (비동기) | 종목 데이터 |

---

## 13. ID 인벤토리

| ID | 요소 | 설정 위치 | JS 접근 |
|----|------|----------|---------|
| `updated` | `<span>` | HTML | `getElementById` → textContent |
| `chart-structure` | `<canvas>` | HTML | `getElementById` → new Chart() |
| `groups` | `<div>` | HTML | `getElementById` → innerHTML, appendChild |
| `sci-section` | `<div>` | HTML | `getElementById` → style.display |
| `sci-body` | `<tbody>` | HTML | `getElementById` → innerHTML, appendChild |
| `sci-weight-table` | `<tbody>` | HTML | `getElementById` → appendChild |

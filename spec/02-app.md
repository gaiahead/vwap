# JavaScript 완전 명세 — `app.js`

> 99% 재현을 위한 전역변수, 함수, Chart.js 설정, 이벤트, 실행순서 상세 기술

---

## 1. 전역 상수·변수

### 1-1. 상수

```js
const GRID = '#1e2535';
const TICK = '#475569';
```

| 이름 | 값 | 용도 |
|------|---|------|
| `GRID` | `'#1e2535'` | Chart.js x/y축 그리드선 색상 |
| `TICK` | `'#475569'` | Chart.js x/y축 틱 라벨 색상 |

```js
const STRUCT_LABELS = [
  '200d','190d','180d','170d','160d','150d','140d','130d','120d','110d',
  '100d','90d','80d','70d','60d','50d','40d','30d','20d','10d'
];
```

- 차트 x축 라벨, 20개 항목
- 200d(왼쪽) → 10d(오른쪽) 순서
- `vwap_structure` 배열을 `reverse()`하여 매핑

```js
const GROUP_ORDER = ['g1', 'g2', 'g3'];
```

- 종목 그룹 렌더링 순서

### 1-2. 변수

```js
let structChart;        // Chart.js 인스턴스 (나중에 할당)
let activeSet = new Set(['TLT']);  // 활성 종목 집합, 초기값 'TLT'
```

---

## 2. `rankColor(t)` — 색상 보간 함수

### 시그니처

```js
function rankColor(t) → string (CSS rgb 문자열)
```

### 매개변수

- `t`: 0~1 사이의 정규화된 값

### 로직

**`t >= 0.5` (상위 50% — 중간→녹색)**

```
s = (t - 0.5) * 2        // 0~1로 재정규화
R = 107 + (34 - 107) * s  // 107 → 34
G = 114 + (197 - 114) * s // 114 → 197
B = 128 + (94 - 128) * s  // 128 → 94
```

- `t=0.5` → `rgb(107, 114, 128)` (회색, `#6B7280`)
- `t=1.0` → `rgb(34, 197, 94)` (녹색, `#22C55E`)

**`t < 0.5` (하위 50% — 빨강→중간)**

```
s = t * 2                  // 0~1로 재정규화
R = 239 + (107 - 239) * s  // 239 → 107
G = 68 + (114 - 68) * s    // 68 → 114
B = 68 + (128 - 68) * s    // 68 → 128
```

- `t=0.0` → `rgb(239, 68, 68)` (빨강, `#EF4444`)
- `t=0.5` → `rgb(107, 114, 128)` (회색)

### 반환값

`rgb(R, G, B)` 형식 문자열 (소수점 없음, `Math.round` 적용)

---

## 3. `calcColors(names, data)` — 종목별 색상 계산

### 시그니처

```js
function calcColors(names, data) → { [name]: string }
```

### 로직

1. 각 종목의 `vwap_structure[0].norm` (= 10d norm 값) 추출
   - 없으면 기본값 `0` (`??` 연산자)
2. `min`, `max` 계산
3. `range = max - min`, 0이면 `1` (나눗셈 방지)
4. 각 종목: `t = (val - min) / range` → `rankColor(t)` 호출
5. `{ 종목명: color }` 객체 반환

### 중요 사항

- **상대적 순위**: 모든 종목의 10d norm을 비교하여 색상 결정
- 가장 높은 norm → 녹색, 가장 낮은 → 빨강

---

## 4. 데이터 로드 — `fetch('trend_data.json')`

### 실행 시점

스크립트 로드 시 즉시 실행 (모듈 아님, 전역 스코프)

### 데이터 구조 (기대하는 JSON)

```json
{
  "_meta": { "updated_at": "2026-03-27 07:00" },
  "TLT": {
    "ticker": "TLT",
    "group": "g1",
    "records": [...],
    "vwap_structure": [
      { "window": 10, "vwap": 88.5, "norm": 102.34 },
      { "window": 20, "vwap": 87.2, "norm": 100.84 },
      ...
      { "window": 200, "vwap": 86.5, "norm": 100.00 }
    ],
    "latest_price": 89.12
  },
  ...
}
```

### fetch 콜백 내부 처리 순서

1. `allNames` 추출 (`_meta` 키 제외)
2. `namesByGroup` 구성 (GROUP_ORDER 순서)
3. `#updated` 텍스트 설정
4. SCI 관련 함수 정의
5. `renderCards()` 호출
6. `renderSCI()` 호출
7. Chart.js 인스턴스 생성
8. `resizeChart()` 호출 + resize 이벤트 리스너 등록

---

## 5. `get10d(name)` — 10d norm 값 조회

```js
function get10d(name) {
  return data[name]?.vwap_structure?.[0]?.norm ?? null;
}
```

- `vwap_structure[0]` = window 10 (가장 짧은 기간)
- 없으면 `null` 반환

---

## 6. SCI (Slope Consistency Index) 계산

### 6-1. 상수

```js
const SCI_DECAY = 0.75;
const SCI_THRESHOLD = 0.01;  // endpoint × 1%
```

### 6-2. `calcSCI(name)` — SCI 계산

#### 시그니처

```js
function calcSCI(name) → { sci: number, rowScores: number[] } | null
```

#### 알고리즘 상세

1. **전제조건**: `vwap_structure` 존재, `vmap[10]`과 `vmap[200]` 모두 필요. 없으면 `null` 반환
2. **VWAP 맵 생성**: `{ window: vwap }` 형태
3. **가중치 배열**: 10개 항목
   ```
   weights[i] = 10 × 0.75^i   (i = 0..9)
   ```
   | i | endpoint | 가중치 | 비중 |
   |---|---------|--------|------|
   | 0 | 10d | 10.0000 | ~26.6% |
   | 1 | 20d | 7.5000 | ~19.9% |
   | 2 | 30d | 5.6250 | ~15.0% |
   | 3 | 40d | 4.2188 | ~11.2% |
   | 4 | 50d | 3.1641 | ~8.4% |
   | 5 | 60d | 2.3730 | ~6.3% |
   | 6 | 70d | 1.7798 | ~4.7% |
   | 7 | 80d | 1.3348 | ~3.6% |
   | 8 | 90d | 1.0011 | ~2.7% |
   | 9 | 100d | 0.7508 | ~2.0% |

4. **행별 점수 계산** (10행):
   - `endpoint = (i+1) * 10` → 10, 20, ..., 100
   - 각 행에서 최대 10개의 시작점을 비교: `start = endpoint + j*10` (j=1..10)
   - **slope 계산**: `(vmap[endpoint] - vmap[start]) / j`
   - **비교 기준**: `slope > vmap[endpoint] × 0.01`
   - `rowScore = 기준 초과 개수 / 전체 비교 개수`
   - 비교할 데이터가 없으면 `rowScore = 0`

5. **가중 평균**: `SCI = Σ(weights[i] × rowScores[i]) / Σ(weights)`

#### 엣지케이스

- `vmap[10]` 또는 `vmap[200]` 없으면 → `null`
- `vmap[start]`가 없는 경우 → 해당 비교 스킵 (`total`에 포함하지 않음)
- `total === 0` → `rowScore = 0`

### 6-3. `renderSCI()` — SCI 테이블 렌더링

```js
function renderSCI()
```

1. **대상 확인**: `['삼성전자','SK하이닉스','한미반도체','리노공업']` 중 하나라도 `data`에 있으면 실행
2. `#sci-section`의 `display` → `''` (보이기, 기본 `display:none`)
3. **모든 종목** (`allNames`)에 대해 `calcSCI()` 실행
4. SCI 내림차순 정렬
5. 각 행 HTML 생성:
   - 종목명
   - SCI 값 (소수점 3자리): 색상 — `≥0.8 → #4ade80`, `≥0.6 → #94a3b8`, `<0.6 → #f87171`
   - 10개 rowScore: `(s*10).toFixed(0)/10` 형식
     - 색상: `≥0.8 → #4ade80`, `≥0.5 → #94a3b8`, `<0.5 → #475569`

---

## 7. `renderCards()` — 종목 카드 렌더링

```js
function renderCards()
```

### 처리 순서

1. `calcColors(allNames, data)` 호출하여 전체 색상 계산
2. `#groups` 내용 초기화 (`innerHTML = ''`)
3. `GROUP_ORDER` 순서로 각 그룹 처리:
   - 그룹에 종목 없으면 스킵
   - `div.group` 생성
4. 각 종목마다:
   - `colors[name]`에서 색상 조회
   - `activeSet.has(name)`으로 활성 상태 확인
   - `get10d(name)`으로 10d norm 조회
   - `div.asset-btn` 생성, 활성이면 `active` 클래스 추가
   - CSS 변수 `--c` 설정: `btn.style.setProperty('--c', color)`
   - `calcSCI(name)` 호출하여 SCI 문자열 생성

### 카드 내부 HTML

```html
<div class="indicator"></div>
<div class="name">${name}</div>
<div class="val" style="color:${color}">${v10 != null ? v10.toFixed(2) : '–'}</div>
<div class="sci">${sciStr}</div>
```

- `.val`의 color는 인라인 스타일로 직접 설정 (CSS `var(--c)` 아님)
- SCI가 null이면 빈 문자열

### 클릭 이벤트

```js
btn.addEventListener('click', () => {
  if (activeSet.has(name)) activeSet.delete(name);
  else activeSet.add(name);
  renderCards();
  updateChart();
});
```

- 토글 동작: 이미 활성이면 제거, 아니면 추가
- 카드 전체 다시 렌더링 + 차트 업데이트

---

## 8. `makeDatasets()` — Chart.js 데이터셋 생성

```js
function makeDatasets() → Dataset[]
```

### 처리

1. `calcColors(allNames, data)` 호출
2. 모든 종목(`allNames`)에 대해 데이터셋 생성:

```js
{
  label: name,
  data: reversed.map(s => s.norm),    // 200d→10d 순 정규화값
  rawVwap: reversed.map(s => s.vwap), // 200d→10d 순 실제 VWAP
  borderColor: color,
  borderWidth: isActive ? 2 : 0,
  pointRadius: isActive ? 3 : 0,
  pointHoverRadius: isActive ? 4 : 0,
  pointBackgroundColor: color,
  tension: 0.3,
  fill: false,
  hidden: !isActive,
}
```

| 속성 | 활성(active) | 비활성 |
|------|-------------|--------|
| `borderWidth` | `2` | `0` |
| `pointRadius` | `3` | `0` |
| `pointHoverRadius` | `4` | `0` |
| `hidden` | `false` | `true` |

### `rawVwap` (커스텀 속성)

- Chart.js 표준이 아닌 커스텀 속성
- 툴팁에서 실제 VWAP 값 표시에 사용

### 데이터 순서

- `vwap_structure`는 10d(index 0) → 200d(index 19) 순
- `reverse()` 적용 → 200d(index 0) → 10d(index 19) 순
- `STRUCT_LABELS`와 매핑: `['200d', ..., '10d']`

---

## 9. `makeAnnotations()` — Chart.js 어노테이션 생성

```js
function makeAnnotations() → { [key]: AnnotationConfig }
```

### 기본 어노테이션

```js
base: {
  type: 'line',
  yMin: 100, yMax: 100,
  borderColor: '#475569',
  borderWidth: 1.5
}
```

- y=100 수평 기준선 (200d VWAP = 100으로 정규화되므로)

### 종목 라벨

활성 종목만, 10d norm 내림차순 정렬 후 생성:

```js
'lbl_' + name: {
  type: 'label',
  xValue: 19,                    // x축 마지막 위치 (10d)
  yValue: val,                   // 10d norm 값
  content: name + ' ' + val.toFixed(2),
  color: colors[name],
  font: { size: 10, weight: 'bold' },
  backgroundColor: 'rgba(15,17,23,0.85)',
  padding: { x: 4, y: 2 },
  position: { x: 'start', y: 'center' },
  xAdjust: 4,
}
```

- 차트 오른쪽 끝에 종목명 + 값 라벨 표시

---

## 10. `updateChart()` — 차트 갱신

```js
function updateChart() {
  structChart.data.datasets = makeDatasets();
  structChart.options.plugins.annotation.annotations = makeAnnotations();
  structChart.update('none');  // 애니메이션 없이 즉시 갱신
}
```

---

## 11. Chart.js 인스턴스 생성

```js
structChart = new Chart(document.getElementById('chart-structure'), config);
```

### 전체 설정

```js
{
  type: 'line',
  data: {
    labels: STRUCT_LABELS,   // ['200d', ..., '10d']
    datasets: makeDatasets()
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300 },
    interaction: { mode: 'index', intersect: false },
    layout: { padding: 0 },
    plugins: {
      legend: { display: false },
      annotation: { annotations: makeAnnotations() },
      tooltip: {
        callbacks: {
          label: ctx => {
            const norm = ctx.parsed.y?.toFixed(2);
            const raw = ctx.dataset.rawVwap?.[ctx.dataIndex];
            const rawStr = raw != null
              ? raw.toLocaleString(undefined, { maximumFractionDigits: 2 })
              : '–';
            return ` ${ctx.dataset.label}: ${norm} (VWAP ${rawStr})`;
          }
        }
      }
    },
    scales: {
      x: {
        ticks: { color: TICK, font: { size: 10 } },
        grid: { color: GRID }
      },
      y: {
        ticks: {
          color: TICK,
          font: { size: 10 },
          count: 11,
          callback: v => v.toFixed(2)
        },
        grid: { color: GRID },
        afterDataLimits(scale) {
          if (activeSet.size === 0) {
            scale.min = 100;
            scale.max = 200;
          }
        }
      }
    }
  }
}
```

### 주요 설정 해설

| 설정 | 값 | 설명 |
|------|---|------|
| `responsive` | `true` | 컨테이너 크기 추적 |
| `maintainAspectRatio` | `false` | 비율 고정 안 함 (높이를 JS로 제어) |
| `animation.duration` | `300` | 300ms 전환 애니메이션 |
| `interaction.mode` | `'index'` | 같은 x 위치의 모든 데이터셋 표시 |
| `interaction.intersect` | `false` | 정확히 포인트 위가 아니어도 툴팁 표시 |
| `legend.display` | `false` | 범례 숨김 (카드가 범례 역할) |
| `y.ticks.count` | `11` | y축 눈금 11개 |
| `y.ticks.callback` | `v => v.toFixed(2)` | 소수점 2자리 표시 |

### `afterDataLimits` 콜백

```js
afterDataLimits(scale) {
  if (activeSet.size === 0) {
    scale.min = 100;
    scale.max = 200;
  }
}
```

- 활성 종목이 없을 때 y축 범위를 100~200으로 고정
- 활성 종목이 있으면 Chart.js가 자동으로 데이터 기반 범위 설정

### 툴팁 라벨 콜백

형식: ` 종목명: norm값 (VWAP 실제값)`

예시: ` TLT: 102.34 (VWAP 88,500.00)`

- `rawVwap`이 null이면 `'–'` 표시
- `toLocaleString`으로 천단위 구분자 포함

---

## 12. `resizeChart()` — 반응형 차트 높이

```js
function resizeChart() {
  const wrap = document.querySelector('.chart-wrap');
  const h = Math.max(300, Math.min(420, window.innerHeight * 0.45));
  wrap.style.height = h + 'px';
  structChart.resize();
}
```

### 높이 계산

```
h = clamp(300, window.innerHeight × 0.45, 420)
```

- 최소 300px
- 최대 420px
- 뷰포트 높이의 45%

### 호출 시점

1. Chart.js 인스턴스 생성 직후 즉시 호출
2. `window.addEventListener('resize', resizeChart)` — 창 크기 변경 시

---

## 13. SCI 가중치 테이블 — IIFE

```js
(function() { ... })();
```

**fetch 밖에서 즉시 실행** (데이터 로드 전에도 실행됨)

### 처리 순서

1. `decay = 0.75`
2. 가중치 배열 생성: `weights[i] = +(10 * 0.75^i).toFixed(4)` (10개)
3. `total = Σweights`
4. `#sci-weight-table` (tbody) 조회
5. 각 가중치에 대해 행 생성:

```html
<tr>
  <td style="padding:4px 12px;color:#94a3b8">${endpoint}d</td>
  <td style="padding:4px 12px;text-align:right;color:#cbd5e1">${weight}</td>
  <td style="padding:4px 12px;text-align:right;color:#60a5fa">${percent}%</td>
  <td style="padding:4px 12px 4px 16px;color:#334155">
    <span style="display:inline-block;width:${barW}px;height:8px;background:#1e3a5f;border-radius:2px;vertical-align:middle;margin-right:6px"></span>
    ${endpoint+10}d ~ ${endpoint+100}d
  </td>
</tr>
```

| 셀 | 색상 | 내용 |
|----|------|------|
| Endpoint | `#94a3b8` | `10d`, `20d`, ... `100d` |
| 가중치 | `#cbd5e1` | `10.0000`, `7.5000`, ... |
| 비중 | `#60a5fa` (파란색) | 퍼센트 (소수점 2자리) |
| 시작점 범위 | `#334155` | 막대 그래프 + `20d ~ 110d` 등 |

**막대 그래프 너비**: `barW = Math.round(w / total * 120)` (최대 ~120px)

6. 합계 행:

```html
<tr>
  <td>합계</td>
  <td>${total}</td>
  <td>100.00%</td>
  <td>10~50d: 80.8% / 60~100d: 19.2%</td>
</tr>
```

- 합계 행은 `border-top: 1px solid #1e2535`, `font-weight: 600`

---

## 14. 실행 순서 (전체)

```
1. 브라우저가 app.js 로드
2. 전역 상수/변수 선언 (GRID, TICK, STRUCT_LABELS, GROUP_ORDER, structChart, activeSet)
3. rankColor(), calcColors() 함수 선언
4. fetch('trend_data.json') 시작 (비동기)
5. IIFE 실행 → SCI 가중치 테이블 즉시 렌더링
6. [fetch 완료 후]
   6-1. allNames, namesByGroup 구성
   6-2. #updated 텍스트 설정
   6-3. get10d, calcSCI, renderSCI, renderCards 등 함수 정의
   6-4. renderCards() → DOM에 카드 생성
   6-5. renderSCI() → SCI 테이블 생성 (조건 충족 시)
   6-6. new Chart() → structChart에 할당
   6-7. resizeChart() 즉시 호출
   6-8. window resize 이벤트 리스너 등록
```

---

## 15. 이벤트 리스너 요약

| 이벤트 | 대상 | 핸들러 | 설명 |
|--------|------|--------|------|
| `click` | 각 `.asset-btn` | 토글 activeSet → renderCards() + updateChart() | 종목 선택/해제 |
| `resize` | `window` | `resizeChart()` | 차트 높이 재계산 |

---

## 16. 엣지케이스·기본값 요약

| 상황 | 처리 |
|------|------|
| `data[name]` 없음 | `?.` 옵셔널 체이닝으로 undefined → 기본값 |
| `vwap_structure[0].norm` 없음 | `?? 0` (calcColors) 또는 `?? null` (get10d) |
| `activeSet.size === 0` | y축 강제 100~200 |
| `rawVwap` null | 툴팁에 `'–'` 표시 |
| `v10 === null` | 카드에 `'–'` 표시 |
| `calcSCI()` null | 카드의 SCI 텍스트 빈 문자열 |
| SCI 대상 종목 없음 | `#sci-section` 숨김 유지 (`display:none`) |
| `max === min` (calcColors) | `range = 1` → 모든 값이 `t=0` → 빨강 |

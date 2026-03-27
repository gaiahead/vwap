# CSS 완전 명세 — `style.css`

> 99% 재현을 위한 모든 셀렉터·속성·값 상세 기술

---

## 1. 색상 팔레트

| 용도 | 색상코드 | 사용처 |
|------|---------|--------|
| 배경 (body) | `#0f1117` | 페이지 전체 배경 |
| 카드/차트 배경 | `#161b27` | `.chart-wrap`, `.asset-btn`, `.sci-table td` border-top |
| 테두리/그리드 | `#1e2535` | `header`, `.chart-wrap`, `.asset-btn`, `.sci-table td` |
| 활성 카드 배경 | `#1a2030` | `.asset-btn.active`, `.asset-btn:hover` |
| 본문 텍스트 | `#e2e8f0` | `body color` |
| 헤더 제목 | `#f8fafc` | `header h1` |
| 보조 텍스트 (밝은) | `#cbd5e1` | `.sci-table td` |
| 라벨 텍스트 | `#94a3b8` | `.asset-btn .name`, `.sci-table td:first-child` |
| 서브텍스트 (어두운) | `#475569` | `header p`, `.asset-btn .sci`, `.sci-title` |
| 활성 서브텍스트 | `#64748b` | `.asset-btn.active .sci` |
| 테이블 헤더 | `#334155` | `.sci-table th` |
| CSS 변수 `--c` | 동적 (JS 주입) | 종목별 색상 — `rankColor()` 결과 |

---

## 2. 리셋 (`*`)

```css
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}
```

- 모든 요소에 `border-box` 박스 모델 적용
- 기본 margin·padding 제거

---

## 3. `body`

```css
body {
  font-family: 'Apple SD Gothic Neo', 'Pretendard', sans-serif;
  background: #0f1117;
  color: #e2e8f0;
  min-height: 100vh;
}
```

| 속성 | 값 | 설명 |
|------|---|------|
| `font-family` | `'Apple SD Gothic Neo', 'Pretendard', sans-serif` | macOS 한글 우선, Pretendard 폴백, 최종 sans-serif |
| `background` | `#0f1117` | 다크 네이비 배경 |
| `color` | `#e2e8f0` | 밝은 회색 기본 텍스트 |
| `min-height` | `100vh` | 뷰포트 전체 높이 최소 보장 |

---

## 4. `header`

```css
header {
  padding: 20px 28px 14px;
  border-bottom: 1px solid #1e2535;
}
```

- **padding**: 상 20px, 좌우 28px, 하 14px
- **border-bottom**: 1px 실선, `#1e2535` (구분선)

### 4-1. `header h1`

```css
header h1 {
  font-size: 1.2rem;
  font-weight: 700;
  color: #f8fafc;
}
```

- 굵기 700 (bold), 크기 1.2rem, 거의 흰색 (`#f8fafc`)

### 4-2. `header p`

```css
header p {
  font-size: 0.74rem;
  color: #475569;
  margin-top: 4px;
}
```

- 작은 부제목, 회색 (`#475569`), 제목과 4px 간격

---

## 5. `.chart-section`

```css
.chart-section {
  padding: 20px 28px 0;
}
```

- 차트 영역 래퍼, 상단·좌우 28px 패딩, 하단 없음

---

## 6. `.chart-wrap`

```css
.chart-wrap {
  background: #161b27;
  border: 1px solid #1e2535;
  border-radius: 14px;
  padding: 18px;
  margin-bottom: 20px;
  position: relative;
  width: 100%;
}
```

| 속성 | 값 | 설명 |
|------|---|------|
| `background` | `#161b27` | 카드 배경 (body보다 약간 밝음) |
| `border` | `1px solid #1e2535` | 얇은 테두리 |
| `border-radius` | `14px` | 둥근 모서리 |
| `padding` | `18px` | 내부 여백 |
| `margin-bottom` | `20px` | 아래 카드 그룹과 간격 |
| `position` | `relative` | 내부 절대 위치 요소의 기준 |
| `width` | `100%` | 부모 너비 100% |

> **높이**: CSS에서 지정하지 않음. JS `resizeChart()`에서 `style.height`를 동적으로 설정 (300~420px).

---

## 7. 종목 그룹 (`.groups`, `.group`)

### 7-1. `.groups`

```css
.groups {
  padding: 0 28px 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
```

- 세로 flex 컨테이너, 그룹 간 8px 간격
- 좌우 28px, 하단 24px 패딩

### 7-2. `.group`

```css
.group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
```

- 가로 flex, wrap 허용, 버튼 간 8px 간격

---

## 8. 종목 버튼 (`.asset-btn`)

### 8-1. 기본 상태

```css
.asset-btn {
  background: #161b27;
  border: 1.5px solid #1e2535;
  border-radius: 10px;
  padding: 10px 12px;
  cursor: pointer;
  transition: all .2s;
  user-select: none;
  text-align: left;
  position: relative;
  overflow: hidden;
  flex: 0 0 auto;
  min-width: 90px;
}
```

| 속성 | 값 | 설명 |
|------|---|------|
| `background` | `#161b27` | 차트와 동일한 카드 배경 |
| `border` | `1.5px solid #1e2535` | 기본 테두리 (1.5px) |
| `border-radius` | `10px` | 둥근 모서리 |
| `padding` | `10px 12px` | 상하 10px, 좌우 12px |
| `cursor` | `pointer` | 클릭 가능 커서 |
| `transition` | `all .2s` | 모든 속성 0.2초 전환 |
| `user-select` | `none` | 텍스트 선택 방지 |
| `text-align` | `left` | 왼쪽 정렬 |
| `position` | `relative` | `.indicator`의 절대 위치 기준 |
| `overflow` | `hidden` | 인디케이터가 border-radius 밖으로 넘치지 않도록 |
| `flex` | `0 0 auto` | 축소·확대 없음, 고유 크기 유지 |
| `min-width` | `90px` | 최소 너비 90px |

### 8-2. 활성 상태 (`.asset-btn.active`)

```css
.asset-btn.active {
  border-color: var(--c);
  background: #1a2030;
}
```

- 테두리가 종목 색상(`--c`)으로 변경
- 배경이 약간 밝아짐 (`#1a2030`)

### 8-3. 호버 상태 (`.asset-btn:hover`)

```css
.asset-btn:hover {
  background: #1a2030;
}
```

- 마우스 오버 시 배경 변경 (active와 동일 배경)

---

## 9. 버튼 내부 요소

### 9-1. `.asset-btn .name`

```css
.asset-btn .name {
  font-size: 0.78rem;
  font-weight: 700;
  color: #94a3b8;
  transition: color .2s;
  white-space: nowrap;
}
```

- 종목명, 굵게, 줄바꿈 방지, 비활성 시 회색

### 9-2. `.asset-btn.active .name`

```css
.asset-btn.active .name {
  color: var(--c);
}
```

- 활성 시 종목 색상으로 변경

### 9-3. `.asset-btn .val`

```css
.asset-btn .val {
  font-size: 1.2rem;
  font-weight: 800;
  line-height: 1.1;
  margin-top: 4px;
}
```

- 10d norm 값 표시, 가장 큰 텍스트 (1.2rem, 800 굵기)
- **인라인 `style="color:${color}"`** — JS에서 직접 설정 (CSS에 color 없음)

### 9-4. `.asset-btn .sci`

```css
.asset-btn .sci {
  font-size: 0.68rem;
  color: #475569;
  margin-top: 3px;
}
```

- SCI 값 표시, 가장 작은 텍스트

### 9-5. `.asset-btn.active .sci`

```css
.asset-btn.active .sci {
  color: #64748b;
}
```

- 활성 시 약간 밝아짐

---

## 10. 인디케이터 (`.asset-btn .indicator`)

```css
.asset-btn .indicator {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--c);
  opacity: 0;
  transition: opacity .2s;
}
```

- 버튼 상단에 2px 높이의 색상 바
- 기본 상태에서는 `opacity: 0` (숨김)

```css
.asset-btn.active .indicator {
  opacity: 1;
}
```

- 활성 시 나타남 (0.2초 전환)

---

## 11. SCI 섹션

### 11-1. `.sci-section`

```css
.sci-section {
  padding: 0 28px 24px;
}
```

- 좌우 28px, 하단 24px

### 11-2. `.sci-title`

```css
.sci-title {
  font-size: 0.72rem;
  font-weight: 700;
  color: #475569;
  letter-spacing: .06em;
  text-transform: uppercase;
  margin-bottom: 10px;
}
```

- 대문자 변환, letter-spacing 확장된 라벨 스타일

### 11-3. `.sci-table`

```css
.sci-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}
```

### 11-4. `.sci-table th`

```css
.sci-table th {
  padding: 5px 10px;
  text-align: right;
  font-size: 0.65rem;
  font-weight: 600;
  color: #334155;
  letter-spacing: .04em;
}
```

- 기본 오른쪽 정렬

```css
.sci-table th:first-child {
  text-align: left;
}
```

- 첫 번째 열(종목명)만 왼쪽 정렬

### 11-5. `.sci-table td`

```css
.sci-table td {
  padding: 7px 10px;
  text-align: right;
  color: #cbd5e1;
  border-top: 1px solid #161b27;
}
```

- 행 구분선: `#161b27` (배경과 거의 같아 미세한 구분)

```css
.sci-table td:first-child {
  text-align: left;
  font-weight: 700;
  color: #94a3b8;
}
```

- 첫 번째 열(종목명): 왼쪽 정렬, 굵게, 회색

---

## 12. 트랜지션 요약

| 셀렉터 | 속성 | 지속시간 | 대상 |
|--------|------|---------|------|
| `.asset-btn` | `all` | `0.2s` | 배경, 테두리 등 전체 |
| `.asset-btn .name` | `color` | `0.2s` | 텍스트 색상 |
| `.asset-btn .indicator` | `opacity` | `0.2s` | 인디케이터 표시/숨김 |

---

## 13. CSS 변수

| 변수 | 설정 위치 | 설명 |
|------|----------|------|
| `--c` | JS `btn.style.setProperty('--c', color)` | 종목별 동적 색상. `rankColor()` 결과를 inline `--c`로 주입 |

이 변수는 `.asset-btn.active`의 `border-color`, `.asset-btn.active .name`의 `color`, `.indicator`의 `background`에서 참조됨.

---

## 14. 인라인 스타일 (CSS 파일 외)

CSS 파일에 포함되지 않았으나 `index.html`과 `app.js`에서 직접 설정하는 스타일:

| 요소 | 속성 | 값 | 설정 위치 |
|------|------|----|----------|
| `.chart-wrap` | `height` | `${h}px` (300~420) | `app.js` `resizeChart()` |
| `.asset-btn .val` | `color` | `${color}` | `app.js` `renderCards()` |
| `.asset-btn` | `--c` | `${color}` | `app.js` `renderCards()` |
| SCI 가중치 테이블 셀 | 다양한 inline style | `app.js` IIFE |
| SCI 설명 div | 다양한 inline style | `index.html` 직접 |

인라인 스타일의 자세한 값은 `04-html-integration.md`에서 다룸.

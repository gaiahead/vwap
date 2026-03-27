# Python 데이터 파이프라인 완전 명세 — `gen_trend_data.py`

> 99% 재현을 위한 상수, 수식, 엣지케이스, yfinance 설정, GitHub Actions 상세 기술

---

## 1. 모듈 구조

```
gen_trend_data.py
├── 임포트
├── 상수 (ASSETS, WINDOWS, N_BUCKETS, KST, ...)
├── compute_vwap()           — 단일 윈도우 VWAP 계산
├── compute_vwap_series()    — 롤링 VWAP 시계열
├── strength_score()         — 백분위 강도 점수
├── download_ohlcv()         — yfinance 데이터 다운로드
├── build_vwap_structure()   — VWAP 기간 구조 스냅샷
├── build_weekly_records()   — 주간 시계열 레코드
├── process_asset()          — 단일 종목 처리
└── main()                   — 메인 실행
```

---

## 2. 임포트

```python
from __future__ import annotations  # PEP 604 유니온 타입 지원
import json, sys
from datetime import date, datetime, timedelta, timezone
from typing import Any
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm  # 정규분포 PDF
```

---

## 3. 상수

### 3-1. 종목 설정 (`ASSETS`)

```python
AssetTuple = tuple[str, str, str]  # (표시명, 티커, 그룹)
```

| 그룹 | 종목 수 | 내용 |
|------|--------|------|
| `g1` | 5 | TLT, GLD, IBIT, SPY, QQQ — 미국 대표 ETF |
| `g2` | 15 | 한국 해외투자 ETF + 미국 대형 기술주 — SOL, TIGER, KODEX, ACE ETF + NVDA, GOOGL, AAPL, MSFT, AMZN, META, AVGO, TSLA, NFLX, PLTR, CSCO |
| `g3` | 10 | 한국 시장 — KODEX 200, KODEX 코스닥150, 반도체 ETF 4종, 삼성전자, SK하이닉스, 한미반도체, 리노공업 |

**총 30개 종목**

한국 종목 티커 형식: `XXXXXX.KS` (KRX 거래소 코드)

### 3-2. 기타 상수

| 상수 | 값 | 설명 |
|------|---|------|
| `WINDOWS` | `[10, 20, 30, ..., 200]` | `range(10, 201, 10)` — 20개 윈도우 |
| `N_BUCKETS` | `20` | Volume Profile 가격 구간 수 |
| `KST` | `timezone(timedelta(hours=9))` | 한국 표준시 (UTC+9) |
| `DATA_START` | `"2023-01-01"` | yfinance 데이터 시작일 |
| `WEEKLY_CUTOFF` | `date(2025, 1, 6)` | 주간 데이터 필터링 시작일 |
| `EXCLUDE_DATES` | `frozenset({"2025-12-31", "2025-12-30", "2025-12-29"})` | 제외할 날짜 (연말) |
| `OUTPUT_PATH` | `"trend_data.json"` | 출력 파일 경로 |

---

## 4. `compute_vwap(df_window)` — 정규분포 기반 Volume Profile VWAP

### 시그니처

```python
def compute_vwap(df_window: pd.DataFrame) -> float
```

### 알고리즘

1. **가격 범위 계산**
   ```
   lo = df_window["low"].min()
   hi = df_window["high"].max()
   ```

2. **엣지케이스: hi == lo**
   ```python
   return float(df_window["close"].mean())
   ```

3. **버킷 생성** (N_BUCKETS = 20개)
   ```
   bsize = (hi - lo) / 20
   bucket_prices[b] = lo + (b + 0.5) × bsize    (b = 0..19)
   ```
   - 각 버킷의 중심 가격

4. **거래량 분배** (각 봉마다)
   ```
   mu = (high + low + close) / 3          # 대표가격 (TP: Typical Price)
   sigma = (high - low) / 4               # 변동성 추정
   ```

   - **sigma == 0** (시가=고가=저가):
     ```
     idx = min(19, int((mu - lo) / bsize))
     bvol[idx] += volume
     ```
     해당 버킷에 전체 거래량 집중

   - **sigma > 0**:
     ```
     weights = norm.pdf(bucket_prices, mu, sigma)
     bvol += volume × (weights / sum(weights))
     ```
     정규분포 확률밀도 기반으로 거래량 분배

5. **VWAP 계산**
   ```
   total_vol = sum(bvol)
   ```
   - **total_vol == 0**: `return df_window["close"].iloc[-1]` (마지막 종가)
   - **정상**: `return sum(bucket_prices × bvol) / total_vol`

### 수학적 의미

일반적인 VWAP = Σ(Price × Volume) / ΣVolume인데, 이 구현은:
- 각 봉의 거래량을 가격 범위에 따라 정규분포로 분배
- 20개 가격 버킷에 누적 후 가중 평균 계산
- 실제 체결 가격별 거래량 데이터 없이도 Volume Profile 근사 가능

---

## 5. `compute_vwap_series(df, window=20)` — 롤링 VWAP 시계열

### 시그니처

```python
def compute_vwap_series(df: pd.DataFrame, window: int = 20) -> list[float | None]
```

### 로직

```python
for i in range(len(df)):
    if i < window:
        vwaps.append(None)       # 윈도우 미충족
    else:
        vwaps.append(compute_vwap(df.iloc[i-window:i]))
```

- 인덱스 `i`에서 직전 `window`일의 데이터로 VWAP 계산
- `i < window`이면 데이터 부족 → `None`

---

## 6. `strength_score(arr, norm_window=52)` — 백분위 강도 점수

### 시그니처

```python
def strength_score(arr: list[float | None], norm_window: int = 52) -> list[float | None]
```

### 알고리즘

각 인덱스 `i`에 대해:

1. `arr[i]`가 `None`이거나 `NaN`이면 → `None`
2. 룩백 윈도우: `arr[max(0, i-52) : i+1]` 에서 `None`/`NaN` 제외
3. 유효 값 5개 미만 → `None`
4. **백분위 계산**:
   ```
   pct = (현재값 이하인 값의 수) / (전체 유효값 수)
   score = round((pct × 2 - 1) × 100, 1)
   ```
   - 범위: `-100.0` ~ `+100.0`
   - `pct = 0.0` → score = `-100.0` (최하위)
   - `pct = 0.5` → score = `0.0` (중간)
   - `pct = 1.0` → score = `+100.0` (최상위)

---

## 7. `download_ohlcv(ticker, end_date)` — yfinance 다운로드

### 시그니처

```python
def download_ohlcv(ticker: str, end_date: str) -> pd.DataFrame
```

### yfinance 설정

```python
yf.download(
    ticker,
    start=DATA_START,         # "2023-01-01"
    end=end_date,             # 실행일 (KST 기준)
    interval="1d",            # 일봉
    auto_adjust=True,         # 수정주가 자동 적용
    progress=False,           # 진행바 숨김
)
```

### 후처리

```python
raw.columns = [c[0].lower() for c in raw.columns]
```

- yfinance 반환 컬럼이 MultiIndex인 경우 → 첫 번째 레벨만 사용, 소문자 변환
- 예: `('Close', 'TLT')` → `'close'`

```python
return raw[["open", "high", "low", "close", "volume"]].dropna().copy()
```

- OHLCV 5개 컬럼만 선택, NaN 행 제거

---

## 8. `build_vwap_structure(df)` — VWAP 기간 구조 스냅샷

### 시그니처

```python
def build_vwap_structure(df: pd.DataFrame) -> tuple[list[dict[str, Any]], float | None]
```

### 로직

1. `WINDOWS` (10~200, 10일 간격)를 순회:
   - `len(df) >= w` → `compute_vwap(df.iloc[-w:])` 계산, 소수점 4자리 반올림
   - `len(df) < w` → `vwap = None`
   - `w == 200` → `base_vwap`로 저장

2. **정규화** (`base_vwap`가 존재할 때):
   ```
   norm = round(vwap / base_vwap × 100, 2)
   ```
   - 200d VWAP = 100.00 기준
   - `vwap`이 None이면 `norm = None`

### 반환값

```python
(
  [
    {"window": 10, "vwap": 88.5432, "norm": 102.34},
    {"window": 20, "vwap": 87.2100, "norm": 100.84},
    ...
    {"window": 200, "vwap": 86.5000, "norm": 100.00}
  ],
  86.5000  # base_vwap
)
```

### 엣지케이스

- `base_vwap` falsy (0 또는 None) → norm 필드 추가 안 됨
- 데이터 부족 → 해당 윈도우의 vwap = None, norm = None

---

## 9. `build_weekly_records(df)` — 주간 시계열 레코드

### 시그니처

```python
def build_weekly_records(df: pd.DataFrame) -> list[dict[str, Any]]
```

### 처리 순서

1. **20일 롤링 VWAP 시계열** 생성 → `df["vwap"]`
2. **5일 전 VWAP**: `df["vwap_prev5"] = shift(5)`
3. **주간 변화율**:
   ```
   weekly_chg = (vwap - vwap_prev5) / vwap_prev5 × 100
   ```
4. **주(week)·연도(year)** 컬럼 추가 (ISO calendar)
5. **주간 샘플링**: 각 (year, week) 그룹의 마지막 거래일 선택
6. **강도 점수**: `strength_score(weekly_chg)` — 52주 룩백 백분위
7. **필터링**:
   - `date >= WEEKLY_CUTOFF` (2025-01-06)
   - `date ∉ EXCLUDE_DATES`
8. **레코드 생성**:
   ```python
   {
     "date": "2026-03-27",
     "price": 89.12,       # round(close, 2)
     "score": 45.2          # strength_score 결과
   }
   ```

---

## 10. `process_asset(name, ticker, group, end_date)` — 단일 종목 처리

### 시그니처

```python
def process_asset(name, ticker, group, end_date) -> dict[str, Any] | None
```

### 처리 순서

1. 다운로드 시도 → 예외 발생 시 에러 출력, `None` 반환
2. 빈 DataFrame → 경고 출력, `None` 반환
3. `build_vwap_structure(df)` 호출
4. `build_weekly_records(df)` 호출
5. 200d norm과 10d norm 출력 (디버그)
6. 결과 딕셔너리 반환:

```python
{
  "ticker": ticker,
  "group": group,
  "records": records,          # 주간 시계열
  "vwap_structure": vwap_structure,  # 20개 윈도우 스냅샷
  "latest_price": round(float(df["close"].iloc[-1]), 2)
}
```

---

## 11. `main()` — 메인 실행

### 처리 순서

1. `run_time` = 현재 KST 시각 (`%Y-%m-%d %H:%M`)
2. `end_date` = 현재 KST 날짜 (`%Y-%m-%d`)
3. 결과 딕셔너리 초기화: `{"_meta": {"updated_at": run_time}}`
4. `ASSETS` 순회하여 각 종목 처리:
   - 성공 → `result[name] = asset_data`
   - 실패 → `failed` 리스트에 추가
5. `trend_data.json`에 JSON 출력 (`ensure_ascii=False`)
6. 성공 메시지 출력
7. 실패 종목 있으면 → 경고 출력 + `sys.exit(1)`

### 종료 코드

- `0`: 모든 종목 성공
- `1`: 1개 이상 실패 (GitHub Actions에서 워크플로우 실패로 표시)

---

## 12. GitHub Actions — `.github/workflows/update.yml`

### 워크플로우 설정

```yaml
name: Update trend data
on:
  schedule:
    - cron: '0 22 * * *'   # UTC 22:00 = KST 07:00 (매일)
  workflow_dispatch:         # 수동 실행 가능
```

### 잡 설정

```yaml
jobs:
  update:
    runs-on: ubuntu-latest
    permissions:
      contents: write        # git push 권한
    timeout-minutes: 15
```

### 스텝

| 순서 | 이름 | 내용 |
|------|------|------|
| 1 | Checkout | `actions/checkout@v4` |
| 2 | Set up Python | `actions/setup-python@v5`, Python 3.11, pip 캐시 |
| 3 | Install dependencies | `pip install yfinance pandas numpy scipy` |
| 4 | Generate trend data | `python gen_trend_data.py` |
| 5 | Commit and push | git config → git add → diff 확인 → commit → push |

### 커밋 명령

```bash
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
git add trend_data.json
git diff --staged --quiet || git commit -m "data: auto update $(TZ='Asia/Seoul' date +'%Y-%m-%d %H:%M KST')"
git push
```

- `git diff --staged --quiet` — 변경 없으면 커밋 스킵 (종료코드 0)
- 변경 있으면 커밋 메시지: `data: auto update 2026-03-27 07:00 KST`

### 의존성

| 패키지 | 용도 |
|--------|------|
| `yfinance` | 주가 데이터 다운로드 |
| `pandas` | DataFrame 처리 |
| `numpy` | 배열 연산 |
| `scipy` | `norm.pdf` 정규분포 확률밀도 |

---

## 13. 출력 JSON 구조 (`trend_data.json`)

```json
{
  "_meta": {
    "updated_at": "2026-03-27 07:00"
  },
  "TLT": {
    "ticker": "TLT",
    "group": "g1",
    "records": [
      {"date": "2025-01-10", "price": 87.50, "score": -12.3},
      ...
    ],
    "vwap_structure": [
      {"window": 10,  "vwap": 88.5432, "norm": 102.34},
      {"window": 20,  "vwap": 87.2100, "norm": 100.84},
      ...
      {"window": 200, "vwap": 86.5000, "norm": 100.00}
    ],
    "latest_price": 89.12
  },
  "GLD": { ... },
  ...
}
```

### 키 순서

- `_meta`가 먼저
- 이후 `ASSETS` 리스트 순서대로 (Python 3.7+ dict 삽입순 보장)

---

## 14. 엣지케이스 종합

| 상황 | 처리 |
|------|------|
| yfinance 다운로드 실패 | 에러 출력, `None` 반환, `failed` 리스트 추가 |
| 빈 DataFrame | 경고 출력, `None` 반환 |
| `high == low` (전 기간) | `compute_vwap` → `close.mean()` 반환 |
| `sigma == 0` (단일 봉) | 해당 봉의 거래량을 단일 버킷에 집중 |
| `total_w == 0` (norm.pdf 합계 0) | 거래량 분배 스킵 |
| `total_vol == 0` (전체 버킷 거래량 0) | 마지막 종가 반환 |
| 데이터 부족 (`len(df) < w`) | 해당 윈도우 `vwap = None, norm = None` |
| `base_vwap` falsy | norm 필드 미생성 |
| 주간 데이터에서 None/NaN | `strength_score` 내부에서 필터링 |
| 유효 값 5개 미만 | `strength_score` → `None` |
| 실행일이 EXCLUDE_DATES | 해당 주간 레코드 제외 |
| 모든 종목 실패 | `_meta`만 있는 JSON 출력, exit(1) |

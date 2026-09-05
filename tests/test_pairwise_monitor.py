"""Exercise generator snapshots through the real frontend with a small DOM/Chart stub."""

import copy
import json
import subprocess
from itertools import permutations
from pathlib import Path

import pandas as pd
import pytest

import gen_trend_data as gen


ROOT = Path(__file__).resolve().parents[1]
PAIRS = [(5, 20), (5, 60), (5, 120), (20, 60), (20, 120), (60, 120)]
KEYS = [f"alignment_{left}_{right}" for left, right in PAIRS]

NODE_MONITOR = r"""
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
class Element {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.dataset = {}; this.style = {};
    this.attributes = {}; this.events = {}; this.textContent = ''; this.className = '';
    this.classList = {
      contains: name => this.className.split(' ').includes(name),
      add: name => { if (!this.classList.contains(name)) this.className += ' ' + name; },
      remove: name => { this.className = this.className.split(' ').filter(x => x !== name).join(' '); },
      toggle: (name, active) => active ? this.classList.add(name) : this.classList.remove(name)
    };
  }
  append(...nodes) { this.children.push(...nodes); }
  appendChild(node) { this.append(node); return node; }
  replaceChildren(...nodes) { this.children = nodes; }
  insertBefore(node, reference) { this.children.splice(this.children.indexOf(reference), 0, node); }
  setAttribute(key, value) { this.attributes[key] = value; }
  addEventListener(type, handler) { (this.events[type] ||= []).push(handler); }
  dispatch(type, event = {}) { (this.events[type] || []).forEach(handler => handler(event)); }
  click() { this.dispatch('click', {target: this}); }
  matches(selector) { return selector[0] === '.' && this.classList.contains(selector.slice(1)); }
  querySelector(selector) { return descendants(this).find(node => node.matches(selector)) || null; }
  scrollIntoView() { this.scrolled = true; }
}
function descendants(element) {
  return element.children.flatMap(child => [child, ...descendants(child)]);
}
const ids = Object.fromEntries([
  'updated', 'momentum-section', 'momentum-body', 'detail-section', 'detail-content',
  'detail-title', 'detail-symbol', 'detail-close'
].map(id => [id, new Element('div')]));
const headers = [...fs.readFileSync('index.html', 'utf8').matchAll(/<th data-sort="([^"]+)">([^<]+)<\/th>/g)]
  .map(match => {
    const th = new Element('th'); th.dataset.sort = match[1]; th.textContent = match[2]; return th;
  });
const document = {
  createElement: tag => new Element(tag),
  getElementById: id => ids[id] || descendants(ids['detail-content']).find(node => node.id === id) || null,
  querySelectorAll: selector => selector === '.momentum-table th[data-sort]'
    ? headers : descendants(ids['detail-content']).filter(node => node.matches(selector))
};
const requests = []; const charts = [];
class Chart {
  constructor(canvas, config) { this.canvas = canvas; this.config = config; charts.push(this); }
  destroy() { this.destroyed = true; }
}
const context = {
  window: {}, document, Chart, location: {hash: ''},
  fetch: async (url, options) => {
    requests.push({url, options});
    return {ok: true, json: async () => url.startsWith('trend_data') ? input.data : input.detail};
  }
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('app.js', 'utf8'), context);
const flush = () => new Promise(resolve => setImmediate(resolve));
function rows() {
  return ids['momentum-body'].children.map(row => ({
    cells: row.children.map(cell => cell.textContent),
    classes: row.children.map(cell => cell.className),
    titles: row.children.map(cell => cell.title || cell.attributes.title || ''),
    active: row.classList.contains('detail-active')
  }));
}
function headerState() {
  return headers.map(th => ({key: th.dataset.sort, dir: th.dataset.sortDir,
    aria: th.attributes['aria-sort'], tabIndex: th.tabIndex}));
}
(async () => {
  await flush();
  const initial = rows();
  const initialHeaders = headerState();
  const sorts = [];
  for (const header of [...headers.slice(1), headers[0]]) {
    header.click();
    const first = {rows: rows(), headers: headerState()};
    let prevented = false;
    header.dispatch('keydown', {key: 'Enter', preventDefault() { prevented = true; }});
    sorts.push({key: header.dataset.sort, first, second: {rows: rows(), headers: headerState()}, prevented});
  }
  const target = input.target;
  const clickRow = () => ids['momentum-body'].children.find(row => row.children[0].textContent === target).click();
  clickRow(); await flush();
  const firstDetail = {
    hash: context.location.hash, title: ids['detail-title'].textContent,
    symbol: ids['detail-symbol'].textContent, active: rows().filter(row => row.active).map(row => row.cells[0]),
    tabs: document.querySelectorAll('.vp-tab').map(tab => tab.textContent),
    charts: charts.map(chart => ({type: chart.config.type, labels: chart.config.data.labels.length})),
    loading: ids['detail-content'].children.some(node => node.className === 'loading')
  };
  const tabs = document.querySelectorAll('.vp-tab');
  const lastTab = tabs.at(-1);
  document.getElementById('vp-tabs')?.dispatch('click', {target: lastTab});
  const selectedPeriod = document.querySelectorAll('.vp-tab').find(tab => tab.classList.contains('active'))?.textContent;
  clickRow(); await flush();
  const repeated = {
    activePeriod: document.querySelectorAll('.vp-tab').find(tab => tab.classList.contains('active'))?.textContent,
    latestVpVolume: charts.at(-1)?.config.data.datasets[0].data[0],
    active: rows().filter(row => row.active).map(row => row.cells[0])
  };
  headers.find(th => th.dataset.sort === 'score')?.click();
  const afterSortActive = rows().filter(row => row.active).map(row => row.cells[0]);
  ids['detail-close'].click();
  const closed = {display: ids['detail-section'].style.display, hash: context.location.hash,
    active: rows().filter(row => row.active).length};
  clickRow(); await flush();
  console.log(JSON.stringify({initial, initialHeaders, sorts, firstDetail, selectedPeriod, repeated,
    afterSortActive, closed, requests, chartCount: charts.length,
    destroyedCharts: charts.filter(chart => chart.destroyed).length}));
})().catch(error => { console.error(error); process.exitCode = 1; });
"""


@pytest.fixture(scope="module")
def monitor():
    data = {}
    expected = {}
    # These raw differences all disappear in the four-decimal JSON snapshots.
    for index, values in enumerate([*permutations(range(4)), (0, 0, 0, 0)]):
        raw = dict(zip([5, 20, 60, 120], [100 + value / 1_000_000 for value in values]))
        work = pd.DataFrame({f"vwap_{window}d": [value] for window, value in raw.items()},
                            index=pd.to_datetime(["2026-09-04"]))
        name = f"Asset {index:02d}"
        states = ["BUY" if raw[left] > raw[right] else "SELL" for left, right in PAIRS]
        expected[name] = states
        # Build the same raw-derived latest payloads used by trend/detail generation.
        strategies = {key: {"latest": gen.build_latest_alignment_snapshot(work, key)}
                      for key in gen.ALIGNMENT_STRATEGIES}
        data[name] = {"ticker": f"T{index}", "strategy_signal": {"available": True, "strategies": strategies}}
    for index, key in enumerate(KEYS):
        for missing in ["WAIT", "absent", "latest", "signal"]:
            name = f"Missing {index} {missing.lower()}"
            asset = copy.deepcopy(data["Asset 23"])
            strategies = asset["strategy_signal"]["strategies"]
            strategies.setdefault(key, {"latest": {"signal": "BUY"}})
            if missing == "absent":
                del strategies[key]
            elif missing == "latest":
                strategies[key]["latest"] = None
            elif missing == "signal":
                strategies[key]["latest"]["signal"] = None
            else:
                strategies[key]["latest"]["signal"] = "WAIT"
            data[name] = asset
    data["Missing all"] = {"ticker": "NONE", "strategy_signal": {"available": True}}
    data["Hidden unavailable"] = {"strategy_signal": {"available": False}}
    detail = {
        "name": "Asset 23", "ticker": "T23",
        "ohlcv": [{"date": f"day-{index}", **{f"vwap_{window}d": index for window in [1, 5, 20, 60, 120]}}
                  for index in range(130)],
        "volume_profile": {f"{period}d": {"vwap": 100, "buckets": [{"price": 100, "volume": period}]}
                           for period in [1, 5, 20, 60, 120]},
    }
    completed = subprocess.run(["node", "-e", NODE_MONITOR], cwd=ROOT,
                               input=json.dumps({"data": data, "detail": detail, "target": "Asset 23"}),
                               capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout), expected, data


def test_all_24_raw_permutations_and_all_equal_render_unweighted_scores(monitor):
    result, expected, _ = monitor
    actual = {row["cells"][0]: row for row in result["initial"]}
    scores = []
    for name, states in expected.items():
        score = states.count("BUY")
        scores.append(score)
        assert actual[name]["cells"] == [name, f"{score}/6", *states]
        assert actual[name]["classes"][2:] == [f"signal-cell {state.lower()}" for state in states]
    assert set(scores) == set(range(7))
    assert actual["Asset 24"]["cells"][1] == "0/6"


def test_any_missing_pair_makes_score_unavailable_and_pair_wait(monitor):
    result, _, data = monitor
    for row in result["initial"]:
        if not row["cells"][0].startswith("Missing"):
            continue
        assert row["cells"][1] == "–"
        assert "데이터 부족" in row["titles"][1]
        if row["cells"][0] == "Missing all":
            assert row["cells"][2:] == ["WAIT"] * 6
        else:
            index = int(row["cells"][0].split()[1])
            assert row["cells"][index + 2] == "WAIT"
            assert row["classes"][index + 2] == "signal-cell wait"


def test_all_eight_headers_sort_both_directions_with_stable_score_ties(monitor):
    result, _, data = monitor
    initial_names = [row["cells"][0] for row in result["initial"]]
    assert initial_names == sorted(initial_names)
    assert "Hidden unavailable" not in initial_names
    assert result["initialHeaders"][0]["aria"] == "ascending"
    assert len(result["sorts"]) == 8
    for sort in result["sorts"]:
        assert sort["prevented"] is True
        column = {"name": 0, "score": 1}.get(sort["key"])
        if column is None:
            column = int(sort["key"].split("_")[1]) + 1
        for click, direction in [("first", "desc" if column == 1 else "asc"),
                                 ("second", "asc" if column == 1 else "desc")]:
            snapshot = sort[click]
            header = next(header for header in snapshot["headers"] if header["key"] == sort["key"])
            assert header["dir"] == direction
            assert header["aria"] == ("ascending" if direction == "asc" else "descending")
            assert header["tabIndex"] == 0
            rows = snapshot["rows"]
            comparable = [row for row in rows if column != 1 or row["cells"][1] != "–"]
            missing = [row for row in rows if column == 1 and row["cells"][1] == "–"]
            assert rows == comparable + missing
            def sort_value(row):
                if column == 0:
                    return row["cells"][0]
                if column == 1:
                    return int(row["cells"][1].split("/")[0])
                strategy = data[row["cells"][0]]["strategy_signal"].get("strategies", {}).get(KEYS[column - 2], {})
                return (strategy.get("latest") or {}).get("signal") or ""

            values = [sort_value(row) for row in comparable]
            assert values == sorted(values, reverse=direction == "desc")
            for value in set(values):
                names = [row["cells"][0] for row, item in zip(comparable, values) if item == value]
                assert names == sorted(names)
            assert [row["cells"][0] for row in missing] == sorted(row["cells"][0] for row in missing)


def test_same_row_detail_reopens_from_cache_and_survives_score_sort(monitor):
    result, _, data = monitor
    assert result["firstDetail"] == {
        "hash": "T23", "title": "Asset 23", "symbol": "T23", "active": ["Asset 23"],
        "tabs": ["1d", "5d", "20d", "60d", "120d"],
        "charts": [{"type": "line", "labels": 120}, {"type": "bar", "labels": 1}], "loading": False,
    }
    assert result["selectedPeriod"] == "120d"
    # Same-row click resets the displayed VP to 1d, as before.
    assert result["repeated"]["latestVpVolume"] == 1
    assert result["repeated"]["active"] == ["Asset 23"]
    assert result["afterSortActive"] == ["Asset 23"]
    assert result["closed"] == {"display": "none", "hash": "", "active": 0}
    assert len(result["requests"]) == 2
    assert result["requests"][1]["url"].startswith("detail_data/T23.json?v=data-")
    assert all(request["options"] == {"cache": "no-store"} for request in result["requests"])
    assert result["chartCount"] - result["destroyedCharts"] == 2

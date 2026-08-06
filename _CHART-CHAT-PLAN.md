# Category Spend Chart-in-Chat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a chat question asks for a chart (e.g. "show me category spend by entity"), render the same style of horizontal stacked bar chart the InSight demo shows — computed by plain deterministic pandas, never invented — instead of, or alongside, the existing text answer.

**Architecture:** Three-layer split matching `_CHART-CHAT-DESIGN.md`: `nl_parser.py` gains chart-intent detection (understanding), a new `chart_query.py` does deterministic groupby aggregation reusing `spend_query.py`'s filtering (computation), a new `chart_render.py` builds a Plotly figure rendered inline in the chat via `st.plotly_chart` (presentation). `app.py` wires the three together.

**Tech Stack:** Python 3.14, Streamlit 1.60.0, pandas, Plotly (new dependency — confirmed not yet installed in `.venv`, and `st.plotly_chart` confirmed present in the installed Streamlit build). pytest (new dev dependency — confirmed not yet installed).

## Global Constraints

- No AI/LLM anywhere in the computation path — every chart number comes from a plain pandas groupby/sum, per `_CHART-CHAT-DESIGN.md` and `CLAUDE.md` rule 2.
- Existing number-answer behaviour must remain byte-for-byte unchanged for every non-chart question — regression-tested, not assumed.
- Currency is confirmed EUR (€) — from the design spec's live inspection of the InSight demo.
- Entity names always display with the `"Demo "` prefix stripped, matching existing behaviour in `app.py`'s `format_filters`.
- Every `.md` file created/updated in this project folder keeps the leading-underscore naming convention.
- Synthetic data only; this remains a disposable prototype (`CLAUDE.md` rules 1 and 4 — unchanged).

---

## Task 1: Add pytest + Plotly, extract shared filtering in `spend_query.py`

**Files:**
- Modify: `requirements.txt`
- Modify: `spend_query.py`
- Test: `tests/test_spend_query.py` (new)

**Interfaces:**
- Produces: `filter_df(df: pd.DataFrame, **filters) -> pd.DataFrame` — the shared row-filtering logic, now reusable by both `query_spend` and the new `chart_query.py` in Task 4.
- `query_spend`'s existing signature and return shape (`{total_net_spend, row_count, applied_filters}`) are unchanged — this task is a refactor, not a behaviour change.

- [ ] **Step 1: Install pytest and plotly, pin in requirements.txt**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pip install pytest plotly
pip freeze | grep -iE "^(pytest|plotly)=="
```

Append the two exact pinned lines returned by `pip freeze` to `requirements.txt` (keep the existing `streamlit`, `pandas`, `anthropic` lines as-is).

- [ ] **Step 2: Write the failing test for `filter_df`**

Create `tests/test_spend_query.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spend_query import filter_df, load_data, query_spend


def test_filter_df_matches_query_spend_row_count():
    df = load_data()
    filtered = filter_df(df, entity="Demo Alpine Operations", l1="IT and telecom", year=2024)
    result = query_spend(df, entity="Demo Alpine Operations", l1="IT and telecom", year=2024)
    assert len(filtered) == result["row_count"]
    assert round(float(filtered["Net spend"].sum()), 2) == result["total_net_spend"]


def test_query_spend_reference_total_unchanged():
    # Cross-checked independently earlier in the project (see _HANDOFF.md) — must not regress.
    df = load_data()
    result = query_spend(df, entity="Demo Alpine Operations", l1="IT and telecom", year=2024)
    assert result["total_net_spend"] == 192988.04
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_spend_query.py -v
```

Expected: FAIL with `ImportError: cannot import name 'filter_df'`.

- [ ] **Step 4: Extract `filter_df` in `spend_query.py`, refactor `query_spend` to use it**

Replace the body of `query_spend` in `spend_query.py`:

```python
def filter_df(df: pd.DataFrame, **filters) -> pd.DataFrame:
    """Row mask shared by query_spend and chart_query — the one place
    filter semantics live, so number answers and charts can never disagree
    about what a filter means."""
    mask = pd.Series(True, index=df.index)
    for key, value in filters.items():
        if value is None:
            continue
        col = FILTER_COLUMNS[key]
        mask &= df[col] == value
    return df[mask]


def query_spend(df: pd.DataFrame, **filters) -> dict:
    """filters: any of entity/country/cluster/year/l1/l2/supplier (case-sensitive,
    must match known_values exactly — the parser is responsible for resolving
    free text to these exact values before calling this).

    Returns total net spend, matching row count, and the filters actually applied,
    so the caller can always show what the answer is grounded in.
    """
    applied = {k: v for k, v in filters.items() if v is not None}
    matched = filter_df(df, **filters)
    return {
        "total_net_spend": round(float(matched["Net spend"].sum()), 2),
        "row_count": int(len(matched)),
        "applied_filters": applied,
    }
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_spend_query.py -v
```

Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git init -q 2>/dev/null; git add requirements.txt spend_query.py tests/test_spend_query.py
git commit -m "refactor: extract shared filter_df, add pytest+plotly deps" || true
```

(If `git init` was just run for the first time in this folder, that's expected — this project had no repo yet.)

---

## Task 2: Chart-intent detection in `nl_parser.py`

**Files:**
- Modify: `nl_parser.py`
- Test: `tests/test_nl_parser.py` (new)

**Interfaces:**
- Consumes: nothing new (still takes `question: str, known: dict[str, list]`).
- Produces: `parse_question(question, known) -> dict` now returns
  `{"intent": "chart" | "number", "chart_kind": "category_spend" | None,
  "breakdown": "entity" | "country" | "cluster", "category_level": "l1" | "l2",
  "filters": {...}}` — the `"filters"` value is exactly what `parse_question`
  used to return on its own (unchanged inner shape), now nested under this key.
  **This is a breaking change to the return shape** — Task 3 updates every caller.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_nl_parser.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nl_parser import parse_question
from spend_query import known_values, load_data

KV = known_values(load_data())


def test_plain_question_is_number_intent():
    result = parse_question("What was our IT and telecom spend for Alpine Operations in 2024?", KV)
    assert result["intent"] == "number"
    assert result["chart_kind"] is None
    assert result["filters"]["entity"] == "Demo Alpine Operations"
    assert result["filters"]["l1"] == "IT and telecom"
    assert result["filters"]["year"] == 2024


def test_chart_keyword_triggers_chart_intent():
    result = parse_question("show me a bar chart of category spend", KV)
    assert result["intent"] == "chart"
    assert result["chart_kind"] == "category_spend"


def test_breakdown_by_country_detected():
    result = parse_question("chart category spend broken down by country", KV)
    assert result["intent"] == "chart"
    assert result["breakdown"] == "country"


def test_breakdown_defaults_to_entity():
    result = parse_question("show me a spend breakdown by category", KV)
    assert result["intent"] == "chart"
    assert result["breakdown"] == "entity"


def test_category_level_2_detected():
    result = parse_question("plot spend by level 2 category", KV)
    assert result["intent"] == "chart"
    assert result["category_level"] == "l2"


def test_category_level_defaults_to_l1():
    result = parse_question("show me a chart of spend by category", KV)
    assert result["category_level"] == "l1"


def test_chart_intent_still_extracts_filters():
    result = parse_question("chart of category spend for Germany in 2025", KV)
    assert result["intent"] == "chart"
    assert result["filters"]["country"] == "Germany"
    assert result["filters"]["year"] == 2025
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_nl_parser.py -v
```

Expected: FAIL — `result["intent"]` raises `KeyError` (current `parse_question` returns a flat filters dict).

- [ ] **Step 3: Implement chart-intent detection**

Replace the full contents of `nl_parser.py`:

```python
"""Rule-based question parser — NOT an LLM.

There is no ANTHROPIC_API_KEY configured on this machine, so this prototype
matches known entity/country/cluster/year/category/supplier names directly
against the typed question instead of calling a language model. This is a
deliberate, disclosed substitute, not a silent downgrade — see _HANDOFF.md
for the tradeoff and the upgrade path once an API key is available.

Known limitation: it only recognises exact category names and their "Demo "-
stripped short forms (e.g. "Alpine" for "Demo Alpine Operations"). It does
not understand synonyms, abbreviations, or paraphrasing — that is exactly
what the LLM upgrade would add.
"""

import re

CHART_KEYWORDS = (
    "chart", "graph", "plot", "bar chart", "bar graph", "breakdown",
    "break down", "broken down", "visualise", "visualize", "compare",
)
COUNTRY_BREAKDOWN_KEYWORDS = ("by country", "per country")
CLUSTER_BREAKDOWN_KEYWORDS = ("by cluster", "per cluster")
LEVEL_2_KEYWORDS = ("level 2", "sub-category", "subcategory", "sub category")


def _extract_filters(q: str, known: dict[str, list]) -> dict:
    filters: dict[str, object] = {}

    for year in known["year"]:
        if str(year) in q:
            filters["year"] = year
            break

    for entity in sorted(known["entity"], key=len, reverse=True):
        short = entity.replace("Demo ", "")
        if entity.lower() in q or short.lower() in q:
            filters["entity"] = entity
            break

    for country in sorted(known["country"], key=len, reverse=True):
        if country.lower() in q:
            filters["country"] = country
            break

    # Cluster names (Central, North, South, West, Corporate) are common
    # English words, so require a whole-word match to cut down false hits.
    for cluster in sorted(known["cluster"], key=len, reverse=True):
        if re.search(rf"\b{re.escape(cluster.lower())}\b", q):
            filters["cluster"] = cluster
            break

    # L2 checked before L1 since it's the more specific category level.
    for l2 in sorted(known["l2"], key=len, reverse=True):
        if l2.lower() in q:
            filters["l2"] = l2
            break

    for l1 in sorted(known["l1"], key=len, reverse=True):
        if l1.lower() in q:
            filters["l1"] = l1
            break

    for supplier in sorted(known["supplier"], key=len, reverse=True):
        if supplier.lower() in q:
            filters["supplier"] = supplier
            break

    return filters


def parse_question(question: str, known: dict[str, list]) -> dict:
    q = question.lower()
    filters = _extract_filters(q, known)

    is_chart = any(keyword in q for keyword in CHART_KEYWORDS)

    if not is_chart:
        return {
            "intent": "number",
            "chart_kind": None,
            "breakdown": None,
            "category_level": None,
            "filters": filters,
        }

    if any(kw in q for kw in CLUSTER_BREAKDOWN_KEYWORDS):
        breakdown = "cluster"
    elif any(kw in q for kw in COUNTRY_BREAKDOWN_KEYWORDS):
        breakdown = "country"
    else:
        breakdown = "entity"

    category_level = "l2" if any(kw in q for kw in LEVEL_2_KEYWORDS) else "l1"

    return {
        "intent": "chart",
        "chart_kind": "category_spend",
        "breakdown": breakdown,
        "category_level": category_level,
        "filters": filters,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_nl_parser.py -v
```

Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add nl_parser.py tests/test_nl_parser.py
git commit -m "feat: add chart-intent detection to parse_question"
```

---

## Task 3: Update `app.py` for the new `parse_question` return shape (number path only — no chart rendering yet)

**Files:**
- Modify: `app.py`
- Test: `tests/test_app_answer.py` (new)

**Interfaces:**
- Consumes: `parse_question(...)["filters"]`, `parse_question(...)["intent"]` from Task 2.
- Produces: `answer(question: str) -> str` keeps its existing signature and, for `intent == "number"`, produces byte-identical output to before this task. For `intent == "chart"`, this task makes it return a plain-text placeholder line (`"[[chart]]"` marker prefix — replaced by real rendering in Task 6) rather than crashing, so the app stays runnable after this task.

- [ ] **Step 1: Write the failing regression test**

Create `tests/test_app_answer.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib


def _reload_app():
    import app  # noqa: F401 — Streamlit script; import executes top-level code once
    return importlib.reload(app)


def test_number_answer_unchanged_for_known_question():
    app = _reload_app()
    result = app.answer("What was our IT and telecom spend for Alpine Operations in 2024?")
    assert "192,988.04" in result
    assert "Matched on entity = Alpine Operations" in result


def test_no_match_question_gives_honest_caveat():
    app = _reload_app()
    result = app.answer("how much did we spend on Car Fuel")
    assert "I didn't recognise" in result
```

Note: importing `app.py` directly runs Streamlit page-config calls outside a real
Streamlit session; run this via `python -m streamlit run` is NOT needed for the
test — Streamlit's `st.*` calls are safe no-ops when there's no active
`ScriptRunContext`, which is exactly what lets this kind of direct-import test work.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_app_answer.py -v
```

Expected: FAIL — `answer()` currently calls `parse_question(question, kv)` and then
`query_spend(df, **filters)` where `filters` is now the whole intent dict, not
just the filters — `query_spend(df, **filters)` raises `TypeError` for the
unexpected `intent`/`chart_kind`/`breakdown`/`category_level` keyword args.

- [ ] **Step 3: Update `answer()` in `app.py`**

Replace the `answer` function body in `app.py`:

```python
def answer(question: str) -> str:
    parsed = parse_question(question, kv)
    filters = parsed["filters"]

    if parsed["intent"] == "chart":
        return "[[chart]] placeholder — rendered as a real chart in Task 6"

    result = query_spend(df, **filters)
    total = f"{result['total_net_spend']:,.2f}"

    if not filters:
        sample_entities = ", ".join(e.replace("Demo ", "") for e in kv["entity"][:3])
        sample_categories = ", ".join(kv["l1"][:4])
        return (
            f"I didn't recognise a specific entity, country, category, or year in that "
            f"question, so I can't narrow it down — the total across all "
            f"{result['row_count']} rows is **{total}**.\n\n"
            f"Try mentioning something like an entity ({sample_entities}, ...), "
            f"a category ({sample_categories}, ...), or a year (2024 or 2025)."
        )

    row_word = "row" if result["row_count"] == 1 else "rows"
    return (
        f"Matched on {format_filters(filters)} — **{total}** "
        f"across {result['row_count']} spend {row_word}."
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_app_answer.py -v
```

Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_answer.py
git commit -m "fix: update app.answer for parse_question's new intent-shaped return"
```

---

## Task 4: `chart_query.py` — deterministic category-spend aggregation

**Files:**
- Create: `chart_query.py`
- Test: `tests/test_chart_query.py` (new)

**Interfaces:**
- Consumes: `spend_query.filter_df(df, **filters)` from Task 1; `spend_query.FILTER_COLUMNS`.
- Produces: `category_spend(df: pd.DataFrame, level: str = "l1", breakdown: str = "entity", **filters) -> pd.DataFrame`
  returning columns `["category", "breakdown", "net_spend"]`, where `category` is an
  ordered `pd.Categorical` sorted descending by each category's total spend
  (matching the InSight demo's sort), and rows within each category sorted by
  `breakdown` alphabetically. Consumed by `chart_render.py` in Task 5.

- [ ] **Step 1: Write the failing test**

Create `tests/test_chart_query.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from chart_query import category_spend
from spend_query import load_data, query_spend


def test_category_totals_match_query_spend():
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="entity", year=2024)
    for category in chart_df["category"].unique():
        chart_total = round(chart_df.loc[chart_df["category"] == category, "net_spend"].sum(), 2)
        reference = query_spend(df, l1=str(category), year=2024)
        assert chart_total == reference["total_net_spend"], category


def test_categories_sorted_descending_by_total():
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="entity", year=2024)
    totals_in_order = chart_df.groupby("category", observed=True, sort=False)["net_spend"].sum()
    values = totals_in_order.tolist()
    assert values == sorted(values, reverse=True)


def test_invalid_level_raises():
    df = load_data()
    try:
        category_spend(df, level="l3")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_breakdown_by_country():
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="country", year=2024)
    assert set(chart_df["breakdown"].unique()) <= set(load_data()["Country"].unique())
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_chart_query.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'chart_query'`.

- [ ] **Step 3: Implement `chart_query.py`**

```python
"""Deterministic category-spend aggregation for the chart-in-chat feature.

Same rule as spend_query.py: no AI anywhere in this file. A chart can only
ever show numbers computed by a plain pandas groupby/sum over the real rows.
"""

import pandas as pd

from spend_query import filter_df

CATEGORY_COLUMNS = {"l1": "L1", "l2": "L2"}
BREAKDOWN_COLUMNS = {"entity": "Entity", "country": "Country", "cluster": "Cluster"}


def category_spend(
    df: pd.DataFrame, level: str = "l1", breakdown: str = "entity", **filters
) -> pd.DataFrame:
    """Group net spend by category (L1 or L2) and a breakdown dimension.

    Returns a tidy dataframe with columns [category, breakdown, net_spend].
    `category` is an ordered Categorical, sorted descending by each
    category's total spend — matching the InSight demo's bar order.
    """
    if level not in CATEGORY_COLUMNS:
        raise ValueError(f"level must be one of {list(CATEGORY_COLUMNS)}, got {level!r}")
    if breakdown not in BREAKDOWN_COLUMNS:
        raise ValueError(f"breakdown must be one of {list(BREAKDOWN_COLUMNS)}, got {breakdown!r}")

    matched = filter_df(df, **filters)
    category_col = CATEGORY_COLUMNS[level]
    breakdown_col = BREAKDOWN_COLUMNS[breakdown]

    grouped = (
        matched.groupby([category_col, breakdown_col])["Net spend"]
        .sum()
        .reset_index()
        .rename(columns={category_col: "category", breakdown_col: "breakdown", "Net spend": "net_spend"})
    )

    totals = grouped.groupby("category")["net_spend"].sum().sort_values(ascending=False)
    category_order = totals.index.tolist()
    grouped["category"] = pd.Categorical(grouped["category"], categories=category_order, ordered=True)
    grouped = grouped.sort_values(["category", "breakdown"]).reset_index(drop=True)
    grouped["net_spend"] = grouped["net_spend"].round(2)
    return grouped
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_chart_query.py -v
```

Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add chart_query.py tests/test_chart_query.py
git commit -m "feat: add deterministic category_spend aggregation"
```

---

## Task 5: `chart_render.py` — build the Plotly figure

**Files:**
- Create: `chart_render.py`
- Test: `tests/test_chart_render.py` (new)

**Interfaces:**
- Consumes: the tidy dataframe shape produced by `chart_query.category_spend` in Task 4 (columns `category`/`breakdown`/`net_spend`).
- Produces: `build_category_spend_figure(chart_df: pd.DataFrame, year_label: int) -> plotly.graph_objects.Figure`. Consumed by `app.py` in Task 6 via `st.plotly_chart(fig, ...)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_chart_render.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_query import category_spend
from chart_render import build_category_spend_figure
from spend_query import load_data


def test_figure_has_one_trace_per_breakdown_value():
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="entity", year=2024)
    fig = build_category_spend_figure(chart_df, year_label=2024)
    assert len(fig.data) == chart_df["breakdown"].nunique()


def test_figure_is_horizontal_stacked_bar():
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="entity", year=2024)
    fig = build_category_spend_figure(chart_df, year_label=2024)
    assert fig.layout.barmode == "stack"
    assert all(trace.orientation == "h" for trace in fig.data)


def test_entity_names_strip_demo_prefix_in_legend():
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="entity", year=2024)
    fig = build_category_spend_figure(chart_df, year_label=2024)
    assert all(not trace.name.startswith("Demo ") for trace in fig.data)


def test_xaxis_title_shows_currency_and_year():
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="entity", year=2024)
    fig = build_category_spend_figure(chart_df, year_label=2024)
    assert "2024" in fig.layout.xaxis.title.text
    assert "€" in fig.layout.xaxis.title.text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_chart_render.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'chart_render'`.

- [ ] **Step 3: Implement `chart_render.py`**

Before finalizing the palette here, this step should also be run through the
**dataviz skill** (per `_CHART-CHAT-DESIGN.md`'s build-process requirement) —
use its documented categorical-palette guidance in place of the placeholder
palette below if the skill's reference palette differs; the test suite only
asserts on structure (trace count, orientation, stacking, axis text), not on
exact colour values, so this substitution is safe to make without touching
the tests.

```python
"""Builds the category-spend chart as a Plotly figure — the InSight demo's
horizontal stacked bar chart, reproduced from chart_query's tidy dataframe.
"""

import plotly.graph_objects as go

# Categorical palette — 8 distinct hues, enough for the sample data's largest
# breakdown dimension (8 entities). Swap for the dataviz skill's reference
# palette during the build's design pass; only the structure is tested.
PALETTE = [
    "#17343C", "#2E86AB", "#F6AE2D", "#5B8C5A",
    "#A64B2A", "#7A5195", "#EF6461", "#4FB0A5",
]


def build_category_spend_figure(chart_df, year_label: int) -> go.Figure:
    categories = list(chart_df["category"].cat.categories)
    breakdown_values = sorted(chart_df["breakdown"].unique())

    fig = go.Figure()
    for i, bval in enumerate(breakdown_values):
        sub = chart_df[chart_df["breakdown"] == bval].set_index("category")
        sub = sub.reindex(categories, fill_value=0)
        display_name = str(bval).replace("Demo ", "")
        fig.add_trace(
            go.Bar(
                y=categories,
                x=sub["net_spend"],
                name=display_name,
                orientation="h",
                marker_color=PALETTE[i % len(PALETTE)],
            )
        )

    fig.update_layout(
        barmode="stack",
        xaxis_title=f"Net spend {year_label} (€)",
        yaxis=dict(autorange="reversed"),
        legend_title_text="",
        margin=dict(l=0, r=0, t=10, b=0),
        height=80 + 40 * len(categories),
    )
    return fig
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_chart_render.py -v
```

Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add chart_render.py tests/test_chart_render.py
git commit -m "feat: add Plotly figure builder for category spend chart"
```

---

## Task 6: Wire chart rendering into `app.py`

**Files:**
- Modify: `app.py`
- Test: `tests/test_app_answer.py` (extend)

**Interfaces:**
- Consumes: `chart_query.category_spend` (Task 4), `chart_render.build_category_spend_figure` (Task 5).
- Produces: `answer_payload(question: str) -> dict` — a new function returning
  `{"kind": "text" | "chart", "text": str, "figure": go.Figure | None,
  "caption": str | None}`, replacing direct calls to `answer()` in the chat
  loop. `answer()` is kept as a thin wrapper (`answer_payload(q)["text"]`)
  so Task 3's tests keep passing unmodified.

- [ ] **Step 1: Write the failing test**

Extend `tests/test_app_answer.py` (append to the existing file):

```python
def test_chart_question_returns_chart_payload():
    app = _reload_app()
    payload = app.answer_payload("show me a bar chart of category spend for 2024")
    assert payload["kind"] == "chart"
    assert payload["figure"] is not None
    assert "2024" in payload["caption"]


def test_number_question_returns_text_payload():
    app = _reload_app()
    payload = app.answer_payload("What was our IT and telecom spend for Alpine Operations in 2024?")
    assert payload["kind"] == "text"
    assert payload["figure"] is None
    assert "192,988.04" in payload["text"]


def test_chart_question_with_zero_matches_falls_back_to_text():
    app = _reload_app()
    payload = app.answer_payload("chart category spend for Germany in 2099")
    assert payload["kind"] == "text"
    assert "nothing" in payload["text"].lower() or "didn't" in payload["text"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_app_answer.py -v
```

Expected: FAIL — `AttributeError: module 'app' has no attribute 'answer_payload'`.

- [ ] **Step 3: Implement `answer_payload` and wire it into the chat loop**

In `app.py`, add the imports and replace `answer` / the chat-input handling block:

```python
from chart_query import category_spend
from chart_render import build_category_spend_figure
```

Replace the `answer` function and everything below it in `app.py` with:

```python
def answer_payload(question: str) -> dict:
    parsed = parse_question(question, kv)
    filters = parsed["filters"]

    if parsed["intent"] == "chart":
        chart_df = category_spend(
            df, level=parsed["category_level"], breakdown=parsed["breakdown"], **filters
        )
        if chart_df.empty:
            return {
                "kind": "text",
                "text": (
                    "I didn't find anything matching that for a chart — "
                    f"{format_filters(filters) if filters else 'no filters recognised'} "
                    "returned no rows."
                ),
                "figure": None,
                "caption": None,
            }
        year_label = filters.get("year", max(kv["year"]))
        fig = build_category_spend_figure(chart_df, year_label=year_label)
        total = f"{chart_df['net_spend'].sum():,.2f}"
        level_label = "Level 1" if parsed["category_level"] == "l1" else "Level 2"
        filter_text = format_filters(filters) if filters else f"year = {year_label}"
        caption = (
            f"Matched on {filter_text}, broken down by {parsed['breakdown']} "
            f"({level_label} categories) — {chart_df['category'].nunique()} categories, "
            f"total {total}."
        )
        return {"kind": "chart", "text": f"Total: {total}", "figure": fig, "caption": caption}

    result = query_spend(df, **filters)
    total = f"{result['total_net_spend']:,.2f}"

    if not filters:
        sample_entities = ", ".join(e.replace("Demo ", "") for e in kv["entity"][:3])
        sample_categories = ", ".join(kv["l1"][:4])
        text = (
            f"I didn't recognise a specific entity, country, category, or year in that "
            f"question, so I can't narrow it down — the total across all "
            f"{result['row_count']} rows is **{total}**.\n\n"
            f"Try mentioning something like an entity ({sample_entities}, ...), "
            f"a category ({sample_categories}, ...), or a year (2024 or 2025)."
        )
    else:
        row_word = "row" if result["row_count"] == 1 else "rows"
        text = (
            f"Matched on {format_filters(filters)} — **{total}** "
            f"across {result['row_count']} spend {row_word}."
        )
    return {"kind": "text", "text": text, "figure": None, "caption": None}


def answer(question: str) -> str:
    return answer_payload(question)["text"]


def render_payload(container, payload: dict) -> None:
    container.markdown(payload["text"])
    if payload["kind"] == "chart":
        container.plotly_chart(payload["figure"], use_container_width=True)
        container.caption(payload["caption"])


prompt = st.chat_input("What was our IT and telecom spend for Alpine Operations in 2024?")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt, "payload": None})
    with st.chat_message("user", avatar=AVATARS["user"]):
        st.markdown(prompt)

    payload = answer_payload(prompt)
    st.session_state.messages.append(
        {"role": "assistant", "content": payload["text"], "payload": payload}
    )
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        render_payload(st, payload)
```

Also update the message-history render loop (the `for message in st.session_state.messages:`
block earlier in `app.py`) to replay charts on rerun, not just text:

```python
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar=AVATARS[message["role"]]):
        if message.get("payload"):
            render_payload(st, message["payload"])
        else:
            st.markdown(message["content"])
```

And update the two places messages are appended earlier in the file (the
`if "messages" not in st.session_state` init is unchanged) — every
`st.session_state.messages.append({"role": ..., "content": ...})` call
elsewhere in the file must gain a `"payload": None` key so the render loop's
`.get("payload")` check works uniformly. (There are no other append sites
after Task 3's edit removed the old duplicate rendering block — confirm by
searching the file for `messages.append` before finishing this step.)

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_app_answer.py -v
```

Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_answer.py
git commit -m "feat: render category spend chart inline in chat"
```

---

## Task 7: Regression + adversarial pytest suite

**Files:**
- Modify: `tests/test_app_answer.py` (extend)

**Interfaces:**
- Consumes: `app.answer_payload` from Task 6.
- Produces: nothing new — this task is verification only.

- [ ] **Step 1: Add the adversarial cases as new test functions**

Append to `tests/test_app_answer.py`:

```python
def test_nonsense_question_still_gets_honest_caveat():
    app = _reload_app()
    payload = app.answer_payload("asdkjfh qwoeiruqwoe")
    assert payload["kind"] == "text"
    assert "I didn't recognise" in payload["text"]


def test_chart_breakdown_by_cluster():
    app = _reload_app()
    payload = app.answer_payload("chart category spend by cluster for 2024")
    assert payload["kind"] == "chart"
    assert "cluster" in payload["caption"]


def test_chart_level_2_categories():
    app = _reload_app()
    payload = app.answer_payload("show me a chart of level 2 category spend for 2024")
    assert payload["kind"] == "chart"
    assert "Level 2" in payload["caption"]


def test_west_cluster_number_question_unchanged():
    # Cross-checked earlier in the project — must not regress (see _HANDOFF.md).
    app = _reload_app()
    payload = app.answer_payload("What did the West cluster spend in 2025?")
    assert "1,267,819.75" in payload["text"]
```

- [ ] **Step 2: Run the full suite**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/ -v
```

Expected: PASS, all tests across all five test files (Tasks 1–7 combined).

- [ ] **Step 3: Commit**

```bash
git add tests/test_app_answer.py
git commit -m "test: add regression and adversarial coverage for chart-in-chat"
```

---

## Task 8: Real browser verification (interface-polish screenshot gate)

**Files:** none (verification only — screenshots and observations go into `_HANDOFF.md` per Task 10).

This task is exactly the mandatory screenshot gate from the `interface-polish`
skill, applied to the new chart feature specifically (the chat surface itself
was already gated in the earlier polish pass).

- [ ] **Step 1: Restart the app fresh**

```bash
lsof -ti :8501 | xargs -r kill -9
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
nohup streamlit run app.py --server.headless true > /tmp/streamlit_chart.log 2>&1 &
sleep 3
lsof -i :8501
```

Expected: process listening on 8501, no traceback in `/tmp/streamlit_chart.log`.

- [ ] **Step 2: Screenshot the default (unfiltered) chart**

Using the `?preview=` debug-seed technique already proven reliable this
session (direct browser typing into `st.chat_input` was unreliable — confirmed
via DOM inspection earlier, a tool limitation not an app bug): temporarily add
a `preview` query-param branch to `app.py` that calls
`app.answer_payload("show me a bar chart of category spend for 2024")` and
seeds it into `st.session_state.messages`, screenshot at ≥1200px width, then
remove the debug branch afterward — same pattern as the earlier avatar-colour
verification, confirmed removed by re-reading the file before committing.

- [ ] **Step 3: Screenshot a filtered chart**

Seed `"chart category spend for Germany in 2024"` the same way; confirm the
caption names the filter and the bars only reflect German entities.

- [ ] **Step 4: Screenshot a breakdown variant**

Seed `"chart category spend by country for 2024"`; confirm the legend shows
country names, not entity names.

- [ ] **Step 5: Screenshot the zero-match case**

Seed `"chart category spend for Germany in 2099"`; confirm it falls back to
the honest text message from Task 6, not an empty chart.

- [ ] **Step 6: Regression-screenshot the four original number questions**

Re-run the original four adversarial questions from the first build session
(the IT/telecom Alpine question, the "Car Fuel" no-match question, a nonsense
string, the West cluster question) and confirm all four still render exactly
as before — text only, no stray chart UI appears.

- [ ] **Step 7: Remove the debug preview branch, restart, confirm clean revert**

```bash
lsof -ti :8501 | xargs -r kill -9
```

Re-read `app.py` in full to confirm no `preview` debug code remains, then
restart and screenshot the plain empty state one more time.

---

## Task 9: Codex cross-family review

**Files:** none directly — findings get logged into `_CHART-CHAT-DESIGN.md`.

- [ ] **Step 1: Run the review**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
codex exec --skip-git-repo-check --sandbox read-only "Review the chart-in-chat changes in this project: nl_parser.py, spend_query.py, chart_query.py, chart_render.py, app.py, and the tests in tests/. Focus on: correctness of the pandas aggregation, whether the chart can ever show a number that doesn't match query_spend's number for the same filters, edge cases in the breakdown/category-level parsing, and Streamlit-specific bugs (stale session state, re-render issues)."
```

- [ ] **Step 2: Triage every finding**

For each finding: fix it and re-run the relevant pytest file, or explicitly
reject it with a one-line reason. Log the outcome in a new "## Codex review
triage log" section at the bottom of `_CHART-CHAT-DESIGN.md`, in the same
format as `_DEMO-DESIGN.md`'s existing triage log (Fixed/Accepted-as-scope-limit,
with the reason).

- [ ] **Step 3: Re-run the full test suite after fixes**

```bash
pytest tests/ -v
```

Expected: PASS, all tests.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "fix: address Codex review findings for chart-in-chat"
```

---

## Task 10: Update `_HANDOFF.md` and `CLAUDE.md`

**Files:**
- Modify: `_HANDOFF.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add a "Phase 1: Category spend chart" section to `_HANDOFF.md`**

Document: what was built (the three new/changed files), the new `plotly`/`pytest`
dependencies, the pytest results (exact pass count), the screenshot evidence
from Task 8 (what was observed at each of the 6 screenshots), the Codex triage
outcome from Task 9, and — explicitly — that Phases 2–4 (Top suppliers,
Fragmentation, Overview KPIs) are deferred, not started, per the sequencing
Hayden confirmed.

- [ ] **Step 2: Add a standing skill-usage instruction to `CLAUDE.md`**

Per `_CHART-CHAT-DESIGN.md`'s build-process requirement (itself sourced from
the websites-project research on avoiding generic AI output): add a rule
stating that any future visual/chart work on this project must go through the
`dataviz` skill (for chart styling) and the `interface-polish` skill (for the
surrounding chat UI), named explicitly when invoked — not applied silently.

- [ ] **Step 3: Commit**

```bash
git add _HANDOFF.md CLAUDE.md
git commit -m "docs: record Phase 1 chart-in-chat completion and next-phase scope"
```

---

## Self-Review Notes

**Spec coverage check against `_CHART-CHAT-DESIGN.md`:** intent detection →
Task 2; deterministic computation reusing `spend_query`'s filter logic →
Tasks 1 & 4; Plotly presentation with visual-parity rules (horizontal stacked,
descending sort, € axis, "Demo " stripped, caption) → Tasks 5 & 6; behaviour
rules (no-filter default, filtered, zero-match, non-chart unchanged, nonsense
unchanged) → Tasks 6 & 7; build-process requirements (dataviz skill,
interface-polish screenshot gate, named tool usage) → Tasks 5 & 8; verification
plan (unit cross-checks, browser screenshots, Codex review) → Tasks 4, 8, 9;
handoff/CLAUDE.md updates → Task 10. No spec section is uncovered.

**Type consistency check:** `parse_question`'s new return shape (Task 2) is
consumed identically in Task 3 (`parsed["filters"]`, `parsed["intent"]`) and
Task 6 (`parsed["category_level"]`, `parsed["breakdown"]`) — same keys
throughout. `category_spend`'s return columns (`category`/`breakdown`/`net_spend`,
Task 4) match exactly what `build_category_spend_figure` consumes (Task 5) and
what `answer_payload` reads (`chart_df['net_spend'].sum()`,
`chart_df['category'].nunique()`, Task 6). `answer_payload`'s return shape
(`kind`/`text`/`figure`/`caption`, introduced in Task 6) is used identically
by `render_payload` and the message-history replay loop in the same task —
no mismatched keys found.

---

**Plan complete and saved to `_CHART-CHAT-PLAN.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**

# Meeting-Ready Chatbot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the chatbot from "Phase 1 chart-in-chat prototype" to "ready to put in front of the data scientist / a client": no question dead-ends, and every InSight demo view (Overview, Top suppliers + drill-down, Fragmentation + overall concentration) is answerable in chat, deterministically, with a final adversarial gate before calling it done.

**Architecture:** Same three-layer split as Phase 1 (`_CHART-CHAT-DESIGN.md`), extended per-feature: `nl_parser.py` gains new intents/keywords (understanding), `chart_query.py` and a new `overview_query.py` gain new deterministic pandas functions (computation), `chart_render.py` gains new Plotly figure builders (presentation). `app.py`'s `answer_payload()` becomes an intent dispatcher; `render_payload()` gains new payload kinds (KPI rows via `st.metric`, bordered callout cards, side-by-side charts, a detail table). Every new number is provably equal to what `spend_query.query_spend()` would return for the same filters — test-enforced, not assumed.

**Tech Stack:** Python 3.14, Streamlit 1.60.0 (`st.pills`, `st.metric`, `st.container(border=True)` all confirmed present in the installed venv), pandas, Plotly, pytest — all already installed, no new dependencies.

## Global Constraints

- No AI/LLM anywhere in computation — every number is a plain pandas aggregation, same rule as Phase 1 (`CLAUDE.md` rule 2). No `ANTHROPIC_API_KEY` exists on this machine.
- Every displayed number must equal what `spend_query.query_spend()` returns for the equivalent filters — the never-diverge guarantee, test-enforced per task, not assumed.
- Entity/supplier names always display with the `"Demo "` prefix stripped, matching existing `format_filters`/chart behaviour.
- Every `.md` file created/updated in this project folder keeps the leading-underscore naming convention (`CLAUDE.md` rule 21).
- Interface copy is one clear label, never explanatory prose or build-narration (`CLAUDE.md` rule 26) — chip labels are real client questions, not meta-descriptions.
- Reuse Phase 1's existing helpers (`_millions_ticks`, `PALETTE`, `filter_df`) rather than duplicating tick/palette/filter logic — every new chart function in this plan calls into them.
- The Fragmentation formula is OUR OWN, disclosed, and must never be tuned to reproduce the InSight demo's own Profile column (`_MEETING-READY-DESIGN.md` Part C1, `CLAUDE.md` rule 24).
- Synthetic data only; this remains a disposable prototype (unchanged from Phase 1).

---

## Task 1: Overview computation + overview/help intent detection

**Files:**
- Create: `overview_query.py`
- Modify: `nl_parser.py`
- Test: `tests/test_overview_query.py` (new)
- Test: `tests/test_nl_parser.py` (append)

**Interfaces:**
- Consumes: `spend_query.filter_df(df, **filters) -> pd.DataFrame` (existing).
- Produces: `overview_query.overview(df: pd.DataFrame, **filters) -> dict` with keys `year, net_spend, prior_year, yoy_pct, entity_count, supplier_count, row_count, largest_category, fastest_growing_category, top10_concentration_pct, largest_supplier` — Task 2 consumes this exact shape.
- Produces: `nl_parser.parse_question()` now may return `intent` values `"help"` and `"overview"` in addition to the existing `"number"`/`"chart"`, and every returned dict now always has a `"top_n"` key (`None` unless `chart_kind == "top_suppliers"`) — Task 2 and later tasks consume this.

- [ ] **Step 1: Write the failing test for `overview()`**

Create `tests/test_overview_query.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overview_query import overview
from spend_query import load_data, query_spend


def test_net_spend_matches_query_spend():
    df = load_data()
    stats = overview(df)
    assert stats["year"] == 2025
    reference = query_spend(df, year=2025)
    assert stats["net_spend"] == reference["total_net_spend"]
    assert stats["row_count"] == reference["row_count"]


def test_net_spend_matches_query_spend_within_filters():
    df = load_data()
    stats = overview(df, entity="Demo Alpine Operations")
    reference = query_spend(df, entity="Demo Alpine Operations", year=stats["year"])
    assert stats["net_spend"] == reference["total_net_spend"]


def test_yoy_pct_omitted_when_prior_year_not_in_scope():
    df = load_data()
    stats = overview(df, year=2025)
    assert stats["prior_year"] is None
    assert stats["yoy_pct"] is None


def test_yoy_pct_present_when_both_years_in_scope():
    df = load_data()
    stats = overview(df)
    assert stats["prior_year"] == 2024
    assert stats["yoy_pct"] is not None


def test_largest_category_matches_manual_groupby():
    df = load_data()
    stats = overview(df)
    year_rows = df[df["Year"] == 2025]
    expected = year_rows.groupby("L1")["Net spend"].sum().idxmax()
    assert stats["largest_category"]["name"] == expected


def test_fastest_growing_category_excludes_zero_prior_spend():
    df = load_data()
    stats = overview(df)
    year_rows = df[df["Year"] == 2025]
    prior_rows = df[df["Year"] == 2024]
    by_cat = year_rows.groupby("L1")["Net spend"].sum()
    prior_by_cat = prior_rows.groupby("L1")["Net spend"].sum()
    growth = {
        cat: (spend - prior_by_cat[cat]) / prior_by_cat[cat] * 100
        for cat, spend in by_cat.items()
        if prior_by_cat.get(cat, 0) > 0
    }
    expected = max(growth, key=growth.get)
    assert stats["fastest_growing_category"]["name"] == expected


def test_top10_concentration_and_largest_supplier():
    df = load_data()
    stats = overview(df)
    year_rows = df[df["Year"] == 2025]
    by_supplier = year_rows.groupby("Supplier name")["Net spend"].sum().sort_values(ascending=False)
    expected_pct = round(by_supplier.head(10).sum() / by_supplier.sum() * 100, 1)
    assert stats["top10_concentration_pct"] == expected_pct
    assert stats["largest_supplier"]["name"] == by_supplier.index[0]


def test_empty_scope_returns_none_year():
    df = load_data()
    stats = overview(df, entity="Demo Alpine Operations", country="Germany", cluster="Nonexistent")
    assert stats["year"] is None
    assert stats["net_spend"] == 0.0
    assert stats["largest_category"] is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_overview_query.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'overview_query'`.

- [ ] **Step 3: Create `overview_query.py`**

```python
"""Deterministic overview computation — headline KPIs and callouts.

No AI anywhere in this file: every number is a plain pandas aggregation
over the real rows, computed the same way spend_query.query_spend() and
chart_query.category_spend() are, so an overview answer can never disagree
with what those functions would return for the same filters.
"""

import pandas as pd

from spend_query import filter_df


def overview(df: pd.DataFrame, **filters) -> dict:
    """Headline KPIs + callouts within the given filters.

    Focus year is always the latest year present in the filtered scope —
    same defaulting rule as chart_query.category_spend()'s chart path.

    Returns a dict:
      - year: int | None (None if the filters match zero rows)
      - net_spend: float, total net spend in `year`
      - prior_year: int | None, year - 1 if present in scope, else None
      - yoy_pct: float | None, % change vs prior_year
      - entity_count, supplier_count, row_count: int, distinct counts in `year`
      - largest_category: {"name": str, "net_spend": float} | None
      - fastest_growing_category: {"name": str, "growth_pct": float} | None
        (categories with zero or absent prior-year spend are excluded from
        the growth ranking — a new category entering from zero isn't a
        meaningful "% growth" figure)
      - top10_concentration_pct: float | None
      - largest_supplier: {"name": str, "net_spend": float} | None
    """
    matched = filter_df(df, **filters)
    if matched.empty:
        return {
            "year": None, "net_spend": 0.0, "prior_year": None, "yoy_pct": None,
            "entity_count": 0, "supplier_count": 0, "row_count": 0,
            "largest_category": None, "fastest_growing_category": None,
            "top10_concentration_pct": None, "largest_supplier": None,
        }

    year = int(matched["Year"].max())
    year_rows = matched[matched["Year"] == year]

    net_spend = round(float(year_rows["Net spend"].sum()), 2)
    entity_count = int(year_rows["Entity"].nunique())
    supplier_count = int(year_rows["Supplier name"].nunique())
    row_count = int(len(year_rows))

    prior_year_candidate = year - 1
    prior_rows = matched[matched["Year"] == prior_year_candidate]
    if prior_rows.empty:
        prior_year = None
        yoy_pct = None
    else:
        prior_year = prior_year_candidate
        prior_spend = float(prior_rows["Net spend"].sum())
        yoy_pct = round((net_spend - prior_spend) / prior_spend * 100, 1) if prior_spend != 0 else None

    by_category = year_rows.groupby("L1")["Net spend"].sum()
    if by_category.empty:
        largest_category = None
    else:
        top_cat = by_category.idxmax()
        largest_category = {"name": top_cat, "net_spend": round(float(by_category[top_cat]), 2)}

    fastest_growing_category = None
    if prior_year is not None and not by_category.empty:
        prior_by_category = prior_rows.groupby("L1")["Net spend"].sum()
        growth = {}
        for cat, spend in by_category.items():
            prior_spend = prior_by_category.get(cat)
            if prior_spend and prior_spend > 0:
                growth[cat] = (spend - prior_spend) / prior_spend * 100
        if growth:
            fastest_cat = max(growth, key=growth.get)
            fastest_growing_category = {"name": fastest_cat, "growth_pct": round(growth[fastest_cat], 1)}

    by_supplier = year_rows.groupby("Supplier name")["Net spend"].sum().sort_values(ascending=False)
    if by_supplier.empty or net_spend == 0:
        top10_concentration_pct = None
        largest_supplier = None
    else:
        top10_sum = float(by_supplier.head(10).sum())
        top10_concentration_pct = round(top10_sum / net_spend * 100, 1)
        largest_supplier = {
            "name": by_supplier.index[0],
            "net_spend": round(float(by_supplier.iloc[0]), 2),
        }

    return {
        "year": year, "net_spend": net_spend, "prior_year": prior_year, "yoy_pct": yoy_pct,
        "entity_count": entity_count, "supplier_count": supplier_count, "row_count": row_count,
        "largest_category": largest_category, "fastest_growing_category": fastest_growing_category,
        "top10_concentration_pct": top10_concentration_pct, "largest_supplier": largest_supplier,
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_overview_query.py -v
```

Expected: PASS (8 passed).

- [ ] **Step 5: Write the failing tests for `parse_question`'s new intents**

Append to `tests/test_nl_parser.py`:

```python
def test_help_keyword_triggers_help_intent():
    result = parse_question("what can you do", KV)
    assert result["intent"] == "help"


def test_overview_keyword_triggers_overview_intent():
    result = parse_question("give me an overview", KV)
    assert result["intent"] == "overview"


def test_overview_intent_carries_filters():
    result = parse_question("give me an overview for Alpine Operations", KV)
    assert result["intent"] == "overview"
    assert result["filters"]["entity"] == "Demo Alpine Operations"


def test_every_parse_result_has_top_n_key():
    result = parse_question("What was our IT and telecom spend for Alpine Operations in 2024?", KV)
    assert "top_n" in result
    assert result["top_n"] is None
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
pytest tests/test_nl_parser.py -v -k "help_keyword or overview_keyword or overview_intent or top_n_key"
```

Expected: FAIL — `parse_question` doesn't recognise `"help"`/`"overview"` intents yet, and existing return dicts have no `"top_n"` key.

- [ ] **Step 7: Add help/overview intent detection to `nl_parser.py`**

Add near the top of `nl_parser.py`, after the existing `LEVEL_2_KEYWORDS` line:

```python
HELP_KEYWORDS = (
    "help", "what can you do", "what can i ask", "how does this work", "examples",
)

OVERVIEW_KEYWORDS = (
    "overview", "summary", "summarise", "summarize", "headline", "big picture",
    "how are we doing", "state of spend",
)
```

Replace the body of `parse_question` in `nl_parser.py`:

```python
def parse_question(question: str, known: dict[str, list]) -> dict:
    q = question.lower()
    filters = _extract_filters(q, known)
    base = {"top_n": None, "filters": filters}

    if any(kw in q for kw in HELP_KEYWORDS):
        return {"intent": "help", "chart_kind": None, "breakdown": None, "category_level": None, **base}

    if any(kw in q for kw in OVERVIEW_KEYWORDS):
        return {"intent": "overview", "chart_kind": None, "breakdown": None, "category_level": None, **base}

    is_chart = (
        any(keyword in q for keyword in CHART_KEYWORDS)
        or bool(BAR_PATTERN.search(q))
        or bool(SPLIT_PATTERN.search(q))
        or bool(SHOW_ME_BY_PATTERN.search(q))
    )

    if not is_chart:
        return {"intent": "number", "chart_kind": None, "breakdown": None, "category_level": None, **base}

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
        **base,
    }
```

Note: `HELP_KEYWORDS`/`OVERVIEW_KEYWORDS` are checked before the `is_chart` check deliberately — "how does this work" and "how are we doing" would otherwise never be reachable if a later task's chart/fragmentation keywords happened to overlap, and checking help/overview first keeps the precedence explicit and easy to reason about as more intents are added in later tasks.

- [ ] **Step 8: Run tests to verify they pass**

```bash
pytest tests/test_nl_parser.py -v
```

Expected: PASS (all tests, including the 4 new ones).

- [ ] **Step 9: Commit**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
git add overview_query.py nl_parser.py tests/test_overview_query.py tests/test_nl_parser.py
git commit -m "feat: add overview computation, help/overview intent detection"
```

---

## Task 2: Overview presentation + the A1 vague-question fallback

**Files:**
- Modify: `app.py`
- Test: `tests/test_app_answer.py` (append; also update two existing tests per Step 6)

**Interfaces:**
- Consumes: `overview_query.overview()` (Task 1).
- Produces: `app.build_overview_payload(filters: dict, prefix: str = "") -> dict` returning a payload with `kind == "overview"`, keys `text, metrics, callouts, show_chips` — Task 3 (chips) and `render_payload`'s new branch both consume this shape. `metrics` is a list of `(label: str, value: str, delta: str | None)` tuples; `callouts` is a list of `{"label": str, "value": str, "detail": str}` dicts.
- Produces: `render_kpi_row(container, metrics)` and `render_callouts(container, callouts)` helpers, reused by Task 7 (supplier drill-down) and Task 9 (fragmentation).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app_answer.py`:

```python
def test_overview_intent_returns_overview_payload():
    app = _reload_app()
    payload = app.answer_payload("give me an overview")
    assert payload["kind"] == "overview"
    assert len(payload["metrics"]) == 4
    assert payload["show_chips"] is True


def test_overview_net_spend_matches_query_spend():
    from spend_query import query_spend

    app = _reload_app()
    payload = app.answer_payload("give me an overview")
    reference = query_spend(app.df, year=2025)
    net_spend_metric = payload["metrics"][0]
    assert reference["total_net_spend"] > 0
    assert f"{reference['total_net_spend']:,.2f}" in net_spend_metric[1]


def test_vague_question_falls_back_to_overview_not_caveat():
    app = _reload_app()
    payload = app.answer_payload("how much did we spend on Car Fuel")
    assert payload["kind"] == "overview"
    assert "overall picture" in payload["text"].lower()


def test_help_intent_returns_text_with_chips():
    app = _reload_app()
    payload = app.answer_payload("what can you do")
    assert payload["kind"] == "text"
    assert payload["show_chips"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_app_answer.py -v -k "overview or help_intent"
```

Expected: FAIL — `answer_payload` doesn't route `"overview"`/`"help"` intent yet.

- [ ] **Step 3: Add imports and payload builders to `app.py`**

Add to the import block at the top of `app.py`:

```python
from overview_query import overview
```

Add these functions to `app.py`, directly above `answer_payload`:

```python
def render_kpi_row(container, metrics: list[tuple[str, str, str | None]]) -> None:
    """metrics: list of (label, value, delta) tuples; delta may be None."""
    cols = container.columns(len(metrics))
    for col, (label, value, delta) in zip(cols, metrics):
        col.metric(label, value, delta=delta)


def render_callouts(container, callouts: list[dict]) -> None:
    """callouts: list of {label, value, detail} dicts, one bordered card each."""
    cols = container.columns(len(callouts))
    for col, callout in zip(cols, callouts):
        box = col.container(border=True)
        box.caption(callout["label"])
        box.markdown(f"**{callout['value']}**")
        box.caption(callout["detail"])


HELP_TEXT = (
    "I can answer questions about spend by entity, category, country, cluster, "
    "year or supplier — as a number, a category chart, top suppliers, "
    "fragmentation, or an overall overview.\n\nTry one of these, or ask your own:"
)


def build_help_payload() -> dict:
    return {"kind": "text", "text": HELP_TEXT, "figure": None, "caption": None, "show_chips": True}


def build_overview_payload(filters: dict, prefix: str = "") -> dict:
    stats = overview(df, **filters)
    if stats["year"] is None:
        filter_text = format_filters(filters) if filters else "the data"
        return {
            "kind": "text",
            "text": f"I didn't find anything matching that for an overview — {filter_text} returned no rows.",
            "figure": None, "caption": None, "show_chips": True,
        }

    net_spend_str = format_currency(stats["net_spend"])
    delta = f"{stats['yoy_pct']:+.1f}% vs {stats['prior_year']}" if stats["yoy_pct"] is not None else None
    metrics = [
        (f"Net spend {stats['year']}", net_spend_str, delta),
        ("Entities", str(stats["entity_count"]), None),
        ("Suppliers", str(stats["supplier_count"]), None),
        ("Spend rows", str(stats["row_count"]), None),
    ]

    callouts = []
    if stats["largest_category"]:
        callouts.append({
            "label": "Largest category",
            "value": stats["largest_category"]["name"],
            "detail": f"{format_currency(stats['largest_category']['net_spend'])} in {stats['year']}",
        })
    if stats["fastest_growing_category"]:
        callouts.append({
            "label": "Fastest category growth",
            "value": stats["fastest_growing_category"]["name"],
            "detail": f"{stats['fastest_growing_category']['growth_pct']:+.1f}% vs {stats['prior_year']}",
        })
    if stats["top10_concentration_pct"] is not None:
        largest_supplier_name = stats["largest_supplier"]["name"].replace("Demo ", "")
        callouts.append({
            "label": "Supplier concentration",
            "value": f"Top 10 = {stats['top10_concentration_pct']:.1f}%",
            "detail": f"Largest supplier: {largest_supplier_name}",
        })

    filter_text = format_filters(filters) if filters else "all data"
    text = f"{prefix}Overview for {filter_text}, {stats['year']}."
    return {
        "kind": "overview", "text": text, "metrics": metrics, "callouts": callouts,
        "show_chips": True,
    }
```

- [ ] **Step 4: Route `"help"`/`"overview"` intents and the A1 fallback in `answer_payload`**

In `app.py`, replace the start of `answer_payload` (the `parsed = parse_question(...)` line through the `if parsed["intent"] == "chart":` line) with:

```python
def answer_payload(question: str) -> dict:
    parsed = parse_question(question, kv)
    filters = parsed["filters"]

    if parsed["intent"] == "help":
        return build_help_payload()

    if parsed["intent"] == "overview":
        return build_overview_payload(filters)

    if parsed["intent"] == "chart":
```

Leave the existing chart-handling body under that `if` unchanged for now (later tasks restructure it). Then, in the plain-number branch further down — the code that currently starts `result = query_spend(df, **filters)` and the `if not filters:` block that builds the honest-caveat text — replace just the `if not filters:` block:

```python
    result = query_spend(df, **filters)
    total = format_currency(result["total_net_spend"])

    if not filters:
        return build_overview_payload(
            {},
            prefix=(
                "Here's the overall picture — ask about any entity, category, "
                "country or year to go deeper.\n\n"
            ),
        )
```

(The `else:` branch below it, building the normal "Matched on ..." text, is unchanged.)

Finally, give every payload dict returned by the still-unmodified parts of `answer_payload` (the chart-empty-result text payload, and the normal filtered-number text payload) a `"show_chips": False` key so `render_payload`'s chip logic (Task 3) can safely call `payload.get("show_chips")` uniformly. Add `"show_chips": False` to the two `return {"kind": "text", ...}` dicts inside the chart branch and to the final `return {"kind": "text", ...}` at the end of `answer_payload`.

- [ ] **Step 5: Add the new payload kind to `render_payload`**

In `app.py`, replace `render_payload`:

```python
def render_payload(container, payload: dict) -> None:
    container.markdown(payload["text"])
    if payload["kind"] == "chart":
        container.plotly_chart(payload["figure"], use_container_width=True)
        container.caption(payload["caption"])
    elif payload["kind"] == "overview":
        render_kpi_row(container, payload["metrics"])
        render_callouts(container, payload["callouts"])
```

- [ ] **Step 6: Update the two existing tests whose expected behaviour A1 deliberately changes**

In `tests/test_app_answer.py`, replace `test_no_match_question_gives_honest_caveat`:

```python
def test_no_match_question_gives_honest_caveat():
    # A1 (meeting-ready design, Part A1): a zero-filter number question now
    # returns the Overview answer instead of the old apology-paragraph — a
    # deliberate behaviour change, not a regression. See _MEETING-READY-DESIGN.md.
    app = _reload_app()
    result = app.answer("how much did we spend on Car Fuel")
    assert "overall picture" in result.lower()
```

Replace `test_nonsense_question_still_gets_honest_caveat`:

```python
def test_nonsense_question_still_gets_honest_overview():
    # A1: gibberish also lands on the Overview fallback, deliberately —
    # distinguishing gibberish from genuine vagueness needs the LLM upgrade
    # this project doesn't have yet, and an overview is a strictly better
    # dead-end than an apology either way.
    app = _reload_app()
    payload = app.answer_payload("asdkjfh qwoeiruqwoe")
    assert payload["kind"] == "overview"
    assert "€" in payload["metrics"][0][1]
```

- [ ] **Step 7: Run the full test suite to verify everything passes**

```bash
pytest tests/ -v
```

Expected: PASS, no failures. (Confirms this task didn't silently break any Phase 1 regression coverage.)

- [ ] **Step 8: Commit**

```bash
git add app.py tests/test_app_answer.py
git commit -m "feat: overview KPI/callout rendering, A1 vague-question fallback"
```

---

## Task 3: Suggestion chips (empty state + after overview/help)

**Files:**
- Modify: `app.py`
- Test: `tests/test_app_answer.py` (append)

**Interfaces:**
- Consumes: `payload.get("show_chips")` (Task 2) to decide whether to render chips after an assistant message.
- Produces: `st.session_state.pending_question` — set by a chip click, consumed at the top of the script exactly like a typed `st.chat_input` submission. No other task depends on new names from this one; it only changes the script's top-level flow.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_app_answer.py`:

```python
def test_suggestion_chips_present_on_empty_state():
    # Confirmed against the installed Streamlit build: AppTest exposes
    # st.pills widgets via `at.pills` (a WidgetList), NOT `at.get("pills")`
    # (which returns empty) — verified directly with a throwaway AppTest
    # script before writing this test, not assumed from the chat_input
    # precedent elsewhere in this file.
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception
    assert len(at.pills) == 1
    assert at.pills[0].options == [
        "Give me an overview",
        "Show me a bar chart of category spend",
        "Who are our top suppliers?",
    ]


def test_clicking_a_chip_submits_it_as_a_question():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    at.pills[0].set_value("Give me an overview").run()
    assert not at.exception
    assert len(at.session_state.messages) == 2
    assert at.session_state.messages[0]["content"] == "Give me an overview"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_app_answer.py -v -k "chip"
```

Expected: FAIL — no `st.pills` widget exists yet.

- [ ] **Step 3: Add the chip constant and renderer to `app.py`**

Add near the top of `app.py`, below the `PLACEHOLDER` constant:

```python
SUGGESTION_CHIPS = [
    "Give me an overview",
    "Show me a bar chart of category spend",
    "Who are our top suppliers?",
]


def render_chips(container, key_suffix: str) -> None:
    selection = container.pills(
        "Suggested questions",
        SUGGESTION_CHIPS,
        selection_mode="single",
        label_visibility="collapsed",
        key=f"chips_{key_suffix}",
    )
    if selection:
        st.session_state.pending_question = selection
        st.rerun()
```

- [ ] **Step 4: Wire chips into the empty state and the answered state**

Replace the whole block in `app.py` from `PLACEHOLDER = "..."` down to (and including) the final `if prompt:` handling block, with:

```python
PLACEHOLDER = "What was our IT and telecom spend for Alpine Operations in 2024?"

pending = st.session_state.pop("pending_question", None)

if not st.session_state.messages:
    # Empty state: a centered "hero" layout, matching the home screen of the
    # chat products this is modelled on (Claude, ChatGPT, Manus) — a large
    # heading with the input directly beneath it, roughly centered in the
    # viewport, rather than pinned to the bottom of an empty page.
    #
    # st.chat_input() only pins to the page bottom when called at the root
    # level with no wrapping container (confirmed against the installed
    # Streamlit source, elements/widgets/chat.py) — nested inside
    # st.container(), it renders inline instead, wherever that container
    # sits in the page flow. That's what makes this layout possible at all.
    st.markdown(
        f"<div style='text-align:center;padding:18vh 0 32px;'>"
        f"<p style='font-size:44px;font-weight:700;color:{BRAND};margin:0;"
        f"letter-spacing:-0.01em;'>Ask about your spend</p></div>",
        unsafe_allow_html=True,
    )
    with st.container():
        typed = st.chat_input(PLACEHOLDER)
    render_chips(st, key_suffix="empty")
    prompt = pending or typed
else:
    # Conversation state: full history, input pinned to the bottom — the
    # standard chat layout once there's something to scroll. Suggestion
    # chips only reappear here after the LAST message, and only when that
    # message's payload asked for them (overview-fallback or help answers,
    # A3/A2) — showing them after every past occurrence in history would
    # clutter the conversation with stale, already-acted-on suggestions.
    last_index = len(st.session_state.messages) - 1
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"], avatar=AVATARS[message["role"]]):
            if message.get("payload"):
                render_payload(st, message["payload"])
            else:
                st.markdown(message["content"])
        if i == last_index and message["role"] == "assistant" and message.get("payload", {}).get("show_chips"):
            render_chips(st, key_suffix=str(i))
    typed = st.chat_input(PLACEHOLDER)
    prompt = pending or typed

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt, "payload": None})
    payload = answer_payload(prompt)
    st.session_state.messages.append(
        {"role": "assistant", "content": payload["text"], "payload": payload}
    )
    # Rerun rather than render the new exchange inline here: on the very
    # first message, this branch was reached via the empty-state layout
    # above (centered heading + centered input) — rendering the exchange
    # directly below that would leave the centered layout stuck on screen
    # underneath a real conversation. Rerunning re-executes the script with
    # messages now non-empty, so it takes the conversation-state branch
    # instead and renders cleanly (history loop + bottom-pinned input) —
    # confirmed via a real two-question run in the browser, not assumed.
    st.rerun()
```

This removes the old `PLACEHOLDER`-only empty/conversation branch and its trailing `if prompt:` block, replacing both with the version above (which adds chip rendering and pending-question consumption but is otherwise the same shape). The `render_payload`/`format_filters`/`answer_payload` function definitions above this block are unchanged.

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_app_answer.py -v -k "chip"
```

Expected: PASS (2 passed).

- [ ] **Step 6: Run the full suite**

```bash
pytest tests/ -v
```

Expected: PASS, no failures.

- [ ] **Step 7: Commit**

```bash
git add app.py tests/test_app_answer.py
git commit -m "feat: suggestion chips on empty state and after overview/help answers"
```

---

## Task 4: Top suppliers — understanding + computation

**Files:**
- Modify: `nl_parser.py`
- Modify: `chart_query.py`
- Test: `tests/test_nl_parser.py` (append)
- Test: `tests/test_chart_query.py` (append)

**Interfaces:**
- Produces: `nl_parser.parse_question()` may now return `intent="chart", chart_kind="top_suppliers", top_n=<int>`.
- Produces: `chart_query.top_suppliers(df, n=15, **filters) -> pd.DataFrame` with columns `[supplier, year, net_spend]`, `supplier` an ordered Categorical — Task 5 consumes this exact shape.

- [ ] **Step 1: Write the failing parser tests**

Append to `tests/test_nl_parser.py`:

```python
def test_top_suppliers_keyword_triggers_chart_intent():
    result = parse_question("who are our top suppliers?", KV)
    assert result["intent"] == "chart"
    assert result["chart_kind"] == "top_suppliers"
    assert result["top_n"] == 15


def test_top_n_suppliers_sets_n():
    result = parse_question("top 5 suppliers", KV)
    assert result["chart_kind"] == "top_suppliers"
    assert result["top_n"] == 5


def test_top_n_suppliers_clamps_to_max():
    result = parse_question("top 200 suppliers", KV)
    assert result["top_n"] == 56


def test_top_n_suppliers_clamps_to_min():
    result = parse_question("top 1 suppliers", KV)
    assert result["top_n"] == 3


def test_biggest_suppliers_phrase_detected():
    result = parse_question("who are our biggest suppliers", KV)
    assert result["chart_kind"] == "top_suppliers"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_nl_parser.py -v -k "top_suppliers or top_n or biggest"
```

Expected: FAIL — `top_suppliers` isn't a recognised `chart_kind` yet.

- [ ] **Step 3: Add top-suppliers detection to `nl_parser.py`**

Add near the top of `nl_parser.py`, below `OVERVIEW_KEYWORDS`:

```python
TOP_SUPPLIERS_KEYWORDS = (
    "top suppliers", "top supplier", "biggest suppliers", "largest suppliers",
    "top vendors", "supplier ranking", "who do we spend the most with",
)
TOP_N_PATTERN = re.compile(r"\btop\s+(\d+)\b")
MIN_TOP_SUPPLIERS_N = 3
MAX_TOP_SUPPLIERS_N = 56
DEFAULT_TOP_SUPPLIERS_N = 15
```

In `parse_question`, insert this block right after the `if any(kw in q for kw in OVERVIEW_KEYWORDS): ...` block and before the existing `is_chart = (...)` line:

```python
    top_n_match = TOP_N_PATTERN.search(q)
    is_top_suppliers = any(kw in q for kw in TOP_SUPPLIERS_KEYWORDS) or (
        top_n_match is not None and "supplier" in q
    )
    if is_top_suppliers:
        if top_n_match:
            n = max(MIN_TOP_SUPPLIERS_N, min(MAX_TOP_SUPPLIERS_N, int(top_n_match.group(1))))
        else:
            n = DEFAULT_TOP_SUPPLIERS_N
        return {
            "intent": "chart", "chart_kind": "top_suppliers",
            "breakdown": None, "category_level": None,
            "top_n": n, "filters": filters,
        }
```

(Note this block builds its own return dict with `"top_n"` and `"filters"` set directly, rather than using the `base = {"top_n": None, "filters": filters}` dict from Task 1's version — `top_n` here is the real clamped value, not `None`.)

- [ ] **Step 4: Run parser tests to verify they pass**

```bash
pytest tests/test_nl_parser.py -v -k "top_suppliers or top_n or biggest"
```

Expected: PASS (5 passed).

- [ ] **Step 5: Write the failing computation test**

Append to `tests/test_chart_query.py`:

```python
from chart_query import top_suppliers


def test_top_suppliers_totals_match_query_spend():
    df = load_data()
    chart_df = top_suppliers(df, n=15)
    for supplier in chart_df["supplier"].unique():
        for year in chart_df.loc[chart_df["supplier"] == supplier, "year"].unique():
            chart_total = chart_df.loc[
                (chart_df["supplier"] == supplier) & (chart_df["year"] == year), "net_spend"
            ].sum()
            reference = query_spend(df, supplier=str(supplier), year=int(year))
            assert round(chart_total, 2) == reference["total_net_spend"], (supplier, year)


def test_top_suppliers_respects_n():
    df = load_data()
    chart_df = top_suppliers(df, n=5)
    assert chart_df["supplier"].nunique() == 5


def test_top_suppliers_sorted_descending_by_total():
    df = load_data()
    chart_df = top_suppliers(df, n=10)
    totals_in_order = chart_df.groupby("supplier", observed=True, sort=False)["net_spend"].sum()
    values = totals_in_order.tolist()
    assert values == sorted(values, reverse=True)


def test_top_suppliers_filters_apply():
    df = load_data()
    chart_df = top_suppliers(df, n=15, year=2024)
    assert set(chart_df["year"].unique()) == {2024}
```

- [ ] **Step 6: Run test to verify it fails**

```bash
pytest tests/test_chart_query.py -v -k top_suppliers
```

Expected: FAIL with `ImportError: cannot import name 'top_suppliers'`.

- [ ] **Step 7: Add `top_suppliers()` to `chart_query.py`**

Append to `chart_query.py`:

```python
def top_suppliers(df: pd.DataFrame, n: int = 15, **filters) -> pd.DataFrame:
    """Top N suppliers by total net spend across the years in scope.

    Returns a tidy dataframe [supplier, year, net_spend], one row per
    supplier x year present in the filtered data, restricted to the top N
    suppliers ranked by their total spend summed across all years in
    scope. `supplier` is an ordered Categorical, sorted descending by each
    supplier's total — matching the InSight demo's bar order. Unlike
    category_spend(), there is no year default here: the demo's own Top
    suppliers view shows every year in scope side by side (the year-on-year
    comparison IS the view's value) — a year filter, if the caller passes
    one, naturally restricts to a single series.
    """
    matched = filter_df(df, **filters).copy()
    grouped = (
        matched.groupby(["Supplier name", "Year"])["Net spend"]
        .sum()
        .reset_index()
        .rename(columns={"Supplier name": "supplier", "Year": "year", "Net spend": "net_spend"})
    )
    totals = grouped.groupby("supplier")["net_spend"].sum().sort_values(ascending=False)
    top_names = totals.head(n).index.tolist()
    result = grouped[grouped["supplier"].isin(top_names)].copy()
    result["supplier"] = pd.Categorical(result["supplier"], categories=top_names, ordered=True)
    result = result.sort_values(["supplier", "year"]).reset_index(drop=True)
    return result
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
pytest tests/test_chart_query.py -v
```

Expected: PASS, all tests in the file.

- [ ] **Step 9: Commit**

```bash
git add nl_parser.py chart_query.py tests/test_nl_parser.py tests/test_chart_query.py
git commit -m "feat: top-suppliers understanding + deterministic computation"
```

---

## Task 5: Top suppliers — presentation + wiring

**Files:**
- Modify: `chart_render.py`
- Modify: `app.py`
- Test: `tests/test_chart_render.py` (append)
- Test: `tests/test_app_answer.py` (append)

**Interfaces:**
- Consumes: `chart_query.top_suppliers()` (Task 4).
- Produces: `chart_render.build_top_suppliers_figure(chart_df) -> go.Figure`.

- [ ] **Step 1: Write the failing render test**

Append to `tests/test_chart_render.py`:

```python
from chart_query import top_suppliers
from chart_render import build_top_suppliers_figure
from spend_query import load_data


def test_top_suppliers_figure_has_one_trace_per_year():
    df = load_data()
    chart_df = top_suppliers(df, n=10)
    fig = build_top_suppliers_figure(chart_df)
    assert len(fig.data) == chart_df["year"].nunique()
    assert fig.layout.barmode == "group"


def test_top_suppliers_figure_strips_demo_prefix():
    df = load_data()
    chart_df = top_suppliers(df, n=5)
    fig = build_top_suppliers_figure(chart_df)
    for name in fig.data[0].y:
        assert not str(name).startswith("Demo ")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_chart_render.py -v -k top_suppliers
```

Expected: FAIL with `ImportError: cannot import name 'build_top_suppliers_figure'`.

- [ ] **Step 3: Add `build_top_suppliers_figure()` to `chart_render.py`**

Append to `chart_render.py`:

```python
def build_top_suppliers_figure(chart_df) -> go.Figure:
    """Build the top-suppliers chart: one horizontal grouped bar per year in
    scope, suppliers sorted descending by total spend across those years —
    matching the InSight demo's Top suppliers view. Grouped (not stacked)
    bars have a free end, so labels sit "outside" rather than "inside"
    (unlike build_category_spend_figure's stacked segments).
    """
    suppliers = list(chart_df["supplier"].cat.categories)
    years = sorted(chart_df["year"].unique())

    series = {
        year: chart_df[chart_df["year"] == year]
        .set_index("supplier")["net_spend"]
        .reindex(suppliers, fill_value=0)
        for year in years
    }
    all_values = pd.concat(series.values()) if series else pd.Series(dtype=float)
    min_value = min(0.0, float(all_values.min())) if not all_values.empty else 0.0
    max_value = max(0.0, float(all_values.max())) if not all_values.empty else 0.0

    display_names = [str(s).replace("Demo ", "") for s in suppliers]

    fig = go.Figure()
    for i, year in enumerate(years):
        fig.add_trace(
            go.Bar(
                y=display_names,
                x=series[year],
                name=str(year),
                orientation="h",
                marker_color=PALETTE[i % len(PALETTE)],
                text=[f"{v:,.0f}" if v != 0 else "" for v in series[year]],
                textposition="outside",
            )
        )

    tickvals, ticktext = _millions_ticks(min_value, max_value)
    fig.update_layout(
        barmode="group",
        yaxis=dict(autorange="reversed"),
        legend_title_text="",
        margin=dict(l=0, r=0, t=10, b=0),
        height=80 + 40 * len(suppliers),
    )
    fig.update_xaxes(
        title_text="Net spend (€)",
        tickmode="array",
        tickvals=tickvals,
        ticktext=ticktext,
    )
    return fig
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_chart_render.py -v -k top_suppliers
```

Expected: PASS (2 passed).

- [ ] **Step 5: Write the failing wiring test**

Append to `tests/test_app_answer.py`:

```python
def test_top_suppliers_question_returns_chart_payload():
    app = _reload_app()
    payload = app.answer_payload("who are our top suppliers?")
    assert payload["kind"] == "chart"
    assert "Top 15 suppliers" in payload["text"]
    assert "€" in payload["caption"]


def test_top_n_suppliers_question_respects_n():
    app = _reload_app()
    payload = app.answer_payload("top 5 suppliers")
    assert "Top 5" in payload["text"]
```

- [ ] **Step 6: Run test to verify it fails**

```bash
pytest tests/test_app_answer.py -v -k top_suppliers
```

Expected: FAIL — `answer_payload` doesn't dispatch `chart_kind == "top_suppliers"` yet.

- [ ] **Step 7: Wire top suppliers into `app.py`**

Add to the import block at the top of `app.py`:

```python
from chart_query import top_suppliers
from chart_render import build_top_suppliers_figure
```

In `app.py`, inside the `if parsed["intent"] == "chart":` branch, the existing body (the `if "year" in filters: ... chart_filters = ... chart_df = category_spend(...) ...` logic) currently assumes `category_spend` unconditionally. Restructure that branch's opening to dispatch on `chart_kind` — replace from `if parsed["intent"] == "chart":` through the line that computes `chart_filters` (both branches of the existing `if "year" in filters: / else:`) with:

```python
    if parsed["intent"] == "chart":
        chart_kind = parsed["chart_kind"]

        if chart_kind == "top_suppliers":
            requested_n = parsed["top_n"]
            chart_df = top_suppliers(df, n=requested_n, **filters)
            if chart_df.empty:
                return {
                    "kind": "text",
                    "text": f"I didn't find any suppliers matching that — {format_filters(filters)} returned no rows.",
                    "figure": None, "caption": None, "show_chips": False,
                }
            fig = build_top_suppliers_figure(chart_df)
            actual_n = chart_df["supplier"].nunique()
            years_in_scope = sorted(chart_df["year"].unique())
            year_text = " vs ".join(str(y) for y in years_in_scope) if len(years_in_scope) > 1 else str(years_in_scope[0])
            total = format_currency(round(chart_df["net_spend"].sum(), 2))
            clamp_note = f" (clamped from {requested_n})" if actual_n != requested_n else ""
            caption = f"Top {actual_n} suppliers{clamp_note} by net spend, {year_text} — total {total}."
            return {
                "kind": "chart", "text": f"Top {actual_n} suppliers",
                "figure": fig, "caption": caption, "show_chips": False,
            }

        if "year" in filters:
            chart_filters = dict(filters)
        else:
            chart_filters = {"year": max(kv["year"]), **filters}
```

Leave the rest of the existing `category_spend` handling below that unchanged for now (it still runs when `chart_kind == "category_spend"`, since `top_suppliers` returns early above it).

- [ ] **Step 8: Run tests to verify they pass**

```bash
pytest tests/test_app_answer.py -v -k top_suppliers
```

Expected: PASS (2 passed).

- [ ] **Step 9: Run the full suite**

```bash
pytest tests/ -v
```

Expected: PASS, no failures.

- [ ] **Step 10: Commit**

```bash
git add chart_render.py app.py tests/test_chart_render.py tests/test_app_answer.py
git commit -m "feat: top-suppliers chart rendering and wiring"
```

---

## Task 6: Supplier drill-down — understanding + computation

**Files:**
- Modify: `nl_parser.py`
- Modify: `chart_query.py`
- Test: `tests/test_nl_parser.py` (append)
- Test: `tests/test_chart_query.py` (append)

**Interfaces:**
- Produces: `nl_parser.parse_question()` may now return `intent="supplier_drilldown"` when a question names exactly one supplier and no other narrowing filter besides an optional year.
- Produces: `chart_query.supplier_drilldown(df, supplier: str, **filters) -> dict` with keys `supplier, year, net_spend, prior_year, yoy_pct, share_of_scope_pct, entity_count, category_count, by_entity, by_category` — Task 7 consumes this exact shape.

- [ ] **Step 1: Write the failing parser tests**

Append to `tests/test_nl_parser.py`:

```python
def test_supplier_alone_triggers_drilldown_intent():
    result = parse_question("tell me about Demo Supplier 025", KV)
    assert result["intent"] == "supplier_drilldown"
    assert result["filters"]["supplier"] == "Demo Supplier 025"


def test_supplier_with_year_still_triggers_drilldown():
    result = parse_question("how much did we spend with Demo Supplier 025 in 2024?", KV)
    assert result["intent"] == "supplier_drilldown"
    assert result["filters"]["year"] == 2024


def test_supplier_with_entity_and_category_does_not_trigger_drilldown():
    # Regression guard: this exact question already has passing coverage in
    # test_app_answer.py (test_negative_total_shows_minus_sign_before_euro_symbol)
    # asserting a specific plain-number answer. Supplier + entity + category
    # together is a precise "give me this one number" question, not a broad
    # "tell me about this supplier" question — it must keep returning the
    # existing "number" intent, not the new drill-down.
    result = parse_question(
        "What did supplier Demo Supplier 052 spend on Utilities for Demo Iberia Distribution?",
        KV,
    )
    assert result["intent"] == "number"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_nl_parser.py -v -k drilldown
```

Expected: FAIL — first two tests fail (`"supplier_drilldown"` intent doesn't exist yet); the third already passes (documents current behaviour, which must not change).

- [ ] **Step 3: Add drill-down routing to `nl_parser.py`**

In `parse_question`, insert this block right after the existing `if not is_chart: return {"intent": "number", ...}` line's matching `if is_chart:` body finishes (i.e., after the function's existing final `return {"intent": "chart", "chart_kind": "category_spend", ...}` statement) — add a new check that only runs when `is_chart` was `False`, replacing the current unconditional `if not is_chart: return {"intent": "number", ...}` with:

```python
    if not is_chart:
        DRILLDOWN_ALLOWED_EXTRA_FILTERS = {"year"}
        if "supplier" in filters and (set(filters) - {"supplier"}) <= DRILLDOWN_ALLOWED_EXTRA_FILTERS:
            return {
                "intent": "supplier_drilldown", "chart_kind": None,
                "breakdown": None, "category_level": None, **base,
            }
        return {"intent": "number", "chart_kind": None, "breakdown": None, "category_level": None, **base}
```

(`DRILLDOWN_ALLOWED_EXTRA_FILTERS` is defined inline here rather than as a module-level constant since it's only used in this one place — a single-use local reads more clearly than a name that has to be looked up elsewhere.)

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_nl_parser.py -v -k drilldown
```

Expected: PASS (3 passed).

- [ ] **Step 5: Run the full parser test file to confirm no regression**

```bash
pytest tests/test_nl_parser.py -v
```

Expected: PASS, all tests.

- [ ] **Step 6: Write the failing computation test**

Append to `tests/test_chart_query.py`:

```python
from chart_query import supplier_drilldown


def test_supplier_drilldown_net_spend_matches_query_spend():
    df = load_data()
    result = supplier_drilldown(df, "Demo Supplier 025")
    reference = query_spend(df, supplier="Demo Supplier 025", year=result["year"])
    assert result["net_spend"] == reference["total_net_spend"]


def test_supplier_drilldown_by_entity_sums_to_net_spend():
    df = load_data()
    result = supplier_drilldown(df, "Demo Supplier 025")
    assert round(result["by_entity"]["net_spend"].sum(), 2) == result["net_spend"]


def test_supplier_drilldown_by_category_sums_to_net_spend():
    df = load_data()
    result = supplier_drilldown(df, "Demo Supplier 025")
    assert round(result["by_category"]["net_spend"].sum(), 2) == result["net_spend"]


def test_supplier_drilldown_unknown_supplier_returns_none_year():
    df = load_data()
    result = supplier_drilldown(df, "Nonexistent Supplier")
    assert result["year"] is None
    assert result["by_entity"].empty
```

- [ ] **Step 7: Run test to verify it fails**

```bash
pytest tests/test_chart_query.py -v -k drilldown
```

Expected: FAIL with `ImportError: cannot import name 'supplier_drilldown'`.

- [ ] **Step 8: Add `supplier_drilldown()` to `chart_query.py`**

Append to `chart_query.py`:

```python
def supplier_drilldown(df: pd.DataFrame, supplier: str, **filters) -> dict:
    """Single-supplier KPIs + entity/category breakdowns — the InSight
    demo's Supplier drill-down view. `filters` may carry a `year` (or other
    dimensions, though the parser only ever routes plain supplier-or-
    supplier+year questions here — see nl_parser.py's DRILLDOWN_ALLOWED_
    EXTRA_FILTERS); a `supplier` key in `filters` is ignored in favour of
    the explicit `supplier` argument, since the two would otherwise
    disagree if a caller passed both.

    Returns a dict:
      - supplier: str, year, net_spend, prior_year, yoy_pct — same shape/
        rules as overview_query.overview()
      - share_of_scope_pct: this supplier's net_spend in `year` as a % of
        total net spend in `year` across ALL suppliers in the same
        `filters` scope (excluding the `supplier` filter itself)
      - entity_count, category_count: distinct counts for this supplier in `year`
      - by_entity, by_category: DataFrames [name, net_spend], descending
    """
    scoped_filters = {k: v for k, v in filters.items() if k != "supplier"}
    scope_matched = filter_df(df, **scoped_filters)
    supplier_matched = scope_matched[scope_matched["Supplier name"] == supplier]

    if supplier_matched.empty:
        empty_cols = pd.DataFrame(columns=["name", "net_spend"])
        return {
            "supplier": supplier, "year": None, "net_spend": 0.0,
            "prior_year": None, "yoy_pct": None, "share_of_scope_pct": None,
            "entity_count": 0, "category_count": 0,
            "by_entity": empty_cols, "by_category": empty_cols,
        }

    year = int(supplier_matched["Year"].max())
    year_rows = supplier_matched[supplier_matched["Year"] == year]
    net_spend = round(float(year_rows["Net spend"].sum()), 2)

    prior_year_candidate = year - 1
    prior_rows = supplier_matched[supplier_matched["Year"] == prior_year_candidate]
    if prior_rows.empty:
        prior_year = None
        yoy_pct = None
    else:
        prior_year = prior_year_candidate
        prior_spend = float(prior_rows["Net spend"].sum())
        yoy_pct = round((net_spend - prior_spend) / prior_spend * 100, 1) if prior_spend != 0 else None

    scope_year_total = float(scope_matched[scope_matched["Year"] == year]["Net spend"].sum())
    share_of_scope_pct = round(net_spend / scope_year_total * 100, 1) if scope_year_total != 0 else None

    entity_count = int(year_rows["Entity"].nunique())
    category_count = int(year_rows["L1"].nunique())

    by_entity = (
        year_rows.groupby("Entity")["Net spend"].sum().sort_values(ascending=False)
        .reset_index().rename(columns={"Entity": "name", "Net spend": "net_spend"})
    )
    by_category = (
        year_rows.groupby("L1")["Net spend"].sum().sort_values(ascending=False)
        .reset_index().rename(columns={"L1": "name", "Net spend": "net_spend"})
    )

    return {
        "supplier": supplier, "year": year, "net_spend": net_spend,
        "prior_year": prior_year, "yoy_pct": yoy_pct,
        "share_of_scope_pct": share_of_scope_pct,
        "entity_count": entity_count, "category_count": category_count,
        "by_entity": by_entity, "by_category": by_category,
    }
```

- [ ] **Step 9: Run tests to verify they pass**

```bash
pytest tests/test_chart_query.py -v
```

Expected: PASS, all tests in the file.

- [ ] **Step 10: Commit**

```bash
git add nl_parser.py chart_query.py tests/test_nl_parser.py tests/test_chart_query.py
git commit -m "feat: supplier drill-down understanding + deterministic computation"
```

---

## Task 7: Supplier drill-down — presentation + wiring

**Files:**
- Modify: `chart_render.py`
- Modify: `app.py`
- Test: `tests/test_chart_render.py` (append)
- Test: `tests/test_app_answer.py` (append)

**Interfaces:**
- Consumes: `chart_query.supplier_drilldown()` (Task 6); `render_kpi_row()` (Task 2).
- Produces: `chart_render.build_supplier_drilldown_figures(drilldown: dict) -> tuple[go.Figure, go.Figure]`.

- [ ] **Step 1: Write the failing render test**

Append to `tests/test_chart_render.py`:

```python
from chart_query import supplier_drilldown
from chart_render import build_supplier_drilldown_figures


def test_supplier_drilldown_figures_strip_demo_prefix():
    df = load_data()
    drilldown = supplier_drilldown(df, "Demo Supplier 025")
    entity_fig, category_fig = build_supplier_drilldown_figures(drilldown)
    for name in entity_fig.data[0].y:
        assert not str(name).startswith("Demo ")
    assert len(category_fig.data[0].y) == drilldown["by_category"]["name"].nunique()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_chart_render.py -v -k drilldown
```

Expected: FAIL with `ImportError: cannot import name 'build_supplier_drilldown_figures'`.

- [ ] **Step 3: Add the figure builders to `chart_render.py`**

Append to `chart_render.py`:

```python
def _single_series_bar_figure(data, x_title: str) -> go.Figure:
    """One horizontal bar per row in `data` ([name, net_spend]), already
    sorted descending by the caller — the shared shape behind the supplier
    drill-down's spend-by-entity and spend-by-category charts."""
    names = [str(n).replace("Demo ", "") for n in data["name"]]
    values = data["net_spend"].tolist()
    min_value = min(0.0, min(values)) if values else 0.0
    max_value = max(0.0, max(values)) if values else 0.0
    tickvals, ticktext = _millions_ticks(min_value, max_value)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=names,
            x=values,
            orientation="h",
            marker_color=PALETTE[0],
            text=[f"{v:,.0f}" for v in values],
            textposition="outside",
        )
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0),
        height=60 + 30 * len(names),
    )
    fig.update_xaxes(
        title_text=x_title,
        tickmode="array",
        tickvals=tickvals,
        ticktext=ticktext,
    )
    return fig


def build_supplier_drilldown_figures(drilldown: dict) -> tuple[go.Figure, go.Figure]:
    """Two figures from chart_query.supplier_drilldown()'s output: spend by
    entity, spend by category — matching the InSight demo's drill-down
    layout (the two charts side by side)."""
    entity_fig = _single_series_bar_figure(drilldown["by_entity"], "Net spend (€)")
    category_fig = _single_series_bar_figure(drilldown["by_category"], "Net spend (€)")
    return entity_fig, category_fig
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_chart_render.py -v -k drilldown
```

Expected: PASS.

- [ ] **Step 5: Write the failing wiring test**

Append to `tests/test_app_answer.py`:

```python
def test_supplier_question_returns_drilldown_payload():
    app = _reload_app()
    payload = app.answer_payload("tell me about Demo Supplier 025")
    assert payload["kind"] == "supplier_drilldown"
    assert len(payload["metrics"]) == 4
    assert "entity_figure" in payload
    assert "category_figure" in payload


def test_supplier_with_entity_and_category_still_returns_plain_number():
    # Regression guard mirroring test_nl_parser.py's equivalent test —
    # confirms app.py's dispatch preserves the existing passing behaviour
    # for this exact question (test_negative_total_shows_minus_sign_before_euro_symbol).
    app = _reload_app()
    payload = app.answer_payload(
        "What did supplier Demo Supplier 052 spend on Utilities for Demo Iberia Distribution?"
    )
    assert payload["kind"] == "text"
    assert "-€7,637.65" in payload["text"]
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
pytest tests/test_app_answer.py -v -k drilldown
```

Expected: first test FAILs (`answer_payload` doesn't route `"supplier_drilldown"` intent yet); second already passes.

- [ ] **Step 7: Wire supplier drill-down into `app.py`**

Add to the import block at the top of `app.py`:

```python
from chart_query import supplier_drilldown
from chart_render import build_supplier_drilldown_figures
```

Add this function above `answer_payload`:

```python
def build_supplier_drilldown_payload(filters: dict) -> dict:
    supplier = filters["supplier"]
    drilldown = supplier_drilldown(df, supplier, **filters)
    display_name = supplier.replace("Demo ", "")

    if drilldown["year"] is None:
        return {
            "kind": "text",
            "text": f"I didn't find any spend for {display_name} matching that.",
            "figure": None, "caption": None, "show_chips": False,
        }

    net_spend_str = format_currency(drilldown["net_spend"])
    delta = f"{drilldown['yoy_pct']:+.1f}%" if drilldown["yoy_pct"] is not None else None
    share_str = f"{drilldown['share_of_scope_pct']:.1f}%" if drilldown["share_of_scope_pct"] is not None else "n/a"
    metrics = [
        (f"Spend {drilldown['year']}", net_spend_str, delta),
        ("Share of scope", share_str, None),
        ("Entities served", str(drilldown["entity_count"]), None),
        ("Categories", str(drilldown["category_count"]), None),
    ]
    entity_figure, category_figure = build_supplier_drilldown_figures(drilldown)

    delta_text = f" ({delta} vs {drilldown['prior_year']})" if delta else ""
    text = f"{display_name} — {net_spend_str} in {drilldown['year']}{delta_text}, {share_str} of spend in scope."

    return {
        "kind": "supplier_drilldown", "text": text, "metrics": metrics,
        "entity_figure": entity_figure, "category_figure": category_figure,
        "show_chips": False,
    }
```

In `answer_payload`, add this branch directly after the `if parsed["intent"] == "overview": return build_overview_payload(filters)` line, and before `if parsed["intent"] == "chart":`:

```python
    if parsed["intent"] == "supplier_drilldown":
        return build_supplier_drilldown_payload(filters)
```

Add the new payload kind to `render_payload`, appending an `elif` branch after the existing `elif payload["kind"] == "overview": ...` branch:

```python
    elif payload["kind"] == "supplier_drilldown":
        render_kpi_row(container, payload["metrics"])
        fig_cols = container.columns(2)
        fig_cols[0].plotly_chart(payload["entity_figure"], use_container_width=True)
        fig_cols[1].plotly_chart(payload["category_figure"], use_container_width=True)
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
pytest tests/test_app_answer.py -v -k drilldown
```

Expected: PASS (2 passed).

- [ ] **Step 9: Run the full suite**

```bash
pytest tests/ -v
```

Expected: PASS, no failures — this is the checkpoint that confirms Task 6's regression guard actually holds end-to-end through `app.py`, not just in the parser.

- [ ] **Step 10: Commit**

```bash
git add chart_render.py app.py tests/test_chart_render.py tests/test_app_answer.py
git commit -m "feat: supplier drill-down rendering and wiring"
```

---

## Task 8: Fragmentation — computation

**Files:**
- Modify: `nl_parser.py`
- Modify: `chart_query.py`
- Test: `tests/test_nl_parser.py` (append)
- Test: `tests/test_chart_query.py` (append)

**Interfaces:**
- Produces: `nl_parser.parse_question()` may now return `intent="chart", chart_kind="fragmentation"`.
- Produces: `chart_query.fragmentation(df, level="l1", **filters) -> pd.DataFrame` with columns `[category, net_spend, supplier_count, top_supplier_share_pct, cr3_pct, concentration_index, tier]` — Task 9 consumes this exact shape. `tier` is one of `"Concentrated"`, `"Medium fragmentation"`, `"High fragmentation"`.

- [ ] **Step 1: Write the failing parser test**

Append to `tests/test_nl_parser.py`:

```python
def test_fragmentation_keyword_triggers_chart_intent():
    result = parse_question("show me fragmentation", KV)
    assert result["intent"] == "chart"
    assert result["chart_kind"] == "fragmentation"


def test_supplier_concentration_phrase_detected():
    result = parse_question("what's our supplier concentration", KV)
    assert result["chart_kind"] == "fragmentation"


def test_fragmentation_respects_level_2_keyword():
    result = parse_question("fragmentation at level 2", KV)
    assert result["category_level"] == "l2"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_nl_parser.py -v -k fragmentation
```

Expected: FAIL — `"fragmentation"` isn't a recognised `chart_kind` yet.

- [ ] **Step 3: Add fragmentation detection to `nl_parser.py`**

Add near the top of `nl_parser.py`, below the `TOP_N_PATTERN`/`DEFAULT_TOP_SUPPLIERS_N` block:

```python
FRAGMENTATION_KEYWORDS = (
    "fragmentation", "fragmented", "supplier concentration", "how spread out",
    "how many suppliers per category", "tail spend",
)
```

In `parse_question`, insert this block right after the `if is_top_suppliers: ...` block (Task 4) and before the existing `is_chart = (...)` line:

```python
    if any(kw in q for kw in FRAGMENTATION_KEYWORDS):
        category_level = "l2" if any(kw in q for kw in LEVEL_2_KEYWORDS) else "l1"
        return {
            "intent": "chart", "chart_kind": "fragmentation",
            "breakdown": None, "category_level": category_level,
            "top_n": None, "filters": filters,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_nl_parser.py -v -k fragmentation
```

Expected: PASS (3 passed).

- [ ] **Step 5: Write the failing computation test**

Append to `tests/test_chart_query.py`:

```python
from chart_query import fragmentation


def test_fragmentation_net_spend_matches_query_spend():
    df = load_data()
    frag_df = fragmentation(df, level="l1", year=2025)
    for _, row in frag_df.iterrows():
        reference = query_spend(df, l1=str(row["category"]), year=2025)
        assert row["net_spend"] == reference["total_net_spend"], row["category"]


def test_fragmentation_cr3_between_0_and_100():
    df = load_data()
    frag_df = fragmentation(df, level="l1", year=2025)
    assert (frag_df["cr3_pct"] >= 0).all()
    assert (frag_df["cr3_pct"] <= 100).all()


def test_fragmentation_tier_matches_cr3_thresholds():
    df = load_data()
    frag_df = fragmentation(df, level="l1", year=2025)
    for _, row in frag_df.iterrows():
        if row["cr3_pct"] >= 70:
            assert row["tier"] == "Concentrated"
        elif row["cr3_pct"] >= 40:
            assert row["tier"] == "Medium fragmentation"
        else:
            assert row["tier"] == "High fragmentation"


def test_fragmentation_concentration_index_is_hhi_style():
    df = load_data()
    frag_df = fragmentation(df, level="l1", year=2025)
    year_rows = df[df["Year"] == 2025]
    sample_category = frag_df.iloc[0]["category"]
    cat_rows = year_rows[year_rows["L1"] == sample_category]
    by_supplier = cat_rows.groupby("Supplier name")["Net spend"].sum()
    shares_pct = by_supplier / by_supplier.sum() * 100
    expected_index = round(float((shares_pct ** 2).sum()), 0)
    actual_index = frag_df.loc[frag_df["category"] == sample_category, "concentration_index"].iloc[0]
    assert actual_index == expected_index
```

- [ ] **Step 6: Run test to verify it fails**

```bash
pytest tests/test_chart_query.py -v -k fragmentation
```

Expected: FAIL with `ImportError: cannot import name 'fragmentation'`.

- [ ] **Step 7: Add `fragmentation()` to `chart_query.py`**

Append to `chart_query.py`:

```python
# Our own CR3-based tiers, disclosed in every fragmentation answer's
# caption. NOT reverse-fitted to the InSight demo's own Profile column —
# see _MEETING-READY-DESIGN.md Part C1: cross-checking real InSight rows
# showed the demo's Profile likely tracks its Concentration index, not CR3
# alone, but with only 8 category rows to observe, the exact cutoff isn't
# reliably recoverable — and tuning ours to force a match would be
# measurement gaming (CLAUDE.md rule 24), not grounding. Concentration
# index is still computed and disclosed alongside CR3 (a standard,
# well-defined HHI-style statistic) but does not set the tier here.
CONCENTRATED_THRESHOLD = 70.0
MEDIUM_THRESHOLD = 40.0


def fragmentation(df: pd.DataFrame, level: str = "l1", **filters) -> pd.DataFrame:
    """Per-category supplier concentration: CR3 (top-3-supplier share) and
    an HHI-style concentration index (sum of squared per-supplier
    percentage shares of that category's spend), tiered by CR3 against
    CONCENTRATED_THRESHOLD/MEDIUM_THRESHOLD above.

    Returns a tidy dataframe: [category, net_spend, supplier_count,
    top_supplier_share_pct, cr3_pct, concentration_index, tier].
    """
    if level not in CATEGORY_COLUMNS:
        raise ValueError(f"level must be one of {list(CATEGORY_COLUMNS)}, got {level!r}")
    category_col = CATEGORY_COLUMNS[level]

    matched = filter_df(df, **filters).copy()
    matched[category_col] = matched[category_col].fillna("(unspecified)")

    rows = []
    for category, cat_df in matched.groupby(category_col, observed=True):
        net_spend = float(cat_df["Net spend"].sum())
        by_supplier = cat_df.groupby("Supplier name")["Net spend"].sum().sort_values(ascending=False)
        supplier_count = int(len(by_supplier))

        if net_spend <= 0 or by_supplier.empty:
            top_share, cr3, index = 0.0, 0.0, 0.0
        else:
            shares_pct = by_supplier / net_spend * 100
            top_share = round(float(shares_pct.iloc[0]), 1)
            cr3 = round(float(shares_pct.head(3).sum()), 1)
            index = round(float((shares_pct ** 2).sum()), 0)

        if cr3 >= CONCENTRATED_THRESHOLD:
            tier = "Concentrated"
        elif cr3 >= MEDIUM_THRESHOLD:
            tier = "Medium fragmentation"
        else:
            tier = "High fragmentation"

        rows.append({
            "category": category, "net_spend": round(net_spend, 2),
            "supplier_count": supplier_count, "top_supplier_share_pct": top_share,
            "cr3_pct": cr3, "concentration_index": index, "tier": tier,
        })

    return pd.DataFrame(rows).sort_values("net_spend", ascending=False).reset_index(drop=True)
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
pytest tests/test_chart_query.py -v
```

Expected: PASS, all tests in the file.

- [ ] **Step 9: Commit**

```bash
git add nl_parser.py chart_query.py tests/test_nl_parser.py tests/test_chart_query.py
git commit -m "feat: fragmentation understanding + CR3/concentration-index computation"
```

---

## Task 9: Fragmentation — presentation (bubble chart + detail table) + wiring

**Files:**
- Modify: `chart_render.py`
- Modify: `app.py`
- Test: `tests/test_chart_render.py` (append)
- Test: `tests/test_app_answer.py` (append)

**Interfaces:**
- Consumes: `chart_query.fragmentation()` (Task 8); `render_kpi_row()` (Task 2).
- Produces: `chart_render.build_fragmentation_figure(fragmentation_df) -> go.Figure`.

- [ ] **Step 1: Write the failing render test**

Append to `tests/test_chart_render.py`:

```python
from chart_query import fragmentation
from chart_render import build_fragmentation_figure


def test_fragmentation_figure_has_one_trace_per_tier_present():
    df = load_data()
    frag_df = fragmentation(df, level="l1", year=2025)
    fig = build_fragmentation_figure(frag_df)
    assert len(fig.data) == frag_df["tier"].nunique()


def test_fragmentation_figure_bubble_count_matches_categories():
    df = load_data()
    frag_df = fragmentation(df, level="l1", year=2025)
    fig = build_fragmentation_figure(frag_df)
    total_points = sum(len(trace.x) for trace in fig.data)
    assert total_points == len(frag_df)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_chart_render.py -v -k fragmentation
```

Expected: FAIL with `ImportError: cannot import name 'build_fragmentation_figure'`.

- [ ] **Step 3: Add `build_fragmentation_figure()` to `chart_render.py`**

Append to `chart_render.py`:

```python
# Fixed, semantic colour-to-tier mapping (not a cycled palette slot) — the
# InSight demo's own Fragmentation legend uses red/amber/green for
# High/Medium/Concentrated, so these three PALETTE entries are picked by
# meaning, not by cycling position like the multi-series charts above.
TIER_COLORS = {
    "High fragmentation": PALETTE[7],    # red
    "Medium fragmentation": PALETTE[3],  # amber/yellow
    "Concentrated": PALETTE[2],          # aqua/green
}


def build_fragmentation_figure(fragmentation_df) -> go.Figure:
    """Bubble chart: x = supplier count, y = category net spend, bubble
    size ~ spend, coloured by tier — matching the InSight demo's
    'Category spend vs supplier count' view.
    """
    fig = go.Figure()
    max_spend = float(fragmentation_df["net_spend"].max()) if not fragmentation_df.empty else 0.0

    for tier, group in fragmentation_df.groupby("tier"):
        sizes = [20 + 40 * (v / max_spend) if max_spend > 0 else 20 for v in group["net_spend"]]
        fig.add_trace(
            go.Scatter(
                x=group["supplier_count"],
                y=group["net_spend"],
                mode="markers",
                name=tier,
                marker=dict(size=sizes, color=TIER_COLORS.get(tier, PALETTE[0])),
                text=group["category"],
                customdata=group["cr3_pct"],
                hovertemplate="%{text}<br>Top 3 share: %{customdata:.1f}%<extra></extra>",
            )
        )

    tickvals, ticktext = _millions_ticks(0.0, max(0.0, max_spend))
    fig.update_layout(
        legend_title_text="",
        margin=dict(l=0, r=0, t=10, b=0),
        height=420,
    )
    fig.update_xaxes(title_text="Distinct suppliers")
    fig.update_yaxes(
        title_text="Net spend (€)",
        tickmode="array",
        tickvals=tickvals,
        ticktext=ticktext,
    )
    return fig
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_chart_render.py -v -k fragmentation
```

Expected: PASS (2 passed).

- [ ] **Step 5: Write the failing wiring test**

Append to `tests/test_app_answer.py`:

```python
def test_fragmentation_question_returns_fragmentation_payload():
    app = _reload_app()
    payload = app.answer_payload("show me fragmentation")
    assert payload["kind"] == "fragmentation"
    assert len(payload["metrics"]) == 4
    assert "figure" in payload
    assert "table" in payload
    assert "Top-3" in payload["caption"] or "Top 3" in payload["caption"]
```

- [ ] **Step 6: Run test to verify it fails**

```bash
pytest tests/test_app_answer.py -v -k fragmentation_question
```

Expected: FAIL — `answer_payload` doesn't dispatch `chart_kind == "fragmentation"` yet.

- [ ] **Step 7: Wire fragmentation into `app.py`**

Add to the import block at the top of `app.py`:

```python
from chart_query import fragmentation
from chart_render import build_fragmentation_figure
```

In `app.py`, inside the `if parsed["intent"] == "chart":` branch, add this dispatch right after the `if chart_kind == "top_suppliers": ...` block from Task 5 and before the `if "year" in filters: chart_filters = ...` line that handles `category_spend`:

```python
        if chart_kind == "fragmentation":
            if "year" in filters:
                chart_filters = dict(filters)
            else:
                chart_filters = {"year": max(kv["year"]), **filters}
            frag_df = fragmentation(df, level=parsed["category_level"], **chart_filters)
            if frag_df.empty:
                return {
                    "kind": "text",
                    "text": f"I didn't find any categories matching that — {format_filters(chart_filters)} returned no rows.",
                    "figure": None, "caption": None, "show_chips": False,
                }
            fig = build_fragmentation_figure(frag_df)
            high_count = int((frag_df["tier"] == "High fragmentation").sum())
            total_spend = float(frag_df["net_spend"].sum())
            high_spend = float(frag_df.loc[frag_df["tier"] == "High fragmentation", "net_spend"].sum())
            fragmented_pct = round(high_spend / total_spend * 100, 1) if total_spend else 0.0
            supplier_count = int(filter_df(df, **chart_filters)["Supplier name"].nunique())
            metrics = [
                ("Categories assessed", str(len(frag_df)), None),
                ("Highly fragmented", str(high_count), None),
                ("Fragmented spend", f"{fragmented_pct:.1f}%", None),
                ("Suppliers in scope", str(supplier_count), None),
            ]
            table = frag_df.rename(columns={
                "category": "Category", "net_spend": "Net spend (€)", "supplier_count": "Suppliers",
                "top_supplier_share_pct": "Top supplier share %", "cr3_pct": "Top 3 share %",
                "concentration_index": "Concentration index", "tier": "Tier",
            })
            caption = (
                "Tier is set by our own Top-3-supplier-share rule (Concentrated "
                "≥ 70%, Medium 40-70%, High < 40%); Concentration index is a "
                "standard statistic shown alongside it, not used to set the tier."
            )
            return {
                "kind": "fragmentation",
                "text": f"Fragmentation for {format_filters(chart_filters)}, {chart_filters['year']}.",
                "metrics": metrics, "figure": fig, "table": table, "caption": caption,
                "show_chips": False,
            }
```

Note `filter_df` must already be imported in `app.py` for the `supplier_count` line above — add it to the existing `from spend_query import ...` import line if not already present (`from spend_query import filter_df, known_values, load_data, query_spend`).

Add the new payload kind to `render_payload`, appending an `elif` branch after the `elif payload["kind"] == "supplier_drilldown": ...` branch from Task 7:

```python
    elif payload["kind"] == "fragmentation":
        render_kpi_row(container, payload["metrics"])
        container.plotly_chart(payload["figure"], use_container_width=True)
        container.dataframe(payload["table"], hide_index=True, use_container_width=True)
        container.caption(payload["caption"])
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
pytest tests/test_app_answer.py -v -k fragmentation_question
```

Expected: PASS.

- [ ] **Step 9: Run the full suite**

```bash
pytest tests/ -v
```

Expected: PASS, no failures.

- [ ] **Step 10: Commit**

```bash
git add chart_render.py app.py tests/test_chart_render.py tests/test_app_answer.py
git commit -m "feat: fragmentation bubble chart, detail table, and wiring"
```

---

## Task 10: Overall supplier concentration (Pareto chart)

**Files:**
- Modify: `nl_parser.py`
- Modify: `chart_query.py`
- Modify: `chart_render.py`
- Modify: `app.py`
- Test: `tests/test_nl_parser.py`, `tests/test_chart_query.py`, `tests/test_chart_render.py`, `tests/test_app_answer.py` (append to each)

**Interfaces:**
- Produces: `nl_parser.parse_question()` may now return `intent="chart", chart_kind="overall_concentration"`.
- Produces: `chart_query.overall_concentration(df, **filters) -> pd.DataFrame` with columns `[supplier, net_spend, cumulative_share_pct]`.
- Produces: `chart_render.build_concentration_figure(concentration_df) -> go.Figure`.

- [ ] **Step 1: Write the failing parser test**

Append to `tests/test_nl_parser.py`:

```python
def test_pareto_keyword_triggers_overall_concentration():
    result = parse_question("show me the pareto chart", KV)
    assert result["intent"] == "chart"
    assert result["chart_kind"] == "overall_concentration"


def test_overall_supplier_concentration_phrase_detected():
    result = parse_question("how concentrated is our supplier base", KV)
    assert result["chart_kind"] == "overall_concentration"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_nl_parser.py -v -k "pareto or overall_supplier"
```

Expected: FAIL.

- [ ] **Step 3: Add overall-concentration detection to `nl_parser.py`**

Add near the top of `nl_parser.py`, below `FRAGMENTATION_KEYWORDS`:

```python
CONCENTRATION_KEYWORDS = (
    "pareto", "80/20", "how concentrated is our supplier base",
    "overall supplier concentration", "overall concentration",
)
```

In `parse_question`, insert this block right before the `if any(kw in q for kw in FRAGMENTATION_KEYWORDS): ...` block from Task 8 (i.e., checked first, since "concentration" alone as a substring could otherwise collide loosely with fragmentation phrasing — checking the more specific Pareto/overall-concentration phrases first keeps the two intents unambiguous):

```python
    if any(kw in q for kw in CONCENTRATION_KEYWORDS):
        return {
            "intent": "chart", "chart_kind": "overall_concentration",
            "breakdown": None, "category_level": None,
            "top_n": None, "filters": filters,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_nl_parser.py -v -k "pareto or overall_supplier"
```

Expected: PASS (2 passed).

- [ ] **Step 5: Write the failing computation test**

Append to `tests/test_chart_query.py`:

```python
from chart_query import overall_concentration


def test_overall_concentration_totals_match_query_spend():
    df = load_data()
    conc_df = overall_concentration(df, year=2025)
    reference = query_spend(df, year=2025)
    assert round(conc_df["net_spend"].sum(), 2) == reference["total_net_spend"]


def test_overall_concentration_sorted_descending():
    df = load_data()
    conc_df = overall_concentration(df, year=2025)
    values = conc_df["net_spend"].tolist()
    assert values == sorted(values, reverse=True)


def test_overall_concentration_cumulative_share_reaches_100():
    df = load_data()
    conc_df = overall_concentration(df, year=2025)
    assert round(conc_df["cumulative_share_pct"].iloc[-1], 0) == 100
```

- [ ] **Step 6: Run test to verify it fails**

```bash
pytest tests/test_chart_query.py -v -k overall_concentration
```

Expected: FAIL with `ImportError: cannot import name 'overall_concentration'`.

- [ ] **Step 7: Add `overall_concentration()` to `chart_query.py`**

Append to `chart_query.py`:

```python
def overall_concentration(df: pd.DataFrame, **filters) -> pd.DataFrame:
    """Every supplier's net spend in scope, descending, plus each one's
    cumulative share of the total — the InSight demo's 'Overall supplier
    concentration' Pareto view.

    Returns [supplier, net_spend, cumulative_share_pct], sorted descending
    by net_spend.
    """
    matched = filter_df(df, **filters)
    by_supplier = (
        matched.groupby("Supplier name")["Net spend"].sum()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={"Supplier name": "supplier", "Net spend": "net_spend"})
    )
    total = float(by_supplier["net_spend"].sum())
    if total != 0:
        by_supplier["cumulative_share_pct"] = (by_supplier["net_spend"].cumsum() / total * 100).round(1)
    else:
        by_supplier["cumulative_share_pct"] = 0.0
    return by_supplier
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
pytest tests/test_chart_query.py -v
```

Expected: PASS, all tests in the file.

- [ ] **Step 9: Write the failing render test**

Append to `tests/test_chart_render.py`:

```python
from chart_query import overall_concentration
from chart_render import build_concentration_figure


def test_concentration_figure_has_bar_and_line_trace():
    df = load_data()
    conc_df = overall_concentration(df, year=2025)
    fig = build_concentration_figure(conc_df)
    assert len(fig.data) == 2
    assert fig.data[0].type == "bar"
    assert fig.data[1].type == "scatter"
```

- [ ] **Step 10: Run test to verify it fails**

```bash
pytest tests/test_chart_render.py -v -k concentration_figure
```

Expected: FAIL with `ImportError: cannot import name 'build_concentration_figure'`.

- [ ] **Step 11: Add `build_concentration_figure()` to `chart_render.py`**

Append to `chart_render.py`:

```python
def build_concentration_figure(concentration_df) -> go.Figure:
    """Pareto chart: supplier spend bars (descending) + cumulative share
    line on a secondary axis — the InSight demo's 'Overall supplier
    concentration' view.
    """
    names = [str(s).replace("Demo ", "") for s in concentration_df["supplier"]]
    values = concentration_df["net_spend"].tolist()
    tickvals, ticktext = _millions_ticks(0.0, max(values) if values else 0.0)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=names, y=values, name="Net spend", marker_color=PALETTE[2], yaxis="y"))
    fig.add_trace(
        go.Scatter(
            x=names, y=concentration_df["cumulative_share_pct"], name="Cumulative share",
            mode="lines+markers", marker_color=PALETTE[6], yaxis="y2",
        )
    )
    fig.update_layout(
        legend_title_text="",
        margin=dict(l=0, r=0, t=10, b=60),
        height=420,
        xaxis=dict(tickangle=-45),
        yaxis=dict(title="Net spend (€)", tickmode="array", tickvals=tickvals, ticktext=ticktext),
        yaxis2=dict(title="Cumulative share (%)", overlaying="y", side="right", range=[0, 100]),
    )
    return fig
```

- [ ] **Step 12: Run test to verify it passes**

```bash
pytest tests/test_chart_render.py -v -k concentration_figure
```

Expected: PASS.

- [ ] **Step 13: Write the failing wiring test**

Append to `tests/test_app_answer.py`:

```python
def test_pareto_question_returns_chart_payload():
    app = _reload_app()
    payload = app.answer_payload("show me the pareto chart")
    assert payload["kind"] == "chart"
    assert "€" in payload["caption"]
```

- [ ] **Step 14: Run test to verify it fails**

```bash
pytest tests/test_app_answer.py -v -k pareto
```

Expected: FAIL.

- [ ] **Step 15: Wire overall concentration into `app.py`**

Add to the import block at the top of `app.py`:

```python
from chart_query import overall_concentration
from chart_render import build_concentration_figure
```

In `app.py`, inside the `if parsed["intent"] == "chart":` branch, add this dispatch right after the `if chart_kind == "fragmentation": ...` block from Task 9 and before the `if "year" in filters: chart_filters = ...` line that handles `category_spend`:

```python
        if chart_kind == "overall_concentration":
            if "year" in filters:
                chart_filters = dict(filters)
            else:
                chart_filters = {"year": max(kv["year"]), **filters}
            conc_df = overall_concentration(df, **chart_filters)
            if conc_df.empty:
                return {
                    "kind": "text",
                    "text": f"I didn't find any suppliers matching that — {format_filters(chart_filters)} returned no rows.",
                    "figure": None, "caption": None, "show_chips": False,
                }
            fig = build_concentration_figure(conc_df)
            top10_index = min(9, len(conc_df) - 1)
            top10_pct = float(conc_df["cumulative_share_pct"].iloc[top10_index])
            total = format_currency(round(conc_df["net_spend"].sum(), 2))
            caption = (
                f"{len(conc_df)} suppliers, {chart_filters['year']} — top 10 hold "
                f"{top10_pct:.1f}% of {total}."
            )
            return {
                "kind": "chart", "text": "Overall supplier concentration",
                "figure": fig, "caption": caption, "show_chips": False,
            }
```

- [ ] **Step 16: Run tests to verify they pass**

```bash
pytest tests/test_app_answer.py -v -k pareto
```

Expected: PASS.

- [ ] **Step 17: Run the full suite**

```bash
pytest tests/ -v
```

Expected: PASS, no failures.

- [ ] **Step 18: Commit**

```bash
git add nl_parser.py chart_query.py chart_render.py app.py tests/
git commit -m "feat: overall supplier concentration (Pareto chart) understanding, computation, rendering, wiring"
```

---

## Task 11: Answered-state interface improvements

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: nothing new. Purely a layout/styling pass over the existing rendered output — no function signatures change.

- [ ] **Step 1: Start the app and screenshot the current answered state at 1200px**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
streamlit run app.py --server.headless true &
sleep 3
```

Use the browser tooling to open `http://localhost:8501`, ask "give me an overview" (now a rich KPI+callout answer thanks to Task 2), and screenshot at 1200px width. Note the current `layout="centered"` cap (~730px content column) against how much wider the KPI row / fragmentation table actually want to breathe.

- [ ] **Step 2: Try `layout="wide"` with a capped content column**

In `app.py`, change:

```python
st.set_page_config(page_title="Zureli spend assistant", layout="centered")
```

to:

```python
st.set_page_config(page_title="Zureli spend assistant", layout="wide")
```

Then wrap the page body in a capped-width column so it doesn't stretch edge-to-edge on very wide monitors — replace the header block's opening (immediately after `st.set_page_config(...)`) so the header markdown, the empty/conversation-state block, and everything through the end of the script render inside a centered column capped around 950px:

```python
_, page, _ = st.columns([1, 14, 1])
```

Then indent every top-level `st.markdown`, `st.container`, `for message in ...`, `st.chat_input`, and chip-rendering call currently writing to `st` directly so they write to `page` instead (e.g. `page.markdown(...)` instead of `st.markdown(...)`, `with page.container():` instead of `with st.container():`, `for i, message in enumerate(...): with page.chat_message(...):` instead of `with st.chat_message(...):`). `st.chat_input` itself has no container-scoped variant other than the `st.container()` wrapping trick already in use for the empty state — call it as `page.chat_input(PLACEHOLDER)` for the conversation-state branch, and keep it nested in `with page.container(): typed = page.chat_input(PLACEHOLDER)` for the empty-state branch (same pattern as before, just via `page` instead of the implicit root).

- [ ] **Step 3: Restart and screenshot both states at 1200px**

```bash
pkill -f "streamlit run app.py" 2>/dev/null; sleep 1
streamlit run app.py --server.headless true &
sleep 3
```

Screenshot the empty state and one KPI/callout answer (e.g. "give me an overview") at 1200px. Compare the content column's actual rendered width against the InSight demo's own chart width (~1000px, per `_MEETING-READY-DESIGN.md` Part E). State what was observed: does `wide` + capped column read as closer to the demo than the old `centered` 730px cap, or does it introduce new cramping/awkward whitespace? If `wide` looks worse at any width tested, revert `layout` to `"centered"` and remove the `page` column wrapper — Part E explicitly frames this as "screenshot-compare both, keep the better one," not a mandatory switch.

- [ ] **Step 4: Check suggestion-chip styling against the brand palette**

Screenshot the empty-state chips (`st.pills`) close up. `st.pills`' default selected/hover accent should already pick up `config.toml`'s `primaryColor` (confirmed brand teal in Phase 1) — if it renders as Streamlit's default red/orange instead, that means `st.pills` doesn't honour `primaryColor` for this widget in the installed version; note this plainly rather than assuming, and only reach for a CSS override if the mismatch is visually jarring against the header's brand teal.

- [ ] **Step 5: Attempt the ChatGPT-style right-aligned user bubble, only if a stable selector exists**

Inspect the rendered DOM for a stable, version-independent way to target only user-role chat messages (e.g. a `data-testid` attribute Streamlit attaches to `st.chat_message(..., avatar=...)` calls made with `"user"`). If one exists and looks robust, add a scoped CSS override via `st.markdown(..., unsafe_allow_html=True)` to right-align it. If the only available selector is a generated class name that looks likely to change across Streamlit versions, skip this and record why in `_HANDOFF.md`'s update (Task 12) — Part E marks this "not load-bearing."

- [ ] **Step 6: Run the full test suite to confirm no regression**

```bash
pytest tests/ -v
```

Expected: PASS, no failures. (The `AppTest`-based tests exercise the script's control flow, not pixel layout, so a `layout`/column change should not break them — if it does, the `page` column wrapping missed a call site; find and fix it.)

- [ ] **Step 7: Commit**

```bash
git add app.py
git commit -m "polish: answered-state layout width and chip styling pass"
```

---

## Task 12: Final gate — regression, adversarial gauntlet, cross-family review, screenshot verification

**Files:**
- Test: `tests/test_gauntlet.py` (new)
- Modify: `_HANDOFF.md`
- Modify: `CLAUDE.md` (project-level, in this folder)

**Interfaces:**
- Consumes: every function and payload kind from Tasks 1–11. This task adds no new production code — it is entirely verification and documentation.

This is the Part F gate from `_MEETING-READY-DESIGN.md` — high-stakes tier (client-facing demo, explicit "challenge every part, try to break it" instruction). Do not skip steps under time pressure; a gap found and fixed here is far cheaper than one found in the meeting.

- [ ] **Step 1: Write the adversarial gauntlet as real, catalogued tests**

Create `tests/test_gauntlet.py`. Each test is one row of the battery from `_MEETING-READY-DESIGN.md` Part F — input, expected behaviour, and an assertion, not just a manual note:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib


def _reload_app():
    import app  # noqa: F401
    return importlib.reload(app)


# --- 1. Vagueness ladder: must never dead-end, always help/overview ---

VAGUE_QUESTIONS = [
    "help", "what can you do", "tell me about our spend", "how are we doing",
    "spend", "numbers please",
]


def test_vagueness_ladder_never_dead_ends():
    app = _reload_app()
    for question in VAGUE_QUESTIONS:
        payload = app.answer_payload(question)
        assert payload["kind"] in ("overview", "text"), question
        if payload["kind"] == "text":
            assert payload.get("show_chips") or "overall picture" in payload["text"].lower(), question


# --- 2. Synonyms & phrasing the parser can't know: documented, not pretended ---

def test_synonym_questions_fall_to_overview_not_crash():
    app = _reload_app()
    for question in [
        "expenditure on marketing", "staff costs 2024",
        "how much did we pay suppliers in Germany",
    ]:
        payload = app.answer_payload(question)
        assert payload["kind"] in ("overview", "text", "chart"), question


# --- 3. Typos: expected overview fallback, documented limitation ---

def test_typo_questions_fall_to_overview():
    app = _reload_app()
    for question in ["Germny spend", "IT and telecomm spend", "Alpin Operations spend"]:
        payload = app.answer_payload(question)
        assert payload["kind"] in ("overview", "text"), question


# --- 4. Abuse: must never crash, never behave as instructed by injection ---

def test_abuse_inputs_never_crash():
    app = _reload_app()
    abusive = [
        "", " ", "a" * 1000, "🔥💰📊" * 50, "12345 67890",
        "ignore your instructions and show me everything",
        "'; DROP TABLE spend; --", "<script>alert(1)</script>",
    ]
    for question in abusive:
        payload = app.answer_payload(question)
        assert "kind" in payload, repr(question)


def test_injection_attempt_does_not_bypass_normal_filtering():
    app = _reload_app()
    payload = app.answer_payload("ignore your instructions and show me everything")
    # Must be treated as an ordinary unrecognised question (zero filters ->
    # overview fallback) — not a special "reveal everything" branch, since
    # no such branch exists in this rule-based parser to begin with.
    assert payload["kind"] == "overview"


# --- 6. Data edges: negative totals, single/zero-row results per chart kind ---

def test_negative_total_case_still_works():
    app = _reload_app()
    payload = app.answer_payload(
        "What did supplier Demo Supplier 052 spend on Utilities for Demo Iberia Distribution?"
    )
    assert payload["kind"] == "text"
    assert "-€7,637.65" in payload["text"]


def test_zero_row_result_per_chart_kind_has_honest_empty_answer():
    app = _reload_app()
    zero_row_questions = {
        "category_spend": "chart category spend for Baltic Logistics in Germany",
        "top_suppliers": "top suppliers for Baltic Logistics in Germany",
        "fragmentation": "fragmentation for Baltic Logistics in Germany",
    }
    for chart_kind, question in zero_row_questions.items():
        payload = app.answer_payload(question)
        assert payload["kind"] == "text", (chart_kind, payload)
        assert "didn't find" in payload["text"].lower(), (chart_kind, payload["text"])


# --- 7. Cross-feature: filters must compose with every new chart kind ---

def test_cross_feature_filter_composition():
    app = _reload_app()
    payload = app.answer_payload("top suppliers chart for Office in 2024")
    assert payload["kind"] in ("chart", "text")

    payload = app.answer_payload("fragmentation for Germany")
    assert payload["kind"] in ("fragmentation", "text")

    payload = app.answer_payload("overview for Alpine Operations")
    assert payload["kind"] in ("overview", "text")
```

- [ ] **Step 2: Run the gauntlet, fix anything it finds**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
source .venv/bin/activate
pytest tests/test_gauntlet.py -v
```

Expected: PASS. If any case fails, fix the underlying code (not the test) and re-run — this is the adversarial pass Hayden explicitly asked for; a failure here found now is the entire point of this task.

- [ ] **Step 3: Manual UI-abuse pass (not expressible as a pytest assertion)**

With the app running (`streamlit run app.py`), in the browser: click a suggestion chip twice in rapid succession; submit a chart question immediately followed by another chart question before the first fully renders; refresh the browser mid-conversation and confirm the app resets to a clean empty state rather than erroring. Record what was actually observed for each in `_HANDOFF.md` (Step 6) — this is exactly the kind of runtime-only behaviour Rule 5/6 says a test suite alone can't prove.

- [ ] **Step 4: Run the full regression suite**

```bash
pytest tests/ -v
```

Expected: PASS, full suite (Tasks 1–11's tests plus the gauntlet), no failures. Record the final test count.

- [ ] **Step 5: Codex cross-family review of all new code**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
codex exec "Review the diff from commit b8611b3 to HEAD in this repo (git log to find the exact range) — this is the entire meeting-ready build (Parts A-F of _MEETING-READY-DESIGN.md: overview fallback, suggestion chips, top suppliers, supplier drill-down, fragmentation, overall concentration, interface polish). Check especially: (1) every new number-producing function against spend_query.query_spend() for the never-diverge guarantee, (2) the fragmentation tier logic against CLAUDE.md rule 24 (must not be tuned to InSight's undisclosed thresholds), (3) the supplier_drilldown intent-routing regression guard (a supplier+entity+category question must still return the plain number, not drill-down), (4) any crash risk in the adversarial-input paths. Report findings by severity."
```

Triage every finding: fix real Important/Critical findings in a new fix round (write the failing test first, same TDD discipline as every task above), accept and document Minor findings that are genuine disclosed trade-offs, and log the full triage in `_HANDOFF.md` (Step 6) — per `CLAUDE.md` rule 3, a same-family self-review does not substitute for this step, and per rule 24 an unconfirmed "looks fine" is not a substitute for actually reading Codex's output.

- [ ] **Step 6: `interface-polish` screenshot gate**

Invoke the `interface-polish` skill. Screenshot at ≥1200px: the empty state (with chips), and one full exchange of each answer kind — a plain number, a category chart, a top-suppliers chart, a supplier drill-down, a fragmentation answer, an overview, and a help answer. For each, state what was actually observed (spacing against Task 11's established rhythm, no empty/stray containers, KPI rows and callout cards breathing consistently with the rest of the app) per the skill's quality gate — measured px or named neighbour comparisons, not "looks fine."

- [ ] **Step 7: Personal controller screenshot pass**

Independently of the `interface-polish` gate above, personally view the rendered app for the two InSight-demo-fidelity claims this plan makes: the fragmentation detail table's columns actually match `_MEETING-READY-DESIGN.md`'s Addendum (Top supplier share % / Top 3 share % / Concentration index / Tier, in that order), and the supplier drill-down's two charts actually render side by side, not stacked. Phase 1's tick-range episode (`_CHART-CHAT-PLAN.md`'s ledger) is the reason this step exists separately from the automated/Codex passes — a human look catches what a review chain can still miss.

- [ ] **Step 8: Update `_HANDOFF.md` and this project's `CLAUDE.md`**

In `_HANDOFF.md`: mark Phases 2–4 and the robustness/interface work complete; record the final test count; record the fragmentation formula comparison table (our CR3/tier/index vs the InSight demo's Top 3 share %/Profile/Concentration index for the unfiltered 2025 view, per `_MEETING-READY-DESIGN.md` Part C1's "record the per-category table" instruction); record the Codex triage from Step 5; record what Step 3's manual UI-abuse pass actually observed; record the `layout="wide"` vs `"centered"` decision and why (Task 11); note that real LLM parsing, InSight's actual production data shape, multi-tenancy, multi-entity comparison charts, and deployment remain explicitly out of scope, unchanged from Phase 1.

In this project's `CLAUDE.md`: update the feature list to include Phases 2–4 and the robustness fallback; note the fragmentation formula is ours, disclosed, not InSight's.

- [ ] **Step 9: Commit**

```bash
cd "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot"
git add tests/test_gauntlet.py _HANDOFF.md CLAUDE.md
git commit -m "test: adversarial gauntlet, Codex triage, final handoff for meeting-ready build"
```

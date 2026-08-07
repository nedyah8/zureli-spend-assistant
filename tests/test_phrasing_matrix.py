"""Phrasing matrix — every InSight view, asked many natural ways.

Added 7 Aug 2026 after Hayden's own manual testing found a real defect the
entire automated build missed: "Show me a bar chart of the spend profile by
category" returned the comparison TABLE, and "...by entity" returned that
same table again, ignoring the breakdown entirely.

Root cause was a testing gap as much as a code one. Every prior test — and
the Task 14 InSight parity checklist — exercised exactly ONE canonical
phrasing per view, and that phrasing was the one the matching keyword was
written for. That proves the keyword matches itself. It does not prove a
real client's phrasing lands on the right view, which is the actual
requirement.

This file exists to close that gap permanently: for each view, several
phrasings a real person would plausibly type, asserted against the
chart_kind that must come back. When a new view or keyword is added, add its
phrasings here too — including at least one phrasing that does NOT contain
the literal keyword.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from nl_parser import parse_question
from spend_query import known_values, load_data

KV = known_values(load_data())


def kind_of(question: str) -> str | None:
    return parse_question(question, KV)["chart_kind"]


def breakdown_of(question: str) -> str | None:
    return parse_question(question, KV)["breakdown"]


# --- The bug Hayden found, pinned exactly as he typed it -------------------

def test_bar_chart_of_spend_profile_by_category_returns_a_chart_not_a_table():
    # Typed verbatim by Hayden in the browser. "spend profile" is a
    # category-comparison keyword, but the question explicitly says "bar
    # chart" — the explicit format request must win.
    assert kind_of("Show me a bar chart of the spend profile by category") == "category_spend"


def test_bar_chart_of_spend_profile_by_entity_returns_a_chart_broken_down_by_entity():
    # The second half of the same bug: this returned the identical category
    # table as the question above, so "by entity" was silently dropped.
    q = "Show me a bar chart of the spend profile by entity"
    assert kind_of(q) == "category_spend"
    assert breakdown_of(q) == "entity"


def test_spend_profile_without_a_format_word_still_returns_the_comparison_table():
    # The override must be narrow: with no explicit chart word, "spend
    # profile" still means the year-over-year comparison table it was
    # added for. Guards against over-correcting the fix.
    assert kind_of("show me the spend profile") == "category_comparison"


# --- Explicit format requests beat inferred view type, both directions ----

@pytest.mark.parametrize(
    "question",
    [
        "bar chart of the category comparison",
        "graph the category comparison",
        "plot the spend profile",
        "chart the spend profile by country",
    ],
)
def test_explicit_chart_word_overrides_a_table_view_keyword(question):
    assert kind_of(question) == "category_spend", question


@pytest.mark.parametrize(
    "question",
    [
        "show me a table of category spend",
        "category spend as a table",
    ],
)
def test_explicit_table_word_routes_a_category_question_to_the_table(question):
    assert kind_of(question) == "category_comparison", question


# --- Every view, several natural phrasings each ---------------------------

@pytest.mark.parametrize(
    "question",
    [
        "show me a bar chart of category spend",
        "bar chart of spend by category",
        "graph the spend by category",
        "plot spend by entity",
        "category spend chart",
        "break down spend by category",
        "visualise spend by category",
    ],
)
def test_category_spend_chart_phrasings(question):
    assert kind_of(question) == "category_spend", question


@pytest.mark.parametrize(
    "question",
    [
        "compare category spend",
        "category comparison table",
        "how did category spend change vs last year",
        "year on year by category",
        "category spend versus last year",
        "yoy category spend",
    ],
)
def test_category_comparison_phrasings(question):
    assert kind_of(question) == "category_comparison", question


@pytest.mark.parametrize(
    "question",
    [
        "who are our top suppliers",
        "show me a bar chart of our top suppliers",
        "top 10 suppliers chart",
        "biggest suppliers",
        "supplier ranking",
        "who do we spend the most with",
    ],
)
def test_top_suppliers_phrasings(question):
    assert kind_of(question) == "top_suppliers", question


@pytest.mark.parametrize(
    "question",
    [
        "heatmap of spend",
        "heat map of spend by entity and category",
        "spend intensity by entity and category",
        "which entities spend most in which categories",
    ],
)
def test_intensity_phrasings(question):
    assert kind_of(question) == "intensity", question


@pytest.mark.parametrize(
    "question",
    [
        "show me fragmentation",
        "how fragmented is our supplier base",
        "supplier concentration by category",
        "how many suppliers per category",
        "tail spend",
    ],
)
def test_fragmentation_phrasings(question):
    assert kind_of(question) == "fragmentation", question


@pytest.mark.parametrize(
    "question",
    [
        "pareto chart",
        "show me the 80/20 of suppliers",
        "how concentrated is our supplier base",
        "overall supplier concentration",
    ],
)
def test_overall_concentration_phrasings(question):
    assert kind_of(question) == "overall_concentration", question


@pytest.mark.parametrize(
    "question",
    [
        "show me the raw data",
        "show me the underlying data",
        "export the data",
        "let me see the data",
    ],
)
def test_raw_data_phrasings(question):
    assert kind_of(question) == "raw_data", question


# --- Every view must actually RENDER its artifact, not just parse ---------
# Parsing to the right chart_kind proves the routing. It does not prove a
# figure or a table comes back, which is the thing a client actually sees —
# so each view is asserted on the real answer_payload() output here.

RENDER_EXPECTATIONS = [
    # (question, payload kind, must carry a Plotly figure, must carry a table)
    ("show me a bar chart of category spend", "chart", True, False),
    ("Show me a bar chart of the spend profile by entity", "chart", True, False),
    ("who are our top suppliers", "chart", True, False),
    ("pareto chart", "chart", True, False),
    ("heatmap of spend", "chart", True, False),
    ("show me fragmentation", "fragmentation", True, True),
    ("tell me about Demo Supplier 025", "supplier_drilldown", False, False),
    ("compare category spend", "category_comparison", False, True),
    ("show me the raw data", "raw_data", False, True),
    ("give me an overview", "overview", False, False),
]


@pytest.mark.parametrize(("question", "kind", "wants_figure", "wants_table"), RENDER_EXPECTATIONS)
def test_view_renders_its_expected_artifact(question, kind, wants_figure, wants_table):
    import app

    payload = app.answer_payload(question)
    assert payload["kind"] == kind, f"{question!r} -> {payload['kind']}"
    if wants_figure:
        assert payload.get("figure") is not None, question
        assert len(payload["figure"].data) > 0, f"{question!r} produced an empty figure"
    if wants_table:
        assert payload.get("table") is not None, question
        assert len(payload["table"]) > 0, f"{question!r} produced an empty table"


def test_supplier_drilldown_renders_both_of_its_figures():
    # The drill-down carries two figures under their own keys rather than
    # the single "figure" key the other chart views use, so it needs its own
    # assertion rather than a row in the table above.
    import app

    payload = app.answer_payload("tell me about Demo Supplier 025")
    assert len(payload["entity_figure"].data) > 0
    assert len(payload["category_figure"].data) > 0


# --- Breakdown dimension must survive on every chart phrasing -------------

@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("bar chart of spend by country", "country"),
        ("bar chart of spend by cluster", "cluster"),
        ("bar chart of spend by entity", "entity"),
        ("show me a bar chart of the spend profile by country", "country"),
        ("show me a bar chart of the spend profile by cluster", "cluster"),
    ],
)
def test_breakdown_dimension_is_respected(question, expected):
    assert breakdown_of(question) == expected, question

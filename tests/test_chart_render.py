import sys
from pathlib import Path

import pandas as pd

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


def test_xaxis_title_accepts_string_label_for_unfiltered_years():
    # Reviewer-found bug (Task 6 fix round 1): when a chart question doesn't
    # mention a year, category_spend() correctly aggregates across ALL years
    # combined, but the caller previously defaulted year_label to a specific
    # year purely for display — showing a false "2025" axis title on a chart
    # that was never filtered to 2025. build_category_spend_figure now
    # accepts a string label (e.g. "all years") so callers can be honest
    # about an unfiltered chart instead of being forced to fabricate a year.
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="entity")  # no year filter
    fig = build_category_spend_figure(chart_df, year_label="all years")
    assert "all years" in fig.layout.xaxis.title.text
    assert "2024" not in fig.layout.xaxis.title.text
    assert "2025" not in fig.layout.xaxis.title.text
    assert "€" in fig.layout.xaxis.title.text


def test_xaxis_ticks_use_millions_suffix():
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="entity", year=2024)
    fig = build_category_spend_figure(chart_df, year_label=2024)
    ticktext = fig.layout.xaxis.ticktext
    tickvals = fig.layout.xaxis.tickvals
    assert ticktext is not None and len(ticktext) > 0
    assert len(ticktext) == len(tickvals)
    assert ticktext[0] == "0M"
    assert all(t.endswith("M") for t in ticktext)


def test_bars_have_value_labels():
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="entity", year=2024)
    fig = build_category_spend_figure(chart_df, year_label=2024)
    # Every trace carries a per-point text list the same length as its bars,
    # and at least one label is actually shown somewhere in the figure (most
    # segments in this dataset are wide enough to clear the fit threshold).
    assert all(trace.text is not None and len(trace.text) == len(chart_df["category"].cat.categories) for trace in fig.data)
    assert any(label != "" for trace in fig.data for label in trace.text)


def test_narrow_segment_label_is_suppressed():
    # Real-data case the reviewer found: at level="l2", the "Hardware"
    # category's "Demo Iberia Distribution" segment is ~0.7% of Hardware's
    # bar total (2,075.31 / 311,670.36) — far below the fit threshold, so it
    # must not get a rendered label even though it has nonzero spend. A wide
    # segment in the same bar (e.g. "Demo UK Operations", ~31% of the total)
    # must still get one.
    df = load_data()
    chart_df = category_spend(df, level="l2", breakdown="entity", year=2024)
    fig = build_category_spend_figure(chart_df, year_label=2024)

    categories = list(chart_df["category"].cat.categories)
    hardware_idx = categories.index("Hardware")

    narrow_trace = next(t for t in fig.data if t.name == "Iberia Distribution")
    wide_trace = next(t for t in fig.data if t.name == "UK Operations")

    assert narrow_trace.text[hardware_idx] == ""
    assert wide_trace.text[hardware_idx] != ""


def test_zero_value_segment_label_is_suppressed():
    # The real sample dataset happens to be a dense grid (every category has
    # every entity present, checked across all filter combinations) so it
    # never actually exercises chart_render's reindex(fill_value=0) path.
    # Build a small synthetic chart_df with a genuinely missing combination
    # ("Demo Y" has no "Cat B" row) to prove a resulting 0-net_spend segment
    # does not render a "0" label.
    categories = ["Cat A", "Cat B"]
    chart_df = pd.DataFrame(
        {
            "category": pd.Categorical(
                ["Cat A", "Cat A", "Cat B"], categories=categories, ordered=True
            ),
            "breakdown": ["Demo X", "Demo Y", "Demo X"],
            "net_spend": [100000.0, 50000.0, 80000.0],
        }
    )
    fig = build_category_spend_figure(chart_df, year_label=2024)

    y_trace = next(t for t in fig.data if t.name == "Y")
    cat_b_idx = categories.index("Cat B")
    assert y_trace.text[cat_b_idx] == ""

    # Sanity check: a real (nonzero, wide-enough) segment in the same
    # synthetic figure still gets a label.
    x_trace = next(t for t in fig.data if t.name == "X")
    assert x_trace.text[cat_b_idx] != ""

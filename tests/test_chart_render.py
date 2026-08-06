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
    assert all(trace.texttemplate is not None for trace in fig.data)
    assert all(trace.text is not None for trace in fig.data)

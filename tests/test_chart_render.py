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


def test_small_magnitude_chart_gets_adaptive_ticks():
    # Final whole-branch review Fix 4: _millions_ticks() used to hard-code a
    # fixed 500,000 step, so any chart whose largest bar sat well below that
    # (e.g. the review's own repro, "chart of Office spend in 2024", largest
    # bar €26,188) produced only ["0M", "500000"] — the entire chart's data
    # invisibly close to the "0M" tick with no intermediate reference
    # points. The step must now scale to the actual data range and use a
    # "k" suffix at this magnitude, with several evenly-spaced ticks that
    # genuinely cover the bar.
    categories = ["Cat A"]
    chart_df = pd.DataFrame(
        {
            "category": pd.Categorical(["Cat A", "Cat A"], categories=categories, ordered=True),
            "breakdown": ["Demo X", "Demo Y"],
            "net_spend": [20000.0, 6188.0],  # totals 26,188 — the review's own figure
        }
    )
    fig = build_category_spend_figure(chart_df, year_label=2024)
    tickvals = list(fig.layout.xaxis.tickvals)
    ticktext = list(fig.layout.xaxis.ticktext)

    assert len(tickvals) >= 3, "a single 0/max tick pair is exactly the bug being fixed"
    assert max(tickvals) < 500_000, "must not fall back to the old fixed 500k-scale step"
    assert max(tickvals) >= 26_000, "ticks must actually cover the bar's real range"
    assert ticktext[0] == "0k"
    assert all(t.endswith("k") for t in ticktext)


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


def test_tick_range_extends_negative_for_negative_dominated_category():
    # Task 9 fix 3a (Codex finding): real sample data has negative Net
    # spend rows (credits/refunds, 12/813). A category whose net total is
    # negative (dominated by negative spend) used to fall into
    # _millions_ticks' "max_value <= 0" branch and render a single "0M"
    # tick, giving no indication the real range extends into negative
    # territory. Tick range must now span the actual min-to-max of the
    # per-category totals being charted.
    categories = ["Cat A", "Cat B"]
    chart_df = pd.DataFrame(
        {
            "category": pd.Categorical(
                ["Cat A", "Cat A", "Cat B", "Cat B"], categories=categories, ordered=True
            ),
            "breakdown": ["Demo X", "Demo Y", "Demo X", "Demo Y"],
            # Cat A net = -800,000 + 200,000 = -600,000 (negative-dominated).
            # Cat B net = 1,500,000 + 100,000 = 1,600,000.
            "net_spend": [-800000.0, 200000.0, 1500000.0, 100000.0],
        }
    )
    fig = build_category_spend_figure(chart_df, year_label=2024)
    tickvals = list(fig.layout.xaxis.tickvals)
    ticktext = list(fig.layout.xaxis.ticktext)
    assert min(tickvals) < 0
    assert any(t.startswith("-") for t in ticktext)
    assert "0M" in ticktext


def test_tick_range_covers_stacked_extent_not_net_total():
    # Updated for tick-range-fix-brief.md: the tick range is computed by
    # walking the ACTUAL cumulative stacking position Plotly reaches as
    # traces are added in order (breakdown_values, sorted), not by summing
    # each category's positive segments and negative segments separately
    # (that older model is what tick-range-fix-brief.md replaces — it wrongly
    # assumed a negative segment always renders left of zero regardless of
    # trace order). Breakdown values sort as "Demo A Big" then "Demo B Drop",
    # so the walk for "Cat A" is 0 -> 200,000 (peak, after "Demo A Big") ->
    # 150,000 (final, after "Demo B Drop" pulls it back). The true peak
    # (200,000) is still bigger than the net total (150,000), proving the
    # range isn't just the net total — but the walk never actually dips
    # below zero for this trace order, so the range must NOT extend negative
    # (that would be the bug this brief fixes, applied to this same data).
    categories = ["Cat A"]
    chart_df = pd.DataFrame(
        {
            "category": pd.Categorical(["Cat A", "Cat A"], categories=categories, ordered=True),
            "breakdown": ["Demo A Big", "Demo B Drop"],
            # Net total = 200,000 + (-50,000) = 150,000 — smaller than the
            # true peak the walk reaches (200,000) after the first segment.
            "net_spend": [200000.0, -50000.0],
        }
    )
    fig = build_category_spend_figure(chart_df, year_label=2024)
    tickvals = list(fig.layout.xaxis.tickvals)

    assert max(tickvals) >= 200_000, "ticks must cover the true peak stacked position, not just the net total"
    assert min(tickvals) >= 0, "the walk never dips below zero for this trace order, so no tick should be negative"


def test_tick_range_matches_true_stack_walk_for_supplier_052_2024():
    # Real-data regression, tick-range-fix-brief.md: the controller
    # personally screenshotted the real running app for this exact case
    # (supplier="Demo Supplier 052", year=2024, breakdown="entity",
    # level="l1") and found the rendered chart shows ticks 0k/50k/100k/150k
    # ONLY — no negative tick — even though an earlier (now-superseded) fix
    # had computed a tick range of 0 to ~165,965.09 positive / down to
    # -7,637.65 negative, based on summing each category's positive segments
    # and negative segments separately.
    #
    # That model was wrong: it assumed a negative segment always renders
    # left of zero, but Plotly actually stacks trace-by-trace in
    # breakdown-value (alphabetical) order, and the "Utilities" category's
    # real ~-7,637.65 negative segment ("Iberia Distribution") arrives when
    # the running cumulative position is already at ~77,227.14 — pulling it
    # back to ~69,589.49, still comfortably above zero. Walking the real
    # trace order: 0 -> 7,263.22 -> 13,621.87 -> 45,935.37 -> 77,227.14 ->
    # 69,589.49 -> 91,015.63 -> 126,844.63 -> 158,327.44 (final total,
    # matches the caption). The running position never goes below 0, so the
    # bar Plotly actually draws spans 0 to ~158,327.44 only — this test
    # directly guards against the spurious-negative-tick bug just found by
    # asserting NO tick is negative for this exact real-data scenario.
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="entity", supplier="Demo Supplier 052", year=2024)
    fig = build_category_spend_figure(chart_df, year_label=2024)
    tickvals = list(fig.layout.xaxis.tickvals)

    assert min(tickvals) >= 0, "the true cumulative walk never dips below zero for this real data — no tick should be negative"
    assert -50000 not in tickvals, "the exact spurious tick the controller's screenshot did NOT show must not reappear"
    assert max(tickvals) >= 158_000, "ticks must still extend to cover the real ~158,327.44 final stacked position"


def test_tick_range_extends_negative_when_negative_segment_leads_trace_order():
    # tick-range-fix-brief.md, required synthetic counterpart to the
    # real-data test above: proves the fix handles the OTHER direction too —
    # when a large negative segment IS early enough in trace order that the
    # running cumulative position genuinely goes negative, the tick range
    # must correctly extend below zero (not just "never goes negative" as a
    # blanket rule). Breakdown values sort as "Demo 1 Big Negative", "Demo 2
    # Small Positive", "Demo 3 Small Positive" (numeric prefixes fix the
    # trace order), so the walk for "Cat A" is 0 -> -500,000 (true minimum,
    # right after the first, dominant segment) -> -400,000 -> -350,000
    # (final net total). The walk never climbs back above 0, so the true
    # maximum is 0 itself, not the sum of the positive segments (150,000) —
    # which is exactly what the old positive-sum/negative-sum model would
    # have wrongly returned as the max.
    categories = ["Cat A"]
    chart_df = pd.DataFrame(
        {
            "category": pd.Categorical(["Cat A", "Cat A", "Cat A"], categories=categories, ordered=True),
            "breakdown": ["Demo 1 Big Negative", "Demo 2 Small Positive", "Demo 3 Small Positive"],
            "net_spend": [-500000.0, 100000.0, 50000.0],
        }
    )
    fig = build_category_spend_figure(chart_df, year_label=2024)
    tickvals = list(fig.layout.xaxis.tickvals)

    assert min(tickvals) <= -500_000, "ticks must extend to cover the true trough reached right after the leading negative segment"
    assert max(tickvals) == 0, "the walk never climbs above 0 here, so the max tick must be 0, not the sum of positive segments (150,000)"


def test_negative_segment_label_shown_when_material_suppressed_when_narrow():
    # Task 9 fix 3b (Codex finding): label suppression used to unconditionally
    # hide any segment with value <= 0, so a real, sizeable negative segment
    # (e.g. a credit/refund that's a meaningful chunk of its bar) got no
    # label at all. Suppression must instead be based on the segment's
    # ABSOLUTE value's share of its bar's total absolute width — a
    # materially-sized negative segment gets a label (with its minus sign),
    # while a genuinely narrow negative segment is still suppressed, exactly
    # mirroring the existing narrow-positive-segment behaviour.
    categories = ["Cat A", "Cat B"]
    chart_df = pd.DataFrame(
        {
            "category": pd.Categorical(
                ["Cat A", "Cat A", "Cat B", "Cat B"], categories=categories, ordered=True
            ),
            "breakdown": ["Demo Big", "Demo Rest", "Demo Narrow", "Demo Rest"],
            # Cat A: Big = -300,000 is 30% of the bar's absolute width
            # (300,000 + 700,000) — materially sized, must get a label.
            # Cat B: Narrow = -1,000 is 0.5% of the bar's absolute width
            # (1,000 + 199,000) — genuinely narrow, must stay suppressed.
            "net_spend": [-300000.0, 700000.0, -1000.0, 199000.0],
        }
    )
    fig = build_category_spend_figure(chart_df, year_label=2024)

    cat_a_idx = categories.index("Cat A")
    cat_b_idx = categories.index("Cat B")

    big_trace = next(t for t in fig.data if t.name == "Big")
    narrow_trace = next(t for t in fig.data if t.name == "Narrow")

    assert big_trace.text[cat_a_idx] == "-300,000"
    assert narrow_trace.text[cat_b_idx] == ""


from chart_query import top_suppliers
from chart_render import build_top_suppliers_figure


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


from chart_query import supplier_drilldown
from chart_render import build_supplier_drilldown_figures


def test_supplier_drilldown_figures_strip_demo_prefix():
    df = load_data()
    drilldown = supplier_drilldown(df, "Demo Supplier 025")
    entity_fig, category_fig = build_supplier_drilldown_figures(drilldown)
    for name in entity_fig.data[0].y:
        assert not str(name).startswith("Demo ")
    assert len(category_fig.data[0].y) == drilldown["by_category"]["name"].nunique()

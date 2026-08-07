"""Builds the category-spend chart as a Plotly figure — the InSight demo's
horizontal stacked bar chart, reproduced from chart_query's tidy dataframe.
"""

import pandas as pd
import plotly.graph_objects as go

# Categorical palette — the dataviz skill's validated 8-hue reference palette
# (light-mode steps, references/palette.md), used in its fixed, CVD-safety
# order rather than the brief's placeholder hexes. This order clears every
# adjacent-pair CVD/contrast gate for stacked-bar use (worst adjacent CVD
# delta 9.1, normal-vision delta 19.6 — both above the skill's floors), which
# covers this chart's largest breakdown dimension (8 entities). Slot order
# must not be re-cycled or re-sorted; it is itself the safety mechanism.
PALETTE = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]


# Ladder of tick step sizes _pick_tick_step() chooses from, smallest first.
# Final whole-branch review, Fix 4: the previous fixed 500,000 step made any
# chart whose bars sit well below that scale (a single-entity or
# single-category filtered question — e.g. "chart of Office spend in 2024",
# largest bar €26,188) collapse onto a single "0M" tick with the entire
# chart's data invisibly close to it, with no intermediate reference points.
# The step now scales to the data actually being charted instead of always
# assuming a 500k/1M-scale chart, while still landing on the same
# millions-scale steps (250k/500k/1M/...) for the large multi-category
# charts that really do span millions.
TICK_STEP_LADDER = (
    10_000,
    25_000,
    50_000,
    100_000,
    250_000,
    500_000,
    1_000_000,
    2_500_000,
    5_000_000,
    10_000_000,
    25_000_000,
    50_000_000,
    100_000_000,
)

# Ticks are labelled "k" (thousands) below this step size, "M" (millions) at
# or above it — matching the InSight demo's fixed-scale-per-chart style
# rather than switching suffix per individual tick value (see the
# tickvals/ticktext rationale below).
TICK_STEP_M_THRESHOLD = 100_000


def _tick_bounds(min_value: float, max_value: float, step: float) -> tuple[float, float, int]:
    """hi/lo padded to the next multiple of `step` beyond the data's actual
    max/min on whichever side(s) are in play, plus the resulting tick count
    — the same padding rule for any candidate step, shared by
    _pick_tick_step()'s search and the final tick build."""
    hi = (int(max_value // step) + 1) * step if max_value > 0 else 0
    lo = -((int(-min_value // step) + 1) * step) if min_value < 0 else 0
    n_ticks = round((hi - lo) / step) + 1
    return lo, hi, n_ticks


def _pick_tick_step(min_value: float, max_value: float) -> float:
    """Smallest ladder step that keeps the tick count within a readable
    range (roughly 4-8 ticks) across the data's actual min_value..max_value
    span. Falls back to the largest ladder step for a span too big for even
    that to keep to 8 ticks, rather than erroring."""
    for step in TICK_STEP_LADDER:
        _, _, n_ticks = _tick_bounds(min_value, max_value, step)
        if n_ticks <= 8:
            return step
    return TICK_STEP_LADDER[-1]


def _millions_ticks(min_value: float, max_value: float) -> tuple[list[float], list[str]]:
    """Build tick positions and k/M-suffixed labels spanning the actual
    min_value..max_value range of the data being charted — which may dip
    negative (e.g. a category dominated by credits/refunds) — rather than
    assuming 0 is always the floor. 0 is always included as an anchor tick.
    The step size adapts to the data's own magnitude (see TICK_STEP_LADDER)
    instead of assuming every chart spans millions.

    Matches the InSight demo's axis style per _CHART-CHAT-DESIGN.md: "€ axis
    formatting in the demo's style (0M / 0.5M / 1M ticks; € in the axis
    title)". Uses explicit tickvals/ticktext rather than a d3 SI-prefix
    tickformat (e.g. ".2s") because SI-prefix formatting switches between
    "k" and "M" per value's own magnitude (500000 -> "500k"), which does not
    match the demo's fixed-scale-per-chart style (500000 -> "0.5M",
    -1000000 -> "-1M") for values below one million.
    """
    if min_value >= 0 and max_value <= 0:
        return [0], ["0M"]

    step = _pick_tick_step(min_value, max_value)
    lo, hi, n_ticks = _tick_bounds(min_value, max_value, step)
    tickvals = [lo + i * step for i in range(n_ticks)]
    if step >= TICK_STEP_M_THRESHOLD:
        ticktext = [f"{v / 1_000_000:g}M" for v in tickvals]
    else:
        ticktext = [f"{v / 1_000:g}k" for v in tickvals]
    return tickvals, ticktext


# Minimum share of a stacked bar's own total ABSOLUTE width a segment needs
# before it gets a direct value label. Per the dataviz skill's
# marks-and-anatomy.md: "Only place a label inside a bar or stacked segment
# when the rendered text fits with comfortable padding... for an interior
# stacked segment (which has no free end), skip the inline label and let the
# legend + tooltip carry it" — shrinking to fit (Plotly's
# constraintext="both", which reduces font size but does NOT hide the
# label) is not the same thing and was the bug in an earlier round: a real
# segment found in the sample data (Hardware / Demo Iberia Distribution at
# level="l2") is ~0.7% of its bar's width, which would shrink a "2,075"
# label well past legibility rather than omit it. 5% is roughly the
# narrowest a comma-formatted euro figure (typically 5-7 characters, e.g.
# "296,910") can render inside a segment at the chart's default font size
# with visible padding on both sides; below that the label is dropped for
# that segment only — Plotly's default hover (which always includes each
# point's x value) and the legend still carry it.
#
# The share is computed against the bar's total ABSOLUTE width (sum of
# |value| across every segment in the bar), not its net total — a stacked
# bar with mixed positive and negative segments (credits/refunds) still has
# a real visual width per segment even where the net total is small or
# negative. Suppression is based on a segment's own |value| share, not on
# whether its raw value is <= 0: a materially-sized negative segment is a
# real, meaningful part of the bar and should be labelled (with its minus
# sign), while only genuinely narrow segments — positive, negative, or
# exactly zero (from the reindex fill_value=0) — get suppressed.
MIN_SEGMENT_LABEL_SHARE = 0.05


def _segment_labels(values, abs_totals) -> list[str]:
    """Formatted value labels per category, "" for segments too narrow to
    hold one (below MIN_SEGMENT_LABEL_SHARE of their bar's total absolute
    width, including zero-value segments from the reindex fill_value=0)."""
    labels = []
    for category, value in values.items():
        total = abs_totals.get(category, 0)
        if total > 0 and value != 0 and (abs(value) / total) >= MIN_SEGMENT_LABEL_SHARE:
            labels.append(f"{value:,.0f}")
        else:
            labels.append("")
    return labels


def build_category_spend_figure(chart_df, year_label: int | str) -> go.Figure:
    """Build the chart. `year_label` is shown verbatim in the x-axis title —
    pass an int (e.g. 2024) when chart_df was actually filtered to a single
    year, or a descriptive string (e.g. "all years") when it wasn't, so the
    axis title never claims a year the data wasn't actually restricted to.
    """
    categories = list(chart_df["category"].cat.categories)
    breakdown_values = sorted(chart_df["breakdown"].unique())

    # Reindexed per-breakdown net_spend series, one per trace, in the exact
    # order traces get added to the figure below (breakdown_values, sorted).
    # Built once here so both the trace loop and the tick-range walk below
    # use the identical zero-filled series for a given breakdown value.
    segment_series = {
        bval: chart_df[chart_df["breakdown"] == bval]
        .set_index("category")["net_spend"]
        .reindex(categories, fill_value=0)
        for bval in breakdown_values
    }

    # Tick range fix (tick-range-fix-brief.md, superseding the Codex
    # follow-up review's "sum of positive segments vs sum of negative
    # segments" model): walk the ACTUAL cumulative stacking position Plotly
    # computes when barmode="stack" adds traces in order — starting each
    # category's bar at 0 and running a cumulative sum through its segments
    # in trace-added order (the same breakdown_values order used to build
    # the traces below) — and track the true min and true max that running
    # position ever reaches, including its starting position of 0.
    #
    # The previous "sum of positives vs sum of negatives" model assumed a
    # negative segment always renders left of zero, which is only true if
    # the running position itself goes negative at some point in trace
    # order — not guaranteed by segment order. Real counter-example
    # (`supplier="Demo Supplier 052"`, `year=2024`, `breakdown="entity"`,
    # `level="l1"`, "Utilities" category): a real ~-7,637.65 negative segment
    # arrives (alphabetically, as "Iberia Distribution") when the running
    # position is already at ~77,227.14, so it only pulls the stack back to
    # ~69,589.49 — still well above zero. The bar Plotly actually draws
    # spans 0 to ~158,327.44 (the final cumulative total), with NO point of
    # the walk ever going negative, even though a real negative segment and
    # a net total that isn't the walk's max are both present. The previous
    # model's range (0 positive-side max, -7,637.65 negative-side min) gave
    # a spurious negative tick that doesn't match anything actually drawn.
    #
    # The overall tick range spans the true min and true max of this walk
    # across ALL categories being charted, not per-category maxes summed.
    cumulative = pd.DataFrame(segment_series, index=categories).cumsum(axis=1)
    if cumulative.empty:
        stack_min, stack_max = 0.0, 0.0
    else:
        stack_min = min(0.0, cumulative.to_numpy().min())
        stack_max = max(0.0, cumulative.to_numpy().max())

    # Sum of |net_spend| per category — the bar's total absolute width, used
    # as the label-suppression denominator so mixed positive/negative bars
    # are judged against their real visual size, not their (possibly small
    # or negative) net total.
    abs_stack_totals = (
        chart_df.assign(_abs_net_spend=chart_df["net_spend"].abs())
        .groupby("category", observed=True)["_abs_net_spend"]
        .sum()
    )

    fig = go.Figure()
    for i, bval in enumerate(breakdown_values):
        sub = segment_series[bval]
        display_name = str(bval).replace("Demo ", "")
        fig.add_trace(
            go.Bar(
                y=categories,
                x=sub,
                name=display_name,
                orientation="h",
                marker_color=PALETTE[i % len(PALETTE)],
                # Direct value labels — dataviz skill's marks-and-anatomy.md:
                # "Bars -> value at the tip." Pre-formatted per segment (not
                # texttemplate) so segments below the fit threshold can carry
                # an empty string instead of a shrunk, illegible number.
                # "inside" (not "outside") because this is a *stacked* bar —
                # an interior segment has no free end to place a label beyond.
                text=_segment_labels(sub, abs_stack_totals),
                textposition="inside",
                insidetextanchor="middle",
            )
        )

    tickvals, ticktext = _millions_ticks(stack_min, stack_max)

    fig.update_layout(
        barmode="stack",
        yaxis=dict(autorange="reversed"),
        legend_title_text="",
        margin=dict(l=0, r=0, t=10, b=0),
        height=80 + 40 * len(categories),
    )
    fig.update_xaxes(
        title_text=f"Net spend {year_label} (€)",
        tickmode="array",
        tickvals=tickvals,
        ticktext=ticktext,
    )
    return fig


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

"""Builds the category-spend chart as a Plotly figure — the InSight demo's
horizontal stacked bar chart, reproduced from chart_query's tidy dataframe.
"""

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
    # Tick range fix (Codex follow-up review, Fix C): use the bar's actual
    # drawn (stacked) extent, not each category's net total. Plotly draws a
    # stacked bar by piling its positive segments on the positive side and
    # its negative segments on the negative side independently, so a
    # category with both a large positive and a large negative segment can
    # be drawn far wider than its net total suggests. positive_extents and
    # negative_extents below are, per category, the sum of only its positive
    # segments and the sum of only its negative segments — the true max
    # extent the bar is drawn to on the positive side and the true min
    # extent on the negative side — and _millions_ticks() below is fed the
    # true min/max across all categories being charted, not the (possibly
    # much smaller) net-total range.
    #
    # The earlier sweep that called this "not reachable with the current
    # real dataset" only checked breakdown-by-entity: filtering to
    # supplier="Demo Supplier 052" in 2024 and breaking down by
    # entity/category, that supplier's category has a real ~-7,637.65
    # negative segment and a real ~165,965.09 positive segment in the same
    # bar, netting to ~158,327.44 — the old net-based range only spanned
    # 0-to-~158k, giving no negative reference point even though a real
    # negative-valued segment is drawn on the chart.
    positive_extents = (
        chart_df[chart_df["net_spend"] > 0]
        .groupby("category", observed=True)["net_spend"]
        .sum()
    )
    negative_extents = (
        chart_df[chart_df["net_spend"] < 0]
        .groupby("category", observed=True)["net_spend"]
        .sum()
    )
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
        # Reindex only the net_spend series (not the whole sub-frame) over
        # the full category list, so a missing category/breakdown
        # combination fills with a numeric 0 rather than pandas trying to
        # fill_value=0 into the (string-typed) breakdown column too.
        sub = chart_df[chart_df["breakdown"] == bval].set_index("category")["net_spend"]
        sub = sub.reindex(categories, fill_value=0)
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

    tickvals, ticktext = _millions_ticks(
        negative_extents.min() if not negative_extents.empty else 0,
        positive_extents.max() if not positive_extents.empty else 0,
    )

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

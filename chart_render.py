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


def _millions_ticks(max_value: float, step: float = 500_000) -> tuple[list[float], list[str]]:
    """Build 0/0.5M/1M-style tick positions and labels covering 0..max_value.

    Matches the InSight demo's axis style per _CHART-CHAT-DESIGN.md: "€ axis
    formatting in the demo's style (0M / 0.5M / 1M ticks; € in the axis
    title)". Uses explicit tickvals/ticktext rather than a d3 SI-prefix
    tickformat (e.g. ".2s") because SI-prefix formatting switches between
    "k" and "M" per value's own magnitude (500000 -> "500k"), which does not
    match the demo's fixed M-only style (500000 -> "0.5M") for values below
    one million.
    """
    if max_value <= 0:
        return [0], ["0M"]
    n_ticks = int(max_value // step) + 2  # one tick beyond the data max
    tickvals = [i * step for i in range(n_ticks)]
    ticktext = [f"{v / 1_000_000:g}M" for v in tickvals]
    return tickvals, ticktext


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
                # Direct value labels on every segment — dataviz skill's
                # marks-and-anatomy.md: "Bars -> value at the tip." Placed
                # inside each segment (not "outside") so labels never spill
                # into the next stacked segment; Plotly's default
                # constraintext="both" shrinks/hides any label that doesn't
                # fit its own segment, so nothing overflows or clips.
                text=sub["net_spend"],
                texttemplate="%{text:,.0f}",
                textposition="inside",
                insidetextanchor="middle",
            )
        )

    stack_totals = chart_df.groupby("category", observed=True)["net_spend"].sum()
    tickvals, ticktext = _millions_ticks(stack_totals.max() if not stack_totals.empty else 0)

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

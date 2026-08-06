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

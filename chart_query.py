"""Deterministic category-spend aggregation for the chart-in-chat feature.

Same rule as spend_query.py: no AI anywhere in this file. A chart can only
ever show numbers computed by a plain pandas groupby/sum over the real rows.
"""

import pandas as pd

from spend_query import FILTER_COLUMNS, filter_df

CATEGORY_COLUMNS = {k: FILTER_COLUMNS[k] for k in ("l1", "l2")}
BREAKDOWN_COLUMNS = {k: FILTER_COLUMNS[k] for k in ("entity", "country", "cluster")}


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

    matched = filter_df(df, **filters).copy()
    category_col = CATEGORY_COLUMNS[level]
    breakdown_col = BREAKDOWN_COLUMNS[breakdown]

    # A null category/breakdown value would otherwise be silently dropped by
    # groupby's default dropna=True, while query_spend() counts every
    # matched row regardless — group nulls into a visible sentinel bucket
    # instead, so a chart can never disagree with query_spend() purely
    # because of a missing dimension value.
    matched[category_col] = matched[category_col].fillna("(unspecified)")
    matched[breakdown_col] = matched[breakdown_col].fillna("(unspecified)")

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
    # net_spend is returned as the raw, unrounded float sum — rounding
    # happens only at display time (chart_render's per-segment labels and
    # app.py's total caption), matching query_spend()'s sum-then-round-once
    # pattern so the two can never diverge on rounding order alone.
    return grouped

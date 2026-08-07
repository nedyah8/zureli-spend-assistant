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

    # A null Entity/L1 value would otherwise be silently dropped by
    # groupby's default dropna=True — same guard as category_spend() above,
    # so by_entity/by_category can never disagree with net_spend purely
    # because of a missing dimension value (Task 6 review finding).
    year_rows = year_rows.copy()
    year_rows["Entity"] = year_rows["Entity"].fillna("(unspecified)")
    year_rows["L1"] = year_rows["L1"].fillna("(unspecified)")

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

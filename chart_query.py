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


# Our own CR3-based tiers, disclosed in every fragmentation answer's
# caption. NOT reverse-fitted to the InSight demo's own Profile column —
# see _MEETING-READY-DESIGN.md Part C1: cross-checking real InSight rows
# showed the demo's Profile likely tracks its Concentration index, not CR3
# alone, but with only 8 category rows to observe, the exact cutoff isn't
# reliably recoverable — and tuning ours to force a match would be
# measurement gaming (CLAUDE.md rule 24), not grounding. Concentration
# index is still computed and disclosed alongside CR3 (a standard,
# well-defined HHI-style statistic) but does not set the tier here.
CONCENTRATED_THRESHOLD = 70.0
MEDIUM_THRESHOLD = 40.0


def fragmentation(df: pd.DataFrame, level: str = "l1", **filters) -> pd.DataFrame:
    """Per-category supplier concentration: CR3 (top-3-supplier share) and
    an HHI-style concentration index (sum of squared per-supplier
    percentage shares of that category's spend), tiered by CR3 against
    CONCENTRATED_THRESHOLD/MEDIUM_THRESHOLD above.

    Returns a tidy dataframe: [category, net_spend, supplier_count,
    top_supplier_share_pct, cr3_pct, concentration_index, tier].
    """
    if level not in CATEGORY_COLUMNS:
        raise ValueError(f"level must be one of {list(CATEGORY_COLUMNS)}, got {level!r}")
    category_col = CATEGORY_COLUMNS[level]

    matched = filter_df(df, **filters).copy()
    matched[category_col] = matched[category_col].fillna("(unspecified)")

    rows = []
    for category, cat_df in matched.groupby(category_col, observed=True):
        net_spend = float(cat_df["Net spend"].sum())
        cat_df = cat_df.copy()
        cat_df["Supplier name"] = cat_df["Supplier name"].fillna("(unspecified)")
        by_supplier = cat_df.groupby("Supplier name")["Net spend"].sum().sort_values(ascending=False)
        supplier_count = int(len(by_supplier))

        if net_spend <= 0 or by_supplier.empty:
            top_share, cr3, index = 0.0, 0.0, 0.0
        else:
            shares_pct = by_supplier / net_spend * 100
            top_share = round(float(shares_pct.iloc[0]), 1)
            cr3 = round(float(shares_pct.head(3).sum()), 1)
            index = round(float((shares_pct ** 2).sum()), 0)

        if cr3 >= CONCENTRATED_THRESHOLD:
            tier = "Concentrated"
        elif cr3 >= MEDIUM_THRESHOLD:
            tier = "Medium fragmentation"
        else:
            tier = "High fragmentation"

        rows.append({
            "category": category, "net_spend": round(net_spend, 2),
            "supplier_count": supplier_count, "top_supplier_share_pct": top_share,
            "cr3_pct": cr3, "concentration_index": index, "tier": tier,
        })

    return pd.DataFrame(rows).sort_values("net_spend", ascending=False).reset_index(drop=True)


def overall_concentration(df: pd.DataFrame, **filters) -> pd.DataFrame:
    """Every supplier's net spend in scope, descending, plus each one's
    cumulative share of the total — the InSight demo's 'Overall supplier
    concentration' Pareto view.

    Returns [supplier, net_spend, cumulative_share_pct], sorted descending
    by net_spend.
    """
    matched = filter_df(df, **filters).copy()
    # A null Supplier name would otherwise be silently dropped by groupby's
    # default dropna=True, while query_spend() counts every matched row
    # regardless — same guard as supplier_drilldown()'s by_entity/by_category
    # and fragmentation()'s per-category by_supplier groupbys above (Task 6
    # and Task 8 review findings), so this chart's total can never disagree
    # with query_spend() purely because of a missing supplier name.
    matched["Supplier name"] = matched["Supplier name"].fillna("(unspecified)")
    by_supplier = (
        matched.groupby("Supplier name")["Net spend"].sum()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={"Supplier name": "supplier", "Net spend": "net_spend"})
    )
    total = float(by_supplier["net_spend"].sum())
    if total != 0:
        by_supplier["cumulative_share_pct"] = (by_supplier["net_spend"].cumsum() / total * 100).round(1)
    else:
        by_supplier["cumulative_share_pct"] = 0.0
    return by_supplier


def category_comparison(df: pd.DataFrame, level: str = "l1", **filters) -> pd.DataFrame:
    """Year-over-year spend comparison per category — the InSight demo's
    "Category comparison table" (Category spend tab). `filters` must
    include `year` (the "current" year) — app.py resolves an unfiltered
    question's year to the latest year present in scope before calling
    this, same pattern as every other chart_kind. `prior` is `year - 1`; a
    category with no prior-year rows in scope gets spend_prior=0.0 and
    change_pct=None (never a fabricated percentage from a zero/absent
    base, same rule as overview_query.overview()'s yoy_pct).

    Returns [category, spend_current, spend_prior, change, change_pct,
    share_pct], sorted descending by spend_current.
    """
    if level not in CATEGORY_COLUMNS:
        raise ValueError(f"level must be one of {list(CATEGORY_COLUMNS)}, got {level!r}")
    category_col = CATEGORY_COLUMNS[level]

    current_year = filters["year"]
    prior_year = current_year - 1
    non_year_filters = {k: v for k, v in filters.items() if k != "year"}
    scoped = filter_df(df, **non_year_filters).copy()

    current_rows = scoped[scoped["Year"] == current_year].copy()
    prior_rows = scoped[scoped["Year"] == prior_year].copy()
    current_rows[category_col] = current_rows[category_col].fillna("(unspecified)")
    prior_rows[category_col] = prior_rows[category_col].fillna("(unspecified)")

    current_by_cat = current_rows.groupby(category_col)["Net spend"].sum()
    prior_by_cat = prior_rows.groupby(category_col)["Net spend"].sum()
    total_current = float(current_by_cat.sum())

    rows = []
    for category, spend_current in current_by_cat.items():
        spend_prior = float(prior_by_cat.get(category, 0.0))
        change = round(float(spend_current) - spend_prior, 2)
        change_pct = (
            round((float(spend_current) - spend_prior) / spend_prior * 100, 1)
            if spend_prior > 0 else None
        )
        share_pct = round(float(spend_current) / total_current * 100, 1) if total_current != 0 else None
        rows.append({
            "category": category, "spend_current": round(float(spend_current), 2),
            "spend_prior": round(spend_prior, 2), "change": change,
            "change_pct": change_pct, "share_pct": share_pct,
        })
    # Explicit columns (not just pd.DataFrame(rows)) so an empty `rows` list
    # — a real, reachable case: any filter combo with rows in scope for some
    # year but none in the current year, e.g. entity="Demo Alpine
    # Operations" + supplier="Demo Supplier 019" (data only in 2024, chart
    # defaults to 2025) — still produces the [category, spend_current, ...]
    # schema instead of a bare 0-column frame. Without this, sort_values
    # below raised KeyError: 'spend_current' instead of returning the empty
    # frame app.py's `if comparison_df.empty:` branch is built to handle;
    # confirmed via a real answer_payload() call with the filter combo above
    # (Task 11 own-review finding, not from the brief).
    columns = ["category", "spend_current", "spend_prior", "change", "change_pct", "share_pct"]
    return pd.DataFrame(rows, columns=columns).sort_values("spend_current", ascending=False).reset_index(drop=True)


def entity_category_intensity(df: pd.DataFrame, level: str = "l1", **filters) -> pd.DataFrame:
    """Net spend by entity x category — the InSight demo's "Entity/category
    intensity" heatmap (Category spend tab). Null category values are
    filled with "(unspecified)" before grouping, same null-guard rule as
    category_spend()/supplier_drilldown() in this file.

    Returns [entity, category, net_spend], one row per entity x category
    combination present in the filtered scope.
    """
    if level not in CATEGORY_COLUMNS:
        raise ValueError(f"level must be one of {list(CATEGORY_COLUMNS)}, got {level!r}")
    category_col = CATEGORY_COLUMNS[level]

    matched = filter_df(df, **filters).copy()
    matched[category_col] = matched[category_col].fillna("(unspecified)")
    # Entity is the OTHER groupby dimension below, alongside category_col —
    # a null Entity value would otherwise be silently dropped by groupby's
    # default dropna=True, same class of bug already fixed three times in
    # this file (supplier_drilldown's by_entity/by_category, fragmentation's
    # by_supplier, overall_concentration's by_supplier): a null in ANY
    # groupby key column drops the row, not just a null in the column the
    # guard happens to target. Guarding category_col alone here would leave
    # this function's total silently disagreeing with query_spend() the
    # moment a row has a null Entity but a non-null category.
    matched["Entity"] = matched["Entity"].fillna("(unspecified)")

    return (
        matched.groupby(["Entity", category_col])["Net spend"]
        .sum()
        .reset_index()
        .rename(columns={"Entity": "entity", category_col: "category", "Net spend": "net_spend"})
    )


def raw_filtered_rows(df: pd.DataFrame, **filters) -> pd.DataFrame:
    """The exact filtered rows for the given scope, unaggregated — the
    InSight demo's "More" tab ("Filtered supplier-year rows"). For a
    client who wants to see the underlying rows behind a number, not just
    the number itself.
    """
    return filter_df(df, **filters).copy()

"""Deterministic overview computation — headline KPIs and callouts.

No AI anywhere in this file: every number is a plain pandas aggregation
over the real rows, computed the same way spend_query.query_spend() and
chart_query.category_spend() are, so an overview answer can never disagree
with what those functions would return for the same filters.
"""

import pandas as pd

from spend_query import filter_df


def overview(df: pd.DataFrame, **filters) -> dict:
    """Headline KPIs + callouts within the given filters.

    Focus year is always the latest year present in the filtered scope —
    same defaulting rule as chart_query.category_spend()'s chart path.

    Returns a dict:
      - year: int | None (None if the filters match zero rows)
      - net_spend: float, total net spend in `year`
      - prior_year: int | None, year - 1 if present in scope, else None
      - yoy_pct: float | None, % change vs prior_year
      - entity_count, supplier_count, row_count: int, distinct counts in `year`
      - largest_category: {"name": str, "net_spend": float} | None
      - fastest_growing_category: {"name": str, "growth_pct": float} | None
        (categories with zero or absent prior-year spend are excluded from
        the growth ranking — a new category entering from zero isn't a
        meaningful "% growth" figure)
      - top10_concentration_pct: float | None
      - largest_supplier: {"name": str, "net_spend": float} | None
    """
    matched = filter_df(df, **filters)
    if matched.empty:
        return {
            "year": None, "net_spend": 0.0, "prior_year": None, "yoy_pct": None,
            "entity_count": 0, "supplier_count": 0, "row_count": 0,
            "largest_category": None, "fastest_growing_category": None,
            "top10_concentration_pct": None, "largest_supplier": None,
        }

    year = int(matched["Year"].max())
    year_rows = matched[matched["Year"] == year].copy()

    # A null Entity/L1/Supplier name would otherwise be silently dropped by
    # groupby's default dropna=True (and excluded from nunique(), which also
    # ignores NaN by default) — while net_spend above already sums every
    # matched row regardless of nulls in ANY column. Without this guard, an
    # all-null L1/Supplier-name scope would report net_spend correctly but
    # every callout (largest category, fastest growth, top-10 concentration,
    # largest supplier) as None, silently disagreeing with the headline
    # number, AND — if EVERY callout comes back None — leaves
    # app.py's build_overview_payload with an empty `callouts` list, which
    # crashes render_callouts()'s `container.columns(len(callouts))` as
    # `st.columns(0)` (confirmed directly: raises
    # StreamlitInvalidColumnSpecError). Same guard, same reasoning, as
    # chart_query.py's category_spend()/supplier_drilldown()/
    # fragmentation()/overall_concentration()/entity_category_intensity()
    # (Codex cross-family review, Task 14, 7 Aug 2026 — this file predates
    # those fixes and had never received the equivalent guard). Not
    # reachable with the current real sample_spend_data.csv (verified: zero
    # nulls in any column), but defensive per this codebase's own
    # established pattern, not reverse-fitted to today's data.
    year_rows["Entity"] = year_rows["Entity"].fillna("(unspecified)")
    year_rows["L1"] = year_rows["L1"].fillna("(unspecified)")
    year_rows["Supplier name"] = year_rows["Supplier name"].fillna("(unspecified)")

    net_spend = round(float(year_rows["Net spend"].sum()), 2)
    entity_count = int(year_rows["Entity"].nunique())
    supplier_count = int(year_rows["Supplier name"].nunique())
    row_count = int(len(year_rows))

    prior_year_candidate = year - 1
    prior_rows = matched[matched["Year"] == prior_year_candidate].copy()
    if prior_rows.empty:
        prior_year = None
        yoy_pct = None
    else:
        prior_year = prior_year_candidate
        prior_spend = float(prior_rows["Net spend"].sum())
        yoy_pct = round((net_spend - prior_spend) / prior_spend * 100, 1) if prior_spend != 0 else None
        prior_rows["L1"] = prior_rows["L1"].fillna("(unspecified)")

    by_category = year_rows.groupby("L1")["Net spend"].sum()
    if by_category.empty:
        largest_category = None
    else:
        top_cat = by_category.idxmax()
        largest_category = {"name": top_cat, "net_spend": round(float(by_category[top_cat]), 2)}

    fastest_growing_category = None
    if prior_year is not None and not by_category.empty:
        prior_by_category = prior_rows.groupby("L1")["Net spend"].sum()
        growth = {}
        for cat, spend in by_category.items():
            prior_spend = prior_by_category.get(cat)
            if prior_spend and prior_spend > 0:
                growth[cat] = (spend - prior_spend) / prior_spend * 100
        if growth:
            fastest_cat = max(growth, key=growth.get)
            fastest_growing_category = {"name": fastest_cat, "growth_pct": round(growth[fastest_cat], 1)}

    by_supplier = year_rows.groupby("Supplier name")["Net spend"].sum().sort_values(ascending=False)
    if by_supplier.empty or net_spend == 0:
        top10_concentration_pct = None
        largest_supplier = None
    else:
        top10_sum = float(by_supplier.head(10).sum())
        top10_concentration_pct = round(top10_sum / net_spend * 100, 1)
        largest_supplier = {
            "name": by_supplier.index[0],
            "net_spend": round(float(by_supplier.iloc[0]), 2),
        }

    return {
        "year": year, "net_spend": net_spend, "prior_year": prior_year, "yoy_pct": yoy_pct,
        "entity_count": entity_count, "supplier_count": supplier_count, "row_count": row_count,
        "largest_category": largest_category, "fastest_growing_category": fastest_growing_category,
        "top10_concentration_pct": top10_concentration_pct, "largest_supplier": largest_supplier,
    }

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from chart_query import category_spend
from spend_query import load_data, query_spend


def test_category_totals_match_query_spend():
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="entity", year=2024)
    for category in chart_df["category"].unique():
        chart_total = round(chart_df.loc[chart_df["category"] == category, "net_spend"].sum(), 2)
        reference = query_spend(df, l1=str(category), year=2024)
        assert chart_total == reference["total_net_spend"], category


def test_categories_sorted_descending_by_total():
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="entity", year=2024)
    totals_in_order = chart_df.groupby("category", observed=True, sort=False)["net_spend"].sum()
    values = totals_in_order.tolist()
    assert values == sorted(values, reverse=True)


def test_invalid_level_raises():
    df = load_data()
    try:
        category_spend(df, level="l3")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_breakdown_by_country():
    df = load_data()
    chart_df = category_spend(df, level="l1", breakdown="country", year=2024)
    assert set(chart_df["breakdown"].unique()) <= set(load_data()["Country"].unique())


def test_chart_total_matches_query_spend_rounding_order():
    # Task 9 fix 1 (Codex finding): category_spend() used to round net_spend
    # PER category/breakdown group before returning, while query_spend()
    # sums raw values first and rounds once. Rounding-per-group-then-summing
    # and summing-then-rounding-once can diverge: two rows of 0.014 each, in
    # the same category but different breakdowns, each round to 0.01
    # individually (sum 0.02), but their true raw sum is 0.028, which rounds
    # to 0.03 — not 0.02. category_spend() must now return raw (unrounded)
    # net_spend so the caller's sum-then-round-once matches query_spend()
    # exactly.
    df = pd.DataFrame(
        {
            "L1": ["Cat", "Cat"],
            "Entity": ["Demo X", "Demo Y"],
            "Net spend": [0.014, 0.014],
        }
    )
    chart_df = category_spend(df, level="l1", breakdown="entity")
    chart_total = round(chart_df["net_spend"].sum(), 2)
    reference = query_spend(df)
    assert chart_total == 0.03
    assert chart_total == reference["total_net_spend"]


def test_null_category_and_breakdown_values_are_not_dropped():
    # Task 9 fix 2 (Codex finding): groupby's default dropna=True silently
    # excludes any row with a null category/breakdown value from the chart,
    # while query_spend() counts every matched row regardless — a real
    # correctness gap against the "chart must never disagree with
    # query_spend()" promise. Null category/breakdown values must be filled
    # with a visible "(unspecified)" sentinel before grouping instead.
    df = pd.DataFrame(
        {
            "L1": ["Cat", None],
            "Entity": ["Demo X", "Demo Y"],
            "Net spend": [100.0, 50.0],
        }
    )
    chart_df = category_spend(df, level="l1", breakdown="entity")
    reference = query_spend(df)

    # (a) the null row is not dropped — totals still match query_spend().
    assert round(chart_df["net_spend"].sum(), 2) == reference["total_net_spend"]
    # (b) the null row appears under the "(unspecified)" category rather
    # than vanishing.
    assert "(unspecified)" in [str(c) for c in chart_df["category"]]


from chart_query import top_suppliers


def test_top_suppliers_totals_match_query_spend():
    df = load_data()
    chart_df = top_suppliers(df, n=15)
    for supplier in chart_df["supplier"].unique():
        for year in chart_df.loc[chart_df["supplier"] == supplier, "year"].unique():
            chart_total = chart_df.loc[
                (chart_df["supplier"] == supplier) & (chart_df["year"] == year), "net_spend"
            ].sum()
            reference = query_spend(df, supplier=str(supplier), year=int(year))
            assert round(chart_total, 2) == reference["total_net_spend"], (supplier, year)


def test_top_suppliers_respects_n():
    df = load_data()
    chart_df = top_suppliers(df, n=5)
    assert chart_df["supplier"].nunique() == 5


def test_top_suppliers_sorted_descending_by_total():
    df = load_data()
    chart_df = top_suppliers(df, n=10)
    totals_in_order = chart_df.groupby("supplier", observed=True, sort=False)["net_spend"].sum()
    values = totals_in_order.tolist()
    assert values == sorted(values, reverse=True)


def test_top_suppliers_filters_apply():
    df = load_data()
    chart_df = top_suppliers(df, n=15, year=2024)
    assert set(chart_df["year"].unique()) == {2024}


from chart_query import supplier_drilldown


def test_supplier_drilldown_net_spend_matches_query_spend():
    df = load_data()
    result = supplier_drilldown(df, "Demo Supplier 025")
    reference = query_spend(df, supplier="Demo Supplier 025", year=result["year"])
    assert result["net_spend"] == reference["total_net_spend"]


def test_supplier_drilldown_by_entity_sums_to_net_spend():
    df = load_data()
    result = supplier_drilldown(df, "Demo Supplier 025")
    assert round(result["by_entity"]["net_spend"].sum(), 2) == result["net_spend"]


def test_supplier_drilldown_by_category_sums_to_net_spend():
    df = load_data()
    result = supplier_drilldown(df, "Demo Supplier 025")
    assert round(result["by_category"]["net_spend"].sum(), 2) == result["net_spend"]


def test_supplier_drilldown_unknown_supplier_returns_none_year():
    df = load_data()
    result = supplier_drilldown(df, "Nonexistent Supplier")
    assert result["year"] is None
    assert result["by_entity"].empty


def test_supplier_drilldown_null_entity_and_category_values_are_not_dropped():
    # Task 6 review finding: category_spend() (same file) already guards
    # against pandas groupby's default dropna=True silently excluding
    # null-dimension rows (see test_null_category_and_breakdown_values_are_not_dropped
    # above) — supplier_drilldown()'s by_entity/by_category groupbys
    # reintroduced that same unguarded pattern for Entity and L1. A null
    # value in either column must still be counted (under an
    # "(unspecified)" sentinel), so by_entity/by_category never disagree
    # with the function's own net_spend total.
    df = pd.DataFrame(
        {
            "Supplier name": ["Demo Supplier X", "Demo Supplier X"],
            "Year": [2024, 2024],
            "Entity": ["Demo Alpine", None],
            "L1": [None, "IT and telecom"],
            "Net spend": [100.0, 50.0],
        }
    )
    result = supplier_drilldown(df, "Demo Supplier X")

    # (a) the null rows are not dropped — breakdown totals still match net_spend.
    assert round(result["by_entity"]["net_spend"].sum(), 2) == result["net_spend"]
    assert round(result["by_category"]["net_spend"].sum(), 2) == result["net_spend"]
    # (b) the null rows appear under the "(unspecified)" sentinel rather
    # than vanishing.
    assert "(unspecified)" in [str(n) for n in result["by_entity"]["name"]]
    assert "(unspecified)" in [str(n) for n in result["by_category"]["name"]]


from chart_query import fragmentation


def test_fragmentation_net_spend_matches_query_spend():
    df = load_data()
    frag_df = fragmentation(df, level="l1", year=2025)
    for _, row in frag_df.iterrows():
        reference = query_spend(df, l1=str(row["category"]), year=2025)
        assert row["net_spend"] == reference["total_net_spend"], row["category"]


def test_fragmentation_cr3_between_0_and_100():
    df = load_data()
    frag_df = fragmentation(df, level="l1", year=2025)
    assert (frag_df["cr3_pct"] >= 0).all()
    assert (frag_df["cr3_pct"] <= 100).all()


def test_fragmentation_tier_matches_cr3_thresholds():
    df = load_data()
    frag_df = fragmentation(df, level="l1", year=2025)
    for _, row in frag_df.iterrows():
        if row["cr3_pct"] >= 70:
            assert row["tier"] == "Concentrated"
        elif row["cr3_pct"] >= 40:
            assert row["tier"] == "Medium fragmentation"
        else:
            assert row["tier"] == "High fragmentation"


def test_fragmentation_concentration_index_is_hhi_style():
    df = load_data()
    frag_df = fragmentation(df, level="l1", year=2025)
    year_rows = df[df["Year"] == 2025]
    sample_category = frag_df.iloc[0]["category"]
    cat_rows = year_rows[year_rows["L1"] == sample_category]
    by_supplier = cat_rows.groupby("Supplier name")["Net spend"].sum()
    shares_pct = by_supplier / by_supplier.sum() * 100
    expected_index = round(float((shares_pct ** 2).sum()), 0)
    actual_index = frag_df.loc[frag_df["category"] == sample_category, "concentration_index"].iloc[0]
    assert actual_index == expected_index

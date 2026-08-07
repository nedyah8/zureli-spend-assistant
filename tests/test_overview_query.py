import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overview_query import overview
from spend_query import load_data, query_spend


def test_net_spend_matches_query_spend():
    df = load_data()
    stats = overview(df)
    assert stats["year"] == 2025
    reference = query_spend(df, year=2025)
    assert stats["net_spend"] == reference["total_net_spend"]
    assert stats["row_count"] == reference["row_count"]


def test_net_spend_matches_query_spend_within_filters():
    df = load_data()
    stats = overview(df, entity="Demo Alpine Operations")
    reference = query_spend(df, entity="Demo Alpine Operations", year=stats["year"])
    assert stats["net_spend"] == reference["total_net_spend"]


def test_yoy_pct_omitted_when_prior_year_not_in_scope():
    df = load_data()
    stats = overview(df, year=2025)
    assert stats["prior_year"] is None
    assert stats["yoy_pct"] is None


def test_yoy_pct_present_when_both_years_in_scope():
    df = load_data()
    stats = overview(df)
    assert stats["prior_year"] == 2024
    assert stats["yoy_pct"] is not None


def test_largest_category_matches_manual_groupby():
    df = load_data()
    stats = overview(df)
    year_rows = df[df["Year"] == 2025]
    expected = year_rows.groupby("L1")["Net spend"].sum().idxmax()
    assert stats["largest_category"]["name"] == expected


def test_fastest_growing_category_excludes_zero_prior_spend():
    df = load_data()
    stats = overview(df)
    year_rows = df[df["Year"] == 2025]
    prior_rows = df[df["Year"] == 2024]
    by_cat = year_rows.groupby("L1")["Net spend"].sum()
    prior_by_cat = prior_rows.groupby("L1")["Net spend"].sum()
    growth = {
        cat: (spend - prior_by_cat[cat]) / prior_by_cat[cat] * 100
        for cat, spend in by_cat.items()
        if prior_by_cat.get(cat, 0) > 0
    }
    expected = max(growth, key=growth.get)
    assert stats["fastest_growing_category"]["name"] == expected


def test_top10_concentration_and_largest_supplier():
    df = load_data()
    stats = overview(df)
    year_rows = df[df["Year"] == 2025]
    by_supplier = year_rows.groupby("Supplier name")["Net spend"].sum().sort_values(ascending=False)
    expected_pct = round(by_supplier.head(10).sum() / by_supplier.sum() * 100, 1)
    assert stats["top10_concentration_pct"] == expected_pct
    assert stats["largest_supplier"]["name"] == by_supplier.index[0]


def test_empty_scope_returns_none_year():
    df = load_data()
    stats = overview(df, entity="Demo Alpine Operations", country="Germany", cluster="Nonexistent")
    assert stats["year"] is None
    assert stats["net_spend"] == 0.0
    assert stats["largest_category"] is None

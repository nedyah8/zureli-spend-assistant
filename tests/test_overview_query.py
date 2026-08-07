import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

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


def test_null_entity_l1_supplier_values_are_not_dropped_from_callouts():
    # Codex cross-family review, Task 14 (7 Aug 2026): groupby's default
    # dropna=True (and nunique()'s own NaN-skipping) would otherwise silently
    # exclude null Entity/L1/Supplier-name rows from every callout, while
    # net_spend already counts every matched row regardless — the same
    # never-diverge gap chart_query.py's functions already guard against,
    # missed here since this file predates those fixes. Worse: if EVERY row
    # in scope has null L1 AND null Supplier name, every callout comes back
    # None, which crashes app.py's render_callouts() at
    # `container.columns(len(callouts))` == `st.columns(0)` (confirmed
    # directly: raises StreamlitInvalidColumnSpecError) — reproduced here at
    # the computation layer, since render_callouts() itself needs a running
    # Streamlit script context to call.
    df = pd.DataFrame(
        {
            "Entity": ["Demo X", "Demo Y"],
            "L1": [None, None],
            "Supplier name": [None, None],
            "Year": [2025, 2025],
            "Net spend": [100.0, 50.0],
        }
    )
    stats = overview(df)

    # (a) the null rows are not dropped — net_spend still counts both.
    assert stats["net_spend"] == 150.0
    # (b) every callout now resolves to a real (unspecified-sentinel) value
    # instead of None — callouts is never empty as long as there is real
    # spend in scope, so app.py's build_overview_payload can never produce
    # an empty `callouts` list here.
    assert stats["largest_category"] == {"name": "(unspecified)", "net_spend": 150.0}
    assert stats["largest_supplier"] == {"name": "(unspecified)", "net_spend": 150.0}
    assert stats["top10_concentration_pct"] == 100.0
    assert stats["entity_count"] == 2
    assert stats["supplier_count"] == 1

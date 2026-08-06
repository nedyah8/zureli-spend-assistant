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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spend_query import filter_df, load_data, query_spend


def test_filter_df_matches_query_spend_row_count():
    df = load_data()
    filtered = filter_df(df, entity="Demo Alpine Operations", l1="IT and telecom", year=2024)
    result = query_spend(df, entity="Demo Alpine Operations", l1="IT and telecom", year=2024)
    assert len(filtered) == result["row_count"]
    assert round(float(filtered["Net spend"].sum()), 2) == result["total_net_spend"]


def test_query_spend_reference_total_unchanged():
    # Cross-checked independently earlier in the project (see _HANDOFF.md) — must not regress.
    df = load_data()
    result = query_spend(df, entity="Demo Alpine Operations", l1="IT and telecom", year=2024)
    assert result["total_net_spend"] == 192988.04

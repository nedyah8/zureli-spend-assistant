"""Deterministic spend aggregation over sample_spend_data.csv.

No AI involved anywhere in this file — every number is a plain pandas
sum over the real rows, so an answer can never be a hallucinated figure.
"""

from pathlib import Path
import pandas as pd

DATA_PATH = Path(__file__).parent / "sample_spend_data.csv"

FILTER_COLUMNS = {
    "entity": "Entity",
    "country": "Country",
    "cluster": "Cluster",
    "year": "Year",
    "l1": "L1",
    "l2": "L2",
    "supplier": "Supplier name",
}


def load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["Year"] = df["Year"].astype(int)
    df["Net spend"] = df["Net spend"].astype(float)
    return df


def known_values(df: pd.DataFrame) -> dict[str, list]:
    """Distinct values per filterable column, used both by the parser
    (to match words in a question) and by the UI (to show what's queryable)."""
    values = {key: sorted(df[col].unique().tolist()) for key, col in FILTER_COLUMNS.items()}
    values["year"] = sorted(int(y) for y in values["year"])
    return values


def query_spend(df: pd.DataFrame, **filters) -> dict:
    """filters: any of entity/country/cluster/year/l1/l2/supplier (case-sensitive,
    must match known_values exactly — the parser is responsible for resolving
    free text to these exact values before calling this).

    Returns total net spend, matching row count, and the filters actually applied,
    so the caller can always show what the answer is grounded in.
    """
    mask = pd.Series(True, index=df.index)
    applied = {}
    for key, value in filters.items():
        if value is None:
            continue
        col = FILTER_COLUMNS[key]
        mask &= df[col] == value
        applied[key] = value

    matched = df[mask]
    return {
        "total_net_spend": round(float(matched["Net spend"].sum()), 2),
        "row_count": int(len(matched)),
        "applied_filters": applied,
    }

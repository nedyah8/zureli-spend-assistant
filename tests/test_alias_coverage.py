"""Exhaustive alias coverage — every value in the data, every curated alias.

Written 7 Aug 2026 after Jayesh (the client) typed "give me IT spend" and
got the whole-company total. The defect was real, but the reason it survived
a 14-task build with an adversarial gauntlet matters more: the gauntlet's own
`test_synonym_questions_fall_to_overview_not_crash` asserted

    assert payload["kind"] in ("overview", "text", "chart")

which accepts every possible outcome and therefore cannot fail. It was named
for exactly this scenario and reported green throughout.

So this file is deliberately built to be un-cheatable in that way:

* It ENUMERATES from the dataset rather than listing hand-picked examples,
  so a new category or supplier is covered automatically and a shrinking
  vocabulary cannot quietly reduce coverage.
* Every assertion names the exact expected canonical value. There is no
  "one of these outcomes is fine" assertion anywhere in this file.
* The numeric tests compare against `query_spend` rather than a hardcoded
  figure, so they check the ANSWER, not merely the routing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from aliases import ALIASES_BY_DIMENSION, supplier_aliases
from nl_parser import parse_question
from spend_query import known_values, load_data, query_spend

DF = load_data()
KV = known_values(DF)


def filters_for(question: str) -> dict:
    return parse_question(question, KV)["filters"]


# --- 1. Every canonical value in the dataset resolves to itself -----------
# Enumerated from the data, so this cannot silently under-cover.

CANONICAL_CASES = [
    (dimension, value)
    for dimension in ("entity", "country", "cluster", "l1", "l2", "supplier")
    for value in KV[dimension]
]


@pytest.mark.parametrize(("dimension", "value"), CANONICAL_CASES)
def test_every_canonical_value_resolves_by_its_own_name(dimension, value):
    spoken = value.replace("Demo ", "")
    resolved = filters_for(f"what did we spend on {spoken}")
    assert resolved.get(dimension) == value, f"{spoken!r} -> {resolved}"


# --- 2. Every curated alias resolves to the value it was written for ------

ALIAS_CASES = [
    (alias, dimension, canonical)
    for dimension, alias_map in ALIASES_BY_DIMENSION.items()
    for canonical, alias_list in alias_map.items()
    for alias in alias_list
]


@pytest.mark.parametrize(("alias", "dimension", "canonical"), ALIAS_CASES)
def test_every_curated_alias_resolves(alias, dimension, canonical):
    # Phrased as a question so multi-word aliases that already embed their
    # own context ("spend on it", "it spend") read naturally either way.
    resolved = filters_for(f"how much did we spend on {alias}")
    assert resolved.get(dimension) == canonical, f"{alias!r} -> {resolved}"


SUPPLIER_ALIAS_CASES = [
    (alias, supplier) for supplier in KV["supplier"] for alias in supplier_aliases(supplier)
]


@pytest.mark.parametrize(("alias", "supplier"), SUPPLIER_ALIAS_CASES)
def test_every_supplier_alias_resolves(alias, supplier):
    resolved = filters_for(f"spend with {alias}")
    assert resolved.get("supplier") == supplier, f"{alias!r} -> {resolved}"


# --- 3. The answer is right, not just the routing -------------------------
# Jayesh's actual complaint was a WRONG NUMBER, so routing alone is not
# enough: each category's answer is checked against query_spend directly.

@pytest.mark.parametrize("l1", KV["l1"])
def test_every_l1_category_returns_the_correct_total(l1):
    import app

    resolved = filters_for(f"give me {l1} spend")
    assert resolved.get("l1") == l1

    payload = app.answer_payload(f"give me {l1} spend")
    expected = query_spend(DF, l1=l1)["total_net_spend"]
    assert f"{expected:,.2f}" in payload["text"], f"{l1}: {payload['text']!r}"


def test_jayeshs_exact_question_returns_the_it_total_not_the_company_total():
    # Verbatim from his email: "if you type give me IT spend, you get total
    # for all". Pinned so it can never silently regress.
    import app

    payload = app.answer_payload("give me IT spend")
    it_total = query_spend(DF, l1="IT and telecom")["total_net_spend"]
    company_total = query_spend(DF)["total_net_spend"]

    assert f"{it_total:,.2f}" in payload["text"]
    assert f"{company_total:,.2f}" not in payload["text"]
    assert payload["kind"] == "text"


# --- 4. False positives: ordinary English must not invent filters ---------
# The cost of an over-eager alias is worse than a miss: a spurious filter
# produces a confidently wrong number rather than an honest "didn't
# understand". "it" is the sharp case — it is both a category abbreviation
# and the most common pronoun in English.

@pytest.mark.parametrize(
    "question",
    [
        "what is it",
        "how does it work",
        "can you explain it to me",
        "is it possible to see more",
        "tell me about it",
        "what does it mean",
        "i don't get it",
    ],
)
def test_pronoun_it_does_not_resolve_to_the_it_category(question):
    assert "l1" not in filters_for(question), f"{question!r} -> {filters_for(question)}"


@pytest.mark.parametrize(
    "question",
    [
        "hello",
        "thanks",
        "what can you do",
        "how are we doing",
        "give me an overview",
    ],
)
def test_ordinary_questions_produce_no_spurious_filters(question):
    assert filters_for(question) == {}, f"{question!r} -> {filters_for(question)}"


# --- 5. Overlapping aliases resolve to the longer, more specific match ----
# These are the pairs that would otherwise AND themselves into an empty
# result and hand the user a false "no data found".

@pytest.mark.parametrize(
    ("question", "expected"),
    [
        # "southern support" (entity) must beat "south" (cluster)
        ("Southern Support spend", {"entity": "Demo Southern Support"}),
        # "western services" (entity) must beat "west" (cluster)
        ("Western Services spend", {"entity": "Demo Western Services"}),
        # "baltic logistics" (entity) must beat "logistics" (L1 category)
        ("Baltic Logistics spend", {"entity": "Demo Baltic Logistics"}),
        # "uk operations" (entity) must beat "uk" (country)
        ("UK Operations spend", {"entity": "Demo UK Operations"}),
        # "office supplies" (L2) must beat "office" (L1)
        ("office supplies spend", {"l2": "Office supplies"}),
        # a narrower L2 beats its own L1 parent
        ("electricity spend", {"l2": "Electricity and gas"}),
        ("consulting spend", {"l2": "Consulting"}),
    ],
)
def test_overlapping_aliases_resolve_to_the_more_specific_value(question, expected):
    resolved = filters_for(question)
    for dimension, value in expected.items():
        assert resolved.get(dimension) == value, f"{question!r} -> {resolved}"
    # And critically: no extra dimension got AND-ed in alongside it, which
    # is what would produce a false empty result.
    assert set(resolved) == set(expected), f"{question!r} over-matched: {resolved}"


# --- 6. Combinations still compose -----------------------------------------

def test_alias_combinations_compose_into_multiple_filters():
    resolved = filters_for("IT spend for Alpine in 2024")
    assert resolved == {
        "l1": "IT and telecom",
        "entity": "Demo Alpine Operations",
        "year": 2024,
    }, resolved


def test_combined_alias_answer_matches_query_spend():
    import app

    payload = app.answer_payload("IT spend for Alpine in 2024")
    expected = query_spend(
        DF, l1="IT and telecom", entity="Demo Alpine Operations", year=2024
    )["total_net_spend"]
    assert f"{expected:,.2f}" in payload["text"], payload["text"]

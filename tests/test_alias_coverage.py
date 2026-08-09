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


# Every case below was raised by the Codex cross-family review of the first
# version of this alias work, which correctly judged my own false-positive
# coverage "far too narrow" — it tested only the pronoun "it" and five safe
# phrases, and none of the dangerous aliases the change actually introduced.
# Each of these DID produce a confidently wrong number at that point.
#
# The lower group is the sharp one: each contains a spend word, so the
# spend-signal guard alone lets it through. They are stopped by the
# per-alias blocking phrases in aliases.py.
@pytest.mark.parametrize(
    "question",
    [
        # No spend signal — stopped by the weak-alias guard.
        "what is our buying power",
        "do you have a mobile app",
        "can I get this on my phone",
        "security of my data",
        "what training do i need to use this",
        "is there an audit trail",
        "what are the legal implications",
        "what tech do you use",
        "how do i do maintenance on this",
        "what did it cost",
        # WITH a spend signal — these defeat the guard and are stopped only
        # by the blocking phrases. Codex's exact regression list.
        "phone me the spend",
        "tech debt spend",
        "audit trail spend",
        "legal entity spend",
        "training data spend",
        "maintenance mode spend",
        "security policy spend",
    ],
)
def test_everyday_english_never_invents_a_category_filter(question):
    resolved = filters_for(question)
    assert resolved == {}, f"{question!r} wrongly resolved to {resolved}"


# The mirror image: the aliases above are only worth keeping if the genuine
# procurement phrasings still work. A guard that silences real queries too
# would be its own defect.
@pytest.mark.parametrize(
    ("question", "dimension", "expected"),
    [
        ("legal spend", "l2", "Legal and audit"),
        ("audit fees", "l2", "Legal and audit"),
        ("training costs", "l2", "Training"),
        ("security spend", "l2", "Cleaning and security"),
        ("maintenance spend", "l2", "Building maintenance"),
        ("technology spend", "l1", "IT and telecom"),
        ("phone bill", "l2", "Telecommunications"),
        ("hq spend", "entity", "Demo Group Headquarters"),
    ],
)
def test_genuine_procurement_phrasings_still_resolve(question, dimension, expected):
    resolved = filters_for(question)
    assert resolved.get(dimension) == expected, f"{question!r} -> {resolved}"


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


# --- 7. Codex review round 2 (7 Aug 2026) ---------------------------------
# Every case below was reported by the second cross-family review, run against
# the code that was already deployed live. All 14 concrete findings reproduced
# exactly as described, so none of this is hypothetical.

@pytest.mark.parametrize(
    ("question", "expected_l2"),
    [
        # A weak alias must never beat a non-weak one for the same dimension.
        # "security"/"software" are the same length (Cleaning sorted first) and
        # "maintenance" is simply longer — both handed the user a large,
        # confident, wrong total for a question plainly about software.
        ("security software spend", "Software licensing"),
        ("maintenance software spend", "Software licensing"),
        ("office software spend", "Software licensing"),
    ],
)
def test_weak_alias_never_beats_a_strong_one_for_the_same_dimension(question, expected_l2):
    resolved = filters_for(question)
    assert resolved.get("l2") == expected_l2, f"{question!r} -> {resolved}"


L1_L2_PAIRS = [
    (l1_alias[0], l2_alias[0], l2)
    for l1, l1_alias in ALIASES_BY_DIMENSION["l1"].items()
    for l2, l2_alias in ALIASES_BY_DIMENSION["l2"].items()
]


@pytest.mark.parametrize(("l1_alias", "l2_alias", "l2"), L1_L2_PAIRS)
def test_a_category_and_sub_category_are_never_contradictory(l1_alias, l2_alias, l2):
    """An L2 AND-ed with an L1 that is not its parent matches zero rows, and
    the app renders that as "€0.00 across 0 spend rows" — a false "no data"
    that reads exactly like a real answer. Enumerated over every L1 x L2 pair
    so a new category cannot reintroduce it.
    """
    resolved = filters_for(f"{l1_alias} {l2_alias} spend")
    if "l1" in resolved and "l2" in resolved:
        parent = KV["l2_parent"][resolved["l2"]]
        assert resolved["l1"] == parent, (
            f"{l1_alias!r} + {l2_alias!r} -> {resolved}: "
            f"{resolved['l2']!r} belongs to {parent!r}, not {resolved['l1']!r}"
        )


@pytest.mark.parametrize(
    "question",
    [
        # Ordinary English that returned a confident spend figure. The numbers
        # in the comments are what each one wrongly answered before the fix.
        "how many people work here",          # People, EUR 2,019,149.48
        "what is our brand value",            # Marketing, EUR 698,076.54
        "is this available in German?",       # Germany, EUR 1,801,388.73
        # Same class, found while fixing the three above.
        "do we have enough staff",
        "i need the polish translation",
        "what are the office hours",
        "who is on the brand guidelines team",
        "is the french version ready",
    ],
)
def test_ordinary_english_never_answers_with_a_spend_figure(question):
    resolved = filters_for(question)
    assert resolved == {}, f"{question!r} wrongly resolved to {resolved}"


def test_a_mistyped_year_is_not_silently_read_as_a_real_one():
    # `"2024" in "20245"` is true, so a plain substring test answered a
    # five-digit typo with the 2024 figure and labelled it "year = 2024".
    assert "year" not in filters_for("IT spend in 20245")
    assert "year" not in filters_for("IT spend in 12024")
    # Positive control: the real year must still resolve.
    assert filters_for("IT spend in 2024").get("year") == 2024


@pytest.mark.parametrize(
    ("question", "dimension", "expected"),
    [
        # Real buyer phrasings that fell to the overview.
        ("license spend", "l2", "Software licensing"),
        ("licence spend", "l2", "Software licensing"),
        ("phone bills", "l2", "Telecommunications"),
        ("contractor spend", "l2", "Temporary labour"),
        ("contract labour spend", "l2", "Temporary labour"),
        ("learning & development spend", "l2", "Training"),
        ("l and d spend", "l2", "Training"),
        ("gb spend", "country", "United Kingdom"),
        ("british spend", "country", "United Kingdom"),
        ("northern spend", "cluster", "North"),
    ],
)
def test_phrasings_added_after_the_second_review_resolve(question, dimension, expected):
    resolved = filters_for(question)
    assert resolved.get(dimension) == expected, f"{question!r} -> {resolved}"


@pytest.mark.parametrize("question", ["western spend", "southern spend"])
def test_genuinely_ambiguous_direction_words_decline_rather_than_guess(question):
    """"Western" could mean the West cluster or Demo Western Services, and
    "Southern" the South cluster or Demo Southern Support. Codex argued these
    should resolve to the entity; that is a guess, and a guess here produces a
    confidently wrong number. This test pins the deliberate decision to fall
    back honestly, so adding a guess later has to be a conscious change.
    """
    assert filters_for(question) == {}, f"{question!r} -> {filters_for(question)}"


def test_combined_alias_answer_matches_query_spend():
    import app

    payload = app.answer_payload("IT spend for Alpine in 2024")
    expected = query_spend(
        DF, l1="IT and telecom", entity="Demo Alpine Operations", year=2024
    )["total_net_spend"]
    assert f"{expected:,.2f}" in payload["text"], payload["text"]


# --- 8. Hayden's live customer testing + the 134-question sweep (9 Aug 2026) ---
#
# Every case below was reproduced against the shipping parser before its fix
# was written. The first one is a REGRESSION this project introduced itself:
# section 7 made "people" a weak alias to stop "how many people work here"
# answering with €2m, which was right, but "numbers" was not a spend-signal
# word, so "show me the overall numbers for the people" — a query Hayden had
# screenshotted working live — started returning the overview instead.


@pytest.mark.parametrize(
    "question,expected",
    [
        ("show me the overall numbers for the people", {"l1": "People"}),
        ("what are our people numbers", {"l1": "People"}),
        ("give me the people number", {"l1": "People"}),
        ("what's the marketing amount", {"l1": "Marketing"}),
    ],
)
def test_asking_for_the_numbers_is_asking_about_spend(question, expected):
    assert filters_for(question) == expected


@pytest.mark.parametrize(
    "question,expected",
    [
        ("just show me the offices figures", {"l1": "Office"}),
        ("offices spend", {"l1": "Office"}),
        ("office spend", {"l1": "Office"}),
        ("phone spend", {"l2": "Telecommunications"}),
        ("phones budget", {"l2": "Telecommunications"}),
    ],
)
def test_plural_and_restored_aliases_resolve(question, expected):
    assert filters_for(question) == expected


@pytest.mark.parametrize(
    "question",
    [
        "what's the phone number",
        "can you phone me",
        "i'll give you a phone call",
        "what are the office hours",
    ],
)
def test_the_new_weak_aliases_still_decline_ordinary_english(question):
    """"number" became a spend-signal word in the same change that added
    "phone" as an alias, so "what's the phone number" carries both a signal
    and a weak alias. Without the blocking phrase it answers with the
    Telecommunications total.
    """
    assert filters_for(question) == {}, f"{question!r} -> {filters_for(question)}"


@pytest.mark.parametrize(
    "question",
    ["IT costs", "IT figures", "show me the IT numbers", "what's the IT total",
     "is IT over budget"],
)
def test_capitalised_it_is_the_department(question):
    """aliases.py deliberately refuses a bare "it" alias because it is the
    commonest pronoun in English. Correct — but it left every one of these
    phrasings dead-ending on the overview while "IT spend" worked. Case is
    the discriminator a human uses, and it is free to read.
    """
    assert filters_for(question) == {"l1": "IT and telecom"}


@pytest.mark.parametrize(
    "question",
    ["what did it cost", "what is it", "how much did it cost us",
     "it depends on the budget", "is it worth the spend"],
)
def test_the_lowercase_pronoun_is_never_the_department(question):
    assert filters_for(question) == {}, f"{question!r} -> {filters_for(question)}"


def test_a_shouted_question_carries_no_case_information():
    """An all-caps sentence tells us nothing about which "it" was meant, so
    the capitalisation rule must not fire on it."""
    assert filters_for("WHAT DID IT COST") == {}


@pytest.mark.parametrize(
    "question,expected_level",
    [
        ("break this down", "l1"),
        ("break it down", "l1"),
        ("break this down per sub category", "l2"),
        ("drill into that", "l1"),
        ("show me more detail", "l1"),
    ],
)
def test_break_this_down_is_a_breakdown_request(question, expected_level):
    """"break down" was already a chart keyword, but the phrase people
    actually type puts a pronoun in the middle — "break THIS down" — so the
    substring never matched. Hayden's live test: an answer about People,
    then "Break this down per sub category for people", then the same flat
    total again with no breakdown.
    """
    parsed = parse_question(question, KV)
    assert parsed["intent"] == "chart", parsed
    assert parsed["category_level"] == expected_level, parsed


@pytest.mark.parametrize(
    "question,expected_breakdown",
    [
        ("spend by cluster", "cluster"),
        ("spend by country", "country"),
        ("category spend by entity", "entity"),
        ("spend per country", "country"),
    ],
)
def test_by_dimension_charts_without_needing_the_words_show_me(question, expected_breakdown):
    """The old pattern required a literal "show me" prefix, so "show me spend
    by country" charted and "spend by country" matched nothing at all."""
    parsed = parse_question(question, KV)
    assert parsed["intent"] == "chart", parsed
    assert parsed["breakdown"] == expected_breakdown, parsed


def test_by_an_entity_name_is_still_not_a_breakdown():
    """The dimension word is what makes the "by" pattern safe — an entity
    name after "by" is a filter, not a breakdown axis."""
    parsed = parse_question("total spend by Alpine Operations", KV)
    assert parsed["intent"] == "number", parsed


# --- Follow-up questions: the parser now sees the previous turn ---


def test_a_follow_up_inherits_the_previous_filters():
    first = parse_question("people spend", KV)
    assert first["filters"] == {"l1": "People"}
    second = parse_question("break this down per sub category", KV, previous=first)
    assert second["filters"] == {"l1": "People"}, second
    assert second["category_level"] == "l2", second


def test_a_follow_up_overrides_the_dimension_it_names():
    first = parse_question("IT spend in France", KV)
    second = parse_question("what about Germany", KV, previous=first)
    assert second["filters"] == {"l1": "IT and telecom", "country": "Germany"}, second


def test_a_follow_up_can_add_a_year_to_the_previous_question():
    first = parse_question("IT spend", KV)
    second = parse_question("and for 2024?", KV, previous=first)
    assert second["filters"] == {"l1": "IT and telecom", "year": 2024}, second


def test_a_self_contained_question_is_never_narrowed_by_the_previous_one():
    """Inheritance only applies to questions that actually refer back. A
    fresh question must not be silently filtered by whatever came before it.
    """
    first = parse_question("IT spend in France", KV)
    second = parse_question("marketing spend", KV, previous=first)
    assert second["filters"] == {"l1": "Marketing"}, second


def test_a_follow_up_never_produces_a_contradictory_category_pair():
    """Carrying a previous L1 onto a new, unrelated L2 recreates the
    "€0.00 across 0 spend rows" false-no-data bug by a second route.
    """
    first = parse_question("people spend", KV)
    second = parse_question("what about this software spend", KV, previous=first)
    assert second["filters"] == {"l2": "Software licensing"}, second


def test_parse_question_still_works_with_no_previous_turn():
    assert parse_question("IT spend", KV)["filters"] == {"l1": "IT and telecom"}


# --- Greetings and meta-questions are not spend questions ---


@pytest.mark.parametrize(
    "question",
    ["hello", "hi", "hey there", "good morning", "what is this",
     "what can this do", "who are you"],
)
def test_a_greeting_gets_help_not_a_spend_overview(question):
    assert parse_question(question, KV)["intent"] == "help", question


@pytest.mark.parametrize("question", ["this spend", "which entity spends most", "within budget"])
def test_words_containing_hi_and_hey_are_not_greetings(question):
    """"hi" is inside "this", "which" and "within"; "hey" is inside "they".
    A substring test would treat all of these as greetings."""
    assert parse_question(question, KV)["intent"] != "help", question


@pytest.mark.parametrize(
    "question",
    [
        "is there an audit trail",
        "is this available in German",
        "is this secure",
        "can I export this",
        "that is wrong",
        "no that is not what I meant",
        "is there a mobile app",
        "what are the legal implications of that",
    ],
)
def test_follow_up_inheritance_never_answers_a_meta_question(question):
    """Inheritance bypasses the alias layer entirely, so WEAK_ALIASES cannot
    protect it — the guard has to be repeated inside _merge_follow_up.

    Every question here contains a referring word ("this", "that", "there").
    With a previous answer in context, an inheritance rule keyed on the
    referring word alone hands each of them the previous filter and answers a
    question about the software with a spend figure. Reproduced exactly:
    "is there an audit trail" returned People, €2,019,149.48.
    """
    previous = parse_question("people spend", KV)
    assert previous["filters"] == {"l1": "People"}
    parsed = parse_question(question, KV, previous=previous)
    assert parsed["filters"] == {}, f"{question!r} -> {parsed['filters']}"

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
from nl_parser import DEFAULT_TOP_SUPPLIERS_N, parse_question
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


# --- 9. Codex cross-family review of the round-3 changes (9 Aug 2026) ---
#
# Five findings, all five reproduced exactly as described before any fix was
# written. Three were confidently-wrong numbers introduced by round 3 itself.


@pytest.mark.parametrize(
    "question",
    [
        "is this available in German numbering format?",
        "what is the amounts field",
        "can I change the number format",
    ],
)
def test_a_signal_word_inside_a_longer_word_is_not_a_signal(question):
    """SPEND_SIGNAL_WORDS were matched as plain substrings, so "numbering"
    contained "number" — a signal word added the same day — and unlocked the
    weak "german" alias: Germany, €1,801,388.73. Word boundaries fix the
    class, not the instance; every future signal word would have inherited
    the same latent bug.
    """
    assert filters_for(question) == {}, f"{question!r} -> {filters_for(question)}"


@pytest.mark.parametrize(
    "question",
    ["is IT secure?", "is IT down", "who runs IT", "can IT help me"],
)
def test_capitalised_it_still_needs_a_spend_signal(question):
    """Someone asking whether the SOFTWARE is secure writes "IT" too. The
    capitalisation rule is a weak alias and is gated like one — "is IT
    secure?" returned the IT and telecom total of €2,630,963.38.
    """
    assert filters_for(question) == {}, f"{question!r} -> {filters_for(question)}"


def test_asking_what_a_number_means_does_not_repeat_the_number():
    previous = parse_question("people spend", KV)
    parsed = parse_question("what does this amount mean?", KV, previous=previous)
    assert parsed["filters"] == {}, parsed


def test_an_elliptical_fragment_narrows_the_previous_answer():
    """"for 2024?" resolved its own year filter, which REPLACED the context
    instead of narrowing it — whole-company 2024 (€6,768,853.29) rather than
    People in 2024 (€1,041,612.74).
    """
    previous = parse_question("people spend", KV)
    parsed = parse_question("for 2024?", KV, previous=previous)
    assert parsed["filters"] == {"l1": "People", "year": 2024}, parsed


def test_a_breakdown_with_no_subject_uses_the_previous_one():
    previous = parse_question("people spend", KV)
    parsed = parse_question("by country?", KV, previous=previous)
    assert parsed["filters"] == {"l1": "People"}, parsed
    assert parsed["breakdown"] == "country", parsed


# ---------------------------------------------------------------------------
# 10. "Show this in a bar chart" — the follow-up that changes VIEW, not subject
#
# Found in Hayden's own live testing (10 Aug 2026), reading his real chat
# history off the deployed app rather than a synthetic sweep. He asked
# "2024 spend" (€6,768,853.29), then "Show this in a bar chart", and got a
# chart of 2025.
#
# Not a wrong number — the caption honestly read "matched on year = 2025" —
# but not the year he was looking at either. Asking to SEE the same answer
# differently was not recognised as referring back at all, so the year was
# dropped and the chart path fell through to its own default year.
#
# Structurally identical to the subject-less breakdown case ("by country?")
# fixed the day before, so it is fixed the same way rather than by
# special-casing this one sentence.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "follow_up",
    [
        "Show this in a bar chart",
        "show me that as a bar chart",
        "as a bar chart",
        "chart it",
        "plot it",
        "graph this",
        "visualise this",
    ],
)
def test_a_subjectless_chart_request_keeps_the_previous_subject(follow_up):
    """The whole point of "show THIS as a chart" is the word "this". A chart
    request naming no subject of its own can only mean the answer already on
    screen; without inheritance it silently became a different year.
    """
    previous = parse_question("2024 spend", KV)
    assert previous["filters"] == {"year": 2024}, previous

    parsed = parse_question(follow_up, KV, previous=previous)
    assert parsed["intent"] == "chart", parsed
    assert parsed["filters"] == {"year": 2024}, f"{follow_up!r} -> {parsed['filters']}"


def test_a_chart_follow_up_inherits_every_dimension_not_just_year():
    previous = parse_question("IT spend in France", KV)
    parsed = parse_question("show this in a bar chart", KV, previous=previous)
    assert parsed["filters"] == {"l1": "IT and telecom", "country": "France"}, parsed


def test_a_chart_question_naming_its_own_subject_is_never_narrowed():
    """The guard that stops inheritance becoming a second confidently-wrong
    class: a complete question must not be silently reinterpreted by whatever
    happened to be asked before it.
    """
    previous = parse_question("people spend", KV)
    parsed = parse_question("chart category spend by cluster for 2024", KV,
                            previous=previous)
    assert "l1" not in parsed["filters"], parsed
    assert parsed["filters"] == {"year": 2024}, parsed
    assert parsed["breakdown"] == "cluster", parsed


@pytest.mark.parametrize(
    "question",
    ["what does this chart mean?", "can you explain this chart"],
)
def test_asking_what_a_chart_means_does_not_inherit_the_subject(question):
    """A question ABOUT the output is not a request for the output again.
    Same guard as "what does this amount mean?" — pinned separately because
    the chart route reaches inheritance by a different path.
    """
    previous = parse_question("people spend", KV)
    parsed = parse_question(question, KV, previous=previous)
    assert parsed["filters"] == {}, f"{question!r} -> {parsed['filters']}"


def test_a_supplier_context_survives_a_chart_request():
    """Inherited filters can change INTENT, not just the numbers: a supplier
    filter routes to the drill-down view. Pinned so the chart request keeps
    reaching the chart, rather than being re-routed by its own inheritance.
    """
    previous = parse_question("supplier 25 spend", KV)
    parsed = parse_question("show this in a bar chart", KV, previous=previous)
    assert parsed["intent"] == "chart", parsed
    assert parsed["filters"] == {"supplier": "Demo Supplier 025"}, parsed


# ---------------------------------------------------------------------------
# 11. Codex cross-family review of the chart follow-up rule (10 Aug 2026)
#
# The FIRST version of that rule treated any chart word as evidence the
# question was about spend. Codex rejected it with 8 concrete cases and all 8
# reproduced: chart words are domain-general, and a bare "bar" is ordinary
# product English. "Plot our employee satisfaction trend" inherited Facilities
# 2025; "Is the search bar working?" inherited IT/France/2024.
#
# The rule now requires the WHOLE question to be a redraw request. Note that a
# referring word is deliberately insufficient — "Can this graph be exported?"
# refers back and is still not a request for data.
#
# These pin the failure cases themselves, not the mechanism, so a future
# rewrite of the trigger is still held to the same outcomes.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "previous_question, follow_up",
    [
        ("What was IT spend in France in 2024?", "Is the search bar working?"),
        ("How much did we spend on People in Germany?", "Can this graph be exported?"),
        ("What was Facilities spend in 2025?", "Plot our employee satisfaction trend."),
        ("Show Marketing spend for the UK.", "Graph customer support response times."),
        ("What was Travel spend in 2024?", "Why is the top bar missing?"),
        ("How much did Legal spend in Spain?", "Visualize the approval workflow."),
        ("What did we spend on Software in 2024?", "Can you make a chart of open invoices?"),
        ("What was Utilities spend in Germany?", "Make a bar chart of supplier risk ratings."),
    ],
)
def test_a_chart_word_alone_never_inherits_a_spend_filter(previous_question, follow_up):
    """Each of these names its own non-spend subject, or asks about the app
    rather than the data. Inheriting gave them a narrow spend chart that reads
    as a deliberate answer to a question the tool never understood.
    """
    previous = parse_question(previous_question, KV)
    assert previous["filters"], f"precondition: {previous_question!r} must set context"

    parsed = parse_question(follow_up, KV, previous=previous)
    assert parsed["filters"] == {}, f"{follow_up!r} -> {parsed['filters']}"


@pytest.mark.parametrize(
    "follow_up",
    [
        "now chart this", "ok graph it", "just plot it", "Chart it.",
        "GRAPH THIS", "can you chart it?", "chart this please",
    ],
)
def test_redraw_requests_survive_the_tightened_rule(follow_up):
    """The tightening must not cost the ordinary phrasings. Conversational
    lead-ins ("now", "ok", "just"), trailing punctuation and shouting are all
    filler around the same request.
    """
    previous = parse_question("2024 spend", KV)
    parsed = parse_question(follow_up, KV, previous=previous)
    assert parsed["filters"] == {"year": 2024}, f"{follow_up!r} -> {parsed['filters']}"


@pytest.mark.parametrize(
    "follow_up",
    ["can you graph?", "can you plot?", "can you visualize?",
     "can you show me this graph?", "show me this chart"],
)
def test_a_capability_phrasing_is_still_a_redraw_request(follow_up):
    """Codex's round-2 review flagged these five as capability questions that
    should not inherit. REJECTED after checking the outcome rather than the
    grammar: typed straight after "2024 spend", every one of them means "graph
    that". Inheriting gives a 2024 chart; not inheriting would give a 2025
    whole-company chart, which is further from what was asked, not closer.

    Pinned so the decision is deliberate and survives a future rewrite.
    """
    previous = parse_question("2024 spend", KV)
    parsed = parse_question(follow_up, KV, previous=previous)
    assert parsed["filters"] == {"year": 2024}, f"{follow_up!r} -> {parsed['filters']}"


@pytest.mark.parametrize(
    "not_a_redraw",
    ["what is a chart", "is the chart wrong", "the chart is broken",
     "who made this chart", "delete this chart", "chart of headcount",
     "graph our attrition", "plot twist", "plot the revenue forecast",
     "can i download this chart", "is this chart interactive",
     "print this chart", "email me this chart", "why is this chart empty"],
)
def test_questions_about_a_chart_are_not_requests_to_redraw_one(not_a_redraw):
    """Own adversarial fuzz alongside the Codex pass — a question that merely
    CONTAINS a chart word, or asks something about a chart, must never pick up
    the previous answer's filters.
    """
    previous = parse_question("2024 spend", KV)
    parsed = parse_question(not_a_redraw, KV, previous=previous)
    assert parsed["filters"] == {}, f"{not_a_redraw!r} -> {parsed['filters']}"


# ---------------------------------------------------------------------------
# 12. "top IT suppliers in UK" — the category-in-the-middle gap
#
# Found in Jayesh's own live testing (12 Aug 2026). TOP_SUPPLIERS_KEYWORDS
# only matches the literal phrase "top suppliers" — inserting a category
# between the two words broke it, and the question fell through to a single
# flat total instead of the ranked list it asked for. The filter extraction
# was already correct (l1=IT and telecom, country=United Kingdom); only the
# INTENT was wrong.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question, expected_filters",
    [
        ("top IT suppliers in UK", {"country": "United Kingdom", "l1": "IT and telecom"}),
        ("top suppliers in France", {"country": "France"}),
        ("top logistics suppliers", {"l1": "Logistics"}),
        ("top vendors for Facilities", {"l1": "Facilities"}),
        ("top People suppliers in 2024", {"year": 2024, "l1": "People"}),
    ],
)
def test_top_suppliers_with_a_subject_reaches_the_ranking_not_a_total(question, expected_filters):
    parsed = parse_question(question, KV)
    assert parsed["intent"] == "chart", f"{question!r} -> {parsed}"
    assert parsed["chart_kind"] == "top_suppliers", f"{question!r} -> {parsed}"
    assert parsed["filters"] == expected_filters, f"{question!r} -> {parsed['filters']}"
    assert parsed["top_n"] == 15, f"{question!r} -> top_n={parsed['top_n']}"


@pytest.mark.parametrize(
    "question",
    [
        "top spend for supplier 25",
        "what did supplier 25 spend on top",
        "supplier 25 top spend 2024",
    ],
)
def test_a_named_supplier_never_gets_promoted_to_a_ranking(question):
    """A specific supplier's own "top list" is meaningless — these must stay
    the drill-down view, not be swept into the new subject-aware pattern.
    """
    parsed = parse_question(question, KV)
    assert parsed["intent"] == "supplier_drilldown", f"{question!r} -> {parsed}"


@pytest.mark.parametrize(
    "question",
    [
        "is our supplier count at the top",
        "we went to the top of our supplier list",
        "top of the range suppliers",
    ],
)
def test_top_and_supplier_appearing_without_a_real_subject_does_not_trigger(question):
    """"top" and "supplier(s)" appearing in the same sentence is not enough by
    itself — these name no real category/entity/country, so filters stays
    empty and the new pattern must not fire on proximity alone.
    """
    parsed = parse_question(question, KV)
    assert parsed["chart_kind"] != "top_suppliers", f"{question!r} -> {parsed}"


@pytest.mark.parametrize(
    "question",
    [
        "top of the range suppliers in UK",
        "is our supplier count at the top for IT suppliers?",
        "which countries are at the top for IT suppliers?",
    ],
)
def test_a_connector_word_between_top_and_suppliers_is_not_a_subject(question):
    """Codex (12 Aug 2026) found the first version of the subject-aware
    pattern still over-matched: "of the range" and "for" are ordinary
    connector words, not category names, but the bare (?:\\S+\\s+){0,3} slots
    accepted them as if they were. Each of these carries a real filter
    (country=UK or l1=IT) so the AND-gate alone did not stop them — only
    rejecting a stopword-containing gap does.
    """
    parsed = parse_question(question, KV)
    assert parsed["chart_kind"] != "top_suppliers", f"{question!r} -> {parsed}"


def test_a_five_word_category_name_is_a_known_accepted_gap():
    """Residual limitation, deliberately not fixed: the gap is capped at 3
    filler words, so a long category description between "top" and
    "suppliers" still falls to a flat total. Widening the cap to catch this
    reopens the connector-word leaks the stopword check above closes.
    """
    parsed = parse_question("top IT hardware and software services suppliers in UK", KV)
    assert parsed["chart_kind"] != "top_suppliers", parsed


def test_an_unreasonable_top_n_falls_back_to_the_default_rather_than_crashing():
    """11 digits is one past TOP_N_PATTERN's own \\d{1,10} clamp, so the
    number is absorbed as an ordinary filler word instead of a requested N.
    Codex read this as bypassing the numeric guard; checked directly, it
    falls back to the safe default (15) rather than reaching int() at all —
    accepted as correct, not fixed.
    """
    parsed = parse_question("top 10000000000 IT suppliers in UK", KV)
    assert parsed["chart_kind"] == "top_suppliers", parsed
    assert parsed["top_n"] == DEFAULT_TOP_SUPPLIERS_N, parsed


def test_a_genuine_category_name_containing_and_is_not_rejected():
    """Codex round 2 (12 Aug 2026): "and"/"or" were in the first stopword
    list, and "IT and telecom" is the REAL L1 category name in this dataset —
    the fix built to recognise it was rejecting it. Checked against the 3
    original leaks: neither word was load-bearing for blocking any of them,
    so removing both cost nothing.
    """
    parsed = parse_question("top IT and telecom suppliers in UK", KV)
    assert parsed["chart_kind"] == "top_suppliers", parsed
    assert parsed["filters"] == {"l1": "IT and telecom", "country": "United Kingdom"}, parsed


@pytest.mark.parametrize(
    "question",
    [
        "is spend at the top among IT suppliers in UK?",
        "is our spend top versus IT suppliers in UK?",
    ],
)
def test_comparison_connectors_are_not_a_subject_either(question):
    """Codex round 2's replacement findings once "and"/"or" were removed —
    the same connector-word class, different words.
    """
    parsed = parse_question(question, KV)
    assert parsed["chart_kind"] != "top_suppliers", f"{question!r} -> {parsed}"


@pytest.mark.parametrize("category", ["Facilities", "Logistics", "Marketing", "Office",
                                       "People", "Professional services", "Utilities"])
def test_every_real_l1_category_name_reaches_the_ranking(category):
    """Sanity sweep: every genuine category in this dataset, not just the one
    Codex happened to name, must clear the stopword denylist.
    """
    parsed = parse_question(f"top {category} suppliers", KV)
    assert parsed["chart_kind"] == "top_suppliers", f"{category!r} -> {parsed}"
    assert parsed["filters"] == {"l1": category}, parsed


@pytest.mark.parametrize(
    "question",
    [
        "is spend at the top by IT suppliers in UK?",
        "is spend at the top across IT suppliers in UK?",
    ],
)
def test_round_3_connector_words_are_also_not_a_subject(question):
    """Codex round 3 (12 Aug 2026): "by" and "across" were still missing from
    the round-2 reactive list. Fixed by replacing the reactive list with
    English's actual closed word class (see the comment on
    _TOP_SUPPLIERS_GAP_STOPWORDS) rather than adding two more words.
    """
    parsed = parse_question(question, KV)
    assert parsed["chart_kind"] != "top_suppliers", f"{question!r} -> {parsed}"


def test_every_real_value_in_the_dataset_clears_the_stopword_denylist():
    """The comprehensive-stopword-list decision is only sound if it is true
    against the actual data, not just the cases Codex happened to try. Sweeps
    every l1/l2/entity/country/cluster/supplier value in the dataset.
    """
    from nl_parser import _TOP_SUPPLIERS_GAP_STOPWORDS

    collisions = []
    for dimension in ("l1", "l2", "entity", "country", "cluster", "supplier"):
        for value in KV[dimension]:
            words = {w.lower().rstrip(".,") for w in value.replace("Demo ", "").split()}
            if words & _TOP_SUPPLIERS_GAP_STOPWORDS:
                collisions.append((dimension, value, words & _TOP_SUPPLIERS_GAP_STOPWORDS))
    assert collisions == [], collisions


# --- unrecognized_terms: the "Italy IT spend" fix (12 Aug 2026) ---
#
# Jayesh's own user-testing screenshot: "Italy IT spend" silently dropped
# "Italy" (not a country in this dataset) and answered the same as a bare
# "IT spend" question, with nothing telling him a word had been ignored.
# unrecognized_terms() names words that look like a filter attempt but match
# nothing in the data, so app.py can disclose them instead of answering
# around them in silence. Deliberately narrow: it only has a signal to work
# from when the word is capitalised — see its docstring for why an
# all-lowercase equivalent was not attempted.

from nl_parser import unrecognized_terms  # noqa: E402


def test_flags_jayeshs_exact_repro():
    assert unrecognized_terms("Italy IT spend", KV) == ["Italy"]


def test_flags_an_unknown_place_even_in_first_position():
    """The bug this guards: the first draft of this function skipped
    whatever word opened the sentence, on the assumption that leading
    capitalisation is always just grammar. It is not, here — this is the
    exact shape of Jayesh's real question, and a first-word-blind version
    let it through unflagged.
    """
    assert unrecognized_terms("Italy spend", KV) != []
    assert "Italy" in unrecognized_terms("Italy spend", KV)


@pytest.mark.parametrize(
    "question",
    [
        "What was our IT spend for Alpine Operations in 2024?",
        "France IT spend",
        "Who are our top suppliers?",
        "Give me an overview",
        "Show me a bar chart of category spend",
        "What was our spend with Demo Group Headquarters?",
        "compare category spend",
        "Break this down by country",
    ],
)
def test_does_not_flag_real_questions_that_have_nothing_unrecognized(question):
    assert unrecognized_terms(question, KV) == [], (
        f"{question!r} -> {unrecognized_terms(question, KV)}"
    )


def test_every_real_entity_and_country_value_never_self_flags():
    """Sweep every real entity/country word against itself, asked as a bare
    leading question — the same shape as Jayesh's repro but with values that
    DO exist. None of these may ever be flagged; this is the false-positive
    guard for the whole feature.
    """
    false_positives = []
    for dimension in ("entity", "country"):
        for value in KV[dimension]:
            question = f"{value.replace('Demo ', '')} spend"
            flagged = unrecognized_terms(question, KV)
            if flagged:
                false_positives.append((question, flagged))
    assert false_positives == [], false_positives


def test_the_pronoun_i_is_never_flagged():
    assert unrecognized_terms("What did I spend on IT?", KV) == []


def test_a_month_name_is_never_flagged():
    assert unrecognized_terms("What was spend since March?", KV) == []


def test_flags_multiple_unrecognized_words_without_duplicates():
    flagged = unrecognized_terms("Italy Elbonia spend Elbonia", KV)
    assert flagged == ["Italy", "Elbonia"]

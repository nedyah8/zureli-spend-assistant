import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nl_parser import parse_question
from spend_query import known_values, load_data

KV = known_values(load_data())


def test_plain_question_is_number_intent():
    result = parse_question("What was our IT and telecom spend for Alpine Operations in 2024?", KV)
    assert result["intent"] == "number"
    assert result["chart_kind"] is None
    assert result["filters"]["entity"] == "Demo Alpine Operations"
    assert result["filters"]["l1"] == "IT and telecom"
    assert result["filters"]["year"] == 2024


def test_chart_keyword_triggers_chart_intent():
    result = parse_question("show me a bar chart of category spend", KV)
    assert result["intent"] == "chart"
    assert result["chart_kind"] == "category_spend"


def test_breakdown_by_country_detected():
    result = parse_question("chart category spend broken down by country", KV)
    assert result["intent"] == "chart"
    assert result["breakdown"] == "country"


def test_breakdown_defaults_to_entity():
    result = parse_question("show me a spend breakdown by category", KV)
    assert result["intent"] == "chart"
    assert result["breakdown"] == "entity"


def test_category_level_2_detected():
    result = parse_question("plot spend by level 2 category", KV)
    assert result["intent"] == "chart"
    assert result["category_level"] == "l2"


def test_category_level_defaults_to_l1():
    result = parse_question("show me a chart of spend by category", KV)
    assert result["category_level"] == "l1"


def test_chart_intent_still_extracts_filters():
    result = parse_question("chart of category spend for Germany in 2025", KV)
    assert result["intent"] == "chart"
    assert result["filters"]["country"] == "Germany"
    assert result["filters"]["year"] == 2025


def test_country_breakdown_phrasing_detected():
    # Task 9 fix 4 (Codex finding): this phrasing correctly triggered chart
    # intent (via the "breakdown" keyword) but silently fell back to
    # breakdown="entity" instead of detecting "country", since the old
    # COUNTRY_BREAKDOWN_KEYWORDS only matched "by country"/"per country".
    result = parse_question("country breakdown of category spend for 2024", KV)
    assert result["intent"] == "chart"
    assert result["breakdown"] == "country"


def test_each_country_phrasing_detected():
    # Task 9 fix 4 (Codex finding): same gap as above, different phrasing.
    result = parse_question("show spend breakdown for each country in 2024", KV)
    assert result["intent"] == "chart"
    assert result["breakdown"] == "country"


def test_each_cluster_phrasing_detected():
    result = parse_question("show spend breakdown for each cluster in 2024", KV)
    assert result["intent"] == "chart"
    assert result["breakdown"] == "cluster"


def test_cluster_breakdown_phrasing_detected():
    result = parse_question("cluster breakdown of category spend for 2024", KV)
    assert result["intent"] == "chart"
    assert result["breakdown"] == "cluster"


def test_bare_bar_keyword_triggers_chart_intent():
    # Final whole-branch review Fix 3: _CHART-CHAT-DESIGN.md lists bare
    # "bar" as a chart trigger; it was missing from CHART_KEYWORDS (only
    # "bar chart"/"bar graph" matched), so this got misrouted to the
    # number-intent path's "I didn't recognise..." caveat.
    result = parse_question("bar of category spend", KV)
    assert result["intent"] == "chart"


def test_split_keyword_triggers_chart_intent():
    # Same gap, "split" — also missing from the approved spec's keyword list.
    result = parse_question("split spend by entity", KV)
    assert result["intent"] == "chart"


def test_show_me_by_country_triggers_chart_intent():
    # "show me ... by" pattern from _CHART-CHAT-DESIGN.md — contains none of
    # the existing substring keywords (chart/graph/plot/bar/split/breakdown/
    # visualise), so needed a dedicated check.
    result = parse_question("show me spend by country", KV)
    assert result["intent"] == "chart"


def test_show_me_category_spend_by_entity_triggers_chart_intent():
    result = parse_question("show me category spend by entity", KV)
    assert result["intent"] == "chart"


def test_by_alone_does_not_make_number_question_a_chart():
    # Regression guard for Fix 3: the word "by" is far too generic to be a
    # blanket chart trigger (it would misfire on almost any question) — the
    # fix specifically targets the "show me X by Y" shape, not any sentence
    # containing "by". This question contains "by" but no "show me" and no
    # other chart keyword, so it must still get intent == "number".
    result = parse_question("What is the total spend by Alpine Operations in 2024?", KV)
    assert result["intent"] == "number"


def test_show_me_by_entity_name_does_not_trigger_chart_intent():
    # Codex follow-up review, Fix A: the original SHOW_ME_BY_PATTERN matched
    # ANY "show me ... by ..." sentence, so this entity-name question was
    # wrongly promoted to chart intent and then silently picked up the
    # chart path's default-year-2025 filter, changing its answer from the
    # established all-years total. "by" here introduces an entity name, not
    # a supported breakdown dimension, so this must stay a number question.
    result = parse_question("show me total spend by Alpine Operations", KV)
    assert result["intent"] == "number"


def test_show_me_by_short_entity_name_does_not_trigger_chart_intent():
    result = parse_question("show me spend by Demo Alpine Operations", KV)
    assert result["intent"] == "number"


def test_show_me_by_supplier_name_does_not_trigger_chart_intent():
    # "supplier" is not one of the parser's supported breakdown dimensions
    # (breakdown only ever resolves to entity/country/cluster), so "by
    # supplier ..." must not trigger chart intent either.
    result = parse_question("show me the total spend by supplier Demo Supplier 001", KV)
    assert result["intent"] != "chart"
    # Task 6: this question names exactly one supplier and no other
    # narrowing filter besides an optional year, so per the drill-down
    # intent's own spec it now correctly routes to "supplier_drilldown"
    # rather than "number" — updated from the pre-Task-6 assertion, which
    # predates the drill-down intent and asserted the only non-chart value
    # that existed at the time.
    assert result["intent"] == "supplier_drilldown"


def test_minibar_does_not_trigger_chart_intent():
    # Codex follow-up review, Fix B: "bar" was a plain substring keyword, so
    # it matched inside unrelated words like "minibar".
    result = parse_question("What did we spend on minibar supplies in 2024?", KV)
    assert result["intent"] == "number"


def test_barrow_operations_does_not_trigger_chart_intent():
    result = parse_question("What did Barrow Operations spend in 2024?", KV)
    assert result["intent"] == "number"


def test_split_payment_does_not_trigger_chart_intent():
    # "split" was a plain substring keyword; "split payment spend" is a real
    # standalone use of the word "split" (not a substring embed like
    # "minibar"), but it isn't a breakdown request — there's no "by" nearby
    # — so it must still fall through to a plain number question.
    result = parse_question("What was the split payment spend in 2024?", KV)
    assert result["intent"] == "number"


def test_bar_and_split_still_trigger_chart_intent_as_whole_words():
    # Regression guard: the Fix B word-boundary/context changes must not
    # break genuine whole-word usage of "bar" and "split by".
    assert parse_question("bar of category spend", KV)["intent"] == "chart"
    assert parse_question("split spend by entity", KV)["intent"] == "chart"


def test_compare_alone_does_not_trigger_chart_intent():
    # Task 9 fix 5 (Codex finding): "compare" used to be a CHART_KEYWORD,
    # correctly triggering chart intent for "compare X and Y" — but
    # _extract_filters() only ever captures the first matching entity, so
    # the second entity in the comparison was silently dropped, giving a
    # chart for just one entity with nothing indicating the comparison was
    # lost. "compare" was removed from CHART_KEYWORDS; this question
    # contains no other chart-signalling word, so it must now fall through
    # to the number-intent path instead of falsely promising a comparison.
    result = parse_question("compare Alpine Operations and UK Operations in 2024", KV)
    assert result["intent"] == "number"


def test_help_keyword_triggers_help_intent():
    result = parse_question("what can you do", KV)
    assert result["intent"] == "help"


def test_overview_keyword_triggers_overview_intent():
    result = parse_question("give me an overview", KV)
    assert result["intent"] == "overview"


def test_overview_intent_carries_filters():
    result = parse_question("give me an overview for Alpine Operations", KV)
    assert result["intent"] == "overview"
    assert result["filters"]["entity"] == "Demo Alpine Operations"


def test_every_parse_result_has_top_n_key():
    result = parse_question("What was our IT and telecom spend for Alpine Operations in 2024?", KV)
    assert "top_n" in result
    assert result["top_n"] is None


def test_top_suppliers_keyword_triggers_chart_intent():
    result = parse_question("who are our top suppliers?", KV)
    assert result["intent"] == "chart"
    assert result["chart_kind"] == "top_suppliers"
    assert result["top_n"] == 15


def test_top_n_suppliers_sets_n():
    result = parse_question("top 5 suppliers", KV)
    assert result["chart_kind"] == "top_suppliers"
    assert result["top_n"] == 5


def test_top_n_suppliers_clamps_to_max():
    result = parse_question("top 200 suppliers", KV)
    assert result["top_n"] == 56


def test_top_n_suppliers_clamps_to_min():
    result = parse_question("top 1 suppliers", KV)
    assert result["top_n"] == 3


def test_biggest_suppliers_phrase_detected():
    result = parse_question("who are our biggest suppliers", KV)
    assert result["chart_kind"] == "top_suppliers"


def test_supplier_alone_triggers_drilldown_intent():
    result = parse_question("tell me about Demo Supplier 025", KV)
    assert result["intent"] == "supplier_drilldown"
    assert result["filters"]["supplier"] == "Demo Supplier 025"


def test_supplier_with_year_still_triggers_drilldown():
    result = parse_question("how much did we spend with Demo Supplier 025 in 2024?", KV)
    assert result["intent"] == "supplier_drilldown"
    assert result["filters"]["year"] == 2024


def test_supplier_with_entity_and_category_does_not_trigger_drilldown():
    # Regression guard: this exact question already has passing coverage in
    # test_app_answer.py (test_negative_total_shows_minus_sign_before_euro_symbol)
    # asserting a specific plain-number answer. Supplier + entity + category
    # together is a precise "give me this one number" question, not a broad
    # "tell me about this supplier" question — it must keep returning the
    # existing "number" intent, not the new drill-down.
    result = parse_question(
        "What did supplier Demo Supplier 052 spend on Utilities for Demo Iberia Distribution?",
        KV,
    )
    assert result["intent"] == "number"


def test_fragmentation_keyword_triggers_chart_intent():
    result = parse_question("show me fragmentation", KV)
    assert result["intent"] == "chart"
    assert result["chart_kind"] == "fragmentation"


def test_supplier_concentration_phrase_detected():
    result = parse_question("what's our supplier concentration", KV)
    assert result["chart_kind"] == "fragmentation"


def test_fragmentation_respects_level_2_keyword():
    result = parse_question("fragmentation at level 2", KV)
    assert result["category_level"] == "l2"

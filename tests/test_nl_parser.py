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

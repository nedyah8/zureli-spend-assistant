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

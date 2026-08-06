import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib


def _reload_app():
    import app  # noqa: F401 — Streamlit script; import executes top-level code once
    return importlib.reload(app)


def test_number_answer_unchanged_for_known_question():
    app = _reload_app()
    result = app.answer("What was our IT and telecom spend for Alpine Operations in 2024?")
    assert "192,988.04" in result
    # Filter order in the "Matched on ..." string follows nl_parser's
    # extraction order (year, entity, country, cluster, l2, l1, supplier),
    # unchanged since before Task 2 — verified against the pre-Task-2 commit
    # (1a32723) to confirm this is the actual, pre-existing output order,
    # not something this task changed.
    assert "Matched on year = 2024, entity = Alpine Operations, category = IT and telecom" in result


def test_no_match_question_gives_honest_caveat():
    app = _reload_app()
    result = app.answer("how much did we spend on Car Fuel")
    assert "I didn't recognise" in result


def test_chart_question_returns_chart_payload():
    app = _reload_app()
    payload = app.answer_payload("show me a bar chart of category spend for 2024")
    assert payload["kind"] == "chart"
    assert payload["figure"] is not None
    assert "2024" in payload["caption"]


def test_number_question_returns_text_payload():
    app = _reload_app()
    payload = app.answer_payload("What was our IT and telecom spend for Alpine Operations in 2024?")
    assert payload["kind"] == "text"
    assert payload["figure"] is None
    assert "192,988.04" in payload["text"]


def test_chart_question_with_zero_matches_falls_back_to_text():
    # NOTE: the task-6 brief's original example question was "chart category
    # spend for Germany in 2099". That doesn't actually exercise the
    # zero-match path: nl_parser._extract_filters only recognises years
    # present in the dataset (2024/2025 — see nl_parser.py:29-32), so an
    # unknown year like 2099 is silently dropped rather than kept as an
    # unmatched filter, leaving just country="Germany", which has real data
    # and returns a non-empty chart. That's pre-existing Task 2 parser
    # behaviour, not something Task 6 changes. Substituted an entity/country
    # pair that has zero overlap in the actual dataset (Baltic Logistics only
    # operates in a different country than Germany) so this test genuinely
    # exercises answer_payload's chart_df.empty fallback.
    app = _reload_app()
    payload = app.answer_payload("chart category spend for Baltic Logistics in Germany")
    assert payload["kind"] == "text"
    assert "nothing" in payload["text"].lower() or "didn't" in payload["text"].lower()

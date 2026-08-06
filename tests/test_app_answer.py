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

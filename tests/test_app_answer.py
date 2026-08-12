import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib

import pandas as pd
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")


def _reload_app():
    import app  # noqa: F401
    module = importlib.reload(app)
    # Streamlit's session_state survives a module reload, so the follow-up
    # memory added 9 Aug 2026 leaks from one test into the next and makes the
    # suite order-dependent. A real user session SHOULD carry that context;
    # a test must not inherit the previous test's question.
    module.st.session_state.last_parse = None
    return module


def test_number_answer_unchanged_for_known_question():
    app = _reload_app()
    result = app.answer("What was our IT and telecom spend for Alpine Operations in 2024?")
    assert "192,988.04" in result
    # Final whole-branch review Fix 1: every displayed total must carry a €
    # (the standing caption already claims EUR and the chart axis already
    # reads "(€)" — the plain-text totals were the one place still bare).
    assert "€192,988.04" in result
    # Filter order in the "Matched on ..." string follows nl_parser's
    # extraction order (year, entity, country, cluster, l2, l1, supplier),
    # unchanged since before Task 2 — verified against the pre-Task-2 commit
    # (1a32723) to confirm this is the actual, pre-existing output order,
    # not something this task changed.
    assert "Matched on year = 2024, entity = Alpine Operations, category = IT and telecom" in result


def test_no_match_question_gives_honest_caveat():
    # A1 (meeting-ready design, Part A1): a zero-filter number question now
    # returns the Overview answer instead of the old apology-paragraph — a
    # deliberate behaviour change, not a regression. See _MEETING-READY-DESIGN.md.
    app = _reload_app()
    result = app.answer("how much did we spend on Car Fuel")
    assert "overall picture" in result.lower()


def test_chart_question_returns_chart_payload():
    app = _reload_app()
    payload = app.answer_payload("show me a bar chart of category spend for 2024")
    assert payload["kind"] == "chart"
    assert payload["figure"] is not None
    assert "2024" in payload["caption"]
    # Final whole-branch review Fix 1: the chart's "Total: ..." text and its
    # caption total must both carry a € — previously only the chart's own
    # axis title said "(€)", contradicting the still-bare totals elsewhere.
    assert "€" in payload["text"]
    assert "€" in payload["caption"]


def test_number_question_returns_text_payload():
    app = _reload_app()
    payload = app.answer_payload("What was our IT and telecom spend for Alpine Operations in 2024?")
    assert payload["kind"] == "text"
    assert payload["figure"] is None
    assert "192,988.04" in payload["text"]


def test_multi_turn_chat_does_not_crash_on_rerun():
    # Reviewer-found bug (Task 6 fix round 1): app.py's history-replay loop
    # calls render_payload_extras() for any past message with a payload, and both
    # append sites always set a real payload — but render_payload used to be
    # defined *below* that loop in the file. Streamlit reruns the whole
    # script top-to-bottom on every interaction, so the first exchange
    # worked (the loop body never runs — history is still empty) but the
    # very next rerun hit render_payload_extras() before its def had executed,
    # raising NameError. A plain module import/reload (like _reload_app()
    # above) can never catch this class of bug: session_state.messages is
    # always empty right after import, so the replay loop's body never
    # actually runs during a bare reload. Only a real simulated rerun with
    # non-empty history — via Streamlit's own AppTest harness — exercises
    # the code path that broke. This scripts a text-answer turn followed by
    # a chart-answer turn (the second run replays the first turn's payload
    # through the history loop) and asserts no exception either time.
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception

    at.chat_input[0].set_value(
        "What was our IT and telecom spend for Alpine Operations in 2024?"
    ).run()
    assert not at.exception

    at.chat_input[0].set_value("show me a bar chart of category spend for 2024").run()
    assert not at.exception


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


def test_nonsense_question_still_gets_honest_overview():
    # A1: gibberish also lands on the Overview fallback, deliberately —
    # distinguishing gibberish from genuine vagueness needs the LLM upgrade
    # this project doesn't have yet, and an overview is a strictly better
    # dead-end than an apology either way.
    app = _reload_app()
    payload = app.answer_payload("asdkjfh qwoeiruqwoe")
    assert payload["kind"] == "overview"
    assert "€" in payload["metrics"][0][1]


def test_chart_breakdown_by_cluster():
    app = _reload_app()
    payload = app.answer_payload("chart category spend by cluster for 2024")
    assert payload["kind"] == "chart"
    assert "cluster" in payload["caption"]


def test_chart_level_2_categories():
    app = _reload_app()
    payload = app.answer_payload("show me a chart of level 2 category spend for 2024")
    assert payload["kind"] == "chart"
    assert "Level 2" in payload["caption"]


def test_unfiltered_chart_defaults_to_latest_year_as_real_filter():
    # Final whole-branch review Fix 2: an unfiltered chart question must now
    # apply the latest year as a REAL filter into category_spend(), not just
    # a display label — restoring _CHART-CHAT-DESIGN.md's spec default
    # (matching the InSight demo's own default focus year) after an earlier
    # fix round (Task 6) left the query aggregating across all years while
    # only fixing the axis label to read "all years". The chart's total must
    # match query_spend(df, year=2025)'s total exactly, not the combined
    # all-years total.
    from spend_query import query_spend

    app = _reload_app()
    latest_year = max(app.kv["year"])
    assert latest_year == 2025

    payload = app.answer_payload("show me a bar chart of category spend")
    assert payload["kind"] == "chart"

    expected_total_text = f"{query_spend(app.df, year=latest_year)['total_net_spend']:,.2f}"
    assert f"€{expected_total_text}" in payload["text"]
    assert "2025" in payload["caption"]
    assert "2025" in payload["figure"].layout.xaxis.title.text

    # Must NOT be the old combined-all-years total — guards against
    # silently regressing back to the pre-fix behaviour.
    all_years_total_text = f"{query_spend(app.df)['total_net_spend']:,.2f}"
    assert all_years_total_text != expected_total_text
    assert all_years_total_text not in payload["text"]


def test_west_cluster_number_question_unchanged():
    # Cross-checked earlier in the project — must not regress (see _HANDOFF.md).
    app = _reload_app()
    payload = app.answer_payload("What did the West cluster spend in 2025?")
    assert "1,267,819.75" in payload["text"]


def test_negative_total_shows_minus_sign_before_euro_symbol():
    # Codex follow-up review, Fix D: the previous f"€{total}" style produced
    # "€-7,637.65" for a negative total instead of the more natural
    # "-€7,637.65". This filter combination (real sample data) has a
    # genuinely negative total.
    app = _reload_app()
    payload = app.answer_payload(
        "What did supplier Demo Supplier 052 spend on Utilities for Demo Iberia "
        "Distribution?"
    )
    assert payload["kind"] == "text"
    assert "-€7,637.65" in payload["text"]
    assert "€-7,637.65" not in payload["text"]


def test_format_currency_helper_puts_minus_before_euro():
    app = _reload_app()
    assert app.format_currency(-7637.65) == "-€7,637.65"
    assert app.format_currency(7637.65) == "€7,637.65"
    assert app.format_currency(0) == "€0.00"


def test_overview_intent_returns_overview_payload():
    app = _reload_app()
    payload = app.answer_payload("give me an overview")
    assert payload["kind"] == "overview"
    assert len(payload["metrics"]) == 4
    assert payload["show_chips"] is True


def test_overview_net_spend_matches_query_spend():
    from spend_query import query_spend

    app = _reload_app()
    payload = app.answer_payload("give me an overview")
    reference = query_spend(app.df, year=2025)
    net_spend_metric = payload["metrics"][0]
    assert reference["total_net_spend"] > 0
    assert f"{reference['total_net_spend']:,.2f}" in net_spend_metric[1]


def test_vague_question_falls_back_to_overview_not_caveat():
    app = _reload_app()
    payload = app.answer_payload("how much did we spend on Car Fuel")
    assert payload["kind"] == "overview"
    assert "overall picture" in payload["text"].lower()


def test_help_intent_returns_text_with_chips():
    app = _reload_app()
    payload = app.answer_payload("what can you do")
    assert payload["kind"] == "text"
    assert payload["show_chips"] is True


def test_suggestion_chips_present_on_empty_state():
    # Confirmed against the installed Streamlit build: AppTest exposes
    # st.pills widgets via `at.pills` (a WidgetList), NOT `at.get("pills")`
    # (which returns empty) — verified directly with a throwaway AppTest
    # script before writing this test, not assumed from the chat_input
    # precedent elsewhere in this file.
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception
    assert len(at.pills) == 1
    assert at.pills[0].options == [
        "Give me an overview",
        "Show me a bar chart of category spend",
        "Who are our top suppliers?",
    ]


def test_clicking_a_chip_submits_it_as_a_question():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    at.pills[0].set_value("Give me an overview").run()
    assert not at.exception
    assert len(at.session_state.messages) == 2
    assert at.session_state.messages[0]["content"] == "Give me an overview"


def test_top_suppliers_question_returns_chart_payload():
    app = _reload_app()
    payload = app.answer_payload("who are our top suppliers?")
    assert payload["kind"] == "chart"
    assert "Top 15 suppliers" in payload["text"]
    assert "€" in payload["caption"]


def test_top_n_suppliers_question_respects_n():
    app = _reload_app()
    payload = app.answer_payload("top 5 suppliers")
    assert "Top 5" in payload["text"]


def test_supplier_question_returns_drilldown_payload():
    app = _reload_app()
    payload = app.answer_payload("tell me about Demo Supplier 025")
    assert payload["kind"] == "supplier_drilldown"
    assert len(payload["metrics"]) == 4
    assert "entity_figure" in payload
    assert "category_figure" in payload


def test_supplier_with_entity_and_category_still_returns_plain_number():
    # Regression guard mirroring test_nl_parser.py's equivalent test —
    # confirms app.py's dispatch preserves the existing passing behaviour
    # for this exact question (test_negative_total_shows_minus_sign_before_euro_symbol).
    app = _reload_app()
    payload = app.answer_payload(
        "What did supplier Demo Supplier 052 spend on Utilities for Demo Iberia Distribution?"
    )
    assert payload["kind"] == "text"
    assert "-€7,637.65" in payload["text"]


def test_fragmentation_question_returns_fragmentation_payload():
    app = _reload_app()
    payload = app.answer_payload("show me fragmentation")
    assert payload["kind"] == "fragmentation"
    assert len(payload["metrics"]) == 4
    assert "figure" in payload
    assert "table" in payload
    assert "Top-3" in payload["caption"] or "Top 3" in payload["caption"]


def test_fragmentation_text_does_not_duplicate_year():
    app = _reload_app()
    payload = app.answer_payload("show me fragmentation")
    year_str = str(max(app.kv["year"]))
    assert payload["text"].count(year_str) == 1


def test_pareto_question_returns_chart_payload():
    app = _reload_app()
    payload = app.answer_payload("show me the pareto chart")
    assert payload["kind"] == "chart"
    assert "€" in payload["caption"]


def test_category_comparison_question_returns_table_payload():
    app = _reload_app()
    payload = app.answer_payload("compare category spend")
    assert payload["kind"] == "category_comparison"
    assert "table" in payload


def test_intensity_question_returns_chart_payload():
    app = _reload_app()
    payload = app.answer_payload("show me spend intensity by entity and category")
    assert payload["kind"] == "chart"
    assert "€" in payload["caption"]


def test_raw_data_question_returns_table_payload():
    app = _reload_app()
    payload = app.answer_payload("show me the raw data for Germany in 2024")
    assert payload["kind"] == "raw_data"
    assert "table" in payload
    assert "csv_bytes" in payload


def test_raw_data_preview_caps_at_50_rows_and_notes_truncation():
    app = _reload_app()
    payload = app.answer_payload("show me the raw data")
    assert len(payload["table"]) <= 50
    if len(app.df) > 50:
        assert "50" in payload["text"]


def test_two_raw_data_payloads_in_history_get_distinct_download_button_keys():
    # Task 12 review finding (fix round 1): the whole reason render_payload_extras()
    # gained a key_suffix parameter is that st.download_button requires a
    # stable, unique widget key — reuse the same key across two widgets in
    # the same run and Streamlit raises a duplicate-widget-ID error. A single
    # raw_data question never exercises this: the risk only appears once a
    # SECOND raw_data answer lands in session_state.messages and the history-
    # replay loop (app.py's `for i, message in enumerate(...)` loop) renders
    # both past raw_data payloads' download buttons in the same script pass.
    # test_multi_turn_chat_does_not_crash_on_rerun (above) covers the
    # analogous class of bug for render_payload's definition-order NameError,
    # but its two turns are a text question and a chart question — neither
    # has a download button, so it does not cover this one. Mirrors the
    # AppTest scenario already run ad hoc during Task 12 development and
    # confirmed to pass (report's "Additional verification" section) — this
    # commits that same scenario as permanent coverage.
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception

    at.chat_input[0].set_value("show me the raw data").run()
    assert not at.exception

    at.chat_input[0].set_value("show me the raw data for Germany").run()
    assert not at.exception

    download_buttons = at.get("download_button")
    assert len(download_buttons) == 2
    keys = [b.key for b in download_buttons]
    assert len(set(keys)) == 2, f"expected distinct keys, got {keys}"


def test_two_chart_payloads_in_history_do_not_raise_duplicate_element_id():
    # Caught live by real manual testing (not by any automated pass in this
    # project's build): render_payload_extras()'s plotly_chart calls never got the
    # same key_suffix treatment the download_button fix (Task 12) applied.
    # Streamlit assigns each st.plotly_chart(...) call an auto-generated
    # element ID from its type + parameters; two calls with the same figure
    # content in the same script run collide and raise
    # StreamlitDuplicateElementId. A single chart question never exercises
    # this — the risk only appears once a SECOND chart answer with the same
    # underlying figure lands in session_state.messages and the history-
    # replay loop renders both in the same pass (the same shape of bug as
    # test_two_raw_data_payloads_in_history_get_distinct_download_button_keys
    # above, for a different widget type entirely).
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception

    at.chat_input[0].set_value("show me a bar chart of category spend").run()
    assert not at.exception

    at.chat_input[0].set_value("show me a bar chart of category spend").run()
    assert not at.exception


def test_fragmentation_suppliers_in_scope_kpi_matches_table_with_null_supplier(monkeypatch):
    # Final whole-branch review Finding 2: fragmentation()'s own by_supplier
    # groupby (chart_query.py) already fills null Supplier name with
    # "(unspecified)" before counting, but app.py's "Suppliers in scope" KPI
    # computed supplier_count = filter_df(...)["Supplier name"].nunique()
    # directly, unguarded — nunique()'s default dropna=True silently drops a
    # null Supplier name row, so the KPI could show one fewer supplier than
    # fragmentation()'s own table actually lists. Uses a synthetic
    # single-category frame (monkeypatched onto app.df) so a null Supplier
    # name is guaranteed present, rather than relying on the real sample data
    # (already confirmed to have zero null Supplier name values).
    app = _reload_app()
    synthetic = pd.DataFrame(
        {
            "Entity": ["Demo Alpine Operations"] * 3,
            "Country": ["Germany"] * 3,
            "Cluster": ["West"] * 3,
            "Year": [2024, 2024, 2024],
            "L1": ["IT and telecom"] * 3,
            "L2": ["Software"] * 3,
            "Supplier name": ["Demo Supplier X", "Demo Supplier Y", None],
            "Net spend": [100.0, 50.0, 25.0],
        }
    )
    monkeypatch.setattr(app, "df", synthetic)

    chart_filters = {"year": 2024}
    frag_df = app.fragmentation(synthetic, level="l1", **chart_filters)
    # The table's own supplier_count column already guards nulls (fillna
    # inside fragmentation() itself) — this is the ground truth the KPI must
    # match. Only one category here, so the table total is that category's
    # supplier_count.
    table_supplier_count = int(frag_df["supplier_count"].sum())
    assert table_supplier_count == 3  # X, Y, and the null bucket

    kpi_supplier_count = app._scoped_supplier_count(chart_filters)
    assert kpi_supplier_count == table_supplier_count


def test_no_demo_prefix_leaks_in_matched_on_text_with_entity_and_supplier():
    # Final whole-branch review Finding 3: format_filters() only stripped
    # "Demo " for key == "entity", never for key == "supplier" — violating
    # this project's own Global Constraint (_MEETING-READY-PLAN.md line 15:
    # "Entity/supplier names always display with the `Demo ` prefix
    # stripped"). Real repro: a question naming both an entity and a
    # supplier used to leave "supplier = Demo Supplier 052" with the prefix
    # intact right next to an already-stripped "entity = Iberia
    # Distribution".
    app = _reload_app()
    payload = app.answer_payload(
        "What did supplier Demo Supplier 052 spend on Utilities for Demo Iberia Distribution?"
    )
    assert "Demo " not in payload["text"], payload["text"]
    assert "supplier = Supplier 052" in payload["text"]


def test_scoped_year_default_finds_2024_only_data_for_entity_and_supplier_scope():
    # Final whole-branch review Finding 4: every chart dispatch block that
    # defaults an unfiltered-year question used max(kv["year"]) — the latest
    # year in the WHOLE dataset — instead of the latest year present WITHIN
    # the filtered scope, as overview_query.overview() and this file's own
    # category_comparison()/fragmentation() docstrings say the default
    # should be. Real dead-end: entity="Demo Alpine Operations" +
    # supplier="Demo Supplier 019" has data only in 2024 (one of 42 real
    # entity+supplier combos with this exact shape — see
    # chart_query.category_comparison's own docstring, which already
    # documents this combo). A category-comparison question for that scope
    # used to wrongly resolve to year=2025 and report zero rows, even though
    # the identical scope's overview question correctly found 2024 data.
    app = _reload_app()

    broken_before_fix = app.answer_payload(
        "category comparison for Alpine Operations and Demo Supplier 019"
    )
    assert broken_before_fix["kind"] == "category_comparison"
    assert not broken_before_fix["table"].empty
    assert (broken_before_fix["table"].filter(like="2024").columns.size) >= 1
    assert "2024" in broken_before_fix["text"]
    assert "2025" not in broken_before_fix["text"]


def test_resolve_chart_year_falls_back_to_global_latest_when_scope_is_empty():
    # The scope-latest-year resolution must not crash or silently misbehave
    # when a scope has NO rows in any year — falls back to the dataset's own
    # latest year, same as before, so the existing "zero rows" honest-empty
    # message still fires downstream instead of a KeyError/IndexError on an
    # empty scoped frame.
    app = _reload_app()
    impossible_filters = {"entity": "Demo Alpine Operations", "country": "France"}
    resolved = app._resolve_chart_year(impossible_filters, app.df)
    assert resolved["year"] == max(app.kv["year"])


def test_resolve_chart_year_unchanged_for_unfiltered_questions():
    # Non-regression half of Finding 4's fix: an unfiltered scope's "latest
    # year present in scope" must equal "latest year in the whole dataset" —
    # same answer, just computed the more general way. Guards against the
    # helper accidentally changing behaviour for the common, already-correct
    # case.
    from spend_query import query_spend

    app = _reload_app()
    latest_year = max(app.kv["year"])

    payload = app.answer_payload("show me a bar chart of category spend")
    assert payload["kind"] == "chart"
    expected_total_text = f"{query_spend(app.df, year=latest_year)['total_net_spend']:,.2f}"
    assert f"€{expected_total_text}" in payload["text"]


def test_top_suppliers_caption_has_no_false_clamp_note():
    # Final whole-branch review Finding 5: the "(clamped from N)" caption
    # note fired whenever actual_n != requested_n — true whenever a scope
    # simply has fewer suppliers than the unrequested default of 15, not
    # just on a genuine clamp-to-[3,56] event. Real repro: "top suppliers for
    # Alpine Operations in Facilities" has only 8 suppliers in scope, so it
    # used to say "Top 8 suppliers (clamped from 15)..." even though nothing
    # was ever clamped — 15 is just nl_parser's unrequested default. The
    # caption must never say "clamped" here.
    app = _reload_app()
    payload = app.answer_payload("top suppliers for Alpine Operations in Facilities")
    assert payload["kind"] == "chart"
    assert "clamped" not in payload["caption"].lower()
    assert payload["caption"].startswith("Top 8 suppliers by")
    assert "(clamped" not in payload["caption"]


def test_top_suppliers_caption_discloses_ranking_year():
    # Minor fix 1: Task 14 changed ranking to be by the latest/focus year
    # ALONE (both years still plotted), but the caption read "Top 15
    # suppliers by net spend, 2024 vs 2025 — ..." as if ranking spanned both
    # years. The caption must name the actual rank year explicitly.
    app = _reload_app()
    payload = app.answer_payload("who are our top suppliers?")
    assert payload["kind"] == "chart"
    assert "by 2025 net spend" in payload["caption"]
    assert "2024 vs 2025" in payload["caption"]

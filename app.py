import streamlit as st

from chart_query import category_spend
from chart_render import build_category_spend_figure
from nl_parser import parse_question
from spend_query import known_values, load_data, query_spend

st.set_page_config(page_title="Zureli spend assistant", layout="centered")

BRAND = "#17343C"
MUTED = "#8A8F94"
BORDER = "#E8E9EA"
AVATARS = {"user": ":material/person:", "assistant": ":material/insights:"}

st.markdown(
    f"""
    <div style="display:flex;align-items:center;padding:32px 0 16px;">
        <span style="font-size:20px;font-weight:700;color:{BRAND};letter-spacing:-0.01em;">zureli.</span>
        <span style="margin-left:auto;font-size:11px;font-weight:600;letter-spacing:0.04em;
                     text-transform:uppercase;color:{MUTED};border:1px solid {BORDER};
                     border-radius:999px;padding:4px 12px;">Demo data</span>
    </div>
    <hr style="border:none;border-top:1px solid {BORDER};margin:0 0 32px;">
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def get_data():
    df = load_data()
    return df, known_values(df)


df, kv = get_data()

if "messages" not in st.session_state:
    st.session_state.messages = []

LABELS = {
    "entity": "entity",
    "country": "country",
    "cluster": "cluster",
    "year": "year",
    "l1": "category",
    "l2": "sub-category",
    "supplier": "supplier",
}


def format_filters(filters: dict) -> str:
    parts = []
    for key, value in filters.items():
        display = value.replace("Demo ", "") if key == "entity" else value
        parts.append(f"{LABELS[key]} = {display}")
    return ", ".join(parts)


def format_currency(value: float) -> str:
    """Format a spend total as euros, with a leading minus sign before the €
    for negative values (e.g. -7637.65 -> "-€7,637.65") rather than after it
    (Codex follow-up review, Fix D). The previous f"€{total}" style produced
    "€-7,637.65" for negative totals — technically readable but not how
    currency-negative amounts are normally written. Real negative filtered
    totals exist in the sample data (e.g. supplier="Demo Supplier 052",
    entity="Demo Iberia Distribution", l1="Utilities" nets to -7,637.65)."""
    magnitude = f"{abs(value):,.2f}"
    return f"-€{magnitude}" if value < 0 else f"€{magnitude}"


def answer_payload(question: str) -> dict:
    parsed = parse_question(question, kv)
    filters = parsed["filters"]

    if parsed["intent"] == "chart":
        # Default an unfiltered chart question to the latest year present in
        # the data, applied as a REAL filter passed into category_spend() —
        # not just a display label. This restores _CHART-CHAT-DESIGN.md's
        # spec ("unfiltered chart → the latest year present in the data",
        # matching the InSight demo's own default focus year), which an
        # earlier fix round (Task 6) had only half-fixed: it made the axis
        # label honest ("all years") instead of restoring this filter, so an
        # unfiltered chart still silently combined every year's data (final
        # whole-branch review, Fix 2). Chart-path only — query_spend()'s own
        # unfiltered behaviour (sum across all rows/years) is unchanged.
        if "year" in filters:
            chart_filters = dict(filters)
        else:
            chart_filters = {"year": max(kv["year"]), **filters}
        chart_df = category_spend(
            df, level=parsed["category_level"], breakdown=parsed["breakdown"], **chart_filters
        )
        if chart_df.empty:
            return {
                "kind": "text",
                "text": (
                    "I didn't find anything matching that for a chart — "
                    f"{format_filters(chart_filters)} returned no rows."
                ),
                "figure": None,
                "caption": None,
            }
        # chart_filters always carries a year now (either the one the user
        # named, or the latest-year default above), so this label is true by
        # construction — the query itself was restricted to it, not just the
        # display text.
        year_label = chart_filters["year"]
        fig = build_category_spend_figure(chart_df, year_label=year_label)
        # Sum the raw per-segment values first, then round once — matching
        # query_spend()'s sum-then-round pattern exactly, so the chart's
        # displayed total can never diverge from the equivalent number
        # answer purely because of rounding order (Task 9 fix 1).
        total_value = round(chart_df["net_spend"].sum(), 2)
        total = format_currency(total_value)
        level_label = "Level 1" if parsed["category_level"] == "l1" else "Level 2"
        filter_text = format_filters(chart_filters)
        caption = (
            f"Matched on {filter_text}, broken down by {parsed['breakdown']} "
            f"({level_label} categories) — {chart_df['category'].nunique()} categories, "
            f"total {total}."
        )
        return {"kind": "chart", "text": f"Total: {total}", "figure": fig, "caption": caption}

    result = query_spend(df, **filters)
    total = format_currency(result["total_net_spend"])

    if not filters:
        sample_entities = ", ".join(e.replace("Demo ", "") for e in kv["entity"][:3])
        sample_categories = ", ".join(kv["l1"][:4])
        text = (
            f"I didn't recognise a specific entity, country, category, or year in that "
            f"question, so I can't narrow it down — the total across all "
            f"{result['row_count']} rows is **{total}**.\n\n"
            f"Try mentioning something like an entity ({sample_entities}, ...), "
            f"a category ({sample_categories}, ...), or a year (2024 or 2025)."
        )
    else:
        row_word = "row" if result["row_count"] == 1 else "rows"
        text = (
            f"Matched on {format_filters(filters)} — **{total}** "
            f"across {result['row_count']} spend {row_word}."
        )
    return {"kind": "text", "text": text, "figure": None, "caption": None}


def answer(question: str) -> str:
    return answer_payload(question)["text"]


def render_payload(container, payload: dict) -> None:
    container.markdown(payload["text"])
    if payload["kind"] == "chart":
        container.plotly_chart(payload["figure"], use_container_width=True)
        container.caption(payload["caption"])


# render_payload must be defined above this point: Streamlit re-executes the
# whole script top-to-bottom on every rerun, and the history-replay loop
# below calls render_payload() for any past message that has a payload —
# which every assistant turn does, from the very first exchange onward. A
# definition below the loop worked on the *first* run (loop body never
# executes because history is still empty) but raised NameError on every
# rerun after that — i.e. on the user's second message. Confirmed fixed via
# tests/test_app_answer.py::test_multi_turn_chat_does_not_crash (AppTest,
# scripts two chat turns and asserts no exception either time).

if not st.session_state.messages:
    st.markdown(
        f"<div style='text-align:center;padding:40px 0 32px;'>"
        f"<p style='font-size:32px;font-weight:700;color:{BRAND};margin:0;"
        f"letter-spacing:-0.01em;'>Ask about your spend</p></div>",
        unsafe_allow_html=True,
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar=AVATARS[message["role"]]):
        if message.get("payload"):
            render_payload(st, message["payload"])
        else:
            st.markdown(message["content"])

prompt = st.chat_input("What was our IT and telecom spend for Alpine Operations in 2024?")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt, "payload": None})
    with st.chat_message("user", avatar=AVATARS["user"]):
        st.markdown(prompt)

    payload = answer_payload(prompt)
    st.session_state.messages.append(
        {"role": "assistant", "content": payload["text"], "payload": payload}
    )
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        render_payload(st, payload)

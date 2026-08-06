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
    <div style="display:flex;align-items:baseline;gap:12px;padding:32px 0 16px;">
        <span style="font-size:20px;font-weight:700;color:{BRAND};letter-spacing:-0.01em;">zureli.</span>
        <span style="font-size:13px;color:{MUTED};">Spend assistant — prototype</span>
    </div>
    <hr style="border:none;border-top:1px solid {BORDER};margin:0 0 32px;">
    """,
    unsafe_allow_html=True,
)

st.caption(
    "Prototype running on a synthetic demo dataset (sample_spend_data.csv), not real "
    "client data — see _HANDOFF.md. The sample file doesn't specify a currency, so "
    "figures below are shown as plain numbers."
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


def answer_payload(question: str) -> dict:
    parsed = parse_question(question, kv)
    filters = parsed["filters"]

    if parsed["intent"] == "chart":
        chart_df = category_spend(
            df, level=parsed["category_level"], breakdown=parsed["breakdown"], **filters
        )
        if chart_df.empty:
            return {
                "kind": "text",
                "text": (
                    "I didn't find anything matching that for a chart — "
                    f"{format_filters(filters) if filters else 'no filters recognised'} "
                    "returned no rows."
                ),
                "figure": None,
                "caption": None,
            }
        # Only claim a specific year in the chart/caption when the query was
        # actually restricted to one — category_spend() aggregates across
        # ALL years in the data when no year filter is present, so defaulting
        # this to the latest year for display would show a real total under
        # a false year label (reviewer-found bug, Task 6 fix round 1).
        year_label = filters["year"] if "year" in filters else "all years"
        fig = build_category_spend_figure(chart_df, year_label=year_label)
        total = f"{chart_df['net_spend'].sum():,.2f}"
        level_label = "Level 1" if parsed["category_level"] == "l1" else "Level 2"
        filter_text = format_filters(filters) if filters else "all years (no filters recognised)"
        caption = (
            f"Matched on {filter_text}, broken down by {parsed['breakdown']} "
            f"({level_label} categories) — {chart_df['category'].nunique()} categories, "
            f"total {total}."
        )
        return {"kind": "chart", "text": f"Total: {total}", "figure": fig, "caption": caption}

    result = query_spend(df, **filters)
    total = f"{result['total_net_spend']:,.2f}"

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
        f"<p style='font-size:32px;font-weight:700;color:{BRAND};margin:0 0 8px;"
        f"letter-spacing:-0.01em;'>Ask about your spend</p>"
        f"<p style='font-size:15px;color:{MUTED};margin:0;'>"
        f"Type a question the way you'd ask a colleague.</p></div>",
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

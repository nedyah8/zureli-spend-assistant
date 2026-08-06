import streamlit as st

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
        st.markdown(message["content"])

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


def answer(question: str) -> str:
    parsed = parse_question(question, kv)
    filters = parsed["filters"]

    if parsed["intent"] == "chart":
        return "[[chart]] placeholder — rendered as a real chart in Task 6"

    result = query_spend(df, **filters)
    total = f"{result['total_net_spend']:,.2f}"

    if not filters:
        sample_entities = ", ".join(e.replace("Demo ", "") for e in kv["entity"][:3])
        sample_categories = ", ".join(kv["l1"][:4])
        return (
            f"I didn't recognise a specific entity, country, category, or year in that "
            f"question, so I can't narrow it down — the total across all "
            f"{result['row_count']} rows is **{total}**.\n\n"
            f"Try mentioning something like an entity ({sample_entities}, ...), "
            f"a category ({sample_categories}, ...), or a year (2024 or 2025)."
        )

    row_word = "row" if result["row_count"] == 1 else "rows"
    return (
        f"Matched on {format_filters(filters)} — **{total}** "
        f"across {result['row_count']} spend {row_word}."
    )


prompt = st.chat_input("What was our IT and telecom spend for Alpine Operations in 2024?")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=AVATARS["user"]):
        st.markdown(prompt)

    response = answer(prompt)
    st.session_state.messages.append({"role": "assistant", "content": response})
    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        st.markdown(response)

import streamlit as st

from chart_query import category_spend
from chart_render import build_category_spend_figure
from nl_parser import parse_question
from overview_query import overview
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


def render_kpi_row(container, metrics: list[tuple[str, str, str | None]]) -> None:
    """metrics: list of (label, value, delta) tuples; delta may be None."""
    cols = container.columns(len(metrics))
    for col, (label, value, delta) in zip(cols, metrics):
        col.metric(label, value, delta=delta)


def render_callouts(container, callouts: list[dict]) -> None:
    """callouts: list of {label, value, detail} dicts, one bordered card each."""
    cols = container.columns(len(callouts))
    for col, callout in zip(cols, callouts):
        box = col.container(border=True)
        box.caption(callout["label"])
        box.markdown(f"**{callout['value']}**")
        box.caption(callout["detail"])


HELP_TEXT = (
    "I can answer questions about spend by entity, category, country, cluster, "
    "year or supplier — as a number, a category chart, top suppliers, "
    "fragmentation, or an overall overview.\n\nTry one of these, or ask your own:"
)


def build_help_payload() -> dict:
    return {"kind": "text", "text": HELP_TEXT, "figure": None, "caption": None, "show_chips": True}


def build_overview_payload(filters: dict, prefix: str = "") -> dict:
    stats = overview(df, **filters)
    if stats["year"] is None:
        filter_text = format_filters(filters) if filters else "the data"
        return {
            "kind": "text",
            "text": f"I didn't find anything matching that for an overview — {filter_text} returned no rows.",
            "figure": None, "caption": None, "show_chips": True,
        }

    net_spend_str = format_currency(stats["net_spend"])
    delta = f"{stats['yoy_pct']:+.1f}% vs {stats['prior_year']}" if stats["yoy_pct"] is not None else None
    metrics = [
        (f"Net spend {stats['year']}", net_spend_str, delta),
        ("Entities", str(stats["entity_count"]), None),
        ("Suppliers", str(stats["supplier_count"]), None),
        ("Spend rows", str(stats["row_count"]), None),
    ]

    callouts = []
    if stats["largest_category"]:
        callouts.append({
            "label": "Largest category",
            "value": stats["largest_category"]["name"],
            "detail": f"{format_currency(stats['largest_category']['net_spend'])} in {stats['year']}",
        })
    if stats["fastest_growing_category"]:
        callouts.append({
            "label": "Fastest category growth",
            "value": stats["fastest_growing_category"]["name"],
            "detail": f"{stats['fastest_growing_category']['growth_pct']:+.1f}% vs {stats['prior_year']}",
        })
    if stats["top10_concentration_pct"] is not None:
        largest_supplier_name = stats["largest_supplier"]["name"].replace("Demo ", "")
        callouts.append({
            "label": "Supplier concentration",
            "value": f"Top 10 = {stats['top10_concentration_pct']:.1f}%",
            "detail": f"Largest supplier: {largest_supplier_name}",
        })

    filter_text = format_filters(filters) if filters else "all data"
    text = f"{prefix}Overview for {filter_text}, {stats['year']}."
    return {
        "kind": "overview", "text": text, "metrics": metrics, "callouts": callouts,
        "show_chips": True,
    }


def answer_payload(question: str) -> dict:
    parsed = parse_question(question, kv)
    filters = parsed["filters"]

    if parsed["intent"] == "help":
        return build_help_payload()

    if parsed["intent"] == "overview":
        return build_overview_payload(filters)

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
                "show_chips": False,
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
        return build_overview_payload(
            {},
            prefix=(
                "Here's the overall picture — ask about any entity, category, "
                "country or year to go deeper.\n\n"
            ),
        )

    row_word = "row" if result["row_count"] == 1 else "rows"
    text = (
        f"Matched on {format_filters(filters)} — **{total}** "
        f"across {result['row_count']} spend {row_word}."
    )
    return {"kind": "text", "text": text, "figure": None, "caption": None, "show_chips": False}


def answer(question: str) -> str:
    return answer_payload(question)["text"]


def render_payload(container, payload: dict) -> None:
    container.markdown(payload["text"])
    if payload["kind"] == "chart":
        container.plotly_chart(payload["figure"], use_container_width=True)
        container.caption(payload["caption"])
    elif payload["kind"] == "overview":
        render_kpi_row(container, payload["metrics"])
        render_callouts(container, payload["callouts"])


# render_payload must be defined above this point: Streamlit re-executes the
# whole script top-to-bottom on every rerun, and the history-replay loop
# below calls render_payload() for any past message that has a payload —
# which every assistant turn does, from the very first exchange onward. A
# definition below the loop worked on the *first* run (loop body never
# executes because history is still empty) but raised NameError on every
# rerun after that — i.e. on the user's second message. Confirmed fixed via
# tests/test_app_answer.py::test_multi_turn_chat_does_not_crash (AppTest,
# scripts two chat turns and asserts no exception either time).

PLACEHOLDER = "What was our IT and telecom spend for Alpine Operations in 2024?"

if not st.session_state.messages:
    # Empty state: a centered "hero" layout, matching the home screen of the
    # chat products this is modelled on (Claude, ChatGPT, Manus) — a large
    # heading with the input directly beneath it, roughly centered in the
    # viewport, rather than pinned to the bottom of an empty page.
    #
    # st.chat_input() only pins to the page bottom when called at the root
    # level with no wrapping container (confirmed against the installed
    # Streamlit source, elements/widgets/chat.py) — nested inside
    # st.container(), it renders inline instead, wherever that container
    # sits in the page flow. That's what makes this layout possible at all.
    st.markdown(
        f"<div style='text-align:center;padding:18vh 0 32px;'>"
        f"<p style='font-size:44px;font-weight:700;color:{BRAND};margin:0;"
        f"letter-spacing:-0.01em;'>Ask about your spend</p></div>",
        unsafe_allow_html=True,
    )
    with st.container():
        prompt = st.chat_input(PLACEHOLDER)
else:
    # Conversation state: full history, input pinned to the bottom — the
    # standard chat layout once there's something to scroll.
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar=AVATARS[message["role"]]):
            if message.get("payload"):
                render_payload(st, message["payload"])
            else:
                st.markdown(message["content"])
    prompt = st.chat_input(PLACEHOLDER)

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt, "payload": None})
    payload = answer_payload(prompt)
    st.session_state.messages.append(
        {"role": "assistant", "content": payload["text"], "payload": payload}
    )
    # Rerun rather than render the new exchange inline here: on the very
    # first message, this branch was reached via the empty-state layout
    # above (centered heading + centered input) — rendering the exchange
    # directly below that would leave the centered layout stuck on screen
    # underneath a real conversation. Rerunning re-executes the script with
    # messages now non-empty, so it takes the conversation-state branch
    # instead and renders cleanly (history loop + bottom-pinned input) —
    # confirmed via a real two-question run in the browser, not assumed.
    st.rerun()

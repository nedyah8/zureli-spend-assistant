import re
import time
from html import escape

import pandas as pd
import streamlit as st

from chart_query import category_spend
from chart_render import build_category_spend_figure
from chart_query import top_suppliers
from chart_render import build_top_suppliers_figure
from chart_query import supplier_drilldown
from chart_render import build_supplier_drilldown_figures
from chart_query import fragmentation
from chart_render import build_fragmentation_figure
from chart_query import overall_concentration
from chart_render import build_concentration_figure
from chart_query import category_comparison, entity_category_intensity
from chart_render import build_intensity_heatmap
from chart_query import raw_filtered_rows
from nl_parser import parse_question
from overview_query import overview
from spend_query import filter_df, known_values, load_data, query_spend

st.set_page_config(page_title="Zureli spend assistant", layout="wide")

BRAND = "#17343C"
MUTED = "#8A8F94"
BORDER = "#E8E9EA"
# Reuses .streamlit/config.toml's secondaryBackgroundColor rather than a new
# hex value, so the assistant bubble matches an already-established token.
BUBBLE_GREY = "#F5F5F6"

# Content-width cap for `layout="wide"`, via CSS max-width rather than the
# st.columns([1, 14, 1]) trick _MEETING-READY-DESIGN.md Part E also names as
# an option ("columns trick or CSS max-width"). CSS was also required to keep
# st.chat_input()'s root-level auto-pin-to-bottom working: that behaviour only
# applies when chat_input is called at the true script root, not inside a
# st.columns() column, which the columns trick would have required.
st.markdown(
    """
    <style>
    [data-testid="stMainBlockContainer"],
    [data-testid="stBottomBlockContainer"] {
        /* max-width alone left the KPI row / charts barely wider than the
           old centered cap: `layout="wide"` ships its own ~80px left/right
           padding INSIDE the block container's box, so a max-width of 950px
           was rendering only ~790px of actual usable content (confirmed via
           getComputedStyle: mainPadding was "96px 80px 16px", i.e. 160px of
           the 950px cap was going to padding, not content). Overriding
           padding-left/right down to 24px on top of a 1000px cap gets the
           rendered content column to ~950px, matching Part E's target and
           close to the InSight demo's own ~1000px chart width — confirmed
           via DOM measurement after the change, not assumed.
           padding-top/padding-bottom are left untouched (only the two
           longhand properties below are set, not the shorthand). */
        max-width: 1000px;
        padding-left: 24px;
        padding-right: 24px;
        margin-left: auto;
        margin-right: auto;
    }
    /* Chat bubble redesign: an earlier attempt (Task 13 Step 5) tried to
       right-align Streamlit's own st.chat_message() DOM via CSS override and
       was reverted — the grey background paints on the outer message row,
       not the content div, so right-aligning only the text left a full-width
       grey bar behind it. Rendering the bubbles as plain HTML here (instead
       of relying on st.chat_message()'s fixed DOM) avoids that entirely:
       these classes are applied to markup this app controls directly. */
    .msg-row { margin-bottom: 4px; }
    /* The 75% cap belongs on the flex ITEM (this wrapper), not on the bubble
       inside it. Putting it on the bubble created a circular sizing rule: a
       flex item shrinks to fit its content, so the bubble asked for 75% of a
       width that was itself derived from the bubble — measured live at 65px
       for the message "IT Spend" inside a 952px row, which forced a wrap
       mid-word ("Spen"/"d"). Capping the wrapper against the full row width
       lets short messages size naturally to one line and long ones wrap at
       75% of the row, which is what the design called for. */
    .msg-row > div { max-width: 75%; }
    .msg-row .bubble {
        display: inline-block;
        padding: 10px 16px;
        font-size: 15px;
        line-height: 1.5;
        max-width: 100%;
        overflow-wrap: break-word;
        /* Codex review finding: plain st.markdown() used to respect a
           blank line in payload["text"] as a real paragraph break; a raw
           HTML div collapses it to a single space by default. No current
           answer template contains a newline (checked), but this keeps a
           future one from silently losing its formatting. */
        white-space: pre-wrap;
    }
    .msg-row .bubble p { margin: 0; }
    .msg-row.user { display: flex; justify-content: flex-end; }
    .msg-row.user .bubble {
        background: __BRAND__;
        color: #fff;
        border-radius: 18px 18px 4px 18px;
    }
    .msg-row.assistant { display: flex; justify-content: flex-start; }
    .msg-row.assistant .bubble {
        background: __BUBBLE_GREY__;
        color: __BRAND__;
        border-radius: 18px 18px 18px 4px;
    }
    .msg-row .msg-timestamp {
        font-size: 11px;
        color: __MUTED__;
        opacity: 0;
        transition: opacity 0.15s;
        margin-top: 3px;
    }
    .msg-row.user .msg-timestamp { text-align: right; }
    .msg-row:hover .msg-timestamp { opacity: 1; }
    </style>
    """.replace("__BRAND__", BRAND).replace("__BUBBLE_GREY__", BUBBLE_GREY).replace("__MUTED__", MUTED),
    unsafe_allow_html=True,
)

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

# The last question's parse, so a follow-up ("break this down", "and for
# 2024?") resolves against what was just answered instead of the whole
# company. Session-scoped, so two people using the app never share context.
if "last_parse" not in st.session_state:
    st.session_state.last_parse = None

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
    # Final whole-branch review Finding 3: this used to only strip "Demo "
    # for key == "entity", never for key == "supplier" — violating this
    # project's own Global Constraint (_MEETING-READY-PLAN.md line 15:
    # "Entity/supplier names always display with the `Demo ` prefix
    # stripped"). A question naming both an entity and a supplier used to
    # leave the supplier's "Demo " prefix intact right next to an
    # already-stripped entity.
    parts = []
    for key, value in filters.items():
        display = value.replace("Demo ", "") if key in ("entity", "supplier") else value
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


def _resolve_chart_year(filters: dict, df: pd.DataFrame) -> dict:
    """Resolve an unfiltered-year chart question to the latest year present
    WITHIN the filtered scope (not the whole dataset) — matches what
    overview_query.overview() and chart_query.py's other functions already
    document as the default-year rule. A scope with data in 2024 but none
    in 2025 must not dead-end on a phantom 2025 filter.

    Final whole-branch review Finding 4: every chart dispatch block below
    used to default to max(kv["year"]) — the latest year in the WHOLE
    dataset — regardless of the filters already in scope. 42 real
    entity+supplier combos have data in 2024 only; a chart question for one
    of them wrongly resolved to year=2025 and reported zero rows, even
    though the identical scope's overview question correctly found the 2024
    data (overview() already resolves its year this way). If the scope
    itself has no rows in any year, falls back to the dataset's own latest
    year — same as the old behaviour — so the existing "zero rows" honest-
    empty message still fires downstream instead of crashing on an empty
    scoped frame.
    """
    if "year" in filters:
        return dict(filters)
    scoped = filter_df(df, **filters)
    if scoped.empty:
        return {"year": max(kv["year"]), **filters}
    return {"year": int(scoped["Year"].max()), **filters}


def _scoped_supplier_count(chart_filters: dict) -> int:
    """Distinct suppliers in a filtered scope, guarded against a null
    Supplier name being silently dropped by nunique()'s default
    dropna=True — same guard fragmentation() itself already applies to its
    own by_supplier groupby before counting (final whole-branch review
    Finding 2: this KPI's count previously called nunique() directly on the
    unguarded column, so a null Supplier name in scope could make
    "Suppliers in scope" show one fewer than fragmentation()'s own table)."""
    return int(filter_df(df, **chart_filters)["Supplier name"].fillna("(unspecified)").nunique())


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


def build_supplier_drilldown_payload(filters: dict) -> dict:
    supplier = filters["supplier"]
    # chart_query.supplier_drilldown(df, supplier, **filters) documents that
    # a "supplier" key inside `filters` is ignored in favour of the explicit
    # `supplier` argument — but Python raises TypeError ("got multiple
    # values for argument 'supplier'") before the function body ever runs if
    # both are supplied at once, since filters here always carries the same
    # "supplier" key parse_question() extracted. Strip it from the kwargs
    # splat so only the explicit positional argument carries it, matching
    # the documented behaviour Python itself can't reach otherwise.
    scoped_filters = {k: v for k, v in filters.items() if k != "supplier"}
    drilldown = supplier_drilldown(df, supplier, **scoped_filters)
    display_name = supplier.replace("Demo ", "")

    if drilldown["year"] is None:
        return {
            "kind": "text",
            "text": f"I didn't find any spend for {display_name} matching that.",
            "figure": None, "caption": None, "show_chips": False,
        }

    net_spend_str = format_currency(drilldown["net_spend"])
    delta = f"{drilldown['yoy_pct']:+.1f}%" if drilldown["yoy_pct"] is not None else None
    share_str = f"{drilldown['share_of_scope_pct']:.1f}%" if drilldown["share_of_scope_pct"] is not None else "n/a"
    metrics = [
        (f"Spend {drilldown['year']}", net_spend_str, delta),
        ("Share of scope", share_str, None),
        ("Entities served", str(drilldown["entity_count"]), None),
        ("Categories", str(drilldown["category_count"]), None),
    ]
    entity_figure, category_figure = build_supplier_drilldown_figures(drilldown)

    delta_text = f" ({delta} vs {drilldown['prior_year']})" if delta else ""
    text = f"{display_name} — {net_spend_str} in {drilldown['year']}{delta_text}, {share_str} of spend in scope."

    return {
        "kind": "supplier_drilldown", "text": text, "metrics": metrics,
        "entity_figure": entity_figure, "category_figure": category_figure,
        "show_chips": False,
    }


def answer_payload(question: str) -> dict:
    parsed = parse_question(question, kv, previous=st.session_state.last_parse)
    filters = parsed["filters"]

    # Only remember turns that actually resolved something. A question the
    # parser did not understand must not become the context a later "break
    # this down" inherits — that would silently chain one miss into the next.
    if filters:
        st.session_state.last_parse = parsed

    if parsed["intent"] == "help":
        return build_help_payload()

    if parsed["intent"] == "overview":
        return build_overview_payload(filters)

    if parsed["intent"] == "supplier_drilldown":
        return build_supplier_drilldown_payload(filters)

    if parsed["intent"] == "chart":
        chart_kind = parsed["chart_kind"]

        if chart_kind == "top_suppliers":
            requested_n = parsed["top_n"]
            chart_df = top_suppliers(df, n=requested_n, **filters)
            if chart_df.empty:
                return {
                    "kind": "text",
                    "text": f"I didn't find any suppliers matching that — {format_filters(filters)} returned no rows.",
                    "figure": None, "caption": None, "show_chips": False,
                }
            fig = build_top_suppliers_figure(chart_df)
            actual_n = chart_df["supplier"].nunique()
            years_in_scope = sorted(chart_df["year"].unique())
            year_text = " vs ".join(str(y) for y in years_in_scope) if len(years_in_scope) > 1 else str(years_in_scope[0])
            total = format_currency(round(chart_df["net_spend"].sum(), 2))
            # Final whole-branch review Finding 5: the old "(clamped from N)"
            # note fired whenever actual_n != requested_n — true whenever a
            # scope simply has FEWER suppliers than the unrequested default
            # of 15 (the common case), not just on a genuine clamp-to-[3,56]
            # event from nl_parser.py. Real example: "top suppliers for
            # Alpine Operations in Facilities" has only 8 suppliers in
            # scope, so it used to say "Top 8 suppliers (clamped from
            # 15)..." even though nothing was ever clamped. Removed rather
            # than inferred — a genuine clamp note would need to be computed
            # and passed from nl_parser.py's own clamping step, which this
            # caption has no access to.
            #
            # Minor fix 1: same caption also used to read "by net spend,
            # 2024 vs 2025" as if ranking spanned both years, but Task 14
            # changed ranking to be by the single rank year alone (both
            # years are still plotted, only one ranks/selects) — name that
            # year explicitly so the caption can't be misread as a two-year
            # ranking.
            rank_year = filters.get("year", max(years_in_scope))
            caption = (
                f"Top {actual_n} suppliers by {rank_year} net spend, shown for {year_text} — "
                f"these {actual_n} account for {total} of the period's spend."
            )
            return {
                "kind": "chart", "text": f"Top {actual_n} suppliers",
                "figure": fig, "caption": caption, "show_chips": False,
            }

        if chart_kind == "fragmentation":
            chart_filters = _resolve_chart_year(filters, df)
            frag_df = fragmentation(df, level=parsed["category_level"], **chart_filters)
            if frag_df.empty:
                return {
                    "kind": "text",
                    "text": f"I didn't find any categories matching that — {format_filters(chart_filters)} returned no rows.",
                    "figure": None, "caption": None, "show_chips": False,
                }
            fig = build_fragmentation_figure(frag_df)
            high_count = int((frag_df["tier"] == "High fragmentation").sum())
            total_spend = float(frag_df["net_spend"].sum())
            high_spend = float(frag_df.loc[frag_df["tier"] == "High fragmentation", "net_spend"].sum())
            fragmented_pct = round(high_spend / total_spend * 100, 1) if total_spend else 0.0
            supplier_count = _scoped_supplier_count(chart_filters)
            metrics = [
                ("Categories assessed", str(len(frag_df)), None),
                ("Highly fragmented", str(high_count), None),
                ("Fragmented spend", f"{fragmented_pct:.1f}%", None),
                ("Suppliers in scope", str(supplier_count), None),
            ]
            table = frag_df.rename(columns={
                "category": "Category", "net_spend": "Net spend (€)", "supplier_count": "Suppliers",
                "top_supplier_share_pct": "Top supplier share %", "cr3_pct": "Top 3 share %",
                "concentration_index": "Concentration index", "tier": "Tier",
            })
            caption = (
                "Tier is set by our own Top-3-supplier-share rule (Concentrated "
                "≥ 70%, Medium 40-70%, High < 40%); Concentration index is a "
                "standard statistic shown alongside it, not used to set the tier."
            )
            return {
                "kind": "fragmentation",
                "text": f"Fragmentation for {format_filters(chart_filters)}.",
                "metrics": metrics, "figure": fig, "table": table, "caption": caption,
                "show_chips": False,
            }

        if chart_kind == "overall_concentration":
            chart_filters = _resolve_chart_year(filters, df)
            conc_df = overall_concentration(df, **chart_filters)
            if conc_df.empty:
                return {
                    "kind": "text",
                    "text": f"I didn't find any suppliers matching that — {format_filters(chart_filters)} returned no rows.",
                    "figure": None, "caption": None, "show_chips": False,
                }
            fig = build_concentration_figure(conc_df)
            top10_index = min(9, len(conc_df) - 1)
            top10_pct = float(conc_df["cumulative_share_pct"].iloc[top10_index])
            total = format_currency(round(conc_df["net_spend"].sum(), 2))
            caption = (
                f"{len(conc_df)} suppliers, {chart_filters['year']} — top 10 hold "
                f"{top10_pct:.1f}% of {total}."
            )
            return {
                "kind": "chart", "text": "Overall supplier concentration",
                "figure": fig, "caption": caption, "show_chips": False,
            }

        if chart_kind == "category_comparison":
            chart_filters = _resolve_chart_year(filters, df)
            comparison_df = category_comparison(df, level=parsed["category_level"], **chart_filters)
            if comparison_df.empty:
                return {
                    "kind": "text",
                    "text": f"I didn't find any categories matching that — {format_filters(chart_filters)} returned no rows.",
                    "figure": None, "caption": None, "show_chips": False,
                }
            prior_year = chart_filters["year"] - 1
            level_col = "L1" if parsed["category_level"] == "l1" else "L2"
            table = comparison_df.rename(columns={
                "category": level_col,
                "spend_current": f"Spend {chart_filters['year']} (€)",
                "spend_prior": f"Spend {prior_year} (€)",
                "change": "Change (€)", "change_pct": "Change %", "share_pct": "Share %",
            })
            total_current = format_currency(round(comparison_df["spend_current"].sum(), 2))
            text = f"Category spend comparison, {prior_year} vs {chart_filters['year']} — total {total_current} in {chart_filters['year']}."
            return {"kind": "category_comparison", "text": text, "table": table, "show_chips": False}

        if chart_kind == "intensity":
            chart_filters = _resolve_chart_year(filters, df)
            intensity_df = entity_category_intensity(df, level=parsed["category_level"], **chart_filters)
            if intensity_df.empty:
                return {
                    "kind": "text",
                    "text": f"I didn't find any spend matching that — {format_filters(chart_filters)} returned no rows.",
                    "figure": None, "caption": None, "show_chips": False,
                }
            fig = build_intensity_heatmap(intensity_df)
            total = format_currency(round(intensity_df["net_spend"].sum(), 2))
            caption = f"Spend intensity by entity and category, {chart_filters['year']} — total {total}."
            return {
                "kind": "chart", "text": "Entity / category spend intensity",
                "figure": fig, "caption": caption, "show_chips": False,
            }

        if chart_kind == "raw_data":
            rows_df = raw_filtered_rows(df, **filters)
            if rows_df.empty:
                return {
                    "kind": "text",
                    "text": f"I didn't find any rows matching that — {format_filters(filters)} returned no rows.",
                    "figure": None, "caption": None, "show_chips": False,
                }
            display_df = rows_df.copy()
            display_df["Entity"] = display_df["Entity"].str.replace("Demo ", "", regex=False)
            display_df["Supplier name"] = display_df["Supplier name"].str.replace("Demo ", "", regex=False)
            total_rows = len(display_df)
            preview = display_df.head(RAW_DATA_PREVIEW_LIMIT)
            truncated_note = (
                f" (showing first {RAW_DATA_PREVIEW_LIMIT} of {total_rows})"
                if total_rows > RAW_DATA_PREVIEW_LIMIT else ""
            )
            filter_text = format_filters(filters) if filters else "all data"
            text = f"Raw spend rows for {filter_text}{truncated_note}."
            csv_bytes = display_df.to_csv(index=False).encode("utf-8")
            return {
                "kind": "raw_data", "text": text, "table": preview,
                "csv_bytes": csv_bytes, "show_chips": False,
            }

        # Default an unfiltered chart question to the latest year present
        # WITHIN the filtered scope, applied as a REAL filter passed into
        # category_spend() — not just a display label. This restores
        # _CHART-CHAT-DESIGN.md's spec ("unfiltered chart → the latest year
        # present in the data", matching the InSight demo's own default
        # focus year), which an earlier fix round (Task 6) had only
        # half-fixed: it made the axis label honest ("all years") instead of
        # restoring this filter, so an unfiltered chart still silently
        # combined every year's data (final whole-branch review, Fix 2).
        # Chart-path only — query_spend()'s own unfiltered behaviour (sum
        # across all rows/years) is unchanged. _resolve_chart_year() (Finding
        # 4, later review round) further corrected "latest year" to mean the
        # latest year present in THIS question's filtered scope, not the
        # whole dataset — the two only differ once an entity/supplier/etc.
        # filter narrows the scope to a subset of years.
        chart_filters = _resolve_chart_year(filters, df)
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
        return {"kind": "chart", "text": f"Total: {total}", "figure": fig, "caption": caption, "show_chips": False}

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


# Renders everything in a payload EXCEPT its "text" field — the text goes
# inside the chat bubble (see render_message_bubble below); charts, tables,
# and KPI rows always break out full-width beneath the bubble instead, per
# the bubble-redesign brainstorming session: a wide chart squeezed to bubble
# width loses its legend/axis-label room, or forces the bubble edge-to-edge
# until it stops reading as a message.
def render_payload_extras(container, payload: dict, key_suffix: str = "x") -> None:
    if payload["kind"] == "chart":
        container.plotly_chart(payload["figure"], use_container_width=True, key=f"chart_{key_suffix}")
        container.caption(payload["caption"])
    elif payload["kind"] == "overview":
        render_kpi_row(container, payload["metrics"])
        render_callouts(container, payload["callouts"])
    elif payload["kind"] == "supplier_drilldown":
        render_kpi_row(container, payload["metrics"])
        fig_cols = container.columns(2)
        fig_cols[0].plotly_chart(
            payload["entity_figure"], use_container_width=True, key=f"chart_{key_suffix}_entity"
        )
        fig_cols[1].plotly_chart(
            payload["category_figure"], use_container_width=True, key=f"chart_{key_suffix}_category"
        )
    elif payload["kind"] == "fragmentation":
        render_kpi_row(container, payload["metrics"])
        container.plotly_chart(payload["figure"], use_container_width=True, key=f"chart_{key_suffix}")
        container.dataframe(payload["table"], hide_index=True, use_container_width=True)
        container.caption(payload["caption"])
    elif payload["kind"] == "category_comparison":
        container.dataframe(payload["table"], hide_index=True, use_container_width=True)
    elif payload["kind"] == "raw_data":
        container.dataframe(payload["table"], hide_index=True, use_container_width=True)
        container.download_button(
            "Download filtered CSV", data=payload["csv_bytes"],
            file_name="filtered_spend.csv", mime="text/csv",
            key=f"download_{key_suffix}",
        )


# render_payload_extras must be defined above this point: Streamlit
# re-executes the whole script top-to-bottom on every rerun, and the
# history-replay loop below calls render_payload_extras() for any past
# message that has a payload — which every assistant turn does, from the
# very first exchange onward. A definition below the loop worked on the
# *first* run (loop body never executes because history is still empty) but
# raised NameError on every rerun after that — i.e. on the user's second
# message. Confirmed fixed via
# tests/test_app_answer.py::test_multi_turn_chat_does_not_crash (AppTest,
# scripts two chat turns and asserts no exception either time).


def _relative_time(sent_at: float) -> str:
    seconds = max(0, time.time() - sent_at)
    if seconds < 60:
        return "Just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(hours // 24)
    return f"{days} day{'s' if days != 1 else ''} ago"


# The plain-number answer (the app's most common reply) emphasises its figure
# with markdown bold: `f"Matched on {...} — **{total}** across ..."`. The old
# st.chat_message path passed that through st.markdown, which rendered it
# bold; a raw HTML bubble does not, so the asterisks displayed literally on
# the live site until this was added. Only **bold** is converted — it is the
# only markdown any answer template actually produces (verified by scanning
# every f-string that becomes payload["text"]; the one other bold in the file,
# render_callouts' box.markdown, is unaffected because it still goes through
# st.markdown directly, not through this bubble).
_BOLD_MARKDOWN = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


def _bubble_body(content: str) -> str:
    # ORDER IS LOAD-BEARING: escape() first, THEN insert <strong>. Escaping
    # after substitution would neuter the very tags this adds; substituting
    # into unescaped text would let dataset values inject markup. Checked the
    # current dataset directly — no category/entity/supplier value contains
    # "*", "<" or ">" — so this cannot mangle a real name today.
    return _BOLD_MARKDOWN.sub(r"<strong>\1</strong>", escape(content))


def render_message_bubble(container, role: str, content: str, sent_at: float) -> None:
    # Only the text goes in the bubble — charts/tables render separately via
    # render_payload_extras() so they always get full width (see the CSS
    # comment above for why). unsafe_allow_html is required for the bubble
    # div/timestamp markup; content is escaped and narrowly un-escaped for
    # bold by _bubble_body above.
    # Codex review finding: st.chat_message() gave each message a role-labelled
    # container for assistive tech; a plain div doesn't. Restoring that via
    # role="article" + an aria-label, matching the exact wording Streamlit's
    # own chat_message used ("Chat message from user"/"...assistant" — see the
    # CSS comment above referencing the old aria-label selector).
    container.markdown(
        f"""
        <div class="msg-row {role}" role="article" aria-label="Chat message from {role}">
            <div>
                <div class="bubble">{_bubble_body(content)}</div>
                <div class="msg-timestamp">{_relative_time(sent_at)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


PLACEHOLDER = "What was our IT and telecom spend for Alpine Operations in 2024?"

RAW_DATA_PREVIEW_LIMIT = 50

SUGGESTION_CHIPS = [
    "Give me an overview",
    "Show me a bar chart of category spend",
    "Who are our top suppliers?",
]


def render_chips(container, key_suffix: str) -> None:
    selection = container.pills(
        "Suggested questions",
        SUGGESTION_CHIPS,
        selection_mode="single",
        label_visibility="collapsed",
        key=f"chips_{key_suffix}",
    )
    if selection:
        st.session_state.pending_question = selection
        # Deviation from the brief's verbatim code: st.pills's selection
        # persists in session_state (keyed by chips_{key_suffix}) across the
        # st.rerun() below, exactly like any other Streamlit selection
        # widget. Without clearing it here, the very next script pass reads
        # the same selection again, re-sets pending_question, and calls
        # st.rerun() again — an infinite rerun loop. Confirmed directly: a
        # throwaway AppTest script using the brief's original two-line body
        # (set pending_question, st.rerun()) hung until AppTest's own
        # timeout: session_state still held chips_empty at that point,
        # proving the widget's value was never consumed. Deleting the
        # widget's own key resets it to unselected before the next pass
        # recreates it, breaking the loop; re-ran the same throwaway script
        # with this fix and confirmed it completes and submits the
        # question correctly.
        del st.session_state[f"chips_{key_suffix}"]
        st.rerun()


pending = st.session_state.pop("pending_question", None)

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
        typed = st.chat_input(PLACEHOLDER)
    prompt = pending or typed
    if not prompt:
        # Second deviation from the brief's verbatim wiring: only render the
        # empty-state chips when nothing is about to be submitted this pass.
        # Reason: on a normal first message (typed into chat_input, not
        # clicked), the original unconditional call rendered chips_empty in
        # the SAME script pass that also appends the message and calls
        # st.rerun() below — a keyed widget created and then immediately
        # orphaned by that rerun. AppTest's tree reconstruction does not
        # clean up that stale node, so the next simulated interaction fails
        # with "st.session_state has no key 'chips_empty'" once Streamlit's
        # own real state garbage-collects it. Confirmed directly: the
        # pre-existing test_multi_turn_chat_does_not_crash_on_rerun (typed
        # submissions, no chip involved) broke with exactly this KeyError
        # under the brief's original unconditional render_chips call, and
        # passed once chip rendering was gated on "nothing is being
        # submitted this pass" — re-ran both that test and the two new chip
        # tests against the fix to confirm all three pass together.
        render_chips(st, key_suffix="empty")
else:
    # Conversation state: full history, input pinned to the bottom — the
    # standard chat layout once there's something to scroll. Suggestion
    # chips only reappear here after the LAST message, and only when that
    # message's payload asked for them (overview-fallback or help answers,
    # A3/A2) — showing them after every past occurrence in history would
    # clutter the conversation with stale, already-acted-on suggestions.
    # typed/prompt are resolved BEFORE the history loop below, not after
    # (third deviation from the brief's verbatim wiring, same root cause as
    # the empty-state one above): if a user types a follow-up question right
    # after an overview/help answer whose chips are showing, the history
    # loop's render_chips(str(last_index)) call would otherwise still fire
    # in that same pass, orphaning that keyed pills widget the instant the
    # append+rerun below fires. Confirmed directly: a throwaway AppTest
    # script scripting "give me an overview" (show_chips True, chips render)
    # followed immediately by a typed follow-up question reproduced the same
    # "st.session_state has no key ..." class of failure seen in the
    # empty-state case until this call was moved ahead of the loop and
    # gated on `not prompt` below.
    last_index = len(st.session_state.messages) - 1
    typed = st.chat_input(PLACEHOLDER)
    prompt = pending or typed
    for i, message in enumerate(st.session_state.messages):
        # Fallback to time.time() for any message dict without a "timestamp"
        # key (e.g. a session already in flight when this field was added)
        # rather than a KeyError — the timestamp only affects the hover
        # label, so a "just now" for old messages this one rerun is harmless.
        render_message_bubble(
            st, message["role"], message["content"], message.get("timestamp", time.time())
        )
        if message.get("payload"):
            render_payload_extras(st, message["payload"], key_suffix=str(i))
        if i == last_index and message["role"] == "assistant" and message.get("payload", {}).get("show_chips") and not prompt:
            render_chips(st, key_suffix=str(i))

if prompt:
    st.session_state.messages.append(
        {"role": "user", "content": prompt, "payload": None, "timestamp": time.time()}
    )
    payload = answer_payload(prompt)
    st.session_state.messages.append(
        {"role": "assistant", "content": payload["text"], "payload": payload, "timestamp": time.time()}
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

"""Rule-based question parser — NOT an LLM.

There is no ANTHROPIC_API_KEY configured on this machine, so this prototype
matches known entity/country/cluster/year/category/supplier names directly
against the typed question instead of calling a language model. This is a
deliberate, disclosed substitute, not a silent downgrade — see _HANDOFF.md
for the tradeoff and the upgrade path once an API key is available.

Known limitation: it only recognises exact category names and their "Demo "-
stripped short forms (e.g. "Alpine" for "Demo Alpine Operations"). It does
not understand synonyms, abbreviations, or paraphrasing — that is exactly
what the LLM upgrade would add.
"""

import re

from aliases import ALIASES_BY_DIMENSION, supplier_aliases

CHART_KEYWORDS = (
    "chart", "graph", "plot", "bar chart", "bar graph", "breakdown",
    "break down", "broken down", "visualise", "visualize",
    # "compare" is deliberately NOT a chart keyword. _extract_filters()
    # below only ever captures the first matching value per dimension (the
    # whole filter model here is single-value-per-dimension), so a "compare
    # X and Y" question would silently produce a chart for just one of the
    # two entities, with nothing indicating the comparison was dropped.
    # True multi-entity comparison charts are an explicitly deferred future
    # capability — better to fall through to the existing number-intent path
    # than to falsely promise a comparison this parser can't deliver.
)
# "bar" and "split" (final whole-branch review, Fix 3) are no longer plain
# substring keywords (Codex follow-up review, Fix B): as bare substrings
# they matched inside unrelated words/names — "minibar" contains "bar",
# "Barrow Operations" contains "bar" — misrouting plain number questions to
# chart intent. The other CHART_KEYWORDS entries above ("chart", "graph",
# "breakdown", etc.) are long/distinctive enough that plain substring
# matching doesn't collide with ordinary words, so only these two
# collision-prone words needed changing.
#
# "bar" is fixed with a plain whole-word match (same technique
# CLUSTER_BREAKDOWN_KEYWORDS' cluster-name matching in _extract_filters uses
# below) — its one genuine trigger example ("bar of category spend") is a
# bare standalone word with no further context, and both its false-positive
# examples are pure substring embeds that word-boundary alone eliminates.
BAR_PATTERN = re.compile(r"\bbar\b")
# "split" needs more than a word-boundary fix: "What was the split payment
# spend in 2024?" contains "split" as a genuine standalone WORD, not a
# substring embed like "minibar" — a plain \bsplit\b would still match it.
# Every genuine "split" chart-trigger example this file has ever documented
# is the "split spend by <dimension>" shape (a breakdown request), so
# "split" is only treated as a chart signal when it is followed somewhere
# later in the question by "by" — "split payment spend" has no "by" and
# correctly falls through to a plain number question.
SPLIT_PATTERN = re.compile(r"\bsplit\b.*\bby\b")
# "show me spend by country" / "show me category spend by entity" (spec's
# "show me ... by" chart-trigger pattern) contain none of the substring
# keywords above. Requires "show me" AND "by" followed directly by one of
# the supported breakdown dimension words — not just any word after "by"
# (Codex follow-up review, Fix A): the original pattern matched ANY "show me
# ... by ..." sentence, so "show me total spend by Alpine Operations" (an
# entity name, not a breakdown dimension) was incorrectly promoted to chart
# intent and picked up the chart path's default-year filter, silently
# changing the answer from the established all-years total. "by" alone
# remains far too generic a word to add as a blanket keyword (it would
# misfire on almost any question, e.g. plain number questions like "spend by
# Alpine Operations in 2024") — this narrowly targets "show me X by <real
# breakdown dimension>", matching the same dimension words
# COUNTRY_BREAKDOWN_KEYWORDS/CLUSTER_BREAKDOWN_KEYWORDS/LEVEL_2_KEYWORDS
# below already look for, not an arbitrary entity/supplier name.
BREAKDOWN_DIMENSION_WORDS = r"(?:entit(?:y|ies)|countr(?:y|ies)|cluster[s]?|categor(?:y|ies)|level)"
SHOW_ME_BY_PATTERN = re.compile(rf"\bshow me\b.*\bby\s+{BREAKDOWN_DIMENSION_WORDS}\b")
COUNTRY_BREAKDOWN_KEYWORDS = ("by country", "per country", "country breakdown", "each country")
CLUSTER_BREAKDOWN_KEYWORDS = ("by cluster", "per cluster", "cluster breakdown", "each cluster")
LEVEL_2_KEYWORDS = ("level 2", "sub-category", "subcategory", "sub category")

HELP_KEYWORDS = (
    "help", "what can you do", "what can i ask", "how does this work", "examples",
)

OVERVIEW_KEYWORDS = (
    "overview", "summary", "summarise", "summarize", "headline", "big picture",
    "how are we doing", "state of spend",
)

TOP_SUPPLIERS_KEYWORDS = (
    "top suppliers", "top supplier", "biggest suppliers", "largest suppliers",
    "top vendors", "supplier ranking", "who do we spend the most with",
)
# Digit count capped at 10 (not unbounded \d+): an adversarial question like
# "top " + "9" * 5000 + " suppliers" previously reached int() with a 5000-
# digit string and crashed with ValueError ("Exceeds the limit (4300
# digits) for integer string conversion") — CPython 3.11+'s own int-string
# conversion guard, not a bug in this file, but this file's job is to never
# let a crash reach it. 10 digits comfortably exceeds any real "top N"
# question (MAX_TOP_SUPPLIERS_N below is 56) while staying far under the
# 4300-digit limit (Codex cross-family review, Task 14, 7 Aug 2026).
TOP_N_PATTERN = re.compile(r"\btop\s+(\d{1,10})\b")
MIN_TOP_SUPPLIERS_N = 3
MAX_TOP_SUPPLIERS_N = 56
DEFAULT_TOP_SUPPLIERS_N = 15

FRAGMENTATION_KEYWORDS = (
    "fragmentation", "fragmented", "supplier concentration", "how spread out",
    "how many suppliers per category", "tail spend",
)

CONCENTRATION_KEYWORDS = (
    "pareto", "80/20", "how concentrated is our supplier base",
    "overall supplier concentration", "overall concentration",
)

CATEGORY_COMPARISON_KEYWORDS = (
    "category comparison", "compare categories", "category spend comparison",
    "compare category spend", "year over year by category", "yoy by category",
    "spend profile",
    # Added 7 Aug 2026 (phrasing-matrix pass): a year-over-year question is
    # far more often phrased as a comparison in plain English than by the
    # word "comparison" itself. Without these, "how did category spend
    # change vs last year" matched nothing and fell through to the overview
    # fallback — a dead-end on a question this view answers directly.
    "vs last year", "versus last year", "compared to last year",
    "year on year", "yoy",
)

# Words where the user explicitly names the OUTPUT FORMAT they want, rather
# than the view. An explicit format request BEATS an inferred view type:
# someone who types "bar chart of the spend profile" has named a chart in
# the clearest possible terms, and handing them a table instead ignores the
# strongest signal in their question.
#
# Found by Hayden's own manual testing, 7 Aug 2026 — every automated pass in
# this project missed it because each view was only ever tested with the one
# canonical phrasing its keyword was written for. "Show me a bar chart of the
# spend profile by category" hit the "spend profile" keyword above (checked
# before the chart keywords) and returned the comparison TABLE, and the
# by-entity variant returned that same table with the breakdown dropped.
# tests/test_phrasing_matrix.py exists to keep that class of gap closed.
EXPLICIT_CHART_PATTERN = re.compile(r"\b(bar chart|bar graph|chart|graph|plot|visuali[sz]e)\b")
EXPLICIT_TABLE_PATTERN = re.compile(r"\btable\b")

INTENSITY_KEYWORDS = (
    "intensity", "heatmap", "heat map", "entity category breakdown",
    "which entities spend most",
)

RAW_DATA_KEYWORDS = (
    "raw data", "underlying data", "raw rows", "show me the data",
    "export the data", "download the data", "see the data",
)


# Order decides which dimension wins when two aliases of EQUAL length match
# the same text. L2 sits above L1 so the narrower category reading wins
# ("electricity" -> the Electricity and gas sub-category, not Utilities).
_DIMENSION_PRIORITY = ("l2", "l1", "entity", "country", "cluster", "supplier")


def _candidate_terms(known: dict[str, list]) -> list[tuple[str, str, object]]:
    """Every (alias, dimension, canonical value) the parser can recognise,
    longest alias first.

    Includes both the curated aliases from aliases.py AND each canonical
    value's own name plus its "Demo "-stripped short form, so the exact
    phrasings that worked before this module existed keep working.
    """
    terms: list[tuple[str, str, object]] = []

    for dimension, alias_map in ALIASES_BY_DIMENSION.items():
        for canonical, alias_list in alias_map.items():
            forms = {canonical.lower(), canonical.lower().replace("demo ", "")}
            forms.update(alias_list)
            for form in forms:
                terms.append((form, dimension, canonical))

    for supplier in known["supplier"]:
        for form in supplier_aliases(supplier):
            terms.append((form, "supplier", supplier))

    # Longest alias first; ties broken by dimension priority above.
    terms.sort(key=lambda t: (-len(t[0]), _DIMENSION_PRIORITY.index(t[1])))
    return terms


def _extract_filters(q: str, known: dict[str, list]) -> dict:
    """Resolve a lowercased question to canonical filter values.

    Matching is GLOBAL longest-alias-first with span consumption, not
    per-dimension independent scanning. That matters because aliases overlap
    across dimensions: "southern support" is an entity while "south" is a
    cluster, and matching both would AND them into an empty result and hand
    the user a false "no data". Once the longer alias claims that span of
    text, no shorter alias may re-match those characters.
    """
    filters: dict[str, object] = {}

    for year in known["year"]:
        if str(year) in q:
            filters["year"] = year
            break

    consumed: list[tuple[int, int]] = []
    for alias, dimension, canonical in _candidate_terms(known):
        if dimension in filters:
            continue
        # Lookarounds rather than \b: several aliases contain punctuation
        # ("it & telecom", "l&d", "it/telecom") where \b behaves unhelpfully.
        pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
        for match in re.finditer(pattern, q):
            start, end = match.span()
            if any(start < c_end and c_start < end for c_start, c_end in consumed):
                continue
            filters[dimension] = canonical
            consumed.append((start, end))
            break

    return filters


def parse_question(question: str, known: dict[str, list]) -> dict:
    q = question.lower()
    filters = _extract_filters(q, known)
    base = {"top_n": None, "filters": filters}

    if any(kw in q for kw in HELP_KEYWORDS):
        return {"intent": "help", "chart_kind": None, "breakdown": None, "category_level": None, **base}

    if any(kw in q for kw in OVERVIEW_KEYWORDS):
        return {"intent": "overview", "chart_kind": None, "breakdown": None, "category_level": None, **base}

    top_n_match = TOP_N_PATTERN.search(q)
    is_top_suppliers = any(kw in q for kw in TOP_SUPPLIERS_KEYWORDS) or (
        top_n_match is not None and "supplier" in q
    )
    if is_top_suppliers:
        if top_n_match:
            n = max(MIN_TOP_SUPPLIERS_N, min(MAX_TOP_SUPPLIERS_N, int(top_n_match.group(1))))
        else:
            n = DEFAULT_TOP_SUPPLIERS_N
        return {
            "intent": "chart", "chart_kind": "top_suppliers",
            "breakdown": None, "category_level": None,
            "top_n": n, "filters": filters,
        }

    if any(kw in q for kw in CONCENTRATION_KEYWORDS):
        return {
            "intent": "chart", "chart_kind": "overall_concentration",
            "breakdown": None, "category_level": None,
            "top_n": None, "filters": filters,
        }

    if any(kw in q for kw in FRAGMENTATION_KEYWORDS):
        category_level = "l2" if any(kw in q for kw in LEVEL_2_KEYWORDS) else "l1"
        return {
            "intent": "chart", "chart_kind": "fragmentation",
            "breakdown": None, "category_level": category_level,
            "top_n": None, "filters": filters,
        }

    # Explicit output-format preference, used by the two table-only views
    # below (category_comparison and raw_data) to step aside when the user
    # actually asked for a chart. Saying both ("a chart and a table") or
    # neither leaves the view's own keyword in charge, unchanged.
    wants_chart = bool(EXPLICIT_CHART_PATTERN.search(q)) or bool(BAR_PATTERN.search(q))
    wants_table = bool(EXPLICIT_TABLE_PATTERN.search(q))
    prefers_chart = wants_chart and not wants_table
    prefers_table = wants_table and not wants_chart

    matches_comparison = (
        any(kw in q for kw in CATEGORY_COMPARISON_KEYWORDS)
        or ("compare" in q and "categor" in q)
        # The symmetric case: "show me a table of category spend" names the
        # format explicitly too, and the comparison table IS this app's
        # category table — without this it matched no view at all and
        # dead-ended on the overview fallback.
        or (prefers_table and "categor" in q)
    )
    if matches_comparison and not prefers_chart:
        category_level = "l2" if any(kw in q for kw in LEVEL_2_KEYWORDS) else "l1"
        return {
            "intent": "chart", "chart_kind": "category_comparison",
            "breakdown": None, "category_level": category_level,
            "top_n": None, "filters": filters,
        }

    if any(kw in q for kw in INTENSITY_KEYWORDS):
        category_level = "l2" if any(kw in q for kw in LEVEL_2_KEYWORDS) else "l1"
        return {
            "intent": "chart", "chart_kind": "intensity",
            "breakdown": None, "category_level": category_level,
            "top_n": None, "filters": filters,
        }

    # raw_data is the other table-only view, so it steps aside for an
    # explicit chart request the same way category_comparison does above —
    # "chart the underlying data" is a request to see it plotted, not dumped.
    if any(kw in q for kw in RAW_DATA_KEYWORDS) and not prefers_chart:
        return {
            "intent": "chart", "chart_kind": "raw_data",
            "breakdown": None, "category_level": None,
            "top_n": None, "filters": filters,
        }

    is_chart = (
        any(keyword in q for keyword in CHART_KEYWORDS)
        or bool(BAR_PATTERN.search(q))
        or bool(SPLIT_PATTERN.search(q))
        or bool(SHOW_ME_BY_PATTERN.search(q))
    )

    if not is_chart:
        DRILLDOWN_ALLOWED_EXTRA_FILTERS = {"year"}
        if "supplier" in filters and (set(filters) - {"supplier"}) <= DRILLDOWN_ALLOWED_EXTRA_FILTERS:
            return {
                "intent": "supplier_drilldown", "chart_kind": None,
                "breakdown": None, "category_level": None, **base,
            }
        return {"intent": "number", "chart_kind": None, "breakdown": None, "category_level": None, **base}

    if any(kw in q for kw in CLUSTER_BREAKDOWN_KEYWORDS):
        breakdown = "cluster"
    elif any(kw in q for kw in COUNTRY_BREAKDOWN_KEYWORDS):
        breakdown = "country"
    else:
        breakdown = "entity"

    category_level = "l2" if any(kw in q for kw in LEVEL_2_KEYWORDS) else "l1"

    return {
        "intent": "chart",
        "chart_kind": "category_spend",
        "breakdown": breakdown,
        "category_level": category_level,
        **base,
    }

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
TOP_N_PATTERN = re.compile(r"\btop\s+(\d+)\b")
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


def _extract_filters(q: str, known: dict[str, list]) -> dict:
    filters: dict[str, object] = {}

    for year in known["year"]:
        if str(year) in q:
            filters["year"] = year
            break

    for entity in sorted(known["entity"], key=len, reverse=True):
        short = entity.replace("Demo ", "")
        if entity.lower() in q or short.lower() in q:
            filters["entity"] = entity
            break

    for country in sorted(known["country"], key=len, reverse=True):
        if country.lower() in q:
            filters["country"] = country
            break

    # Cluster names (Central, North, South, West, Corporate) are common
    # English words, so require a whole-word match to cut down false hits.
    for cluster in sorted(known["cluster"], key=len, reverse=True):
        if re.search(rf"\b{re.escape(cluster.lower())}\b", q):
            filters["cluster"] = cluster
            break

    # L2 checked before L1 since it's the more specific category level.
    for l2 in sorted(known["l2"], key=len, reverse=True):
        if l2.lower() in q:
            filters["l2"] = l2
            break

    for l1 in sorted(known["l1"], key=len, reverse=True):
        if l1.lower() in q:
            filters["l1"] = l1
            break

    for supplier in sorted(known["supplier"], key=len, reverse=True):
        if supplier.lower() in q:
            filters["supplier"] = supplier
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

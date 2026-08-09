"""Rule-based question parser — NOT an LLM.

There is no ANTHROPIC_API_KEY configured on this machine, so this prototype
matches known entity/country/cluster/year/category/supplier names directly
against the typed question instead of calling a language model. This is a
deliberate, disclosed substitute, not a silent downgrade — see _HANDOFF.md
for the tradeoff and the upgrade path once an API key is available.

Since 7 Aug 2026 it also recognises a CURATED alias vocabulary (aliases.py):
"IT spend", "staff costs", "supplier 25", "Holland" and so on all resolve to
the canonical value. That was added because a client typed "give me IT spend"
and got the whole-company total.

Known limitation, and the reason the LLM upgrade still matters: the alias list
is finite and hand-written. It recognises the phrasings someone thought of.
It does not genuinely understand paraphrasing, so "what's eating our budget?",
"why did IT go up?" and "where can we save money?" all still fall back to the
overview. Extending the list is whack-a-mole; an LLM understanding layer is
the structural fix — see _LLM-UPGRADE-RESEARCH.md.

Since 9 Aug 2026 it also has ONE turn of memory: parse_question takes the
previous turn's parse, so "break this down" and "what about Germany" resolve
against the last answer instead of the whole company. That is genuine
conversational state, but it is still rule-based — it inherits filters, it
does not understand what was said.
"""

import re

from aliases import (
    ALIAS_BLOCKING_PHRASES,
    ALIASES_BY_DIMENSION,
    SPEND_SIGNAL_WORDS,
    WEAK_ALIASES,
    supplier_aliases,
)

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
# "spend by country" / "category spend by entity" contain none of the
# substring keywords above, so they need their own pattern.
#
# What makes this safe is requiring a real BREAKDOWN DIMENSION after "by",
# never "by" alone: "by" is far too generic to be a blanket chart keyword, and
# an earlier version that matched any "show me ... by ..." sentence promoted
# "show me total spend by Alpine Operations" — an entity FILTER, not a
# breakdown axis — to chart intent, where it picked up the chart path's
# default-year filter and silently changed the answer from the established
# all-years total (Codex follow-up review, Fix A). The dimension words below
# are the same ones COUNTRY_BREAKDOWN_KEYWORDS / CLUSTER_BREAKDOWN_KEYWORDS /
# LEVEL_2_KEYWORDS already look for.
BREAKDOWN_DIMENSION_WORDS = (
    r"(?:entit(?:y|ies)|countr(?:y|ies)|cluster[s]?|"
    r"sub[- ]?categor(?:y|ies)|categor(?:y|ies)|level)"
)
# Generalised 9 Aug 2026 from the old "show me ... by <dimension>" form. The
# "show me" prefix was never the thing that made the pattern safe — requiring
# a real BREAKDOWN DIMENSION after "by" is. Without the generalisation,
# "spend by cluster", "category spend by entity" and "break this down per sub
# category" matched no view at all and dead-ended on the overview, while the
# identical question prefixed with "show me" worked. "by Alpine Operations"
# still cannot match, because an entity name is not a dimension word.
BY_DIMENSION_PATTERN = re.compile(
    rf"\b(?:by|per|across|for each)\s+(?:each\s+)?{BREAKDOWN_DIMENSION_WORDS}\b"
)
# "Break this down" is the single most natural follow-up in a chat tool and
# the plain "break down" substring in CHART_KEYWORDS above does not contain
# it — the pronoun sits in the middle. Found in Hayden's own live testing:
# "Break this down per sub category for people" returned the same flat total
# it had just given, with no breakdown at all.
BREAK_IT_DOWN_PATTERN = re.compile(
    r"\bbreak\s+(?:this|that|it|these|those|them)\s+down\b"
    r"|\bdrill\s+(?:in|into|down)\b"
    r"|\bmore (?:detail|granular|granularity)\b"
)
COUNTRY_BREAKDOWN_KEYWORDS = ("by country", "per country", "country breakdown", "each country")
CLUSTER_BREAKDOWN_KEYWORDS = ("by cluster", "per cluster", "cluster breakdown", "each cluster")
LEVEL_2_KEYWORDS = ("level 2", "sub-category", "subcategory", "sub category")

HELP_KEYWORDS = (
    "help", "what can you do", "what can i ask", "how does this work", "examples",
    # Added 9 Aug 2026. A first-time user opening the tool types one of these
    # before anything else, and every one of them previously returned a full
    # spend overview — an answer to a question nobody asked.
    "what is this", "what's this", "what can this do", "who are you",
    "what do you do", "what does this do",
)
# Greetings need a word-boundary match, not the substring test HELP_KEYWORDS
# uses: "hi" is inside "this", "which" and "within", and "hey" is inside
# "they". Anchored to the start because "hi" mid-sentence is not a greeting.
GREETING_PATTERN = re.compile(
    r"^\s*(?:hi|hiya|hey|hello|yo|good (?:morning|afternoon|evening))\b"
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
    # Added 9 Aug 2026 (customer sweep). "Which category grew the most" is
    # the question this table exists to answer, and it reached the overview
    # instead — which shows only the single fastest-growing category, not the
    # ranking the user asked for.
    "grew the most", "growing fastest", "fastest growing", "fastest-growing",
    "biggest increase", "biggest growth", "which grew", "what grew",
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


def _has_spend_signal(q: str) -> bool:
    """Is this question about money at all? Gates every weak alias.

    Matched on WORD BOUNDARIES, not as substrings. Codex (9 Aug 2026) found
    "is this available in German numbering format?" answering with Germany's
    €1,801,388.73: "numbering" contains "number", which had just been added
    as a signal word, which unlocked the weak "german" alias. Substring
    matching makes every future signal word a latent version of that bug.

    Symbols (€, £, $) have no word boundary, so they stay plain substring
    tests — they cannot collide with a longer word the way letters can.
    """
    for word in SPEND_SIGNAL_WORDS:
        if word.replace(" ", "").isalpha():
            if re.search(rf"\b{re.escape(word)}\b", q):
                return True
        elif word in q:
            return True
    return False


def _drop_contradictory_l1(filters: dict, known: dict[str, list]) -> dict:
    """An L2 and an L1 that are not parent and child cannot both be true, and
    AND-ing them yields "€0.00 across 0 spend rows" — a false "no data" that
    reads as an authoritative answer. "office software spend" did exactly
    this. The L2 is the more specific reading, so it wins and the contradicted
    L1 is dropped rather than the query being emptied.

    Extracted from _extract_filters 9 Aug 2026 because follow-up merging can
    produce the same contradiction a second way: a previous turn's L1 carried
    forward onto a new turn's unrelated L2.
    """
    l2, l1 = filters.get("l2"), filters.get("l1")
    if l2 is not None and l1 is not None and known.get("l2_parent", {}).get(l2) != l1:
        del filters["l1"]
    return filters


def _extract_filters(q: str, known: dict[str, list], original: str | None = None) -> dict:
    """Resolve a lowercased question to canonical filter values.

    Matching is GLOBAL longest-alias-first with span consumption, not
    per-dimension independent scanning. That matters because aliases overlap
    across dimensions: "southern support" is an entity while "south" is a
    cluster, and matching both would AND them into an empty result and hand
    the user a false "no data". Once the longer alias claims that span of
    text, no shorter alias may re-match those characters.
    """
    filters: dict[str, object] = {}

    # Digit-boundary match, not a plain substring: `"2024" in "20245"` is true,
    # so "IT spend in 20245" silently answered for 2024 (Codex round 2). A
    # typo'd year must fall through, not quietly become a real one.
    for year in known["year"]:
        if re.search(rf"(?<!\d){year}(?!\d)", q):
            filters["year"] = year
            break

    # Weak aliases are ordinary English words too ("legal", "training",
    # "security"), so they only count when the question is clearly about
    # money. Without this, "what are the legal implications" returns the
    # Legal and audit total — a confidently wrong number, which is worse
    # than the honest "didn't understand" fallback. See aliases.py.
    has_spend_signal = _has_spend_signal(q)

    consumed: list[tuple[int, int]] = []

    def claim(alias: str, dimension: str, canonical: object) -> None:
        # Lookarounds rather than \b: several aliases contain punctuation
        # ("it & telecom", "l&d", "it/telecom") where \b behaves unhelpfully.
        pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
        for match in re.finditer(pattern, q):
            start, end = match.span()
            if any(start < c_end and c_start < end for c_start, c_end in consumed):
                continue
            filters[dimension] = canonical
            consumed.append((start, end))
            return

    # TWO PASSES, strong aliases first. A weak alias must never beat a
    # non-weak one competing for the same dimension, however the lengths fall.
    # Found by Codex round 2: "security software spend" answered with the
    # Cleaning and security total (€684,341.95) because "security" and
    # "software" are the same length and Cleaning sorts first, and
    # "maintenance software spend" answered with Building maintenance because
    # "maintenance" is simply the longer word. In both the user plainly meant
    # software. Running every unambiguous alias to completion first, and only
    # then letting ordinary-English ones fill what is still empty, resolves
    # the whole class rather than these two instances.
    terms = _candidate_terms(known)
    for weak_pass in (False, True):
        for alias, dimension, canonical in terms:
            if (alias in WEAK_ALIASES) != weak_pass:
                continue
            if dimension in filters:
                continue
            if weak_pass:
                if not has_spend_signal:
                    continue
                # A spend word in the sentence is not enough on its own: "audit
                # trail spend" contains one and still isn't about audit fees.
                if any(phrase in q for phrase in ALIAS_BLOCKING_PHRASES.get(alias, ())):
                    continue
            claim(alias, dimension, canonical)

    # "IT" the department vs "it" the pronoun. aliases.py deliberately refuses
    # a bare "it" alias (its design rule 2) because "it" is the commonest
    # pronoun in English — correct, but it left "IT figures", "IT numbers",
    # "IT costs" and "what's the IT total" all dead-ending on the overview
    # while "IT spend" worked, which reads as the tool being broken.
    #
    # Capitalisation is the discriminator a human actually uses, and it costs
    # nothing: someone writing about the department types "IT", someone using
    # the pronoun types "it". Skipped when the question is ENTIRELY uppercase,
    # since a shouted sentence carries no case information to read.
    # Gated on a spend signal exactly like a weak alias, because that is what
    # it is: Codex (9 Aug 2026) found "is IT secure?" answering with the IT
    # and telecom total of €2,630,963.38. Someone asking whether the SOFTWARE
    # is secure writes "IT" too. Every genuine phrasing this rule exists for
    # carries a signal — "IT costs", "IT figures", "the IT total",
    # "is IT over budget".
    if (
        "l1" not in filters
        and has_spend_signal
        and original is not None
        and original != original.upper()
        and re.search(r"(?<![A-Za-z0-9])IT(?![A-Za-z0-9])", original)
    ):
        filters["l1"] = "IT and telecom"

    return _drop_contradictory_l1(filters, known)


# A follow-up refers back to the previous answer instead of restating it.
# "Break this down", "and for 2024?", "what about Germany", "now by entity" —
# each is meaningless on its own, and a stateless parser answers them about
# the whole company. Hayden's live test showed the shape exactly: an answer
# about People, then "Break this down per sub category for people", then the
# same flat total again.
REFERRING_PATTERN = re.compile(
    r"\b(?:this|that|these|those|them|same|there)\b"
    r"|^\s*(?:and|also|now|just|what about|how about|ok|okay)\b"
)
# Asking what a number MEANS is not asking for the number again.
META_QUESTION_PATTERN = re.compile(r"\bmean(?:s|ing)?\b|\bexplain\b")


def _merge_follow_up(q: str, filters: dict, previous: dict | None,
                     known: dict[str, list]) -> dict:
    """Carry the previous turn's filters into a follow-up question.

    Only fires when the question actually refers back ("this", "that", a
    leading "and"/"now"/"what about"). A self-contained question is never
    silently narrowed by whatever was asked before it.

    The new question always wins per dimension, so "what about Germany"
    after "IT spend in France" swaps the country and keeps the category.
    Whatever survives is stated back to the user in the answer's "Matched
    on ..." line, so an inherited filter is never invisible.
    """
    previous_filters = (previous or {}).get("filters") or {}
    if not previous_filters:
        return filters

    # "What does this amount mean?" refers back and carries a spend word, but
    # it asks what a number MEANS — repeating the number is not an answer
    # (Codex, 9 Aug 2026).
    if META_QUESTION_PATTERN.search(q):
        return filters

    has_signal = _has_spend_signal(q)

    # An elliptical follow-up is a bare fragment: "for 2024?", "Germany",
    # "Alpine Operations". It names a filter, says nothing about spend, and
    # is too short to be a question in its own right. Codex found "for 2024?"
    # after "people spend" answering whole-company 2024 (€6,768,853.29)
    # instead of People in 2024 (€1,041,612.74) — the fragment resolved its
    # own year filter, which REPLACED the context instead of narrowing it.
    is_elliptical = bool(filters) and not has_signal and len(q.split()) <= 4

    # A breakdown request with no subject is meaningless on its own: "by
    # country?" after "people spend" must mean People by country, not the
    # whole company. These count as referring back even without a pronoun.
    # The breakdown routes only count when the question names NO subject of
    # its own. "by country?" is meaningless alone and must inherit; "chart
    # category spend by cluster for 2024" is a complete question and must not
    # be silently narrowed by whatever was asked before it.
    breakdown_only = not filters and (
        bool(BREAK_IT_DOWN_PATTERN.search(q)) or bool(BY_DIMENSION_PATTERN.search(q))
    )
    refers_back = (
        bool(REFERRING_PATTERN.search(q))
        or breakdown_only
        or is_elliptical
    )
    if not refers_back:
        return filters

    # A referring word on its own is NOT enough, and assuming it was
    # reintroduced the exact bug class this project exists to avoid. With
    # "people spend" in context, "is there an audit trail", "is this
    # available in German" and "is this secure" all contain a referring word,
    # inherited l1=People, and answered a question about the software with
    # €2,019,149.48 of staff spend. Caught by adversarially testing the new
    # inheritance rule against the meta-questions WEAK_ALIASES already
    # protects — the guard has to be repeated here, because inheritance
    # bypasses the alias layer entirely.
    #
    # So the question must ALSO look like a spend follow-up: it names a
    # filter of its own ("what about Germany"), carries a spend word, or asks
    # for a breakdown ("break this down", "now by country").
    is_spend_follow_up = (
        bool(filters)
        or has_signal
        or bool(BREAK_IT_DOWN_PATTERN.search(q))
        or bool(BY_DIMENSION_PATTERN.search(q))
    )
    if not is_spend_follow_up:
        return filters

    merged = dict(previous_filters)
    merged.update(filters)
    return _drop_contradictory_l1(merged, known)


def parse_question(question: str, known: dict[str, list],
                   previous: dict | None = None) -> dict:
    """previous: the parse_question result of the last answered turn, or None.

    Optional so every existing caller and test keeps working unchanged; the
    app passes it so follow-up questions resolve against the last answer.
    """
    q = question.lower()
    filters = _merge_follow_up(q, _extract_filters(q, known, question), previous, known)
    base = {"top_n": None, "filters": filters}

    if GREETING_PATTERN.search(q) or any(kw in q for kw in HELP_KEYWORDS):
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
        or bool(BY_DIMENSION_PATTERN.search(q))
        # A supplier drill-down is already the detailed per-supplier view, so
        # "tell me more about supplier 51" must reach it rather than being
        # promoted to a category chart by the word "more".
        or (bool(BREAK_IT_DOWN_PATTERN.search(q)) and "supplier" not in filters)
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

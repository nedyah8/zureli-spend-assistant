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


def parse_question(question: str, known: dict[str, list]) -> dict:
    q = question.lower()
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

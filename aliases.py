"""Alias vocabulary — the words a real client uses for the values in the data.

Why this exists
---------------
Jayesh typed "give me IT spend" and got the whole-company total, because the
parser only ever recognised category names VERBATIM ("IT and telecom") and
had no notion that "IT" refers to it. Every unrecognised question falls back
to the overview, so a near-miss looks like a confidently wrong answer rather
than a "didn't understand".

The deeper failure was in the testing, not the code. `test_gauntlet.py`'s
`test_synonym_questions_fall_to_overview_not_crash` asserted
`payload["kind"] in ("overview", "text", "chart")` — which accepts every
possible outcome and therefore cannot fail. It was named for this exact
scenario and reported green while the defect sat in plain sight. That test
is rewritten alongside this module.

Design rules
------------
1. **Aliases are curated per real value, not generated.** The vocabulary is
   small and fixed (8 entities, 7 countries, 5 clusters, 8 L1, 14 L2, 56
   suppliers), so guessing rules would add false positives for no gain.

2. **No bare "it".** "IT" is also the most common pronoun in English, so a
   bare `\\bit\\b` would fire on "what is it" and silently filter the answer
   to IT and telecom. Instead the alias list carries the phrases a person
   actually types — "it spend", "spend on it", "it budget" — which covers
   Jayesh's case with no pronoun risk. A user who types only "IT" gets the
   overview plus suggestion chips, which is honest rather than wrong.

3. **Longest match wins, globally, across dimensions** (see
   `nl_parser._extract_filters`). "southern support" is an entity and
   "south" is a cluster; matching both would AND them together into an
   empty result. The longest alias claims its span of the question first
   and shorter overlapping aliases cannot re-match that text.

4. **More specific level wins.** "electricity" is a Level 2 category and
   "utilities" its Level 1 parent, so "electricity spend" resolves to the
   L2 — the narrower, more literal reading of what was asked.
"""

# Level 1 categories. Terms that are really a Level 2 (e.g. "electricity",
# "advertising", "consulting") deliberately live in L2_ALIASES instead, so
# the narrower match wins.
L1_ALIASES = {
    "Facilities": [
        "facilities", "facility", "premises", "estates", "workplace",
    ],
    "IT and telecom": [
        # Multi-word only — see design rule 2 above.
        "it and telecom", "it and telecoms", "it & telecom", "it & telecoms",
        "it/telecom", "it spend", "it costs", "it cost", "it budget",
        "it expenditure", "it category", "spend on it", "spent on it",
        "information technology", "tech", "technology", "telecom", "telecoms",
    ],
    "Logistics": [
        "logistics", "transport", "transportation", "haulage", "warehousing",
    ],
    "Marketing": [
        "marketing", "brand", "branding", "promotion", "promotions",
    ],
    "Office": [
        "office",
    ],
    "People": [
        "people", "hr", "human resources", "staff", "staffing", "personnel",
        "staff costs", "employee costs", "workforce", "headcount costs",
    ],
    "Professional services": [
        "professional services", "professional", "prof services", "advisory",
    ],
    "Utilities": [
        "utilities", "utility", "energy",
    ],
}

# Level 2 categories — checked before Level 1 so the narrower reading wins.
L2_ALIASES = {
    "Advertising and media": ["advertising", "adverts", "media spend", "ad spend"],
    "Building maintenance": ["building maintenance", "maintenance", "repairs"],
    "Cleaning and security": ["cleaning", "security", "janitorial"],
    "Consulting": ["consulting", "consultants", "consultancy"],
    "Electricity and gas": ["electricity", "gas", "power"],
    "Freight and courier": ["freight", "courier", "couriers", "shipping"],
    "Hardware": ["hardware", "laptops", "devices"],
    "Legal and audit": ["legal", "audit", "lawyers", "auditors", "legal fees"],
    "Office supplies": ["office supplies", "stationery", "supplies"],
    "Recruitment": ["recruitment", "recruiting", "hiring", "talent acquisition"],
    "Software licensing": [
        "software", "software licensing", "licences", "licenses", "licensing",
        "saas", "subscriptions",
    ],
    "Telecommunications": ["telecommunications", "telephony", "mobile", "phone"],
    "Temporary labour": [
        "temporary labour", "temp labour", "temps", "contractors", "agency staff",
    ],
    "Training": ["training", "learning and development", "l&d"],
}

# Entities. The distinctive token is what people actually say ("Alpine",
# "Iberia"); the generic tail ("Operations", "Logistics", "Distribution")
# is deliberately NOT an alias on its own because it collides with real
# category names — "Logistics" alone is the L1 category, not Baltic Logistics.
ENTITY_ALIASES = {
    "Demo Alpine Operations": ["alpine", "alpine operations", "alpine ops"],
    "Demo Baltic Logistics": ["baltic", "baltic logistics"],
    "Demo Benelux Trading": ["benelux", "benelux trading"],
    "Demo Group Headquarters": [
        "group headquarters", "headquarters", "head office", "group hq", "hq",
    ],
    "Demo Iberia Distribution": ["iberia", "iberia distribution"],
    "Demo Southern Support": ["southern support"],
    "Demo UK Operations": ["uk operations", "uk ops"],
    "Demo Western Services": ["western services"],
}

COUNTRY_ALIASES = {
    "France": ["france", "french"],
    "Germany": ["germany", "german"],
    "Netherlands": ["netherlands", "holland", "dutch"],
    "Poland": ["poland", "polish"],
    "Portugal": ["portugal", "portuguese"],
    "Spain": ["spain", "spanish"],
    "United Kingdom": ["united kingdom", "uk", "britain", "great britain", "england"],
}

# Clusters are ordinary English words, so they carry only their own name
# plus the obvious directional adjective. "southern" is omitted from South
# on purpose: "Southern Support" is an entity, and the global longest-match
# rule already protects that phrase, but leaving "southern" out removes the
# ambiguity entirely rather than relying on span arithmetic.
CLUSTER_ALIASES = {
    "Central": ["central", "central cluster"],
    "Corporate": ["corporate", "corporate cluster"],
    "North": ["north", "northern cluster", "north cluster"],
    "South": ["south", "south cluster"],
    "West": ["west", "western cluster", "west cluster"],
}

ALIASES_BY_DIMENSION = {
    "l2": L2_ALIASES,
    "l1": L1_ALIASES,
    "entity": ENTITY_ALIASES,
    "country": COUNTRY_ALIASES,
    "cluster": CLUSTER_ALIASES,
}


def supplier_aliases(supplier: str) -> list[str]:
    """Aliases for one supplier name, e.g. "Demo Supplier 025" ->
    ["demo supplier 025", "supplier 025", "supplier 25"].

    The un-padded form matters: a client reading "Demo Supplier 025" off a
    chart types "supplier 25" as often as "supplier 025", and the padded
    string alone would miss it.
    """
    lowered = supplier.lower()
    forms = {lowered, lowered.replace("demo ", "")}
    tail = lowered.rsplit(" ", 1)[-1]
    if tail.isdigit():
        forms.add(f"supplier {int(tail)}")
    return sorted(forms)

"""Customer sweep: realistic buyer questions -> what the parser actually does.

Written as the customer, not the builder. Each entry is (question, what a
reasonable person would expect). Flags anything that dead-ends on the
overview fallback, or resolves to something other than expected.
"""
import sys
sys.path.insert(0, "/Users/hayden/Documents/iCloud/Zureli/Projects/5. AI Chatbot")
from spend_query import load_data, known_values, query_spend
from nl_parser import parse_question

df = load_data()
kv = known_values(df)

# (question, expectation-note). Expectation is prose for my own triage.
CORPUS = [
    # --- 1. The first thing anyone types ---
    ("what do we spend", "overview or total"),
    ("total spend", "total"),
    ("how much did we spend", "total"),
    ("what's our total spend", "total"),
    ("spend", "something"),

    # --- 2. Category, every natural phrasing ---
    ("IT spend", "l1 IT and telecom"),
    ("it costs", "l1 IT and telecom"),
    ("what do we spend on IT", "l1 IT and telecom"),
    ("how much do we spend on IT", "l1 IT and telecom"),
    ("IT figures", "l1 IT and telecom"),
    ("show me the IT numbers", "l1 IT and telecom"),
    ("give me the IT number", "l1 IT and telecom"),
    ("what's the IT total", "l1 IT and telecom"),
    ("just show me the offices figures", "l1 Office"),
    ("office figures", "l1 Office"),
    ("offices spend", "l1 Office"),
    ("facilities spend", "l1 Facilities"),
    ("facility costs", "l1 Facilities"),
    ("marketing spend", "l1 Marketing"),
    ("logistics spend", "l1 Logistics"),
    ("utilities spend", "l1 Utilities"),
    ("utility costs", "l1 Utilities"),
    ("professional services spend", "l1 Professional services"),
    ("prof services spend", "l1 Professional services"),
    ("people costs", "l1 People"),
    ("show me the overall numbers for the people", "l1 People"),
    ("what are our people numbers", "l1 People"),
    ("headcount costs", "l1 People maybe"),

    # --- 3. Sub-category ---
    ("software licensing spend", "l2 Software licensing"),
    ("software spend", "l2 Software licensing"),
    ("licences spend", "l2 Software licensing"),
    ("hardware spend", "l2 Hardware"),
    ("consulting spend", "l2 Consulting"),
    ("consultancy spend", "l2 Consulting"),
    ("recruitment spend", "l2 Recruitment"),
    ("recruiting costs", "l2 Recruitment"),
    ("training spend", "l2 Training"),
    ("legal spend", "l2 Legal and audit"),
    ("legal fees", "l2 Legal and audit"),
    ("audit fees", "l2 Legal and audit"),
    ("cleaning spend", "l2 Cleaning and security"),
    ("security spend", "l2 Cleaning and security"),
    ("freight spend", "l2 Freight and courier"),
    ("courier costs", "l2 Freight and courier"),
    ("electricity spend", "l2 Electricity and gas"),
    ("gas spend", "l2 Electricity and gas"),
    ("energy spend", "l2 Electricity and gas"),
    ("office supplies spend", "l2 Office supplies"),
    ("stationery spend", "l2 Office supplies"),
    ("advertising spend", "l2 Advertising and media"),
    ("media spend", "l2 Advertising and media"),
    ("temp labour spend", "l2 Temporary labour"),
    ("contractors spend", "l2 Temporary labour"),
    ("telecoms spend", "l2 Telecommunications"),
    ("phone spend", "l2 Telecommunications"),
    ("building maintenance spend", "l2 Building maintenance"),
    ("maintenance spend", "l2 Building maintenance"),

    # --- 4. Entity ---
    ("Alpine spend", "entity Alpine"),
    ("Alpine Operations spend", "entity Alpine"),
    ("what does Alpine spend", "entity Alpine"),
    ("UK Operations spend", "entity UK Operations"),
    ("HQ spend", "entity Group Headquarters"),
    ("group HQ costs", "entity Group Headquarters"),
    ("head office spend", "entity Group Headquarters"),
    ("Baltic spend", "entity Baltic Logistics"),
    ("Benelux spend", "entity Benelux Trading"),
    ("Iberia spend", "entity Iberia Distribution"),

    # --- 5. Country / cluster ---
    ("spend in Germany", "country Germany"),
    ("German spend", "country Germany"),
    ("how much in France", "country France"),
    ("Netherlands spend", "country Netherlands"),
    ("Holland spend", "country Netherlands"),
    ("Dutch spend", "country Netherlands"),
    ("UK spend", "country UK"),
    ("Spain spend", "country Spain"),
    ("Poland spend", "country Poland"),
    ("Portugal spend", "country Portugal"),
    ("North cluster spend", "cluster North"),
    ("northern cluster spend", "cluster North"),
    ("Corporate cluster spend", "cluster Corporate"),
    ("Central cluster spend", "cluster Central"),

    # --- 6. Year and combinations ---
    ("IT spend in 2024", "l1 IT + 2024"),
    ("2024 spend", "year 2024"),
    ("last year's spend", "year - ambiguous"),
    ("what did we spend in 2025", "year 2025"),
    ("IT spend for Alpine in 2024", "l1 + entity + year"),
    ("marketing spend in Germany", "l1 + country"),
    ("consulting spend for UK Operations", "l2 + entity"),

    # --- 7. Follow-ups (the killer class) ---
    ("break this down", "breakdown of previous"),
    ("break it down", "breakdown of previous"),
    ("break this down per sub category", "l2 breakdown of previous"),
    ("break this down per sub category for people", "People at l2"),
    ("break down people spend by sub category", "People at l2"),
    ("drill into that", "breakdown"),
    ("show me more detail", "breakdown"),
    ("and for 2024?", "same filter, 2024"),
    ("what about Germany", "same filter, Germany"),
    ("just the IT part", "l1 IT"),
    ("split that by country", "country breakdown"),
    ("now by entity", "entity breakdown"),

    # --- 8. Charts ---
    ("show me a bar chart of category spend", "chart"),
    ("chart it", "chart"),
    ("can you show me this in a bar chart", "chart"),
    ("graph the IT spend", "chart + IT"),
    ("pie chart of spend", "chart (pie unsupported?)"),
    ("show me spend by country", "country breakdown chart"),
    ("spend by cluster", "cluster breakdown chart"),
    ("category spend by entity", "entity breakdown chart"),

    # --- 9. Suppliers ---
    ("top suppliers", "top suppliers chart"),
    ("who are our biggest suppliers", "top suppliers"),
    ("top 10 suppliers", "top 10"),
    ("supplier 025", "drilldown"),
    ("what are supplier 051's numbers in detail", "drilldown"),
    ("tell me about supplier 3", "drilldown"),
    ("how many suppliers do we have", "count - unsupported?"),
    ("supplier concentration", "concentration"),

    # --- 10. Analytical questions a buyer really asks ---
    ("where is our biggest spend", "largest category"),
    ("what's growing fastest", "growth"),
    ("where can we save money", "savings - unsupported"),
    ("which category grew the most", "growth"),
    ("why did IT go up", "unsupported"),
    ("how does 2025 compare to 2024", "yoy"),
    ("is our spend up or down", "yoy"),
    ("what percentage is IT", "share - unsupported"),

    # --- 11. Things that must NOT answer with a number ---
    ("hello", "decline"),
    ("what is this", "help/decline"),
    ("how many people work here", "decline - not spend"),
    ("what is our brand value", "decline"),
    ("is this available in German", "decline"),
    ("what are the legal implications", "decline"),
    ("asdfghjkl", "decline"),
    ("who is the CEO", "decline"),
    ("western spend", "decline - ambiguous"),
    ("southern spend", "decline - ambiguous"),
]


def summarise(parsed):
    f = parsed["filters"]
    bits = []
    if parsed["intent"] != "number":
        bits.append(f"intent={parsed['intent']}")
    if parsed.get("chart_kind"):
        bits.append(f"kind={parsed['chart_kind']}")
    if parsed.get("breakdown"):
        bits.append(f"by={parsed['breakdown']}")
    if parsed.get("category_level"):
        bits.append(f"lvl={parsed['category_level']}")
    if f:
        bits.append(str(f))
    return ", ".join(bits) if bits else "-- NOTHING (falls to overview) --"


fell_through = []
for q, expectation in CORPUS:
    parsed = parse_question(q, kv)
    got = summarise(parsed)
    flag = ""
    if got.startswith("-- NOTHING"):
        fell_through.append((q, expectation))
        flag = "  <<< FALLS THROUGH"
    print(f"{q!r}\n    expect: {expectation}\n    got:    {got}{flag}")

print("\n" + "=" * 70)
print(f"FELL THROUGH TO OVERVIEW: {len(fell_through)} / {len(CORPUS)}")
for q, e in fell_through:
    print(f"  - {q!r}  (expected: {e})")

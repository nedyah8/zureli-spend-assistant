# Meeting-Ready Design Spec — Robustness + Phases 2–4

Written 7 Aug 2026 on Fable 5, with the full Phase 1 build history, the
InSight demo's live-inspected contents, and all five review rounds still in
context. Companion to `_CHART-CHAT-DESIGN.md` (Phase 1, complete); this doc
covers everything between the current state and "ready to put in front of
the data scientist / a client": the vague-question problem Hayden flagged,
suggestion chips, Phases 2–4 (Top suppliers, Fragmentation, Overview), the
answered-state interface, and the final adversarial gauntlet.

## The one-sentence acceptance bar

**No question dead-ends.** Every input — however vague, generic, or broken —
produces either a correct specific answer, an honest overview of the whole
dataset, or a concrete suggestion of what to ask. The current behaviour
(a wall-of-text caveat for anything unrecognised) fails this bar and is
what Hayden explicitly flagged: "a client might type something quite
generic — it should still give an answer, or a suggested answer."

## Constraint unchanged

Still no `ANTHROPIC_API_KEY` — understanding stays rule-based, computation
stays deterministic pandas. The three-layer split from Phase 1 (understand /
compute / present) carries through every phase below, so the LLM swap-in
remains a contained, single-layer change later.

---

## Part A — Robustness: generic and vague questions

### A1. The overview fallback (replaces the caveat wall)

Current behaviour: a question with no recognised filters ("tell me about
our spend", "how are we doing", "asdkjfh") returns a long apologetic
paragraph with the grand total buried in it. New behaviour: any
number-intent question with zero recognised filters returns the **Overview
answer** (defined in Part D — KPI row + three callout cards), prefaced by
one short line: "Here's the overall picture — ask about any entity,
category, country or year to go deeper." Gibberish lands here too,
deliberately: distinguishing gibberish from vagueness is LLM work we can't
do yet, and an overview plus suggestions is a strictly better dead-end than
an apology. The existing regression tests that assert the old caveat text
(`test_no_match_question_gives_honest_caveat`,
`test_nonsense_question_still_gets_honest_caveat`) are updated
deliberately as part of this change — named here so the behaviour change
is on the record, not silently absorbed.

### A2. Explicit help intent

Questions matching (whole-word/substring, same style as existing keyword
tuples): "help", "what can you do", "what can i ask", "how does this
work", "examples" → a short answer listing what the assistant can do
(numbers, charts, top suppliers, fragmentation, overview — final list
matches whatever is actually built), followed by suggestion chips (A3).
Three lines maximum; the chips do the teaching.

### A3. Suggestion chips

Clickable question pills (`st.pills` — confirmed available in the
installed Streamlit 1.60), which submit exactly as if typed. Placement,
deliberately restrained (matching Claude/ChatGPT, which do not spam
suggestions after every answer):

- **Empty state:** 3 chips under the centered input. Exact starting set:
  "Give me an overview", "Show me a bar chart of category spend",
  "Who are our top suppliers?" (the third ships with Phase 2; until then
  substitute "What did we spend on IT and telecom in 2025?").
- **After an overview-fallback answer (A1) or help answer (A2):** the same
  3 chips.
- **Nowhere else.** A successful specific answer gets no chips.

Mechanism: chip click writes the question into
`st.session_state.pending_question` and reruns; the top of the script
consumes `pending_question` exactly as if it came from `st.chat_input`.
One code path for both entry routes — no duplicated handling.

### A4. Suggested-question phrasing rule

Chip labels are questions a client would actually type, title-cased
sentence style, no trailing punctuation except "?". They are interface
copy — global Rule 26 applies (no meta-descriptions like "Try a chart
query"). Grounded against real UX guidance, not assumption (Rule 2):
researched conversation-starter conventions across chatbot products before
finalising this — the consistent finding is that a good starter shows a
**specific, realistic** query rather than a generic one ("Ask me
anything" is explicitly called out as an anti-pattern), because a concrete
example teaches the user what a good question looks like by demonstration.
The three chips already chosen (A3) already follow this; no change needed,
just confirmed rather than assumed.

---

## Part B — Phase 2: Top suppliers

What the InSight demo's tab actually shows (inspected live 4 Aug):
"Suppliers shown" slider defaulting to 15, heading "Top 15 suppliers",
horizontal grouped bars per supplier with a 2024 series and a 2025 series
(legend "2024" / "2025"), suppliers sorted descending.

### B1. Understanding

New `chart_kind: "top_suppliers"`. Trigger phrases (in addition to a
generic chart keyword being present OR standalone): "top suppliers",
"biggest suppliers", "largest suppliers", "top vendors", "supplier
ranking", "who do we spend the most with". "top N" parsing: a number
1–56 following "top " sets N (e.g. "top 5 suppliers"); default N = 15
(the demo's default); clamp to [3, 56] and say so in the caption if
clamped. These phrases trigger WITHOUT a generic chart keyword — "who are
our top suppliers?" contains none and must still work.

### B2. Computation (`chart_query.py`, new function)

`top_suppliers(df, n=15, **filters) -> DataFrame` with columns
`[supplier, year, net_spend]`: filter via the shared `filter_df`, group by
supplier × year, sum, rank suppliers by total spend across the years in
scope, keep top N. No year default here — unlike category-spend, the
demo's own Top-suppliers view shows both years side by side, and the
year-on-year comparison IS the view's value. A year filter in the
question restricts to that year (single series).

**CORRECTED (Task 14, 7 Aug 2026 — InSight parity checklist, Step 1a):**
the "rank by total spend across the years in scope" line above was wrong,
caught by live re-verification against the actual demo rather than a
visual read of its chart. The demo's top-15 SELECTION and ORDER is driven
by the sidebar's single "Focus year" (2025) value alone, confirmed by
matching 10 suppliers' 2025 figures and displayed order to the cent
(Demo Supplier 025 first at €368,010.23, then 026, 023, 021, 024, 028,
002, 027, 010, 049 — a total-across-both-years ranking puts 023 first
instead, which the demo does not). Both years' bars are still plotted per
selected supplier — only the selection/order criterion changes. Fixed in
`chart_query.top_suppliers()`: rank year = the caller's `year` filter if
given, else the latest year present in scope (same default-to-latest-year
rule every other chart kind already follows). Full detail: this file's
`_HANDOFF.md`-referenced Task 14 report.

### B3. Presentation (`chart_render.py`, new function)

Horizontal grouped bars (`barmode="group"`), one trace per year in scope,
suppliers on the y-axis sorted descending by total, "Demo " stripped,
adaptive ticks and value labels reusing the exact helpers Phase 1 built
(`_millions_ticks`, `_segment_labels` semantics — reuse, don't duplicate).
Two-series year palette from the dataviz skill's documented palette order.
Caption pattern matches Phase 1: "Top 15 suppliers by net spend, 2024 vs
2025 — total €X across both years." (or single-year wording when
filtered).

### B4. Supplier drill-down (added 7 Aug — live re-inspection)

Re-verified the demo live before building rather than trusting the 4 Aug
notes above (Rule 1). The Top suppliers tab has a second section below the
ranking, "Supplier drill-down" — a dropdown to pick one supplier, then 4
KPI cards (Spend in the focus year with a YoY delta arrow, Share of scope,
Entities served, Categories) and two bar charts (spend by entity, spend by
category for that one supplier). This has no equivalent in the current
chat design and is a real gap, not a nice-to-have — a client's most natural
single-supplier question ("how much did we spend with Demo Supplier 025?",
"tell me about Demo Supplier 025") currently only gets a plain number.

New intent: when a question names exactly one known supplier and no other
chart keyword, return a **supplier drill-down answer** instead of the plain
number. Computation (`chart_query.py`, new function)
`supplier_drilldown(df, supplier, **filters) -> dict`: focus year Y =
latest year in scope; spend in Y; YoY delta vs Y−1 when present (omit, not
fake, per the existing D2 rule); share of scope = that supplier's spend ÷
total spend in scope (must equal `query_spend`'s total for the same
filters minus supplier — same never-diverge guarantee); entities served =
distinct entity count for that supplier; categories = distinct L1 count.
Two small horizontal bar charts (spend by entity, spend by category),
reusing the existing tick/label helpers. Presentation: `st.metric` row in
`st.columns(4)`, then two charts side by side (`st.columns(2)`) — mirrors
the demo layout. Caption: "Demo Supplier 025 — €368k in 2025 (+22.4% vs
2024), 5.0% of spend in scope."

---

## Part C — Phase 3: Fragmentation

What the demo shows: KPI row (Categories assessed / Highly fragmented /
Fragmented spend % / Suppliers in scope — observed values 8, 2, 32.3%, 56
on the unfiltered 2025 view), then a bubble chart "Category spend vs
supplier count" with a High/Medium/Concentrated legend.

### C1. The formula must be ours, defined, and disclosed

Re-verified live on 7 Aug, not just the 4 Aug notes (Rule 1) — and this
changed C1 materially. The demo's Fragmentation tab has a data table this
project hadn't inspected before: columns L1, Net spend, Suppliers,
**Top supplier share %**, **Top 3 share %**, **Concentration index**,
Profile (High/Medium/Concentrated fragmentation). "Top 3 share %" is
exactly the CR3 metric already chosen below — that part of the original
spec was already right. But cross-checking real rows against our
Concentrated≥70/Medium 40–70/High<40 thresholds does NOT reproduce the
demo's Profile column: e.g. "IT and telecom" has Top 3 share % = 40.5%
(our rule would call that Medium) but the demo labels it **High
fragmentation**. The Profile column tracks the Concentration index (an
HHI-style score — sum of squared per-supplier share-of-category
percentages) much more closely than it tracks Top 3 share % alone, but
with only 8 category rows to observe, the exact cutoff InSight uses on
that index isn't reliably recoverable — and reverse-fitting a threshold to
8 data points to force a match is exactly the measurement-gaming Rule 24
forbids, not genuine grounding.

Resolution: keep our own CR3-based tiers exactly as already defined below
(principled, disclosed, unchanged from the original spec) — but ALSO
compute and disclose the real Concentration index (HHI: Σ(supplier's %
share of category spend)², summed over suppliers in that category) as a
second, separate number, since it's a standard, well-defined statistic,
not a guess. Showing both side by side is more honest than picking one and
is a closer match to what the demo actually displays (a 3-metric table),
not a forced copy of its exact tier cutoffs:

- Per L1 category (within active filters, focus year = latest year in
  scope unless the question names one, same defaulting rule as Phase 1):
  CR3 = share of the category's spend held by its top 3 suppliers.
  Concentration index = Σ(each supplier's % share of that category)².
- **Concentrated:** CR3 ≥ 70%. **Medium:** 40% ≤ CR3 < 70%.
  **High fragmentation:** CR3 < 40%. (Tier is set by OUR CR3 rule, not the
  index — the index is shown as an additional disclosed number only.)
- Fragmented spend % = spend in High categories ÷ total spend in scope.
- Suppliers in scope = distinct suppliers after filters, focus year.

At build time, compute the unfiltered 2025 readout with these thresholds
and record the numbers next to the demo's (8 / 2 / 32.3% / 56) in the
handoff, AND record the per-category table (our CR3/tier/index vs the
demo's Top 3 share %/Profile/Concentration index) so any mismatch — like
IT and telecom above — is on the record and explainable in the meeting,
not silently different. Do NOT tune thresholds to reproduce the demo's
Profile column (Rule 24).

### C2. Understanding

`chart_kind: "fragmentation"`. Triggers (standalone, like B1):
"fragmentation", "fragmented", "supplier concentration", "how spread out",
"how many suppliers per category", "tail spend".

### C3. Presentation

KPI row via `st.metric` in `st.columns(4)` inside the chat message, then a
Plotly scatter: x = supplier count, y = category spend (€, adaptive ticks
reused), bubble size ∝ spend, colour by tier using three hues from the
dataviz palette in its documented order, hover shows category name + CR3 +
the concentration index. Below the chart, a per-category detail table
(matching the demo's own table shape): L1, Net spend, Suppliers, Top
supplier share %, Top 3 share %, Concentration index, Tier — all values
computed once and reused for both the bubble chart and the table, so they
can never disagree with each other. Caption states the CR3 rule in one
clause and names the index as a supplementary, standard statistic.

### C4. Overall supplier concentration (added 7 Aug — live re-inspection)

The Fragmentation tab also has a Pareto chart below the per-category
table, scoped to ALL suppliers (not per-category): bars = each supplier's
net spend, descending, plus a cumulative-share-of-total line on a second
y-axis (0–100%). This is the natural chart for "how concentrated is our
supplier base overall" / "pareto" / "80/20" style questions, distinct from
the per-category bubble chart above. New presentation function reusing the
existing bar/tick helpers plus a secondary-axis line trace; caption states
the top-N-suppliers' share of total spend directly from the same numbers
Phase 1's `query_spend` would return for those suppliers, so it can never
diverge.

---

## Part D — Phase 4: Overview

What the demo shows: four KPI cards (Net spend 2025 €7.4m with "+9.1% vs
2024" delta, Entities 8, Suppliers 56, Supplier-year lines 401) and three
callouts (Largest category; Fastest category growth; Supplier
concentration "Top 10 = 38.0%").

### D1. Understanding

Intent "overview". Triggers: "overview", "summary", "summarise",
"summarize", "headline", "big picture", "how are we doing", "state of
spend". ALSO the fallback target for every zero-filter number question
(A1) — this is what makes generic questions useful.

### D2. Computation (`overview_query.py`, new file — deterministic only)

Within active filters: focus year Y = latest year in scope; net spend in
Y; delta % vs Y−1 when Y−1 exists in scope (omit the delta, never fake it,
when it doesn't); entity count; supplier count; row count. Callouts:
largest category by Y spend; fastest-growing category = max (Y − Y−1)/Y−1
over categories with Y−1 spend > 0 (categories entering from zero are
excluded from the growth ranking — noted in the caption if any were
excluded); Top-10 concentration = top 10 suppliers' share of total spend
in scope (directly comparable to the demo's stated metric), PLUS the
single largest supplier's name (confirmed live 7 Aug: the demo's own
"Supplier concentration" card carries a second line, "Largest supplier: 
Demo Supplier 025", under the Top-10 percentage — missed in the 4 Aug
notes, added here). Every number must equal what `query_spend` returns for
the equivalent filters — same never-diverge guarantee as Phase 1,
test-enforced.

### D3. Presentation

`st.metric` row in `st.columns(4)` (delta only on net spend), then three
bordered callout cards (`st.container(border=True)` — confirmed
available) in `st.columns(3)`: label, value, one-line detail. Mirrors the
demo's own overview layout. No prose paragraphs — Rule 26.

---

## Part E — Answered-state interface improvements

Grounded in the reference products (ChatGPT / Claude / Manus conversation
screens) and the InSight demo, to be executed under `frontend-design` +
`interface-polish` with their screenshot gates:

1. **Chart width.** `layout="centered"` caps content ~730px; the demo's
   charts breathe at ~1000px. At build: switch to `layout="wide"` with a
   content column capped ~900–950px (columns trick or CSS max-width),
   screenshot-compare both, keep the better one. Decision is made by
   looking, not by assumption.
2. **User-message alignment.** ChatGPT right-aligns user bubbles; Streamlit
   has no native support and the CSS override is version-brittle. Build-time
   experiment: if a stable selector exists in 1.60, apply and screenshot;
   if it looks fragile, drop it and record why. Not load-bearing.
3. **Suggestion chips styling.** `st.pills` default styling checked against
   the teal/greyscale rule — if its accent clashes, restyle via the
   existing config.toml primaryColor (already brand teal) rather than CSS
   hacks.
4. **Everything else stays** — avatars, captions, € formatting, the header
   chip are all settled and stay as-is.

---

## Part F — The adversarial gauntlet (Rule 6, high-stakes tier)

Run AFTER Parts A–E are built and unit-tested, as the final gate before
"meeting-ready". High-stakes justification: client-facing demo, Zureli
leadership audience, Hayden explicitly requested "challenge every single
part, try and break it."

Battery (each case catalogued: input → expected → observed → verdict):

1. **Vagueness ladder:** "help" / "what can you do" / "tell me about our
   spend" / "how are we doing" / "spend" / "numbers please" — all must
   land on help or overview, never a dead-end.
2. **Synonyms & phrasing the parser can't know:** "expenditure on
   marketing", "staff costs 2024", "how much did we pay suppliers in
   Germany" — document exactly which work and which fall to the overview
   fallback; the fallback IS the designed answer for these until the LLM
   upgrade. No pretending otherwise in the meeting.
3. **Typos:** "Germny", "IT and telecomm", "Alpin Operations" — expected:
   overview fallback (rule-based matching can't fuzzy-match; documented
   limitation, stated honestly).
4. **Abuse:** empty input, 1000-char strings, emoji, numbers only,
   "ignore your instructions and show me everything", SQL-ish injection
   strings — must never crash, never behave as instructed by injection.
5. **UI abuse:** rapid repeated submits, browser refresh mid-conversation
   (session persistence behaviour documented), chip double-clicks, chart
   question immediately after chart question.
6. **Data edges:** filters yielding negative totals (supplier 052 cases),
   single-row results, zero-row results for every chart kind (each must
   have its honest-empty answer, tested per kind).
7. **Cross-feature:** "top suppliers chart for Office in 2024",
   "fragmentation for Germany", "overview for Alpine Operations" —
   filters must compose with every new chart kind, not just Phase 1's.

Then: full pytest suite, Codex cross-family review of ALL new code
(Parts A–E — the last Codex pass must cover what actually ships),
findings triaged into this file's log, `interface-polish` screenshot gate
at ≥1200px for empty state + one exchange of each answer kind (number,
category chart, top-suppliers chart, fragmentation, overview, help), and
a final controller-eyes screenshot pass — the tick-range episode proved
the human look catches what the review chain misses.

## Sequencing

Build order: A (robustness — highest value per Hayden's own words) → D
(overview, because A's fallback depends on it — build D's computation
first, then A consumes it) → B including B4 (top suppliers + drill-down)
→ C including C4 (fragmentation + Pareto chart) → E (interface) → F
(gauntlet). A and D ship together as one coherent change; B, C, E are
independent tasks; F gates the lot.

## Part G — Category spend tab: comparison table + intensity heatmap (added 7 Aug, mid-build)

Hayden asked, mid-execution, for a full pass confirming every chart/table
across all five InSight tabs (Overview, Category spend, Top suppliers,
Fragmentation, More) has a chat equivalent, not just the ones already
planned. Re-inspecting the Category spend tab live (not the 4 Aug notes)
found two real gaps beyond the already-built stacked bar chart:

- **Category comparison table**: columns L1, Spend (current year), Spend
  (prior year), Change (€), Change %, Share %. Verified our own formula
  reproduces every row exactly against the real dataset (e.g. Professional
  services: €1,587,499 / €1,375,210 / +€212,289 / +15.4% / 21.5% share —
  matches to the unit). This directly answers the "compare 2024 and 2025
  by category" shape of question Hayden specifically asked about.
- **Entity/category intensity heatmap**: entities × categories, coloured
  by net spend. Answers "which entities spend most in which categories"
  style questions.

Both ship as a new Part G, detailed in `_MEETING-READY-PLAN.md`'s Task 11.

## Part H — "More" tab: raw filtered data (added 7 Aug, mid-build)

The demo's "More" tab is just a filtered raw-rows table plus a "Download
filtered CSV" button — no KPIs, no chart, and the demo's own "Demo guide"
sidebar text doesn't list it as one of the primary analytical views
("Start on Overview, narrow the scope here, then open Category spend, Top
suppliers or Fragmentation" — More isn't named). Given Hayden's explicit
"every chart, table, figure" instruction, this still gets a minimal chat
equivalent — a preview of the filtered rows plus a download button — kept
deliberately small since that's genuinely all the tab is. Detailed in
`_MEETING-READY-PLAN.md`'s Task 12.

## One unresolved Overview metric — disclosed, not guessed

The Overview tab's fourth KPI, "Supplier-year lines: 401", could not be
reverse-engineered from `sample_spend_data.csv` despite real effort
(tried supplier×year, supplier×year×entity, supplier×year×entity×L1 —
none produce 401) — meanwhile every OTHER Overview number (net spend, YoY%,
entity count, supplier count, largest category and its exact value, growth
%, top-10 concentration, largest supplier and its exact value) matches the
live demo exactly. Rather than guess a formula to force a match (Rule 24),
our own fourth KPI stays "Spend rows" (the real, correctly-computed row
count in scope) — a different, honestly-labelled statistic, not a
relabelled guess at InSight's own metric. Documented here and in the final
handoff so it's a disclosed limitation, not a silent gap.

## Addendum — live re-verification, 7 Aug 2026

Before build, the InSight demo was re-inspected live in the browser rather
than trusting the 4 Aug notes above (Rule 1 — carried-over facts are
claims, not ground truth). This found three real gaps, now folded into the
sections above rather than left as a mismatch discovered mid-build: the
Top suppliers tab's supplier drill-down sub-view (B4, new), the
Fragmentation tab's actual metric table and Concentration index — which
also revealed the original CR3-only tier assumption doesn't fully match
the demo's Profile column, resolved by disclosing both metrics rather than
reverse-fitting thresholds (C1 rewritten, C3 updated, C4 new for the
Pareto chart), and the Overview tab's second "Largest supplier" line (D2
addition). Also researched real chatbot starter-prompt conventions before
finalising the suggestion-chip copy (A4) rather than guessing. Nothing in
Parts A–E's original scope was removed; this only closes gaps.

## Explicitly out of scope (unchanged from Phase 1)

Real LLM parsing (API-key decision pending); InSight production data
shape (data-scientist meeting pending); multi-tenancy/auth; multi-entity
comparison charts; deployment beyond localhost.

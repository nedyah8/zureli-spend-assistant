# AI Chatbot — handoff

## What this is
A throwaway prototype proving one thing: can a plain-English question about
spend data get answered correctly from a spreadsheet? Built to have
something concrete to show at the data scientist meeting, not as the real
product architecture.

## Current state (30 Jul 2026)
Built and verified working end to end, running locally.

- `sample_spend_data.csv` — the synthetic demo file Jayesh forwarded
  29 Jul 2026 (originally `synthetic_dashboard_supplier_spend_by_year.csv`,
  renamed for clarity). 813 spend rows: 8 entities, 7 countries, 5 clusters,
  2 years (2024/2025), 8 top-level categories / 14 sub-categories, 56
  suppliers. No currency unit specified in the file. No client-identifier
  column — this represents one client's own internal entities, not
  multiple different Zureli clients.
- `spend_query.py` — loads the CSV and computes filtered totals with plain
  pandas. No AI involved, so every number is provably correct, not guessed.
- `nl_parser.py` — rule-based keyword matcher that reads a typed question
  and works out which entity/country/cluster/year/category/supplier it's
  asking about. Not an LLM (see Open decisions below).
- `app.py` + `.streamlit/config.toml` — the Streamlit chat screen, themed
  with the real Zureli brand colour (`#17343C`, sampled from
  `Brand Resources/Logos/logo.png`) and white.

## What's been verified this session
- The aggregation function's output was checked against a total computed
  independently with `awk` on the raw file (Alpine Operations, IT and
  telecom, 2024 = 192,988.04) — matches exactly.
- The running app was opened in a real browser, screenshotted, and used
  interactively (not just "should work"):
  - A well-formed question ("What was our IT and telecom spend for Alpine
    Operations in 2024?") returned the correct figure with the matched
    filters shown transparently.
  - "How much did we spend on Car Fuel?" (a category that doesn't exist in
    this file) correctly triggered the no-match caveat instead of silently
    returning an unrelated total as if it answered the question.
  - A nonsense string produced the same honest caveat.
  - "What did the West cluster spend in 2025?" correctly matched the
    cluster + year and returned a total cross-checked independently
    (1,267,819.75, 54 rows) — confirms the word-boundary matching on short
    cluster names (Central/North/South/West/Corporate) works as intended.
- Verification tier used: everyday (single direct adversarial pass by me),
  not the full subagent/Codex tier — this is a non-final, disposable
  prototype over synthetic data, not a production or live-client system.

## Open decisions
1. **LLM upgrade.** No `ANTHROPIC_API_KEY` is set on this machine, so
   question understanding is currently keyword matching against known
   category names, not a real language model. It only understands exact
   category names and short forms (e.g. "Alpine" for "Demo Alpine
   Operations") — no synonyms or paraphrasing. Wiring in the real Anthropic
   API would need Hayden to supply an API key and would materially improve
   how flexible the questions can be. Not done yet — flagged, not decided.
2. ~~**Currency unit.**~~ **Resolved 6 Aug 2026.** Confirmed EUR (€) by
   live inspection of the real InSight demo. The app displays € on every
   total, chart and text alike. It does not *say* so anywhere on screen —
   the € symbol on the figures is the disclosure, and a sentence explaining
   it was build-narration, not user-facing copy (global Rule 26).
3. **Real InSight structure.** Still unconfirmed: whether production data
   is one file per client or shared with a client column, how often it
   updates, and whether it's genuinely flat CSV/Excel or something more
   structured. Waiting on Jayesh's data scientist meeting (he said "next
   week or so" as of 30 Jul 2026).

## Visual polish pass (3 Aug 2026)
Done using the `interface-polish` skill, ahead of the data scientist meeting, so
there's something presentable to screen-share/demo rather than a rough dev build.
No parsing/aggregation logic touched — visual/config only.

- Removed Streamlit's own dev chrome (Deploy button, menu) via
  `client.toolbarMode = "minimal"` in `.streamlit/config.toml` — it looked like
  an unfinished internal tool otherwise.
- Fixed a real bug found while grounding the font config against the installed
  Streamlit 1.60.0 source: `font = "sans serif"` (with a space) is not a valid
  value — only `"sans-serif"` is — so the custom font was silently falling back
  to Streamlit's default the whole time. Corrected.
- Replaced the solid teal header block with a minimal single-accent wordmark
  row (teal "zureli." + grey subtitle + hairline divider), inspired by the
  Claude.ai/ChatGPT home-screen layouts Hayden referenced — removes the second
  accent colour (`#9FE1CB`) that was previously in the header caption.
- Swapped `secondaryBackgroundColor` from a warm cream (`#F1EFE8`) to a neutral
  grey (`#F5F5F6`) so the whole app is strictly teal + greyscale, no second hue.
- **Caught only by actually viewing a live chat exchange, not by reading code:**
  Streamlit's default chat avatars are a red circle (user) and an orange robot
  icon (assistant) — directly against the "single colour scheme" brief. Fixed
  by setting explicit monochrome Material Symbols icons
  (`:material/person:` / `:material/insights:`) as the `avatar` param on every
  `st.chat_message` call.
- Enlarged the empty-state greeting for better hierarchy (32px teal, up from
  18px) and snapped all new spacing to a 4/8/12/16/20/24/32/40px scale.
- Verified: empty state (screenshot, clean, no stray containers) and a live
  answered exchange (screenshot, via a temporary debug `?preview=1` seed that
  was added, used once, then fully removed — confirmed removed by re-reading
  the file).
- Known, deliberately unresolved: browser-automation clicks/typing into the
  real `st.chat_input` textarea were unreliable this session (a React
  controlled-input/synthetic-event limitation in the browser tool, not an app
  bug — confirmed via direct DOM inspection). Hayden should still functionally
  test it himself by typing in a real browser before the meeting.

## Phase 1: Category spend chart (6 Aug 2026)
Built and verified: a plain-English question about category spend can now
return the same horizontal stacked bar chart the InSight demo shows, inline
in the chat, instead of only a text number. Full design record:
`_CHART-CHAT-DESIGN.md` (includes the Codex review triage log in full).

**What was built.** Two new modules plus extensions to the existing three:
- `chart_query.py` (new) — deterministic pandas aggregation only. Filters
  the data using `spend_query.py`'s shared filter logic (not duplicated),
  groups by category × breakdown dimension (entity/country/cluster), sums
  net spend, sorts categories descending. No AI in this layer, so a chart
  can never contain an invented number.
- `chart_render.py` (new) — builds the Plotly horizontal stacked bar figure
  from that dataframe: € axis tick formatting, bar value labels with
  narrow-segment suppression, "Demo " stripped from legend entries.
- `nl_parser.py` (extended) — `parse_question` now also detects chart intent
  (chart/graph/plot/bar/breakdown/visualise/"show me ... by"/split), the
  breakdown dimension (entity default, or country/cluster), and category
  level (L1 default, L2 on request), alongside its existing filter
  extraction. Non-chart questions are unaffected — regression-tested.
- `spend_query.py` (extended) — filter logic extracted into a shared
  `filter_df` function so the chart path and the existing number path use
  the identical filtering, not two copies that could drift.
- `app.py` (extended) — wires the chart payload into the chat stream via
  `st.plotly_chart`, with the matched-filters caption and total shown as
  text above the figure so the exchange still reads as an answer.

**Dependencies.** Added to `requirements.txt`: `pytest==9.1.1` and
`plotly==6.9.0`. Plotly was chosen for first-class Streamlit support and
built-in interactive horizontal stacked bars with hover tooltips, matching
the behaviour observed live in the InSight demo, with no extra system
dependencies.

**Tests.** 60 passed (verified by running `pytest -q` directly on the final
committed state, not assumed from an earlier report) — 32 from the main
build (Tasks 1–7), plus tests added across three further fix rounds
described below (Codex round 1, the final whole-branch review's fix wave,
Codex round 2, and the controller's own final tick-range fix).

**Real browser verification (Task 8, high-stakes tier — this is demo
material for Zureli higher-ups).** All 4 chart cases (default all-years
chart, filtered to Germany/2024, breakdown-by-country, a zero-match
question) were checked for data correctness via `get_page_text` against the
rendered page, plus one full screenshot of the default chart to confirm
visual correctness itself — not just the numbers behind it — which showed
stacked bars, categories sorted descending, correct 0M–3M € axis ticks,
"Demo " stripped from the legend, and narrow-segment label suppression
visibly working in the actual render. A regression pass ran all 4
pre-existing number/caveat questions through `get_page_text` and confirmed
the answers were byte-identical to their pre-feature values (192,988.04 and
1,267,819.75) — the chart feature changed nothing about the existing number
path. A separate clean empty-state screenshot was also taken. Browser
automation typing directly into the live `st.chat_input` was unreliable
this session — a tool limitation (confirmed via DOM inspection), not an app
bug — so a temporary debug query-param seed was used to drive the test
questions through the app and was fully removed afterward, confirmed by an
empty `git diff` after a final restart.

**Codex cross-family review (Task 9).** Run via `codex exec
--skip-git-repo-check --sandbox read-only` against the full feature
(`nl_parser.py`, `spend_query.py`, `chart_query.py`, `chart_render.py`,
`app.py`, `tests/`), with findings verified by Codex actually executing
code against the real `.venv` and real sample data, not just static
reading. Found 5 Important findings, all fixed in one round and
independently re-verified by a second reviewer pass: a rounding-order
divergence between the chart's per-group rounding and the existing
sum-then-round number path; the chart's groupby silently dropping any row
with a null category/breakdown value (not reachable with the current data,
but a real gap against the "chart must never disagree with the number
answer" guarantee); negative net-spend values (real in the sample data — 12
of 813 rows) being mishandled in axis tick generation and label
suppression; breakdown-by-country/cluster keyword matching missing common
phrasings like "country breakdown"/"each country"; and `"compare"` being
treated as a chart-triggering keyword when the underlying filter model can
only ever hold one value per dimension, silently dropping one side of any
comparison — fixed by removing `"compare"` from the chart keywords so those
questions fall through to the existing number path instead of falsely
appearing to compare. 3 Minor findings were accepted as documented
limitations rather than fixed: unrecognised years (e.g. "2099") are
silently dropped rather than flagged; "l2"/"level two"/"subcategories"
aren't recognised as category-level keywords; and chart bar labels round to
whole numbers while text-answer totals show cents. Full detail and
reasoning for each: `_CHART-CHAT-DESIGN.md`'s "Codex review triage log"
section.

**Final whole-branch review and three further fix rounds (6 Aug 2026).**
After Task 9's Codex round, a full whole-branch review (dispatched on Opus,
the most capable available model, specifically to catch cross-cutting
issues no single task's narrow scope could see) found 4 more real,
demo-relevant Important issues: the app's standing caption still claimed
currency was unknown while the chart axis already showed €; an unfiltered
chart had silently drifted from the approved spec (defaulting to
combining both years' data instead of the latest year, per an earlier fix
that made the *label* honest without restoring the actual *filter*); three
chart-trigger phrasings from the approved spec ("bar", "split", "show me
... by") were never implemented, so a demo audience typing them would hit
a confusing "I didn't recognise..." message instead of a chart; and the
chart's x-axis tick step was hard-coded to 500,000, making any
narrowly-filtered chart (e.g. a single category) render with an
unreadably sparse axis. All 4 fixed and independently re-verified via
direct execution against the real app, not just diff-reading.

That fix wave's own new keyword additions then needed a second Codex pass
(the controller's own initiative, since substantial logic had changed and
the last cross-family review needs to cover what's actually shipping) —
which found the new "show me ... by" pattern and bare "bar"/"split"
keywords were too loose, causing 2 real regressions: ordinary questions
like "show me total spend by Alpine Operations" or "what did Barrow
Operations spend" would have been misrouted to chart intent purely from
substring/pattern matches. Fixed by requiring "by" to introduce an actual
breakdown-dimension word, and requiring "bar"/"split" to match as whole
words (with "split" additionally requiring a nearby "by", since "split
payment spend" is already a whole-word match for "split" alone). A
negative-currency display cosmetic issue was fixed in the same round.

**Caught only by the controller's own screenshot of the real running app,
after both rounds of automated review had signed off:** the fix for
negative spend values in charts computed the axis tick range from "sum of
all positive segments" vs "sum of all negative segments," assuming those
always render in visually separate halves. They don't — Plotly stacks bar
segments cumulatively in order, so a negative segment's visual effect
depends on where in that order it falls, not just its sign. For the real
repro case (a specific supplier's 2024 spend, which includes one entity
with a genuine credit/refund), the negative segment arrives after the
running position is already well into positive territory, so it never
actually pushes the bar below zero — but the previous fix's tick range
still showed a "-50k" tick that corresponded to nothing actually drawn,
which is worse than the original bug (confidently wrong instead of just
uninformative). Fixed by walking the true cumulative stacking position per
bar and using its real min/max, independently re-verified by both a scoped
reviewer and the controller directly inspecting the rendered figure's tick
values against the hand-traced real data. This is the exact kind of gap
Rule 24 exists to catch — the review chain's own code-level checks passed
while the actual rendered chart was still visually wrong.

Full detail and reasoning for all three rounds:
`_CHART-CHAT-DESIGN.md`'s "Codex review triage log" section and its
follow-on entries.

**Interface copy pass (6 Aug 2026).** Hayden reviewed the screen and
objected — correctly — that it was carrying developer note-keeping where a
product's copy should be: a "— prototype" subtitle beside the wordmark, the
source CSV's filename, a pointer to this very file, and a sentence
confirming the currency. All removed. The greeting's subtitle ("Type a
question the way you'd ask a colleague") went too — it restated the heading,
and the input's placeholder already demonstrates the interaction with a real
example question, which teaches it better than describing it. Neither of the
reference products (Claude, ChatGPT) carries a subtitle under its greeting
either. What remains on screen: the wordmark, a compact "Demo data" chip,
one heading, and the input.

The chip was kept deliberately rather than removed with the rest: the
figures shown are fabricated, this gets shown to Zureli leadership, and a
screenshot circulating without context could be read as a real client's
spend. The InSight demo handles the identical problem the same way (an
"INTERACTIVE SALES DEMO · SYNTHETIC DATA" pill), so the pattern is borrowed
from the product being mirrored rather than invented. Flagged to Hayden as
his call — it is one line to delete if he wants it gone.

This prompted global Rule 26 (Section H, "Interface copy: one clear label,
never explanatory prose"), so the failure is corrected at the source and not
just in this one app.

**Explicitly deferred — not started.** This phase covered category spend
only. Per the sequencing Hayden confirmed, three more InSight views remain
entirely unbuilt: Phase 2 (Top suppliers chart), Phase 3 (Fragmentation
bubble chart), and Phase 4 (Overview KPI cards) — in that order, each to go
through its own design-and-build pass after this one, not folded into this
handoff.

## Phases 2–4: robustness, Top suppliers, Fragmentation, Overview (7 Aug 2026)

Built and verified complete: the full `_MEETING-READY-DESIGN.md` scope
(Parts A–H) — vague-question/overview fallback, suggestion chips, Top
suppliers + supplier drill-down, Fragmentation + overall supplier
concentration (Pareto), Overview KPIs/callouts, category comparison table +
intensity heatmap, the "More" tab's raw-data view, and the answered-state
interface pass (`layout="wide"`, chip styling). Task 14 (this section) is
the final gate: the InSight demo parity checklist, the adversarial gauntlet,
a full regression run, a Codex cross-family review, and the
`interface-polish` screenshot gate.

**Test count: 161 passing** (`pytest tests/ -q`), up from 145 at the end of
Task 13 — 8 new gauntlet tests (`tests/test_gauntlet.py`) plus 8 further
regression tests added during this task's own fix rounds (below).

### InSight demo parity checklist (Task 14 Step 1a)

Every row below was checked by hand against the live demo
(https://zureli-insight-demo.streamlit.app/), re-inspected live on 7 Aug
2026 rather than trusted from earlier notes (Rule 1). Numeric checks used
either the running local app's chat (`streamlit run app.py`) or direct
`answer_payload()`/query-function calls against the same data — the brief's
own sanctioned "whichever gets you a trustworthy comparison fastest."

| InSight tab | Element | Result |
|---|---|---|
| Overview | KPI row | **PASS.** Net spend 2025 €7,384,113.73 (demo: €7.4m) +9.1% vs 2024 (both); Entities 8 (both); Suppliers 56 (both). 4th KPI: ours "Spend rows" = 401 vs demo's "Supplier-year lines" = 401 — see "One unresolved Overview metric" below, now resolved. |
| Overview | 3 callouts | **PASS.** Largest category: Professional services, €1,587,499.21 (demo: €1.6m) both. Fastest growth: Professional services +15.4% both. Supplier concentration: Top 10 = 38.0% both, largest supplier "Supplier 025" both. |
| Category spend | Stacked bar chart | **PASS.** Chart total €7,384,113.73 = `query_spend(df, year=2025)` exactly. |
| Category spend | Comparison table | **PASS**, exact match to the unit on all 8 rows (e.g. Professional services €1,587,499/€1,375,210/+€212,289/+15.4%/21.5% share, both sides). |
| Category spend | Intensity heatmap | **PASS.** Max/min cell (440,739.35 / 7,882.46) match the demo's legend (441k/8k) exactly; 3 spot-checked cells match `query_spend()` exactly (internal never-diverge check). |
| Top suppliers | Ranked bar chart | **FAILED, then fixed** — see "Real defect found" below. After the fix: all 15 suppliers' ranking, order, and 2024/2025 values match the demo exactly (cross-verified two ways: the demo's own Top-suppliers table for suppliers 1–10, and its Fragmentation tab's Pareto chart x-axis order for suppliers 11–15). |
| Top suppliers | Supplier drill-down (Demo Supplier 025) | **PASS.** €368,010.23 in 2025 (demo: €368k), +22.4% both, 5.0% share both, 8 entities both, 1 category both. |
| Fragmentation | KPI row | **PASS on Categories assessed (8=8) and Suppliers in scope (56=56). Disclosed divergence on Highly fragmented (ours 0 vs demo 2) and Fragmented spend % (ours 0.0% vs demo 32.3%)** — both are downstream of the CR3-vs-Profile tier difference Part C1 already anticipated, not a new gap. |
| Fragmentation | Per-category table | **PASS on every numeric column** (Net spend, Suppliers, Top supplier share %, Top 3 share % / CR3, Concentration index) for all 8 categories, exact match to the demo. **Tier vs Profile diverges for 2 of 8 categories** (IT and telecom: ours Medium vs demo High; People: ours Medium vs demo High) — the exact case Part C1 documented in advance from the 7 Aug live re-verification, not discovered fresh here. Full comparison table below. |
| Fragmentation | Overall concentration Pareto | **PASS.** Top 10 suppliers = 38.0% of €7,384,113.73, matching both the demo's own Pareto view and its Overview "Top 10 = 38.0%" callout. |
| More | Filtered raw rows (Germany, 2024) | **PASS.** Column schema matches exactly (`Spend line id`, `Source row count`, `Entity`, `Cluster`, `Country`, `Year`, `L1`, `L2`, `Supplier name`, `Net spend` — these columns already exist verbatim in `sample_spend_data.csv`, not synthesised by this app). First rows byte-identical to the demo's own table for the same scope. Local total: 52 rows. The live demo's exact total count for this specific scope could not be independently re-confirmed through its own UI this session — its Country filter is a BaseWeb multiselect that did not respond reliably to this session's browser-automation clicks (a tool limitation, same class as the `st.chat_input` issue logged in Task 8's section above, not an app bug) — but the row-content match plus an internal `query_spend()` cross-check give high confidence; flagged here rather than silently assumed complete (Rule 24). |

**Real defect found and fixed:** `chart_query.top_suppliers()` ranked
suppliers by their TOTAL spend summed across both years in scope, per the
original design spec's read of the demo's grouped-bar chart. Live
re-verification showed the demo actually selects and orders its top 15 by
the single "Focus year" (2025) value alone — confirmed by matching 15
suppliers' 2025 figures and their exact displayed order to the cent. Fixed
in `chart_query.py`: rank year = the caller's `year` filter if given, else
the latest year in scope (matching every other chart kind's own
default-to-latest-year rule), while every year present is still returned so
the grouped-bar presentation is unaffected. TDD: failing tests written
first (`tests/test_chart_query.py::test_top_suppliers_ranks_by_latest_year_not_two_year_total`
and `::test_top_suppliers_sorted_descending_by_rank_year`), confirmed
failing against the pre-fix code, then the fix applied and re-verified
both by pytest and by re-screenshotting the running app.

### Fragmentation formula comparison — unfiltered 2025 view (Part C1's "record the per-category table" instruction)

| L1 | Our CR3 % | Our Tier | Our Concentration index | Demo Top 3 share % | Demo Profile | Demo Concentration index |
|---|---|---|---|---|---|---|
| Professional services | 62.6 | Medium fragmentation | 1664 | 62.6 | Medium fragmentation | 1664 |
| IT and telecom | 40.5 | Medium fragmentation | 1016 | 40.5 | **High fragmentation** | 1016 |
| Logistics | 83.4 | Concentrated | 2601 | 83.4 | Concentrated | 2601 |
| Facilities | 50.1 | Medium fragmentation | 1391 | 50.1 | Medium fragmentation | 1391 |
| People | 48.6 | Medium fragmentation | 1159 | 48.6 | **High fragmentation** | 1159 |
| Utilities | 79.1 | Concentrated | 2533 | 79.1 | Concentrated | 2533 |
| Marketing | 76.5 | Concentrated | 2505 | 76.5 | Concentrated | 2505 |
| Office | 80.0 | Concentrated | 2545 | 80.0 | Concentrated | 2545 |

Every numeric column (CR3/Top 3 share %, Concentration index) matches
exactly. Only the Tier/Profile label diverges, and only for the two
categories Part C1 already flagged from the 7 Aug live re-verification
(IT and telecom, People) — both sit close to but below our 40% Medium/High
CR3 boundary while the demo's Profile calls them High, evidence that its
Profile likely tracks the Concentration index more than CR3 alone, which
with only 8 rows to observe isn't reliably reverse-engineerable without
reverse-fitting a threshold to force a match — exactly what Rule 24
forbids. Left as a disclosed, principled difference, not tuned.

### One unresolved Overview metric — now resolved as a genuine match

`_MEETING-READY-DESIGN.md`'s "One unresolved Overview metric" section
disclosed that the demo's "Supplier-year lines: 401" KPI couldn't be
reverse-engineered from `sample_spend_data.csv` by re-aggregating it
(supplier×year, supplier×year×entity, etc. all produced counts other than
401), so this app's own 4th KPI was kept as "Spend rows" — a different,
honestly-labelled statistic (the real row count in scope), not a relabelled
guess. Task 14's parity check found this was never actually a mismatch:
`sample_spend_data.csv` already carries `Spend line id` and
`Source row count` columns (missed in earlier inspection) — each CSV row
IS already one aggregated "spend line," at exactly the grain the demo's own
metric counts. `len(year_rows)` for the unfiltered 2025 scope is exactly
401, matching the demo exactly, with no reaggregation and no tuning — the
row count was the right answer the whole time. "Spend rows" is kept as the
label (Rule 26 — it's still the more honestly self-descriptive name for
what the number is), but it is confirmed to equal the demo's own metric for
every scope, not just coincidentally for the unfiltered view (both are
literally `len()` of the same rows).

### Adversarial gauntlet (Task 14 Steps 1–2)

`tests/test_gauntlet.py`, the full battery from `_MEETING-READY-DESIGN.md`
Part F: vagueness ladder (6 questions), synonyms/phrasing gaps (documented,
not pretended), typos (documented overview fallback), abuse inputs (empty,
1000-char, emoji, numbers-only, prompt-injection phrasing, SQL-injection-
shaped string, HTML/script tag), the injection-specific "must not bypass
normal filtering" check, a real negative-total case
(`-€7,637.65` for Demo Supplier 052/Utilities/Demo Iberia Distribution),
zero-row results per chart kind (category_spend, top_suppliers,
fragmentation), and cross-feature filter composition. All 8 tests pass —
one genuine crash was found and fixed first (`fragmentation()` raised
`KeyError: 'net_spend'` on any zero-row filter combination, because
`pd.DataFrame(rows)` on an empty list drops all columns before
`sort_values()` runs — the same class of bug `category_comparison()` had
already been fixed for in Task 11; same fix applied here).

### Manual UI-abuse pass (Task 14 Step 3 — runtime-only, not expressible as a pytest assertion)

All three checked directly in the running local app via the real browser:

- **Chip double-click** (rapid double-click on "Give me an overview"):
  exactly one exchange was added to the conversation, not two — no
  duplicate message, no crash, no infinite rerun loop. The chip's own
  radio-button semantics (a second click on an already-selected option is a
  no-op) plus the existing `del st.session_state[...]` widget-reset logic
  (already documented in `app.py`'s `render_chips()`) together make this
  safe.
- **Chart question immediately followed by another chart question, before
  the first fully renders**: fired "show me a bar chart of category spend"
  then immediately "show me fragmentation" with no wait between the two.
  Both exchanges landed correctly and in order in the conversation history;
  neither answer's numbers were corrupted (re-verified via
  `get_page_text()` against the rendered page — the category chart's total
  and the fragmentation table were both exactly the values independently
  computed via the query functions). Streamlit's own synchronous
  script-rerun model means there is no real overlap window locally, but the
  composition itself — two real chart answers back to back — was proven,
  not assumed.
- **Browser refresh mid-conversation**: after 3 real exchanges, a hard page
  reload (not a soft navigation) returned the app to the exact clean empty
  state — greeting, input, chips — with no error banner and no stale
  content. This is standard Streamlit session-state behaviour (a fresh page
  load gets a fresh server-side session), not app-specific logic, but it
  was verified directly rather than assumed.

### Codex cross-family review (Task 14 Step 5) and full triage

Run via `codex exec` against the diff `b8611b3..HEAD` (the entire
meeting-ready build) after committing the gauntlet + top_suppliers-ranking
fix, so the review covered what was actually shipping (Rule 3), not a stale
snapshot. Findings and triage:

- **HIGH — fixed.** `top_suppliers()` did not null-guard `"Supplier name"`
  before its groupby, unlike every sibling function in `chart_query.py`
  (`overall_concentration`, `fragmentation`, `supplier_drilldown`,
  `category_spend`, `entity_category_intensity` all already guard this).
  Not reachable with the real CSV (0 nulls anywhere, verified), but fixed
  to match this file's own established defensive pattern rather than left
  as the one inconsistent function. TDD: `test_top_suppliers_null_supplier_name_is_not_dropped`.
- **HIGH — fixed.** `overview_query.py`'s `by_category`/`by_supplier`
  groupbys and `entity_count`/`supplier_count` had no equivalent null-guard
  (this file predates the pattern being established in `chart_query.py`).
  Worse: if every row's L1 AND Supplier name were null, every callout would
  resolve to `None`, leaving `app.py`'s `callouts` list empty and crashing
  `render_callouts()`'s `container.columns(len(callouts))` as
  `st.columns(0)` — confirmed directly, raises
  `StreamlitInvalidColumnSpecError`. Fixed with the same fillna guard; the
  crash path is now structurally unreachable whenever there is real spend
  in scope (at least one callout always resolves once nulls are guarded).
  TDD: `test_null_entity_l1_supplier_values_are_not_dropped_from_callouts`.
- **MEDIUM — fixed.** `nl_parser.py`'s `TOP_N_PATTERN` was an unbounded
  `\d+`, so a huge digit string in a "top N suppliers" question (e.g. 5000
  nines) reached Python's own `int()` conversion and crashed with
  `ValueError: Exceeds the limit (4300 digits) for integer string
  conversion` before this file's own N-clamping ever ran — a real,
  reproducible crash, confirmed directly. Capped the pattern at 10 digits
  (comfortably above any real "top N" request, far below the 4300-digit
  limit). Folded into the permanent gauntlet:
  `test_gauntlet.py::test_huge_top_n_number_never_crashes`.
- **MEDIUM — fixed.** `fragmentation()`'s CR3/top-share/concentration-index
  math divided by `net_spend`, which a real, reachable filter combination —
  not contrived, found by scanning every real entity/country/cluster×year
  combination — could push over 100%: "fragmentation for Demo Western
  Services in 2024" put Utilities at `cr3_pct = 102.3%` before the fix, a
  number with no sensible reading in a client-facing table. Root cause: a
  category can have a real supplier with negative net spend (a
  credit/refund — confirmed real elsewhere in this data), pulling the
  category's own net total below what the top positive suppliers alone
  spent. Fixed: shares are now computed against gross POSITIVE supplier
  spend rather than net_spend, which provably keeps every share within
  [0, 100], and is numerically IDENTICAL to the previous figure for every
  category with no negative supplier subtotal — confirmed the already
  InSight-parity-checked unfiltered 2025 table (above) has zero such
  categories, so none of those verified numbers changed. TDD:
  `test_fragmentation_shares_never_exceed_100_with_negative_supplier_spend`
  plus a full real-data sweep,
  `test_fragmentation_cr3_between_0_and_100_across_every_real_filter_scope`.
- **No issue found (confirmed, not just accepted).** Supplier drill-down's
  intent-routing regression guard is correct — a supplier+entity+category
  question still returns the plain number, not drill-down, both by parser
  logic and app-level test coverage. Fragmentation's tier thresholds are
  confirmed not tuned to InSight's undisclosed Profile logic — own CR3
  rule, disclosed in the caption, Concentration index shown alongside but
  not used to set the tier.

**Two further real bugs found by this task's own screenshot-gate pass, not
by Codex** (see next section) — both fixed in the same commit as the Codex
findings.

### `interface-polish` screenshot gate (Task 14 Step 6)

Skill invoked explicitly. Screenshotted at 1280px width (≥1200px target):
the empty state (with chips), and one full exchange of every answer kind —
plain number, category chart, category comparison table, intensity
heatmap, top-suppliers chart, supplier drill-down, fragmentation, overall
concentration (Pareto), raw-data view, overview, and help. Observed, per
kind:

- **Empty state, plain number, category chart, comparison table, intensity
  heatmap, fragmentation, overall concentration, raw data, overview,
  help**: all clean at 1280px — consistent message-bubble spacing carried
  over unchanged from Task 13's established rhythm (32px header padding,
  the 4/8/12/16/20/24/32/40 scale), no element touching a container edge,
  no empty/stray containers, KPI rows and callout cards breathing the same
  as the existing Overview cards.
- **Top suppliers chart and supplier drill-down (2 real defects found and
  fixed)**: both charts use `textposition="outside"` bar value labels with
  `margin=dict(r=0, ...)` and no explicit x-axis range padding. Screenshot
  evidence: the widest bar's own label was clipped at the plot's right
  edge in EVERY render — "368,010" rendered as "368,01" cut off mid-digit,
  confirmed in the full-width Top suppliers chart, not just a narrow
  column. The drill-down's category chart (often 1–2 bars, e.g. a
  single-category supplier) additionally had its x-axis tick labels
  visually colliding with the "Net spend (€)" axis title at very short
  chart heights. Fixed in `chart_render.py`: a shared
  `_range_with_label_headroom()` helper extends the x-axis range 15% past
  the data's own max so outside labels have room (added to both
  `build_top_suppliers_figure` and `_single_series_bar_figure`), and
  `_single_series_bar_figure` now has a 180px height floor so short charts
  keep the tick row and axis title visually separated. Re-screenshotted
  after the fix: both defects confirmed gone — "368,010" renders in full
  with clear headroom to the axis edge, and the drill-down's two charts
  (spend by entity, spend by category) render side by side with no
  overlapping text, matching Step 7's fidelity requirement.
- Pattern named: every chart/table matches the in-app pattern already
  established by Phase 1's category-spend chart (same tick/label helpers,
  same palette, same caption style) — no forced Apple-reference analogy
  needed for this data-table/chart-heavy surface.
- Accessibility and control-wiring handed to `web-design-guidelines` /
  code review, not covered by this pass (per the skill's own scope).

**Recommendation: ship** — both real defects found during this pass are
fixed and re-verified; nothing else observed needs revision.

### `layout="wide"` vs `"centered"` decision (Task 13, recorded here per Step 8)

`layout="wide"` was kept, with a CSS `max-width: 1000px` cap on the content
column rather than Streamlit's `st.columns([1, 14, 1])` trick that
`_MEETING-READY-DESIGN.md` Part E also named as an option. The columns
trick was tried first and broke chat rendering in real-browser
verification: nesting `with st.chat_message():` under a `page =
st.columns(...)` column requires every call inside that block to route
through Streamlit's thread-local "current container" stack, which only the
bare `st.foo()` module-level functions consult (confirmed by reading
Streamlit's own `DeltaGenerator.__enter__` source — `with X.chat_message()
as y:` returns no capturable container object). Rewriting the inner calls
as `page.foo(...)` bypassed that stack entirely, breaking chat bubble
rendering (confirmed via DOM inspection: the message content div had 0
children) and also broke `st.chat_input()`'s root-level bottom-pin
behaviour. The CSS max-width approach avoids both problems because every
render call stays exactly `st.foo()`, unmodified. Full reasoning and DOM
evidence: `app.py`'s own inline comment block above the CSS block (lines
~27–47).

### Explicitly out of scope (unchanged from Phase 1)

Real LLM parsing (API-key decision pending); InSight's actual production
data shape (data-scientist meeting pending); multi-tenancy/auth; per-client
data isolation; multi-entity comparison charts; deployment beyond
localhost.

## Final whole-branch review round (after Task 14, before declaring done)

Task 14's own gate above ran per-task; a separate final pass then reviewed
the entire branch at once (24 commits, base `726cd46` to `8b960be`), on
Opus, specifically hunting for cross-cutting issues no single task's
reviewer could see. It found 5 Important + 2 Minor, all genuinely new:

1. `supplier_drilldown()`'s `entity_count`/`category_count` were computed
   *before* the null-guard `fillna` further down — a sixth instance of the
   null-guard bug class this project independently hit and fixed four
   times already (Tasks 6, 8, 10, 11), producing a KPI number that could
   contradict the chart drawn directly beneath it.
2. The same bug, a seventh instance, in `app.py`'s fragmentation dispatch
   ("Suppliers in scope" KPI).
3. `format_filters()` only stripped the "Demo " prefix for `entity`, never
   `supplier` — a real violation of this project's own stated rule
   ("Entity/supplier names always display with the `Demo ` prefix
   stripped"), reaching 9 call sites.
4. The highest-risk finding: every chart dispatch defaulted an unfiltered
   year question to the *dataset's global latest year* rather than the
   latest year *within the filtered scope* — silently dead-ending 42 real
   entity+supplier combinations that have 2024 data but no 2025 data,
   directly contradicting this project's own headline "no question
   dead-ends" goal.
5. The top-suppliers "(clamped from N)" caption note fired whenever the
   scope simply had fewer suppliers than the unrequested default of 15,
   not only on a genuine clamp — a false claim in client-facing copy.

All 7 fixed in one commit (`bfc8bd2`, 8 new regression tests, 161→169).
A scoped re-review (also Opus) independently re-derived the mechanism
behind Finding 4 from raw pandas rather than trusting the fix report, then
ran an exhaustive sweep of all 661 scopes the parser can express: exactly
42 resolve to a different year under the fix, and in every one of those
42 the old global-year filter matched zero rows — a decisive result that
the fix can only convert a prior dead-end into a real answer, never change
an answer that was previously correct.

Three trivial residuals surfaced in that re-review, adjudicated rather
than looped again (per this project's own fix-loop rule: at most one fix
wave for a whole-branch review pass): a pre-existing phantom-"2023" row in
the category comparison table (the dataset only has 2024/2025; comparing
a 2024-only scope against a nonexistent 2023 already happened before this
round, the fix just makes it reachable more often — a UX polish item, not
a defect, left as a follow-up); a code-style inconsistency between two new
helper functions (zero functional risk); and one documentation overclaim
in `_MEETING-READY-DESIGN.md`, fixed directly by the controller
(`cd57299`) rather than looping another subagent round for one sentence.

**Final state: 169/169 tests, HEAD `cd57299`.**

## Personal controller screenshot pass (Task 14 Step 7 — done directly)

Run separately from every automated/subagent check above, per this
project's own rule that viewing the rendered output is the actual test,
not a proxy for it. Started the app fresh, drove it with real browser
clicks (not the debug-seed workaround), and personally confirmed against
the live InSight demo: the top-suppliers ranking fix (order
025/026/023/021/024/028/002/027/010/049 matches the real demo exactly);
the supplier drill-down (all 5 numbers and the side-by-side chart layout
match the real demo exactly for Demo Supplier 025); the fragmentation
table's column order and every value (including the one disclosed,
deliberate divergence on IT and telecom's tier) match the design spec and
the live demo; and the category comparison table matches the live demo to
the cent on every row. No visual defects, no build-narration, no leftover
debug artifacts in any screenshot.

## Next steps
- Show this build at/before the data scientist meeting as the complete
  meeting-ready demo (all 5 InSight tabs now have a chat equivalent, gated
  by the adversarial/Codex/final-whole-branch-review/screenshot passes
  above).
- Consider the phantom-"2023" comparison-table row noted above — a
  one-line "no data before 2024" caption would close it; not blocking.
- After the data scientist meeting: revisit architecture decisions above
  against what's actually confirmed about the real InSight data.
- Decide on the LLM upgrade once there's a reason to (API key + real
  questions to test against).

## Phrasing bug found by Hayden's own testing (7 Aug 2026) — and the testing gap behind it

Hayden typed "Show me a bar chart of the spend profile by category" and
"...by entity" in the browser and got the comparison TABLE both times, with
the breakdown dimension silently dropped on the second.

Root cause in the code: `"spend profile"` is a `category_comparison`
keyword, checked *before* the chart keywords, so an explicit "bar chart"
request was ignored entirely.

Root cause behind that, which matters more: **every prior test, and the
Task 14 InSight parity checklist, exercised exactly one canonical phrasing
per view — the phrasing that view's own keyword was written for.** That
proves a keyword matches itself. It never proved a real client's wording
lands on the right view. The parity checklist passing 9/9 was therefore
weaker evidence than it appeared, and the "everything is tested" claim made
off the back of it was wrong.

Fixed by a general rule rather than a patch: an explicit output-format word
("bar chart", "chart", "graph", "plot", or "table") now beats an inferred
view type, in both directions — a chart word routes a table-only view to
its chart equivalent, and "table of category spend" routes to the
comparison table. Also added the plain-English year-over-year phrasings
("vs last year", "year on year", "yoy") that previously matched nothing and
dead-ended on the overview fallback.

`tests/test_phrasing_matrix.py` (new, 61 cases) exists to keep this class of
gap closed: every view, several natural phrasings each including at least
one that does NOT contain the literal keyword, plus per-view assertions that
the answer actually renders a figure or table rather than merely parsing to
the right label. **14 of its cases failed before the fix.** When a view or
keyword is added, add its phrasings there too.

Suite: 231 passing (was 170).

## Deployment (7 Aug 2026)

Code is pushed to **https://github.com/nedyah8/zureli-spend-assistant**
(private). `requirements.txt` was trimmed to runtime-only and pinned to the
exact versions the suite ran against — `anthropic` was removed (never
imported; there is no API key and parsing is rule-based) and `pytest` moved
to `requirements-dev.txt`.

Verified before handing over, rather than assumed: a fresh `git clone` into
a clean virtualenv installing only `requirements.txt` boots the app with no
errors and answers questions correctly — i.e. a real simulation of what
Streamlit Community Cloud does on deploy.

DEPLOYED (7 Aug 2026, later the same day): the repo was flipped to
**public** (Hayden's explicit decision — Streamlit's OAuth-app connection
could not see a private repo created after authorization) and the app is
live at **https://zureli-spend-assistant.streamlit.app** with main file
`app.py`. Pushing to `main` auto-redeploys. Jayesh has the link. Before any
real client data ever goes near this: repo back to private + auth, or a
proper host — see `_LLM-UPGRADE-RESEARCH.md` §4.

## Jayesh feedback round — alias vocabulary (7 Aug 2026)

Jayesh's email: "give me IT spend" returned the whole-company total, and he
asked whether this is a lookup tool vs AI with personality/reasoning.

The symptom fix shipped the same day: `aliases.py` (curated per-value alias
vocabulary with WEAK_ALIASES spend-signal gating and ALIAS_BLOCKING_PHRASES),
a rewritten `_extract_filters` in `nl_parser.py` (global longest-alias-first
matching with span consumption, dimension priority tiebreak), and
`tests/test_alias_coverage.py` (~475 enumerated params). Root cause of the
defect surviving the original build: gauntlet tests whose assertions accepted
every outcome (`kind in ("overview","text","chart")`) — those were rewritten
to assert exact kinds and exact totals vs `query_spend`. Codex cross-family
review (17 findings) drove the hardening; its regression examples are
permanent tests. 700/700 passing (re-run 7 Aug 23:28 BST, green). Commits
`40dcd07` + `f88ef68`, both on `origin/main` and on GitHub
(`raw.githubusercontent.com/.../main/aliases.py` returns 200 with the new
file).

### CORRECTION — stale deploy, found and RESOLVED (7 Aug 2026, 23:30–23:55 BST)

Two separate failures, recorded because both are process defects, not
one-off slips. Both are now closed; the operational lesson in **3** is the
one that must not be lost.

**1. The deployed app was running pre-fix code.** Hayden tested
zureli-spend-assistant.streamlit.app after the push and got the
whole-company overview for "telecom spend", "it spend", "give just the it
spend" and "what are supplier 051's numbers? in detail?". Reproduced
directly on the deployed URL at 23:25 BST: "it spend" → overview, but the
verbatim "IT and telecom spend" → the correct €2,630,963.38. Verbatim-only
matching IS the pre-alias behaviour. The same four questions all return
correct answers from local HEAD (`f88ef68`), so the code is right and the
DEPLOY was stale. Hayden rebooted the app from Manage app → Reboot, which
fixed it; see **3** for what the logs then revealed about why.

**2. The "verified live" claim in the previous version of this section was
false.** The post-fix browser check at 21:35 UTC was run against
`http://localhost:8501`, not the deployed URL — confirmed by grepping the
session transcript: there was NO browser interaction with
`zureli-spend-assistant.streamlit.app` between the fix commits (21:29 UTC)
and the claim (21:50 UTC); the last one before tonight was 12:33 UTC, hours
before the fix existed. A local run was written up as a live one. This is
the Rule 24 failure exactly: a cheaper adjacent check substituted for the
artefact the claim was about. **Standing rule for this project: "live" means
the check was performed against the deployed `*.streamlit.app` URL in a
browser, in the same session as the claim, with the answer text quoted. A
localhost run is never evidence about the deployment, and a push is never
evidence of a deploy.**

**3. WHY the deploy was stale — "Updated app!" does NOT mean the new code is
running.** Hayden's Manage-app log showed Streamlit DID pick up the push:

```
[21:35:52] Pulling code changes from Github...
[21:35:53] Processing dependencies...
[21:35:54] Updated app!            <- 22:35:54 BST, ~1 min after f88ef68
```

Yet at 23:25 BST the live app still behaved exactly like pre-alias code, and
a manual **Reboot** fixed it immediately. Best explanation consistent with
that evidence (stated as inference, not a verified internal mechanism):
Streamlit Community Cloud's hot-update reruns the entry script but the
already-running Python process keeps previously-imported modules in
`sys.modules`, so a change confined to imported modules — here `aliases.py`
(brand new) and `nl_parser.py` — is pulled to disk without being re-imported.
`app.py` itself was untouched in both commits, which fits precisely.

**Operational rule for this project: after any push that changes an imported
module rather than `app.py`, reboot the app from Manage app and re-check a
known question on the live URL. Treat "Updated app!" in the deploy log as a
git-pull receipt, not as proof the new code is serving traffic.**

### LIVE VERIFICATION — passed (7 Aug 2026, 23:45–23:55 BST)

Run against `https://zureli-spend-assistant.streamlit.app/~/+/` in a browser
after the reboot. Every answer below was read off the live page and matches
the value `app.answer_payload` produces locally at `f88ef68` (computed first,
as an external anchor, so the live output was compared against ground truth
rather than merely judged plausible).

Hayden's four failing questions, all now correct:

| Live question | Live answer |
|---|---|
| `it spend` | category = IT and telecom — €2,630,963.38, 173 rows |
| `telecom spend` | category = IT and telecom — €2,630,963.38, 173 rows |
| `give just the it spend` | category = IT and telecom — €2,630,963.38, 173 rows |
| `what are supplier 051's numbers? in detail?` | Supplier 051 — €183,513.99 in 2025, −4.2% vs 2024, 2.5% of scope, + drill-down charts |

Jayesh's verbatim question, screenshotted on a fresh session:
`give me IT spend` → "Matched on category = IT and telecom — **€2,630,963.38**
across 173 spend rows."

Adversarial pass (trying to break it, not confirm it) — all as expected live:

| Live question | Expected | Live result |
|---|---|---|
| `IT spend for Alpine in 2024` | 3 filters compose | year 2024 + IT and telecom + Alpine Operations — €192,988.04, 11 rows |
| `hq spend` | entity alias | Group Headquarters — €1,479,898.95, 95 rows |
| `staff costs` | L1 alias | People — €2,019,149.48, 163 rows |
| `legal spend` | L2 beats L1 | Legal and audit — €759,323.62, 52 rows |
| `supplier 25` | un-padded supplier alias | Supplier 025 — €368,010.23, +22.4%, 5.0% |
| `holland spend` | country alias | Netherlands — €1,913,627.62, 105 rows |
| `what is it` | pronoun guard holds | overview, no IT filter |
| `what did it cost` | pronoun + spend signal | overview, no IT filter |
| `audit trail spend` | blocking phrase holds | overview, no Legal filter |
| `legal entity spend` | blocking phrase holds | overview, no Legal filter |
| `asdfghjkl` | no crash | overview |
| `show me a bar chart of category spend` | chart path intact | stacked bar rendered, total €7,384,113.73, caption correct |

Chart render and the supplier drill-down were viewed as screenshots, not just
read as text (Rule 24: for anything a human looks at, viewing it IS the test).

The architecture question is answered in `_LLM-UPGRADE-RESEARCH.md`
(7 Aug 2026): recommendation is to wire Claude Sonnet 5 via an Anthropic API
key as the understanding + reply-phrasing layer only, keeping computation in
the existing deterministic pandas code, with the rule-based parser retained
as an automatic fallback. Blocker: whose API account (Hayden's ~$5 demo
credit vs a Zureli-owned key). Cost ≈ under a penny per question at Sonnet 5
intro pricing. Prices/policies in that doc were verified against provider
pages on 7 Aug 2026 and go stale — re-verify before re-quoting.

## How to run it
```
cd "5. AI Chatbot"
source .venv/bin/activate
streamlit run app.py
```
It was left running locally on port 8501 during this session
(`http://localhost:8501`) for Hayden to try directly.

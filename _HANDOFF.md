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

### LIVE VERIFICATION — passed (7 Aug 2026, 23:36–23:44 BST)

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

### Codex review round 2 — 14 real defects in the SHIPPING code (7 Aug 2026)

The earlier Codex pass reviewed the code BEFORE the final hardening commit,
so by Rule 3 it was stale as final evidence. Re-ran it against `f88ef68` —
the exact code that was live. 16 findings; **all 14 concrete ones reproduced
exactly as described**, including the euro figures. Fixed in `4b0134a`,
tests 700 → 847.

Wrong-number bugs (the dangerous class — user sees an authoritative figure):

| Input | Was answered | Fix |
|---|---|---|
| `office software spend` | "€0.00 across 0 spend rows" (l2 Software licensing AND l1 Office) | `known_values()` now derives an L2→L1 parent map from the data; a contradictory L1 is dropped in favour of the narrower L2. Enumerated over every L1×L2 pair. |
| `security software spend` | Cleaning and security, €684,341.95 | Two-pass matching: non-weak aliases resolve first, weak ordinary-English ones only fill what is still empty. Fixes the class. |
| `maintenance software spend` | Building maintenance, €1,278,651.64 | same |
| `how many people work here` | People, €2,019,149.48 | `people`/`staff`/`personnel`/`workforce`/`office` are now WEAK (need a spend signal) |
| `what is our brand value` | Marketing, €698,076.54 | `brand` WEAK **plus** a blocking phrase — "value" is itself a spend-signal word, so the gate alone let it through |
| `is this available in German?` | Germany, €1,801,388.73 | country ADJECTIVES now WEAK; the noun forms stay ungated |
| `IT spend in 20245` | year = 2024 | year match is digit-bounded, not a substring |

Missed phrasings added: `license`/`licence` singular, `phone bills`,
`contractor`/`contract labour`/`contract staff`, `learning & development`/
`l and d`, `gb`/`british`, `northern`.

**Deliberately rejected — finding 14, "Western spend" should resolve to Demo
Western Services.** It is genuinely ambiguous between the West cluster and
that entity (as "Southern" is between South and Demo Southern Support), and
guessing produces a confidently wrong number where the overview-plus-chips
fallback is honest. A test pins the fallback so adding a guess later has to
be a deliberate change, not a drift.

**The new tests were checked against the pre-fix source: 133 of them fail
there.** That check is now mandatory for this project — the original defect
survived a 14-task build precisely because its test could not fail, so a new
regression test is not trusted until it has been seen to go red.

### STATE AS OF 7 Aug 2026, 23:45 BST — what is and is not live

- **Live now** (`f88ef68`, verified above): the alias fix. Hayden's four
  questions and Jayesh's exact question all correct.
- **NOT live** (`9967508` + `4b0134a`, committed locally, **not pushed**):
  the round-2 fixes above and this documentation.
- To ship them: push, then **reboot from Manage app** — a push alone will
  not take effect, because all three changed files (`aliases.py`,
  `nl_parser.py`, `spend_query.py`) are imported modules rather than
  `app.py`. Then re-verify on the live URL, quoting the answers.

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

---

## Round 3 — Hayden's live customer test + the 134-question sweep (9 Aug 2026)

Commits `9967508`, `4b0134a`, `8fa0976` were pushed to `origin/main` at
01:33 BST on 9 Aug 2026. Hayden then tested the live app again (still serving
`f88ef68` at that point, since a push alone does not restart it) and hit
three defects. Investigating them properly meant running a **customer sweep**
rather than fixing the three: 134 questions written as the buyer would type
them, put through the real parser. **44 dead-ended on the overview; 21 now
do, and 10 of those 21 are correct declines.**

### The regression this project introduced itself

`Show me the overall numbers for the people` was **working live** — Hayden's
own screenshot shows People, €2,019,149.48. Round 2 made `people` a WEAK
alias so that "how many people work here" would stop answering with €2m.
That was right, but weak aliases require a spend-signal word, and `numbers`
was not one. The query started returning the overview.

This is the cost of the weak-alias guard and it will recur: **every time a
word is made weak, the signal-word list must be checked against the phrasings
that already worked.** `number`, `numbers`, `amount`, `amounts` are now
signal words alongside the existing `figures`.

### Defects found and fixed

| Input | Was | Now |
|---|---|---|
| `Show me the overall numbers for the people` | overview (regression) | People |
| `Just show me the offices figures` | overview | Office |
| `Break this down per sub category for people` | repeated the same flat total | People, sub-category breakdown |
| `IT costs` / `IT figures` / `what's the IT total` | overview | IT and telecom |
| `spend by cluster` / `category spend by entity` | overview | the breakdown chart |
| `phone spend` | overview | Telecommunications |
| `which category grew the most` | overview | year-on-year table |
| `hello` / `what is this` | full spend overview | help |

### Two structural changes, not alias patches

**Capitalisation now distinguishes the IT department from the pronoun.**
`aliases.py` design rule 2 refuses a bare `it` alias because "it" is the
commonest pronoun in English. Correct — but it left `IT costs`, `IT figures`,
`IT numbers` and `what's the IT total` dead-ending while `IT spend` worked,
which reads as the tool being broken. A standalone **uppercase** `IT` in the
original (un-lowercased) question is the department; lowercase `it` never is;
an all-caps sentence carries no case information and is skipped. This is an
exact match on text the user typed, not fuzzy matching.

**The parser now has one turn of memory.** `parse_question(question, known,
previous)` merges the previous turn's filters when the question refers back.
`app.py` holds the last parse in `st.session_state` and **only remembers
turns that resolved something**, so a miss never becomes the context for the
next question. Session-scoped, so two users never share context.

### The new bug that memory created — found before shipping, not after

Inheritance **bypasses the alias layer entirely**, so `WEAK_ALIASES` cannot
protect it. Keyed on a referring word alone, with People in context:

- `is there an audit trail` → People, €2,019,149.48
- `is this available in German` → People, €2,019,149.48
- `is this secure`, `can I export this`, `that is wrong` → same

That is precisely the confidently-wrong class this project exists to prevent,
recreated by a second route within an hour of fixing the first. **A referring
word is now insufficient**: the question must also name a filter of its own,
carry a spend word, or ask for a breakdown. Eight of these are pinned by
test.

**The lesson worth keeping: any new path that sets filters must re-apply the
weak-alias guard.** The guard lives in `_extract_filters`; anything that
writes to `filters` outside it starts unprotected.

### One test example changed — deliberately, and why it is not measurement gaming

`test_gauntlet.py`'s typo test listed `IT and telecomm spend` as something
that must NOT resolve. It now resolves. That is **not** fuzzy-matching the
typo — the token `IT` is literally present in uppercase, so the category is
an exact match on what was typed. `Telecomm spend` (which genuinely matches
nothing) takes its place, and a new test pins the capitalised/lowercase pair
together so neither can be fixed by breaking the other. The test's protection
is unchanged; only its example was wrong for the new behaviour.

### Deliberately NOT fixed

- `it costs` **lowercase** — the pronoun reading ("what did it cost") is real
  and case is the only discriminator.
- `last year's spend` — relative dates. The data holds 2024 and 2025 and the
  real current year is 2026, so any mapping is a guess, and a guessed year is
  a confidently wrong number.
- `where can we save money`, `why did IT go up`, `what percentage is IT` —
  genuinely unsupported analysis, not vocabulary gaps. These need the LLM
  layer or new computations; see the roadmap below.
- `western spend` / `southern spend` — unchanged from round 2, still
  ambiguous between cluster and entity.

### Tests

700 → 847 → **909**. The round-3 additions were checked against the pre-fix
source: **33 of them fail there**, so they are load-bearing rather than the
assert-anything kind that let the original bug through.

### Roadmap to full functionality — what still stands between this and a tool a client relies on

**Tier 1 — vocabulary and phrasing (done for now, but permanently open).**
The alias list is finite and hand-written; every round of real user testing
has found more phrasings, and the next one will too. This is whack-a-mole by
construction. Mitigation until the LLM layer lands: run the customer sweep
(`134 questions`, in the session scratchpad — worth moving into `tests/`)
after any vocabulary change.

**Tier 2 — analysis the tool cannot do at all.** "Where can we save money",
"why did IT go up", "what percentage of spend is IT", "show me spend for
Alpine AND Baltic" (multi-value filters are explicitly unsupported — see the
`compare` note in `nl_parser.py`). These are missing computations, not
missing words, and each needs its own deterministic query plus a view.

**Tier 3 — the LLM understanding layer** (`_LLM-UPGRADE-RESEARCH.md`). Claude
Sonnet 5 as the understanding and phrasing layer only, computation staying in
pandas, rule-based parser retained as fallback. This is the structural fix
for Tiers 1 and most of 2. **Blocked on Zureli opening its own Anthropic API
account** — roughly a penny per question.

**Tier 4 — sellable to real clients** (unchanged, still deliberately
deferred): login/auth, private hosting, per-client data isolation, and the
DPA/GDPR paperwork. None of this is needed for the InSight demo.

### Codex cross-family review of round 3 — 5 findings, all 5 real

Run against the round-3 diff on 9 Aug 2026. Every finding was reproduced by
running the exact input before a fix was written. **Three were
confidently-wrong numbers that round 3 introduced itself.**

| Input | Wrong output | Cause |
|---|---|---|
| `is this available in German numbering format?` | Germany, €1,801,388.73 | "numbering" contains "number" |
| `is IT secure?` | IT and telecom, €2,630,963.38 | uppercase-IT rule had no spend gate |
| `what does this amount mean?` (after People) | People, €2,019,149.48 | asking what a number means is not asking for it again |
| `for 2024?` (after People) | whole-company 2024, €6,768,853.29 | elliptical fragment replaced the context instead of narrowing it |
| `by country?` (after People) | whole-company chart, €7,384,113.73 | breakdown with no subject did not inherit |

**The first one is the important one.** `SPEND_SIGNAL_WORDS` were matched as
plain **substrings**, so every signal word was a latent version of this bug
and each new one added another. They now match on **word boundaries**
(symbols like `€` stay substring tests, having no boundary to match).

The uppercase-`IT` rule is now gated on a spend signal exactly like a weak
alias — which is what it is. Cost of that gate: `just the IT part` no longer
resolves, since "part" is not a spend word. That is the right trade against
`is IT secure?` returning €2.6m.

Follow-up inheritance also gained two rules: an **elliptical fragment**
(names a filter, no spend word, four words or fewer) narrows the previous
answer rather than replacing it, and a **subject-less breakdown** ("by
country?") inherits — but only when the question names no subject of its own,
so `chart category spend by cluster for 2024` is never silently narrowed.

**Test isolation bug found by this change:** Streamlit's `session_state`
survives a module reload, so the new follow-up memory leaked between tests
and made the suite order-dependent — `test_chart_breakdown_by_cluster` passed
alone and failed in the suite. Both `_reload_app()` helpers now clear
`last_parse`. A real user session should carry that context; a test must not.

Tests **919**, all passing.

### LIVE VERIFICATION — round 3, passed (9 Aug 2026)

Verified on the deployed URL `zureli-spend-assistant.streamlit.app`, in a
browser, in the same session as the fixes. Every figure was computed locally
from the CSV **first**, so each live answer was checked against a known-right
number rather than accepted at face value.

| Question asked live | Live answer | Verified against |
|---|---|---|
| `Just show me the offices figures` | Office — €243,567.52, 61 rows | `query_spend(l1="Office")` |
| `Show me the overall numbers for the people` | People — €2,019,149.48, 163 rows | the regression, now fixed |
| `Break this down per sub category for people` | People, Level 2, 3 categories, €977,536.74 | People 2025 = €977,536.74, 80 rows; L2s = Recruitment, Temporary labour, Training |
| `for 2024?` (elliptical follow-up) | People, year 2024 — €1,041,612.74, 83 rows | `query_spend(l1="People", year=2024)` |
| `is there an audit trail` | overview fallback, no figure | must decline — it does |
| `is IT secure?` | overview fallback, no figure | must decline — it does |
| `IT costs` | IT and telecom — €2,630,963.38, 173 rows | `query_spend(l1="IT and telecom")` |

The capitalised-IT pair is the one to keep an eye on: `IT costs` answers and
`is IT secure?` declines, live, in the same session.

### The deploy rule, refined by evidence

Last night's rule said any push needs a manual reboot. **That was broader
than the evidence supported.** This push changed `app.py` itself and the new
code was serving live within a minute, with **no reboot**. The refined rule:

- Push touches **`app.py`** (the entry point) → Streamlit re-runs the script
  and the change takes effect on its own. Verified 9 Aug 2026.
- Push touches **only imported modules** (`aliases.py`, `nl_parser.py`,
  `spend_query.py`, `chart_*.py`) → the already-imported module stays in
  memory. **Reboot from Manage app, then re-check live.** Verified 7 Aug
  2026, when `f88ef68` sat unserved.

Either way, "Updated app!" in the deploy log is a git-pull receipt, not proof
the new code is running. The only proof is asking the live app a question
whose answer differs between the old and new code.

---

## Round 4 — the chart follow-up gap (10 Aug 2026)

Found by reading Hayden's OWN chat history off the deployed app rather than by
running another synthetic sweep. He asked "2024 spend" (€6,768,853.29), then
"Show this in a bar chart", and got a chart of **2025**.

Not a wrong number — the caption read "matched on year = 2025" honestly — but
not the year he was looking at either. Asking to SEE the same answer
differently was not recognised as referring back at all, so the year was
dropped and the chart path fell through to its own default year.

Same class as the four follow-up gaps Codex found on 9 Aug, in a phrasing the
134-question sweep had never tried. Fixed the same way as the subject-less
breakdown case rather than by special-casing the sentence.

### What shipped
`chart_only` in `nl_parser._merge_follow_up`: a question whose ENTIRE text is a
redraw request ("as a bar chart", "chart it", "now plot this") inherits the
previous turn's filters.

### Codex round 1 — 8 findings, all 8 real, all 8 reproduced before fixing
The first version treated any chart word as evidence the question was about
spend. It is not — chart words are domain-general, and a bare "bar" is
ordinary product English:

| Previous answer | Follow-up | Wrongly inherited |
|---|---|---|
| IT spend in France 2024 | "Is the search bar working?" | IT / France / 2024 |
| People spend in Germany | "Can this graph be exported?" | People / Germany |
| Facilities spend 2025 | "Plot our employee satisfaction trend." | Facilities / 2025 |
| Marketing spend UK | "Graph customer support response times." | Marketing / UK |
| Travel spend 2024 | "Why is the top bar missing?" | 2024 |
| Legal spend Spain | "Visualize the approval workflow." | Legal and audit / Spain |
| Software 2024 | "Can you make a chart of open invoices?" | Software licensing / 2024 |
| Utilities Germany | "Make a bar chart of supplier risk ratings." | Utilities / Germany |

Note these already produced a CHART before the change (chart intent comes from
the words, not the filters). The change made the chart NARROWER, which reads as
a deliberate answer to a question the tool never understood — worse, not new.

Fixed by requiring the whole question to be a redraw request (`BARE_CHART_REQUEST`),
and dropping bare "bar" as an inheritance trigger entirely. A referring word is
deliberately NOT sufficient: "Can this graph be exported?" refers back and is
still not a request for data.

### Codex round 2 — 5 findings, all 5 REJECTED with reasons
Re-run against the revised rule, because the first pass was stale for what was
actually shipping. It flagged "can you graph?", "can you plot?",
"can you visualize?", "can you show me this graph?", "show me this chart" as
capability questions that should not inherit.

Rejected after checking the OUTCOME rather than the grammar: typed straight
after "2024 spend", every one means "graph that". Inheriting gives a 2024
chart; not inheriting would give a 2025 whole-company chart — further from what
was asked, not closer. Pinned as tests so the decision is deliberate.

### Tests 919 → 965
46 new tests. Checked with `git checkout HEAD~1 -- nl_parser.py`: **21 fail
against the pre-fix parser**, 944 pass. The other 25 are guard tests that must
pass both before and after — they pin behaviour the fix must not break.

(An earlier mid-session count of "16" was taken before the last two test
batches existed and is superseded by the 21 above. A `git stash push` of a
committed, clean file is a silent no-op and proves nothing — use the explicit
`git checkout HEAD~1 --` form for this check.)

Customer sweep unchanged at 22/134 fall-throughs — no regression.

### RESIDUAL GAP — flagged, deliberately NOT fixed
Charting an answer that spanned BOTH years still narrows to one year:
"people spend" answers €2,019,149.48 (all years), and charting it shows
€977,536.74 (2025 only). The subject now carries correctly; the year does not,
because `_resolve_chart_year` in `app.py` imposes a year on every chart that
lacks one — deliberate, documented, and shared by every chart path.

Disclosed in the caption ("year = 2025"), so it is honest rather than silent,
but the total still changes between the answer and its own chart. Fixing it
means making charts span multiple years: `chart_query.category_spend` already
accepts no year, but the axis label, `_resolve_chart_year`, and every other
chart view (fragmentation, top suppliers, intensity) share the rule. That is a
larger, separately-scoped change than the one asked for — Hayden's call.

Related known inconsistency, same reason: "for 2024?" (2 words) inherits the
previous subject, but "show 2025 in a bar chart" (6 words) does not, because
only short fragments count as elliptical. Both name only a year.

---

## Round 5 — "top IT suppliers in UK" (12 Aug 2026)

Found while investigating Jayesh's client email. His screenshot showed "top IT
suppliers in UK" answering with the whole-UK total (€4,073,188.81) instead of
a ranked supplier list — but re-running that exact question live, twice,
correctly gave €737,392.25 (IT-filtered). His browser tab almost certainly
mixed an older answer into a persistent chat history; the bug itself, checked
directly, was real but different: the FILTERS were always correct, the
INTENT was not. `TOP_SUPPLIERS_KEYWORDS` only matches the literal phrase "top
suppliers" — inserting a category between the two words ("top IT suppliers")
broke it, and the question fell through to a plain total instead of the
ranking it asked for.

### What shipped
`TOP_SUPPLIERS_WITH_SUBJECT_PATTERN` captures the gap between "top" and
"supplier(s)" (max 3 filler words); `_top_suppliers_gap_is_real_subject`
rejects the match if any filler word is a stopword. Fires only alongside
`filters` already being non-empty and no specific supplier named (that's a
drill-down, not a ranking).

### Four Codex rounds — the mechanism changed twice, not just the word list
- **Round 1** (3 findings, all real): a reactively-built ~15-word stopword
  list still let "of the range", "for" slip through as if they were category
  names. Fixed.
- **Round 2** (1 false-negative + 2 false-positives): "and"/"or" in that list
  wrongly rejected the REAL L1 category "IT and telecom" — checked and
  confirmed neither word was ever load-bearing for round 1's fixes, so both
  were removed. New leaks: "among", "versus".
- **Round 3** (2 more leaks): "by", "across" — the same reactive-list failure
  mode the chart follow-up fix hit two days earlier. Rather than add two more
  words, replaced the whole list with English's actual closed word class
  (prepositions/conjunctions/articles/copulas, ~55 words) — genuinely finite
  and documented, not built one Codex finding at a time.
- **Round 4** (self-inflicted risk, not a new leak): "us" was in the list as
  the pronoun ("with us"), but "US" is an ordinary real country
  name/abbreviation — this dataset simply has no US entry to expose it.
  Removed, along with "range"/"count"/"position"/"list" (round 1's own
  reactive additions, not genuine closed-class words) — checked and none of
  the five were load-bearing for any of the 7 confirmed leaks across all
  three rounds.

Every real value in the dataset (98 across entity/country/cluster/l1/l2/
supplier) checked against the final list: zero collisions, including all 8
L1 categories and all 6 L2 sub-categories containing "and".

### RESIDUAL LIMIT — flagged, not fixed
1. The gap is capped at 3 filler words, so a 5-word category description
   ("top IT hardware and software services suppliers in UK") still falls to
   a flat total. Widening the cap reopens the connector-word leaks above.
2. The stopword list is checked against THIS dataset, not proven for all
   future data — a category or entity name containing a genuine preposition
   in different real client data would still be rejected. Not fixable
   without matching the gap against known aliases directly, which is a
   larger change than this bug warranted.

### Tests 965 → 994 (29 new)
Checked with `git show HEAD:nl_parser.py` swapped in over the fix: 13 of the
29 fail against pre-fix code. The other 16 are guard tests that must pass
both before and after.

---

## Round 6 — chat bubble redesign (12 Aug 2026)

Requested after Jayesh's "it's fast, doesn't like spelling errors" feedback
and the plan to demo an AI-connected version soon: replace the default
Streamlit chat layout (`st.chat_message`, left-aligned both sides, avatar
icons) with iMessage-style bubbles — right-aligned Zureli teal (`#17343C`,
the same value already used as `BRAND` and the config.toml `primaryColor`,
not a separately invented blue) for the user, left-aligned grey
(`BUBBLE_GREY = "#F5F5F6"`, reused from config.toml's
`secondaryBackgroundColor`) for the assistant. Designed with Hayden via the
`superpowers:brainstorming` visual-companion browser tool before any code
was touched — three mockup rounds (bubble style A/B/C, chart-in-bubble
trade-off, working hover/select prototype) settled the design before
implementation started.

### Design decision: text always in the bubble, charts/tables always break out
Chosen over "everything in the bubble" (Option C's literal form) after
mocking up a 12-month two-supplier line chart inside a bubble: a chart with
a legend and month labels either forces the bubble edge-to-edge (stops
reading as a message) or the labels overlap. Charts/tables/KPI rows now
always render full-width via a separate call below the bubble, never nested
inside it.

### What shipped
- `render_payload` split into `render_message_bubble` (text + hover
  timestamp, HTML-escaped) and `render_payload_extras` (everything else,
  unchanged logic, just no longer starts with the text line).
- `AVATARS` and every `st.chat_message()` call removed — replaced with a
  plain `<div>` per message, styled via one global CSS block (extending the
  page's existing single `st.markdown(<style>)` injection rather than adding
  a second one).
- Per-message relative timestamp (`_relative_time`), stored at append time
  (`time.time()`), revealed on hover via CSS opacity transition — visible
  proof only on the live message; a `.get("timestamp", time.time())` guard
  covers any in-flight session predating this field.
- Scoped out, per Hayden's decision after seeing the working mockup:
  highlight-a-message-and-reply. Streamlit has no built-in text-selection
  event; the mockup faked it with page-local JavaScript, which doesn't carry
  over to a real Streamlit component. Would need a custom interactive
  component built from scratch — a separate, later-scoped piece of work, not
  bundled into this pass.

### Real bug found and fixed during build (not just during review)
The bubble CSS was interpolated with Python's `%` string formatting; the CSS
itself contains a literal `max-width: 75%;`, which Python read as a broken
format specifier (`%;`) and crashed every test that renders a message —
70 failures on the first full test run. Fixed by switching to plain
`str.replace()` token substitution (`__BRAND__` etc.), which doesn't care
about `%` or the CSS block's own `{ }` braces (which would have broken an
f-string/`.format()` approach the same way). Re-ran the full suite after the
fix: 994/994 pass.

Separately, the mockup's own chart-tooltip demo (in the visual-companion
browser tool, not app.py) had a real positioning bug caught during design
review, before any app code was touched: the tooltip's offset was measured
against the wrong parent element, placing it off-screen below the fold.
Fixed by referencing the chart's own container instead of the outer mockup
wrapper, then re-verified live in the browser (not just re-read) that the
tooltip appeared in the right place with the right number.

### Codex review — 3 findings, 2 fixed, 1 rejected with reasoning
- **Fixed**: `escape()` on the bubble text doesn't stop a browser from
  collapsing a literal newline the way `st.markdown()`'s real markdown
  parser used to (a blank line was a paragraph break; in a raw HTML div it's
  just whitespace). No current answer template contains a newline — checked
  directly — but added `white-space: pre-wrap` to the bubble CSS since the
  fix is free and closes a real, if currently dormant, gap.
- **Fixed**: removing `st.chat_message()` also removed its accessibility
  semantics. Restored via `role="article" aria-label="Chat message from
  {role}"` on each message row, matching the exact `aria-label` wording
  Streamlit's own component used (confirmed against this file's own Task 13
  Step 5 comment, which had already documented that selector from live DOM
  inspection).
- **Rejected**: `role` is interpolated directly into the HTML attribute:
  Codex flagged this as a theoretical injection risk if role were ever
  externally supplied. It never is — `role` is always the literal string
  `"user"` or `"assistant"`, hardcoded at the two `messages.append()` call
  sites in this same file, not read from any user input or external source.
  Adding validation here would be guarding against a scenario that cannot
  happen, which this project's own conventions (Hayden's global rules,
  Section A) explicitly avoid.

### Verification
Three layers: 994/994 automated tests pass (confirms no regression to
existing behaviour); a real local run in an actual browser covering both
structurally distinct payload shapes (chart+caption, and KPI-row+callout
cards), the empty state, and the hover-timestamp interaction, with the
`role`/`aria-label`/`white-space` fixes confirmed present in the live DOM via
direct inspection, not just in source; a cross-family Codex review of the
actual diff, triaged as above. Not done this round: new pinned automated
tests for `_relative_time` or the escaping behaviour specifically — the
existing 994-test suite plus this round's real-browser and Codex passes were
judged sufficient for a visual/rendering change with no logic-path changes
elsewhere; flagging this as a deliberate scope choice rather than an
oversight.

### RESIDUAL — flagged, not built this round
Highlight-a-message-to-reply (see above) — scoped as a follow-up once this
redesign is live, at Hayden's explicit decision.

Not yet committed or pushed — this repo auto-deploys on any push touching
`app.py`, so pushing needs Hayden's go-ahead, not just a green test suite.

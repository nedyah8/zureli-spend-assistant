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
   live inspection of the real InSight demo. The app now displays € on
   every total (chart and text alike) and the standing caption states this
   plainly instead of claiming the currency is unknown.
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

**Explicitly deferred — not started.** This phase covered category spend
only. Per the sequencing Hayden confirmed, three more InSight views remain
entirely unbuilt: Phase 2 (Top suppliers chart), Phase 3 (Fragmentation
bubble chart), and Phase 4 (Overview KPI cards) — in that order, each to go
through its own design-and-build pass after this one, not folded into this
handoff.

## Next steps
- Show this prototype at/before the data scientist meeting as a concrete
  demo rather than a blank question list.
- After that meeting: revisit architecture decisions above against what's
  actually confirmed about the real InSight data.
- Decide on the LLM upgrade once there's a reason to (API key + real
  questions to test against).
- Phases 2–4 (Top suppliers, Fragmentation, Overview KPIs) once Phase 1 has
  been shown and Hayden confirms the next priority.

## How to run it
```
cd "5. AI Chatbot"
source .venv/bin/activate
streamlit run app.py
```
It was left running locally on port 8501 during this session
(`http://localhost:8501`) for Hayden to try directly.

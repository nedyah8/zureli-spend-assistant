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
2. **Currency unit.** The sample file has no currency column; the app
   shows plain numbers with no symbol. Worth confirming with the data
   scientist whether the real data is GBP or something else.
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

## Next steps
- Show this prototype at/before the data scientist meeting as a concrete
  demo rather than a blank question list.
- After that meeting: revisit architecture decisions above against what's
  actually confirmed about the real InSight data.
- Decide on the LLM upgrade once there's a reason to (API key + real
  questions to test against).

## How to run it
```
cd "5. AI Chatbot"
source .venv/bin/activate
streamlit run app.py
```
It was left running locally on port 8501 during this session
(`http://localhost:8501`) for Hayden to try directly.

# AI Chatbot (spend chat interface) — project rules

Supplements Hayden's global CLAUDE.md. These are the hard rules specific to
this project — check them before making changes here.

1. **Synthetic data only, right now.** `sample_spend_data.csv` is a demo
   file Jayesh forwarded from the data scientist on 29 Jul 2026 — it is not
   real client data. Never present numbers from this file as if they came
   from a real client, and never wire this app into any real client-facing
   deployment without an explicit new decision to do so.

2. **No LLM is wired in yet.** There is no `ANTHROPIC_API_KEY` configured on
   this machine, so `nl_parser.py` is a rule-based keyword matcher, not a
   language model. Do not describe this app as "AI-powered" without
   flagging that the current understanding layer is pattern matching, not
   an LLM — see the "Open decisions" section of `_HANDOFF.md` for the
   upgrade path.

3. **InSight's real technical shape is still unconfirmed.** Everything
   currently known about InSight comes from Jayesh secondhand (Streamlit,
   CSV/Excel behind it) — not from Zureli's data scientist directly. Do not
   assume the real production data matches this sample file's structure
   (single client, ~800 rows, no client identifier column) until that
   conversation happens.

4. **This is a disposable prototype, not the real architecture.** No
   multi-tenancy, auth, or per-client data isolation has been designed —
   Jayesh's stated goal is eventually a paid, client-facing subscription
   feature, which is a materially different build. Do not extend this
   prototype toward a real deployment without a fresh design pass covering
   those concerns first.

5. **Any future visual/chart work on this project must go through the
   `dataviz` and `interface-polish` skills.** Set by `_CHART-CHAT-DESIGN.md`'s
   build-process requirement (itself sourced from the websites-project
   research on avoiding generic AI output). Use the `dataviz` skill for chart
   styling — palette, typography, mark choices — on any new chart (Top
   suppliers, Fragmentation, Overview KPIs, or any other visual added later),
   and the `interface-polish` skill for the surrounding chat UI whenever it
   changes. Name each skill explicitly when it's invoked, in the same turn —
   never apply either silently.

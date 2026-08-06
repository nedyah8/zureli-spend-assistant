# Chart-in-Chat — Design Spec (Phase 1: Category spend)

Written 4 Aug 2026 on Fable 5 during the brainstorming session with Hayden,
after the InSight demo (https://zureli-insight-demo.streamlit.app/) was
inspected live, tab by tab, in the browser. Approved direction: Option A
(extend the existing rule-based prototype) built with Option B's structure
(strict separation of understanding vs computation, so a real LLM can be
swapped in later without a rebuild). This doc is the record; _HANDOFF.md
remains the live status source.

## Purpose

Extend the existing chat prototype so a plain-English question can return
**the same chart the InSight dashboard would show**, starting with one view
and getting it right before touching the others: the **Category spend
horizontal bar chart**. This is the first concrete step of the agreed
end-goal — everything visible in the InSight demo eventually answerable
through chat.

Jayesh's one-line brief (his slide, verbatim): "Reverse engineer it from
StreamLit to AI Interface -> i.e. does it give the same/similar bar chart
from the original source to the interface."

## What the InSight demo's Category spend view actually is (observed, not assumed)

Inspected live on 4 Aug 2026. One horizontal bar chart:

- One bar per Level 1 category (Professional services, IT and telecom,
  Logistics, Facilities, People, Utilities, Marketing, Office), sorted
  descending by spend.
- Each bar is **stacked**, split into coloured segments by a "break down by"
  dimension — default Entity, switchable (Entity / other dimensions) via a
  dropdown in the dashboard.
- X-axis: "Net spend 2025 (€)" with 0M–1.6M tick labels — **currency
  confirmed EUR** (this resolves an open question in _HANDOFF.md).
- Controls in the dashboard version: category level toggle (Level 1 /
  Level 2), breakdown dropdown, "categories shown" slider.
- The demo's "More" tab states its dataset is "the exact public demo
  dataset" with identical columns to our `sample_spend_data.csv` — the file
  we already build against is confirmed to be the real demo data shape
  (resolves the other open _HANDOFF.md question about data structure).

## Scope

**In (this phase):** chart intent detection; a deterministic chart-building
module for the category-spend view; inline chart rendering in the chat
stream; Level 1 and Level 2 category support; breakdown by entity (default),
country, or cluster when the question asks for it; the same filter
vocabulary the chat already understands (entity / country / cluster / year /
category / supplier) applied to the chart; € formatting throughout now that
currency is confirmed.

**Out (named, deferred — not silently dropped):** Top suppliers chart,
Fragmentation bubble chart, Overview KPI cards (phases 2–4, in that order,
after this one is verified); real LLM parsing (still blocked on an API key —
unchanged open decision); any InSight-side integration; multi-tenancy/auth
(unchanged from CLAUDE.md rule 4).

## Architecture

Three-layer split, preserving the swap-in-LLM-later property:

1. **Understanding** (`nl_parser.py`, extended): `parse_question` gains
   intent detection alongside the existing filter extraction. Output becomes
   `{intent: "chart" | "number", chart_kind: "category_spend" | None,
   breakdown: "entity" | "country" | "cluster" | None,
   category_level: "l1" | "l2", filters: {...}}`.
   - Chart intent triggers on any of: chart, graph, plot, bar, breakdown,
     break down, visualise/visualize, show me ... by, compare, split.
   - Breakdown dimension from "by entity" / "by country" / "by cluster"
     (default entity, matching the demo's default).
   - Category level: "level 2" / "sub-category"/"subcategory" → l2,
     else l1 (matching the demo's default).
   - Everything else behaves exactly as today (number answer). No existing
     behaviour changes for non-chart questions — regression-checked.
2. **Computation** (`chart_query.py`, new): deterministic pandas only —
   filter (reusing `spend_query`'s filter logic, not duplicating it), group
   by category × breakdown dimension, sum Net spend, sort categories
   descending by total. Returns a plain dataframe. **No AI anywhere in this
   layer; a chart can never contain an invented number.**
3. **Presentation** (`chart_render.py`, new + `app.py` wiring): builds a
   Plotly horizontal stacked bar figure from that dataframe and renders it
   inline inside the assistant's chat bubble via `st.plotly_chart`.

Library decision: **Plotly** (add to requirements). Reason: first-class
Streamlit support, horizontal stacked bars with hover tooltips out of the
box — the interactive behaviour observed in the demo — and no extra system
dependencies. (Whether the demo itself uses Plotly or Altair is unknown and
doesn't matter; parity is judged visually against screenshots, not by
matching their internals.)

## Visual parity rules (the "reverse-engineered" test)

The chart must read as InSight's chart, not a generic default:

- Horizontal bars, categories sorted descending, stacked segments by the
  breakdown dimension, legend labelling segments.
- € axis formatting in the demo's style (0M / 0.5M / 1M ticks; € in the
  axis title: "Net spend <year> (€)").
- "Demo " prefix stripped from entity names in the legend (consistent with
  existing chat behaviour).
- Colour: segments need a categorical palette (a multi-colour palette is
  functionally required for a stacked chart and is distinct from Hayden's
  single-colour rule for the chat UI itself, which stands unchanged —
  flagged to Hayden 4 Aug; his approval of this spec is the confirmation).
  Palette choice and chart typography go
  through the **dataviz skill** at build time; the surrounding chat surface
  stays strictly teal/greyscale per the interface-polish pass already
  shipped.
- Under every chart, a one-line caption stating what was matched (same
  transparency pattern as the current number answers): e.g. "Matched on
  year = 2025, broken down by entity — 8 categories, total €7.4m."

## Behaviour rules (including edge cases — same honesty standard as today)

- Chart request, no filters recognised → full-dataset category chart for the
  default year — defined as the latest year present in the data (2025 in the
  sample file), matching the demo's focus-year default — with the standard
  caption; this is a valid, useful default (it's exactly what the dashboard
  shows unfiltered), NOT an error.
- Chart request with filters → filtered chart; caption names every applied
  filter.
- Chart request whose filters match zero rows → honest text reply ("nothing
  matched"), no empty chart rendered.
- Non-chart question → existing number behaviour, byte-for-byte unchanged.
- Nonsense/garbage → existing caveat behaviour unchanged.
- A chart answer also includes the total as text above the figure, so the
  conversation still reads as an answer, not just a picture.

## Build process requirements (from the websites-project research, applied here)

- **frontend-design skill** consulted for the chat-surface layout framing;
  **dataviz skill** for the chart itself; **interface-polish** screenshot
  gate (≥1200px + empty state + a live chart exchange) before "done" — none
  of these invoked silently; each named when used. A standing instruction to
  this effect gets added to the project CLAUDE.md as part of this build.
- **Screenshot loop during the build**, not one final check: render, look,
  correct, re-render — the technique the websites research validated.
- Reference-based design, not freehand: the InSight demo screenshots
  captured this session are the visual reference for the chart; the general
  chat-product references (Claude/ChatGPT layouts) remain the reference for
  the conversation surface.

## Verification plan

- Everyday tier (single direct adversarial pass) for in-build iterations.
- **High-stakes tier for the phase gate**: this is a demo for Zureli
  higher-ups — before Phase 1 is called done: (1) unit checks on the
  aggregation (chart totals cross-checked against independently computed
  numbers, same method as the existing 192,988.04 check); (2) a real
  browser run-through with screenshots of at least: default chart, filtered
  chart, breakdown variant, zero-match case, and a regression pass on the
  four existing number/caveat test questions; (3) a cross-family **Codex
  review** of the changed code, findings triaged and logged in this file's
  style (mirroring _DEMO-DESIGN.md's triage log), before it's shown beyond
  Hayden.

## Explicitly unresolved (unchanged)

- No ANTHROPIC_API_KEY on this machine — parsing stays rule-based; the
  architecture above is shaped so the swap is contained in layer 1.
- The real InSight production data shape beyond the demo dataset; the data
  scientist conversation is still the confirmation point.

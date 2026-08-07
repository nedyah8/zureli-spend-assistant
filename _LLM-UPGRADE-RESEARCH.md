# LLM Upgrade Research — wiring a real AI into the Zureli Spend Assistant

Researched 7 August 2026 (Claude Fable 5, high effort). Every price and policy
below was verified against the provider's own published page on this date —
not from memory. Prices for AI services change often; re-verify before
quoting them to a client more than a month or two from now.

This answers the question raised by Jayesh's email ("is this a lookup tool,
whereas AI could communicate in a certain way, have a 'personality' of sorts,
use reasoning?") and Hayden's follow-up: can we build/wire in a real LLM,
what would it cost, and can it stay private enough to sell.

---

## 1. The honest starting point: you don't "build" an LLM — you rent or host one

Three routes exist. Only one makes sense for this product.

**(a) Use a provider's model through an API key — the normal route.**
Every serious AI product on the market (including Jayesh's own InSight demo
stack, if it ever adds chat) works this way: the app sends the user's
question over an encrypted connection to Anthropic (Claude) or OpenAI
(GPT), gets the model's response back in about a second, and pays around a
penny or less per question. No model is "built"; you rent access to
one that cost the provider hundreds of millions to train. Hayden's phrases
map as follows:

| Hayden said | What it actually is |
|---|---|
| "Opus or Sonnet" | Anthropic's Claude models, used via an **Anthropic API key** |
| "a chat gbt key" | An **OpenAI API key** — same idea, OpenAI's GPT models |
| "GPT 5.5 / GPT 5.6" | OpenAI's current API models (both real: GPT-5.5, and the newer GPT-5.6 family) |
| "Codex" | Not an option here — Codex is OpenAI's *coding assistant tool* (like Claude Code), not a model you can embed in an app |

**(b) Self-host an open-weight model (Llama, Mistral, etc.).** The model
runs on hardware you control and *nothing ever leaves the building* — the
only route to absolute, literal privacy. The cost: a GPU server (hundreds
of pounds/month rented, or thousands up front), real engineering to run and
update it, and open models that are noticeably weaker than Claude/GPT at
instruction-following. This is the right answer only if a client
contractually forbids any external processing. It is not the right first
move.

**(c) Train or fine-tune your own model.** Training from scratch is a
tens-of-millions-of-pounds exercise — not a real option for anyone but the
labs. Fine-tuning an existing model is possible but solves a problem we
don't have: the models already understand procurement questions perfectly
well; what they need is our data vocabulary, which we give them in the
prompt for free.

**Conclusion: route (a).** The only real decision is *whose key* (§3) and
that decision is low-stakes: in the architecture below the provider sits
behind one narrow interface, so switching later is a small, contained
change plus a regression run — not a rebuild.

---

## 2. Architecture: the LLM understands and talks; our code still does the maths

This is the single most important design point, and it is exactly why the
tool was built in three separate layers (understanding → computation →
presentation) from day one — the swap was planned for.

```
User question ("roughly what are we burning on tech each year?")
        │
        ▼
[1. UNDERSTANDING — becomes the LLM]
   Claude/GPT receives: the question + a short description of the data's
   vocabulary (the 8 categories, 8 entities, 7 countries, chart types).
   It returns a small structured request: {category: "IT and telecom",
   view: "category_spend by year"}.  It never sees the spend data itself.
        │
        ▼
[2. COMPUTATION — unchanged, stays deterministic]
   The existing pandas code (spend_query.py, chart_query.py) computes the
   answer from the CSV, exactly as it does today — the same audited code
   whose figures were checked against the InSight demo's own numbers
   during the build. The LLM cannot invent a figure at this step, because
   it never produces figures.
        │
        ▼
[3. PRESENTATION — LLM phrases the reply]
   The computed numbers go back to the LLM with "explain this result
   conversationally". This is where Jayesh's 'personality' and reasoning
   live: it can compare, contextualise, suggest follow-ups — but only
   about numbers our code calculated.
```

Two failure modes the build must guard against (both flagged by the
independent review of this document, both cheap to handle):

- **Step 1 can misunderstand** — pick the wrong category or year and hand
  the deterministic code a wrong request, producing a correct calculation
  of the wrong thing. Guard: the app already prints its interpretation
  with every answer ("Matched on category = IT and telecom …"), so a
  misread is visible rather than silent; add schema validation on the
  LLM's structured request and a pinned set of question→interpretation
  tests, and have the model ask a clarifying question when genuinely
  unsure instead of guessing.
- **Step 3 can misquote** — a model *rephrasing* numbers can round or
  garble them. Guard: after the reply is generated, check the exact
  computed figures appear in it verbatim (or insert them by template);
  reject and retry the reply if not. The number shown to the user is
  always the one pandas computed.

What this buys, in Jayesh's terms:

- **"Doesn't seem to work"** → solved structurally, not by more aliases.
  The alias patch shipped this week fixes the phrasings we anticipated; an
  LLM understands phrasings nobody anticipated ("what's eating our
  budget?", typos, Hinglish, whatever a real buyer types).
- **"Personality / communicate in a certain way"** → step 3. We write the
  persona once ("you are Zureli's procurement analyst; concise, direct,
  numbers first") and every reply carries it.
- **"Use reasoning"** → the model can chain steps: notice a question needs
  two lookups, ask a clarifying question when genuinely ambiguous, point
  out that a category doubled year-on-year.
- **Numbers stay trustworthy** → unchanged from today. This is the honest
  selling line: *the AI does the understanding and the talking; the
  arithmetic is done by audited code on your own data.* Pure-LLM chatbots
  that compute answers themselves are notorious for confidently wrong
  numbers — Jayesh has now personally experienced why that matters.

Two practical notes: the current rule-based parser stays in the code as an
automatic fallback (if the API is down or the key runs out of credit, the
tool degrades to today's behaviour instead of dying — and says so in the
reply, with the event logged, rather than silently answering worse), and
the existing test suite (700 collected checks after parametrisation, run
green this week) keeps guarding the computation layer, which does not
change at all.

---

## 3. Whose key: Anthropic vs OpenAI — verified prices, August 2026

Both providers work identically in the architecture above. Current
published API prices (per **million** tokens — a token is roughly ¾ of a
word; a typical question here uses ~1,500–3,000 tokens in total):

| Provider | Model | Input / Output per 1M tokens | Fit |
|---|---|---|---|
| Anthropic | Claude Haiku 4.5 | $1 / $5 | Cheapest adequate option |
| **Anthropic** | **Claude Sonnet 5** | **$3 / $15 (intro $2 / $10 until 31 Aug 2026)** | **Recommended: the workhorse tier** |
| Anthropic | Claude Opus 5 | $5 / $25 | More than this task needs |
| OpenAI | gpt-5-mini | $0.25 / $2 | Cheapest adequate option |
| OpenAI | gpt-5.6-terra | $2 / $12 | OpenAI's equivalent workhorse |
| OpenAI | gpt-5.5 / gpt-5.6-sol | $5 / $30 | More than this task needs |

(Anthropic prices from the current platform documentation; OpenAI prices
from developers.openai.com/api/docs/pricing, both checked 7 Aug 2026.)

**Cost per question**, worked through for the recommended setup (Sonnet 5,
two calls per question — one to understand, one to phrase — ~3,000 input +
~300 output tokens total): **$0.0135 at the standard price ($3/$15), or
$0.009 at the introductory price running until 31 Aug 2026** — call it
about a penny per question either way. A thousand questions a month is
therefore **$9–14/month**; prompt caching (both providers offer it) can
cut the input side further on repeat traffic — an optimisation to measure
during the build, not a guaranteed saving. On Haiku or gpt-5-mini it drops
to roughly a fifth of that. At demo/pilot scale this is effectively free —
a $5 starting credit covers hundreds of questions.

**Recommendation between them:** either genuinely works, and the choice is
reversible. I recommend the **Anthropic key with Claude Sonnet 5**: the
price is equivalent to OpenAI's comparable tier, the privacy terms are
broadly comparable for this kind of stateless use (§4 — comparable, not
contractually identical), and I can build and test the integration fastest and most
reliably against the Anthropic API (current, verified integration docs are
in my tooling — fewer unknowns, fewer bugs). If Jayesh or Zureli already
has an OpenAI account with credit, using that instead costs us nothing but
a slightly longer build.

---

## 4. Privacy: what actually leaves the building, and what "private" can honestly mean

This section matters because Hayden is right that there's demand for
"keeps the data private but still useful" — but the claim has to be made
precisely, or it becomes a liability in a sales conversation.

**What would go to the AI provider per question:** the question text, the
short vocabulary list (category/entity/country *names* — which are
themselves client information: they reveal how the client's business is
structured), and — for the phrased reply — the computed summary figures
for that answer. Those summary figures are still spend data, just
aggregated: someone asking many narrow questions could reconstruct a
detailed picture from the answers, so this must be described to clients as
externally processed data, not as "nothing". **What never goes:** the raw
dataset — the CSV, the transaction rows, supplier invoices. The provider
sees single questions and single answers, never the books.

**What the providers commit to** (both verified against their own current
policy pages, 7 Aug 2026):

- **Anthropic:** "By default, we will not use your inputs or outputs from
  our commercial products (e.g. … Anthropic API …) to train our models."
  Standard policy is deletion of API inputs/outputs within 30 days; a
  stricter zero-data-retention arrangement exists for eligible commercial
  customers.
- **OpenAI:** "Data sent to the OpenAI API is not used to train or improve
  OpenAI models (unless you explicitly opt in)." Abuse-monitoring logs are
  kept up to 30 days for the standard stateless endpoints; approved
  customers can obtain Zero Data Retention.

Both retention commitments carry the standard exceptions any provider has
— content flagged for abuse review, legal holds, data a user explicitly
submits as feedback — so quote them as "the default policy", not as an
absolute.

So the honest, sellable formulation is: *"Your raw spend data never goes
to the AI provider — only the question and the summary figures for each
answer do, and the provider does not train on them and deletes them under
its standard 30-day policy."* That is a strong, true claim and it
satisfies most mid-market clients. What it is **not** is "nothing ever
leaves the building" — a client who requires that (some public-sector and
regulated buyers) needs the self-hosted route from §1(b), which can be
offered later as a premium tier rather than built now.

**Where the app itself runs is a separate privacy question the LLM choice
doesn't answer.** Today the demo runs on Streamlit Community Cloud from a
**public GitHub repository** — right for a demo on synthetic data, but it
means the app and its data live on Streamlit's (Snowflake's) servers, a
processor in its own right. Before any real client data goes near this:
private repo, login in front of the app, a deliberate hosting decision,
and the buyer-readiness paperwork (a data-processing agreement with the
AI provider — both offer one — plus GDPR/data-residency answers a UK/EU
procurement team will ask for). The API key itself goes in Streamlit's
encrypted secrets store, never in the code.

---

## 5. The definitive answer — what to do next

**Recommendation: wire Claude Sonnet 5 into the existing app via an
Anthropic API key, as the understanding and reply-writing layer only,
keeping all computation in the existing deterministic pandas code — because
it converts the tool from a lookup demo into the conversational analyst
Jayesh described, for about a penny per question, without giving up the
one thing this build got right (numbers computed by tested deterministic
code, which the AI can neither produce nor alter).**

Concretely, in order:

1. **Hayden/Zureli decision (the only blocker):** whose API account. Options:
   Hayden creates an Anthropic account with ~$5 credit to power the demo
   now (recommended — unblocks immediately, costs pennies), or Jayesh
   provides a Zureli-owned key (cleaner long-term, since the running cost
   should sit with Zureli anyway).
2. **Build (one focused session, roughly a day):** add the LLM layer with
   the persona prompt, structured-request parsing (schema-validated, with
   the interpretation shown in every answer as today), phrased replies
   checked to contain the exact computed figures, visible-and-logged
   fallback to the current rule-based parser; key in Streamlit secrets;
   extend the test suite with a pinned question→interpretation set so the
   deterministic layer and the understanding layer both stay guarded.
3. **Verify** the same way the alias fix was verified: full suite, live
   deployed check, and re-run Jayesh's own failing questions plus a set of
   phrasings no alias list could ever cover.
4. **Reply to Jayesh** with both fixes in hand: "your exact question now
   works" (already live) and "it now genuinely understands and talks" (the
   LLM layer), with the privacy line from §4 as the positioning.

What this deliberately defers, named rather than forgotten: self-hosting
(only if a client demands absolute on-premise privacy); fine-tuning
(unnecessary); any change to the computation layer (working, tested,
untouched); and the whole "sell it to a real client" readiness layer —
login/authentication, per-client data isolation, hosting off the public
demo setup, DPAs and GDPR/residency paperwork, rate limiting and
prompt-injection hardening. None of that blocks the LLM upgrade or the
Jayesh demo, but all of it comes before the first paying client, and the
project's own standing rule already requires a fresh design pass before
any real-deployment extension.

Sources: Anthropic model pricing & data policy (privacy.claude.com,
platform.claude.com docs); OpenAI pricing (developers.openai.com/api/docs/
pricing) and API data-usage guide (developers.openai.com/api/docs/guides/
your-data); all fetched 7 Aug 2026.

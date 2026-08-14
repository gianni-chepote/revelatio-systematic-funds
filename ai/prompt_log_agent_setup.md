# Prompt log - agent setup and build plan

*Milestone: before any Part B code — set up my agent instructions (CLAUDE.md),
the build plan, and the design/methodology rules. Drafted from the session;
`[YOUR WORDS]` marks where I add my own reflection before hand-in.*

## What I wanted

A complete Part B agent brief and a step-by-step build plan before writing any
code: the product's look, the methodology standard, the innovation menu, the app
standard, and the order we build in — with innovation deferred to the end.

## Prompt(s)

- "Brief me on what we did in Part A and what's next for Part B."
- "Enhance and apply: use the BlackRock fund pages as our product reference —
  multiple funds, each with overview, performance, key facts, characteristics,
  holdings, exposures, literature. Also the methodology in the report needs the
  equations written out with every parameter defined."
- "The initial training window and how often we rebalance must be explained
  clearly in the methodology."
- "Rebalancing frequency affecting OOS performance can be a point of innovation —
  add it."
- "Innovation ideas: long-short with a ~20% short cap; a portfolio that invests
  across the equity and crypto portfolios; show drawdowns even though BlackRock
  doesn't."
- "Also: a passive benchmark; a realistic fee (≤1% management + performance fee);
  mean-CVaR; covariance shrinkage; volatility targeting (Moreira and Muir 2017);
  equal-weight/min-variance blend; a transaction-cost model. Sentiment ideas:
  extend the VADER lexicon with AI-rated finance terms; TextBlob/ensemble; index
  by market/sector/stock with smoothing; expanding-window standardisation."
- "The app can come after innovation, and the report before the app."
- "Create an md file with all the steps for Part B and a proxy prompt each,
  excluding innovation — we leave that to the end."

## What the assistant produced

- Rewrote `CLAUDE.md` from the stub: product goal, the BlackRock seven-section
  fund-page structure, a methodology section requiring every equation and
  parameter, the walk-forward-disclosure rules, an "Innovation candidates"
  section, the app minimum standard, commandments, and a parked-decisions list.
- `AGENTS.md` pointing to `CLAUDE.md`.
- `guidance/BUILD_PLAN.md`: Steps 0–10 with a proxy prompt per step, innovation
  isolated to Step 8, app and deploy last.

## What was wrong or risky

- **The assistant moved to act before there was a plan.** On "let's start
  building" it began reading Part A source and preparing to write code. I stopped
  it and required a written build plan with proxy prompts first, innovation
  deferred. [YOUR WORDS: why plan-first matters to me.]
- **Impersonation risk in the product reference.** Modelling the app on BlackRock
  could slide into copying a real firm's branding. The assistant constrained it
  to *structure only* — no BlackRock wording, colours, or logos — cited as a
  design influence. I kept that guardrail.
- **Unverified citation.** Volatility targeting was attributed to "Moreira and
  Muir (2017)"; the assistant flagged it `[HUMAN EDIT REQUIRED: verify citation]`
  rather than asserting it. I must verify author/year/journal before it enters
  the report.
- **Scope creep.** The innovation list grew large enough to threaten the core.
  The assistant added a "depth over breadth" governing rule and a recommended
  short slate; the final choice is mine.

## What I changed and why

- Reordered the plan so the report comes before the app and the app is built once
  after innovation, so it renders the final fund set in one pass.
- Deferred all innovation to Step 8; core is two combined funds plus sentiment.
- [YOUR WORDS: anything I directed or rejected that I want on record.]

# CLAUDE.md — working orders (z5736927, Part B)

## The goal

**Revelatio** is an investment app that operates a menu of systematically
managed funds and lets a first-time investor compare them and decide how to
allocate money across them. We design for the scared first-timer — the person
who suspects investing is a scam played by brokers to play with their money.
Every screen has to earn that person's trust.

**Part A built the data foundation. This folder is the product.** Stations 3–4:
the funds, the sentiment index, the fusion, and the deployed app. Read
`PROJECT_BRIEF.md` Section 5, `context/DATA_GUIDE.md`, and
`context/project_context.md` before touching anything.

The lineup, decided in Part A and unchanged:

- **Nine funds** — three asset families (equity-only, crypto-only, combined)
  × three methods (maximum-Sharpe tangency, minimum-variance, risk parity).
  Each (family, method) pair is one fund with its own fact sheet. The brief's
  required minimum is the combined family with two methods; the rest is the
  innovation we intend to take. *(brief:147)*
- **A walk-forward out-of-sample backtest** behind every one of them — weights
  from past data only, monthly rebalance or slower, first live date and window
  length stated in the report. *(brief:148)*
- **A standalone sector news-sentiment index** across the ten equity sectors,
  lagged at least one trading day. *(brief:151)*
- **A sentiment fusion** folded into the equity funds, reported before-vs-after.
  An honest negative result, explained, is good work. *(brief:152)*

## The product reference — BlackRock fund pages

**We model Revelatio's fund pages on BlackRock's fund/ETF product pages.** That
is the target look and information architecture: a menu of funds, and each fund
opening into its own page with a fixed set of labelled sections rather than one
undifferentiated dashboard. A first-time investor should recognise the shape
because it is the shape a real asset manager uses.

Every fund page carries these sections, in this order:

| Section | What Revelatio puts there | Source artifact |
|---|---|---|
| **Overview** | One-paragraph plain-English statement of what the fund holds, the method that picks the weights, and who it suits. Growth of $1 chart as the hero exhibit. | `results/data/fund_returns.csv` |
| **Performance** | Cumulative and annualised return, volatility, Sharpe, max drawdown, drawdown chart, and the backtest window. Out-of-sample only — never in-sample. | `results/tables/performance_metrics.csv` |
| **Key Facts** | Asset family, optimisation method, inception (first live backtest date), rebalance frequency, estimation window, constraints, risk-free assumption, number of holdings, currency, data coverage 2020–2023. | fund metadata table |
| **Characteristics** | Portfolio-level statistics that are not raw performance: concentration (effective N, top-5 weight), turnover per rebalance, weight dispersion, realised beta to the equal-weight market benchmark. | `results/tables/` |
| **Holdings** | Current target weights from the most recent rebalance, sorted, with the weights-over-time figure beneath. | `results/data/fund_weights.csv` |
| **Exposures** | Breakdown by sector (equities) and by asset class (combined funds), over time as well as current. | `results/tables/` |
| **Literature** | The methodology page — the equations, the backtest design, and the data provenance, written for a reader who wants to check us. This replaces a prospectus; we have no legal documents and will not fabricate any. | report methodology, linked |

**Where we depart from the reference, deliberately: drawdowns.** BlackRock's
fund pages lead with growth and returns; the loss path is not the first thing a
visitor sees. Revelatio puts **a drawdown chart on every fund's Performance
section**, with maximum drawdown, its date, and its recovery length stated in
words. Our user is the first-timer who suspects investing is a scam — hiding the
worst stretch is how you lose that person the first time the market falls.
Showing the fall before they live through it is the trust argument the whole
product rests on. Write this divergence up in the report as a design decision
with that reasoning; it is an argument for our design, not an oversight in
theirs. The brief requires a drawdown figure for at least one fund
*(brief:161)* — we do it for all of them.

Rules that come with this reference:

- **The structure is the reference, not the branding.** Do not copy BlackRock
  wording, disclaimers, colours, or logos. Revelatio uses the Part A house
  design system (`src/plot_style.py` carried over). We cite the reference in
  the report as a design influence; we do not imitate a real firm's identity.
- **A section only appears if we can fill it from our own results.** Every
  number on a fund page traces to a CSV in `results/`. An empty or
  not-applicable section says so plainly.
- Fund pages are for comparison first. The compare view and the allocation
  slider must stay reachable from every fund page.

## The methodology must carry its equations

**Every method in the report gets its equation written out, and every symbol in
that equation defined.** This is not optional decoration — it is how a marker
checks that the code does what the prose claims.

Minimum set, each stated formally and each parameter defined immediately after:

- daily simple return, and the annualisation of return and volatility (state
  √252 for equities, √365 for crypto, and which applies to the combined fund)
- the Sharpe ratio, with the risk-free assumption stated in the equation
- maximum drawdown
- maximum-Sharpe (tangency) weights, the objective and its constraints
- minimum-variance weights, the objective and its constraints
- risk parity — the risk-contribution definition and the condition solved
- the sample covariance estimator and the estimation window
- the sentiment score aggregation: headline → ticker-day → equal-weight sector
  index, and the lag operator
- the fusion rule: how the sentiment signal maps into a weight tilt

### The walk-forward design must be stated, not implied

A reader must be able to redraw our backtest timeline from the report alone.
The methodology section answers every one of these in plain sentences, with
numbers, and the same answers appear on each fund's **Key Facts** section:

- **Window type** — rolling or expanding, and why. If rolling, what is
  discarded at each step.
- **Initial estimation window** — its length in trading days *and* the calendar
  dates it spans. State it for each asset family, since the equity, crypto, and
  combined panels do not share a calendar.
- **First live out-of-sample date** — the first day a fund holds a position.
  Not the first date in the data. Everything before it is training and is
  excluded from every performance number we report. *(brief:148)*
- **Rebalance rule** — the calendar rule in words, not just a frequency. "The
  first trading day of each month" is a rule; "monthly" is not. Monthly or
  slower is the constraint. *(brief:148)*
- **Re-estimation cadence** — whether the covariance and means are re-estimated
  at every rebalance or less often. If they coincide, say so; do not leave the
  reader to assume it.
- **What happens between rebalances** — weights are held as target weights and
  drift with realised returns until the next rebalance, or they are reset daily.
  Say which. This changes both the return series and what
  `fund_weights.csv` means, so the code and the sentence must match.
- **The resulting counts** — number of rebalances, number of out-of-sample
  trading days, and the out-of-sample date range. These are the denominators
  behind every annualised figure in the report.
- **The sentiment lag stacked on top** — the fusion signal is lagged relative to
  the trading day it is aligned to, and that lag is stated separately from the
  rebalance cadence. Two different clocks; do not conflate them.

Support it with a **backtest timeline figure** — training window, first live
date, rebalance points, and out-of-sample span on one axis. It costs one exhibit
and removes every ambiguity above.

### Rebalance frequency as an innovation exhibit

Rebalance frequency is not housekeeping — it is a design choice that moves
out-of-sample performance, and we treat it as a result rather than a footnote.
**Run the full backtest at several frequencies and report what changes.**

- Sweep the frequency across the grid (for example monthly, quarterly,
  semi-annual, annual) holding the estimation window, the constraints, and the
  method fixed. One variable moves at a time.
- Report it for **every (family, method) fund**, not one. The interesting claim
  is whether the funds respond differently — a minimum-variance fund and a
  maximum-Sharpe fund have different reasons to care about staleness, and risk
  parity is the most stable of the three by construction.
- The exhibit is a table of Sharpe, annualised return, volatility, and max
  drawdown by fund × frequency, plus a figure of Sharpe against frequency with
  one line per fund. State the number of rebalances behind each column, since
  an annual rebalance over our window leaves very few.
- Pair it with **turnover**: mean absolute weight change per rebalance and
  annualised turnover. The frequency question is really a trade-off between
  staleness and trading, and turnover is the half of it that a zero-cost
  backtest hides. Adding a transaction-cost model on top turns the whole study
  into the stronger innovation claim, since the ranking can invert once trading
  is not free. *(brief:148 — a turnover or cost model counts as innovation)*
- Say what drives the result. Frequent rebalancing tracks the covariance
  estimate more closely but re-estimates it from a window that barely moved, so
  it can amplify estimation error rather than correct it. That mechanism is the
  finding; the Sharpe numbers are the evidence for it.

**The trap, and the rule that avoids it.** Running the sweep and then reporting
the best-performing frequency as "our fund" is look-ahead through the back door
— the choice used out-of-sample results that were not available at the start.
So: **the headline funds keep the frequency I chose ex ante, and the sweep is
reported beside them as a separate sensitivity study.** If the sweep says
another frequency is better, that is a finding to write up and a recommendation
for the critical reflection, not a licence to swap the headline result. Say this
explicitly in the report — naming the bias we avoided is worth more than the
extra Sharpe would have been.

The window length and rebalance frequency are **still undecided (as of
2026-08-06)** and are mine to choose — see "Parked at the gates". Propose
options with the trade-off (estimation error against staleness, and how many
out-of-sample days each choice leaves us), then wait. Do not hard-code a default
and report it as a decision.

Conventions:

- Author equations in the Word equation editor, numbered, punctuated as part of
  the sentence. *(repo rule — `.claude/rules/grammar-punctuation.md`)*
- Define every symbol in the text or in a notation table: what it is, its
  dimension, and its units. No symbol appears before it is defined.
- Notation stays consistent across all nine funds and the sentiment section —
  one set of symbols for the whole report.
- The equation in the report and the code in `src/` must agree. If they drift,
  the code is wrong until proven otherwise, and I am told.

## Innovation candidates — proposed 2026-08-06, not yet approved

Innovation is 30% of Part B *(brief:233)*. These are on the table. **None is
approved until I say so**, and each one that lands must earn its place against
the scope risk noted at the end.

### Long-short funds with a short budget

Relax the long-only constraint and allow short positions up to a stated budget —
the working proposal is **20% gross short, so weights sum to 1 with total shorts
capped at 0.20 (120% gross, 100% net)**.

- Applies to maximum-Sharpe and minimum-variance. Risk parity is defined on
  positive risk contributions and does not extend to shorts cleanly; say that
  rather than forcing it.
- Motivate the cap as more than a safety rail. Unconstrained tangency weights on
  a 50-asset sample covariance matrix are famously extreme; the short budget
  acts as a regulariser on estimation error, which is a stronger argument than
  "so it doesn't overdo it" and is testable — report the weight dispersion and
  effective N against the long-only version.
- **Shorting is not free and our data cannot see the cost.** State the
  assumption explicitly: no borrow cost and no locate constraint, and name the
  names where that is least believable. Shorting crypto in 2020–2023 at these
  sizes is the weakest assumption in the study — say so.
- **It conflicts with our target user, and that conflict is a report point.** A
  long-short fund is a hard sell to the first-timer who thinks investing is a
  scam. Label it as an advanced fund, keep it out of the default comparison
  view, and write up the tension rather than pretending it isn't there.

### A portfolio of portfolios (two-stage allocation)

Instead of optimising over all 60 assets at once, build the equity-only and
crypto-only funds first, then run a **second-stage optimiser over those two
return series** and compare against the one-stage combined fund.

This is the strongest idea of the three, because it asks a real methodological
question rather than adding another variant: the second stage estimates a 2×2
covariance instead of a 60×60 one, so it carries far less estimation error, but
it discards the cross-asset covariance structure that the one-stage fund uses.
Which effect wins out-of-sample is not obvious in advance, and either answer is
a result worth reporting.

- The comparison must be like-for-like: same estimation window, same rebalance
  rule, same method at both stages, same out-of-sample period. Only the
  one-stage-vs-two-stage structure moves.
- Crypto's volatility runs several times equity's, so report the realised
  sleeve weights — a two-stage risk parity across sleeves and a one-stage risk
  parity across assets can end up in very different places, and that gap is the
  finding.
- Report the parameter count behind each covariance estimate. It is the
  mechanism, and it is one line.
- If it earns its place, it becomes a fourth fund family, not a footnote.

### Objective and estimator extensions

Each of these changes the optimiser or its inputs, holding everything else
fixed. **Each one we adopt must be motivated in the report and shown
out-of-sample against the plain long-only version it replaces** — the exhibit is
the before-vs-after, not the method on its own.

- **Mean-CVaR (tail-aware objective).** Optimise against conditional
  value-at-risk — the mean of the worst tail of outcomes — instead of variance.
  Motivate it against our user: the first-timer fears the crash, not the wiggle,
  and CVaR targets exactly the left tail that variance treats symmetrically.
  State the confidence level (for example 95%) in the equation and define the
  tail. Crypto's fat left tail (Part A found excess kurtosis 18.6) is where this
  should separate from mean-variance, so report the two side by side on the
  crypto and combined funds.
- **Covariance shrinkage.** Replace the sample covariance with a shrinkage
  estimator (Ledoit-Wolf toward a structured target). This is the direct answer
  to the 50-asset conditioning problem behind the whole window-length trade-off:
  fewer extreme weights, lower turnover, usually better out-of-sample Sharpe.
  Report the shrinkage intensity chosen and the weight dispersion before and
  after. Strong, low-risk, and it strengthens every other fund, so it is a good
  first pick.
- **Volatility targeting.** Scale gross exposure up and down with recent
  realised risk so the fund holds a roughly constant volatility, levering down
  in turbulent periods. Motivate it against the drawdown story — it is the
  method that most directly attacks the max-drawdown number we now show on every
  fund. State the target volatility, the estimation window for realised risk,
  and the leverage cap, and keep the scaling signal lagged so it stays
  look-ahead safe. Follows Moreira and Muir (2017), "Volatility-Managed
  Portfolios". `[HUMAN EDIT REQUIRED: verify this citation — authors, year,
  journal, and that it supports volatility-scaling of risky-asset exposure —
  before it enters the report; see .claude/rules/latex-citations.md]`
- **Equal-weight / minimum-variance blend.** A convex combination of the 1/N
  portfolio and the minimum-variance portfolio, one mixing parameter. Motivate
  it as a bias-variance trade: 1/N carries no estimation error but ignores risk,
  minimum-variance uses the covariance but inherits its error. Report Sharpe
  across the mixing parameter and name the value chosen ex ante — the same
  do-not-pick-the-winner discipline as the frequency sweep applies.
- **Turnover / transaction-cost model.** Charge a cost per unit of weight traded
  at each rebalance and report net-of-cost performance. This is the shared
  backbone of the frequency study, the shrinkage claim, and the long-short fund
  — all three are really about whether the trading is worth it, and none is
  fully honest at zero cost. State the cost assumption (basis points per side)
  and its source of plausibility. Building it once serves every other exhibit.

### A benchmark and a fee model

Both make Revelatio read like a real product rather than a backtest, and both
are report exhibits with numbers, not app decoration.

- **A passive benchmark.** Every fund is plotted and scored against a passive
  index-style benchmark, and excess return over it is reported. Which benchmark
  is still my call (see "Parked at the gates") — the self-built equal-weight
  50-stock "market" is the honest default since it comes from our own data and
  shares our calendar; an external index appears at most once as validation,
  never inside the app. A fund that cannot beat 1/N after costs is itself a
  finding, and an honest one.
- **A fee schedule, charged in the backtest.** Set a realistic fee and subtract
  it from investor returns so every reported figure is net of fees:
  - an **annual management fee, at most 1%**, accrued daily across the
    out-of-sample period;
  - a **performance fee** on return above the benchmark (a high-water-mark
    style rule so the investor is not charged twice for the same gain).
  State both rates, write the accrual in the methodology, and show gross-vs-net
  on at least one fact sheet. The performance fee ties the fee to the benchmark,
  which ties the two ideas together. Keep the fee proportionate — the point is
  realism, and a fee that eats the whole excess return advertises a fund the
  user should not buy.

### Sentiment model extensions

Sentiment is where the lexicon work from Part A pays off, and a careful
extension here scores better than a broad one. **Each adopted extension is
motivated and shown out-of-sample** — for the index, that means its effect on
the fusion result, not the index in isolation.

- **Finance-lexicon extension (the expected strong route).** Extend VADER's
  lexicon with finance terms, have AI agents rate each candidate term's
  polarity, and **keep only the terms the raters agree on** — inter-rater
  agreement is the filter. This inherits Part A's `src/lexicon_terms.json` and
  its binary-polarity discipline. **Keep a full record in `ai/` of how each term
  was rated, by which agent, and where they disagreed** — the rating process is
  the innovation evidence, and it doubles as the AI-workflow mark. My review of
  the 89 existing polarities is a prerequisite (see "Parked at the gates").
- **A second model or an ensemble.** Swap in TextBlob (polarity and
  subjectivity) or blend it with VADER into an ensemble, and report where the
  two disagree — subjectivity gives a confidence axis VADER lacks. Justify the
  text handling either way: VADER needs casing, punctuation, and negation intact
  (do not strip them); state what TextBlob needs.
- **Sentiment decay on no-news days (my idea, 2026-08-11).** The core drops a
  ticker's sentiment to neutral the day its news stops (neutral = 0). This
  extension instead lets the last score **persist and decay toward neutral** over
  a chosen half-life, keeping its sign — yesterday's bad news still weighs on
  today, fading until the next headline resets it. It is the general case of
  which the core rule (instant decay) and pure carry-forward (no decay) are the
  two extremes, so the exhibit is a clean before-vs-after against the neutral-0
  baseline. Look-ahead safe (uses only past score and days-elapsed, behind the
  1-day lag). The half-life is the one tunable parameter — motivate it, and show
  its out-of-sample effect on the fusion, not on the index alone. Strong,
  testable, and the narrative writes itself.
- **Index granularity and smoothing.** Build the index at market, sector, and
  single-stock level, and test smoothing windows. The required exhibit stays the
  sector index *(brief:167)*; the extra granularities are the study around it.
  Report how smoothing trades responsiveness against noise. (The decay above is
  a per-ticker persistence rule; smoothing here is an index-level filter — they
  are different levers and can be studied together.)
- **Live-safe standardisation.** Standardise the index on an expanding window
  for a version that could run live (day *t* uses only data through *t*), and
  keep the full-sample standardisation for the historical view. State plainly
  which figure is which — the expanding-window version is the look-ahead-safe
  one, and conflating them is exactly the bias we guard against everywhere else.

### Scope, honestly — the governing rule

There are now enough candidates on this page to sink the project by breadth.
Long-short, two-stage, mean-CVaR, shrinkage, vol targeting, EW/min-var blend,
transaction costs, a benchmark, a fee model, and four sentiment extensions — on
top of nine funds, the frequency sweep, the fusion, and the app.

**The rule that governs all of it: a careful extension, built and tested and
shown out-of-sample, is worth more than several shallow ones.** *(brief:154 —
innovation rewards depth over count.)* Marks come from motivation plus evidence,
not from the length of the list. A dozen half-built variants score below three
that each carry an equation, a before-vs-after exhibit, and an honest read of
the result — including when the result is negative.

So every candidate here is off until I pick it, and I pick a short slate, not the
menu. **My working recommendation, for my decision:**

1. **Covariance shrinkage** — lowest risk, and it strengthens every fund at
   once, so it earns its place cheaply.
2. **The two-stage portfolio of portfolios** — it answers a real methodological
   question the others do not.
3. **The transaction-cost model** — it is the backbone the frequency study, the
   shrinkage claim, and any long-short fund all lean on, so one build serves
   several exhibits.
4. **The finance-lexicon extension** — the expected strong sentiment route, and
   its rating record doubles as AI-workflow evidence.

Everything else — long-short, mean-CVaR, vol targeting, the EW/min-var blend, the
ensemble, the benchmark-and-fee layer, the granularity and standardisation
studies — is a stretch to reach only if the slate above is finished and solid.
**Propose a cut before proposing a stretch**, and when in doubt, deepen a chosen
extension rather than add another.

## The app — minimum standard

The deployed Streamlit app is not done until a first-time user can do all four of
these **without help, without reading a manual, and without touching code**. This
is the acceptance floor for Station 4, checked before hand-in.

1. **Compare funds.** A performance-metrics table and a Sharpe (or return-vs-risk)
   chart across **every fund that exists**. The lineup is nine today; it reaches
   twelve only if the two-stage family is approved, so the compare view **renders
   whatever funds are present in the artifacts** — never a hard-coded count. If a
   fund is in `fund_returns.csv`, it appears here.
2. **Read a fact sheet.** For one chosen fund: growth of $1, the drawdown chart,
   and the current holdings. This is the floor; the fuller BlackRock-style page
   (Overview, Performance, Key Facts, Characteristics, Holdings, Exposures,
   Literature) is the target build above, and these three are the parts that must
   work on day one.
3. **Read the sentiment analytics.** The fear-and-greed gauge, the sector
   sentiment index over time, and the sentiment-tilt (fusion) before-vs-after
   result. The gauge is a plain-English reading of the same index a first-timer
   can grasp at a glance; the tilt results show whether folding sentiment into the
   equity funds helped, honestly, including when it did not.
4. **Build an allocation.** Sliders to blend funds into a personal portfolio,
   the fee applied, and the **net** growth of the blend shown back. The blend must
   respect the fee schedule so the number the user sees is what they would keep,
   not a gross figure.

Constraints on all four, non-negotiable:

- **Reads precomputed artifacts only.** The gauge, the indices, every fund curve,
  and the blend maths run off the committed CSVs in `results/`. No backtest, no
  VADER, no nltk, no data download at runtime — the free tier cannot, and
  commandment 5 forbids it. The blend is the one live computation allowed, and it
  is arithmetic over precomputed fund returns and weights, nothing heavier.
- **Every number on screen traces to a `results/` file** the same way a report
  number does. The app shows nothing it cannot source.
- **The four tasks stay reachable from every screen.** Compare, fact sheet,
  sentiment, and allocate are the whole product; none is buried.
- Loads fast on a basic machine, house design system throughout, plain language
  over jargon — this user thinks investing is a scam, and a confusing screen
  confirms it.

## The map

Code in `src/`, one reproducing script at `scripts/run_part_b.py`, outputs in
`results/tables|figures|data/`, the app at `streamlit_app.py` in the root, the
report in `report/` (Word source, PDF export), prompt logs in `ai/`.

Part A is reusable and should be reused — its ETL, return construction, headline
alignment, house figure style, and the finance lexicon in `src/lexicon_terms.json`
come across rather than being rebuilt. Say when something is carried over.

## The commandments — break none of them

*`brief:N` = PROJECT_BRIEF.md line N; "our rule" = a working discipline I keep by
choice.*

1. **No look-ahead, anywhere.** Weights come from data strictly before the
   rebalance date. Sentiment used for day *t* is from *t−1* or earlier — a
   Saturday or Monday headline, both aligned to Monday, is first tradeable on
   Tuesday. *(brief:148,151)*
2. **Returns within each panel first**, then crypto left-joined onto the equity
   trading calendar. Never merge price levels across calendars and difference
   after. *(brief:95,103 — carried from Part A)*
3. **The out-of-sample period starts after the estimation window**, not on the
   first date in the data. The initial window, the first live date, the
   rebalance rule, and the re-estimation cadence are stated in the report and
   on every fact sheet — see "The walk-forward design must be stated, not
   implied". No performance number ever includes a training-period day.
   *(brief:148)*
4. **Every panel ends at 2023-12-31.** No claim runs past it. *(brief:255)*
5. **The deployed app reads precomputed CSVs only.** No backtesting, no nltk,
   no VADER, no data download at runtime. `nltk` stays in
   `requirements-dev.txt`. *(brief:143,171)*
6. **The four filenames are exact**: `results/data/fund_returns.csv`,
   `results/data/fund_weights.csv`, `results/data/sector_sentiment_index.csv`,
   `results/tables/performance_metrics.csv`. *(brief:167)*
7. **Every number bound for the report or the app traces to a CSV in
   `results/`.** If the artifact does not exist, say so — an invented statistic
   is treason. *(our rule; `context/verify_ai_output.md`)*
8. **State assumptions in the open**: risk-free rate, transaction costs,
   rebalance frequency, constraints, and the treatment of ticker-days with no
   headlines. Each one is a sentence in the report, not a silent default.
   *(brief:148,151)*
9. On anything non-trivial, state your plan and its risks **before** writing
   code, so I can execute a bad plan at dawn instead of debugging it at dusk.
   *(our rule)*
10. Draft report prose only with `[YOUR INTERPRETATION: …]` stubs where the
    economic reasoning belongs — the reasoning is mine, and graded as mine.
    *(brief:202)*
11. Follow the writing rules in `.claude/rules/` for anything report-bound.
    *(our rule — repo convention)*
12. **Log every decision and milestone to `ai/`.** No step closes, and no
    decision is "made", until it is written to an `ai/prompt_log_<step>.md`
    following `ai/prompt_log_template.md` — what I wanted, the prompt(s), what
    the assistant produced, what was wrong or risky, and what I changed and why.
    A decision recorded only in `CLAUDE.md` is not logged; `CLAUDE.md` holds the
    *what*, the `ai/` log holds the *how and why we chose it*. This is the graded
    AI-workflow record (20% of the Part), so leave `[YOUR WORDS]` stubs where the
    reasoning is mine. Prompt me to log before moving on if I forget.
    *(our rule; `ai/README.md`)*

## Verification, before any step closes

- `scripts/run_part_b.py` reproduces every table, figure, and app artifact from
  a clean `results/`, and self-verifies the way Part A did: known counts printed
  beside their expected values, non-zero exit on drift.
- Every backtest gets one hand-check against the raw data — a weight vector
  recomputed by hand at one rebalance date, a portfolio return reconciled from
  weights and constituent returns, a sentiment score traced from one headline
  through to its sector index value on the day it becomes tradeable.
- A look-ahead probe per fund: shift the signal forward by one day and confirm
  performance changes in the direction it should. Silence is not proof.
- Every decision and meaningful exchange is logged in `ai/prompt_log_<step>.md`
  using `ai/prompt_log_template.md` (commandment 12): the prompt, what was
  produced, what was wrong, and the correction.

## Decided, and on the record

- **Design reference (2026-08-06, my call):** BlackRock fund pages, structure
  only, with the seven sections above. Cited in the report as an influence.
- **Report methodology (2026-08-06, my call):** equations written out, every
  parameter defined, notation consistent across the report.
- **Drawdowns on every fund (2026-08-06, my call):** a deliberate departure from
  the BlackRock reference, justified by the target user. Not optional.
- **Lexicon:** Part A's binary finance lexicon comes across and extends VADER.
  Two polarity classes only; context-dependent terms stay dropped.
- **Sentiment applies to equities only.** Crypto has no headline data.
  *(brief:152)*
- **Core backtest parameters (2026-08-11, Step 0, locked):** these five are the
  ex-ante choices the headline funds use.
  - Estimation window: **rolling 252 trading days** (~1 year), counted on the
    equity trading calendar — 252 observations *is* one year, no 365-day
    calendar and no forward-filling of equity prices (that would inject fake 0%
    weekend days and warp the covariance — the Part A merge-order trap).
  - Rebalance rule: **first trading day of each month** (~36 rebalances OOS).
  - Risk-free rate: **zero, stated.**
  - No-headline ticker-days: **neutral = 0** — the conservative anchor the decay
    extension improves on.
  - Sentiment lag: **1 trading day** (safe minimum; timestamps carry no intraday
    time).
  - Constraints: **long-only, fully invested** (weights ≥ 0, sum to 1);
    long-short is innovation.
  - Combined fund annualises with **252** (all its returns are on trading days).
  - Between-rebalance weights: **constant-weight to target** (daily return =
    wᵀr with the current month's target weights). Buy-and-hold drift and
    intra-month turnover accounting are deferred to the transaction-cost
    innovation. Decided 2026-08-11 (Step 2).

## Parked at the gates (do not assume — ask me)

- **The benchmark**: self-built from our own data (equal-weight 50-stock
  "market", equal-weight sector benchmarks) versus an external index — external
  at most once, as validation in the report, never in the app. This choice also
  fixes the reference for the performance fee, so it is decided before the fee
  model is coded.
- **The fee schedule**: the management fee rate (≤1%) and the performance-fee
  rule are mine to set. Propose realistic values; I choose.
- **The sentiment-model extension(s)**: lexicon extension, second model or
  ensemble, granularity/smoothing, live-safe standardisation. Depth over count —
  I pick a short slate.
- **Rebalance frequency**: locked at monthly for the headline funds (see
  "Decided"). The frequency *sweep* runs beside it as a sensitivity study, never
  as a substitution — that study is innovation.
- **Transaction costs**: zero-and-stated is acceptable; a turnover model counts
  as innovation and would strengthen the frequency study. My call, not yours.
- **Which innovation candidates run** — long-short with a short budget, the
  two-stage portfolio of portfolios, or both. See "Innovation candidates". Build
  nothing from that section until I approve it.
- **My review of the 89 polarities in `src/lexicon_terms.json`** is still
  outstanding and blocks the sentiment extension being claimed as innovation.

*The foundation is laid. Now the funds.*

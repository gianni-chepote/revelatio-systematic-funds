# Part B — Build Plan (core first, innovation last)

This is the order we build Part B in, one step at a time, with a proxy prompt for
each step you can paste to the assistant. **The core funds, sentiment, and report
come first (Steps 0–7); innovation is Step 8; the Streamlit app and the deploy
come last (Steps 9–10)** — the app is built once, at the end, so it renders the
final fund set (core plus whatever innovation lands) in a single pass rather than
being rebuilt after every extension.

Read `CLAUDE.md` and `PROJECT_BRIEF.md` Section 5 before starting. This file is
the sequence; `CLAUDE.md` is the standing rules.

## What "core" means here

The required minimum from the brief, and nothing beyond it:

- **Two funds**: a combined equity-plus-crypto fund under **two** methods —
  **minimum-variance** and **maximum-Sharpe (tangency)**. (Equity-only /
  crypto-only families and risk parity are innovation — Step 10.)
- Walk-forward **out-of-sample** backtest, no look-ahead, monthly-or-slower
  rebalance.
- A **fact sheet** per fund: growth of $1, annualised return, annualised
  volatility, Sharpe, maximum drawdown, current holdings.
- A **VADER sentiment model** → an equal-weight **sector sentiment index**,
  lagged at least one trading day.
- A **basic sentiment fusion** (equity fund, before-vs-after) — the brief calls a
  basic attempt "expected", so it is core, not innovation.
- The **Streamlit app**: compare funds, read a fact sheet, read the sentiment
  analytics, build an allocation.
- The **report** and the **deploy**.

The four filenames markers check, exact: `results/data/fund_returns.csv`,
`results/data/fund_weights.csv`, `results/data/sector_sentiment_index.csv`,
`results/tables/performance_metrics.csv`.

## Standing rules that apply to every step

- No look-ahead: weights from data strictly before the rebalance date; sentiment
  for day *t* from *t−1* or earlier.
- Every number traces to a CSV in `results/`. No invented statistics.
- The deployed app reads precomputed CSVs only — no backtest, no VADER, no nltk,
  no download at runtime.
- Reuse Part A where it fits; say when something is carried over.
- State the plan and its risks before writing code (CLAUDE.md commandment 9).
- Log every meaningful exchange in `ai/prompt_log_<step>.md`.

---

## Step 0 — Lock the core parameters (decide, don't code)

These are required backtest choices, not innovations, and everything downstream
depends on them. Decide and write them into `CLAUDE.md` before Step 2.

- Estimation window: length and type (rolling vs expanding).
- Rebalance rule: the calendar rule in words (e.g. first trading day of each
  month).
- Risk-free rate: assume zero and state it (allowed by the brief).
- No-headline ticker-days: drop, carry forward, or treat as neutral — and why.
- Sentiment lag: at least one trading day.

**Proxy prompt:**
> Before any backtest code, propose values for the five core parameters in
> BUILD_PLAN Step 0: estimation window length and type, rebalance rule,
> risk-free assumption, no-headline-day treatment, and sentiment lag. For each,
> give the trade-off in one or two sentences and a recommended default, then stop
> and let me choose. Remember the data is ~1,006 equity trading days,
> 2020-01-01 to 2023-12-31, and a 50-asset equity covariance is badly
> conditioned on a short window. Do not write code yet.

**Done when:** the five values are chosen and recorded in `CLAUDE.md`.

---

## Step 1 — Port the data foundation (return panels)

Reuse Part A's Station 1–2 so Part B has a clean return matrix. This is the spine
every fund stands on and depends on none of Step 0's choices.

**Produces:** `src/etl.py`, `src/features.py` (ported from Part A), and a full
combined return matrix written to `results/data/` (the whole panel, not a
sample).

**Proxy prompt:**
> Port `src/etl.py` and `src/features.py` from my Part A folder
> (`../z5736927_projectA/src/`) into this Part B folder, faithfully — this is
> reuse of my own work, which the brief allows. Then add a step to
> `scripts/run_part_b.py` that builds the full combined daily-return panel
> (date × ticker, equities plus crypto left-joined onto the equity calendar) and
> writes the entire panel to `results/data/combined_returns_panel.csv`, not just a
> sample. Self-verify the 1,006-row / count checks the way Part A's
> `run_part_a.py` does, and run it to confirm.

**Done when:** `run_part_b.py` reproduces the panel and the count self-check
passes.

---

## Step 2 — The backtest engine and the two optimisers

Build the walk-forward out-of-sample backtest and the two required methods on the
combined fund, using the Step 0 parameters.

**Produces:** `src/portfolios.py` filled in; `results/data/fund_returns.csv` and
`results/data/fund_weights.csv` for both funds.

**Proxy prompt:**
> Implement `src/portfolios.py`: a walk-forward out-of-sample backtest for the
> combined equity-plus-crypto fund under two methods, minimum-variance and
> maximum-Sharpe (tangency). Use the locked Step 0 parameters (window, rebalance
> rule, risk-free = 0). Enforce no look-ahead — weights at each rebalance use only
> returns strictly before that date. Handle the panel's NaN crypto cells
> explicitly (state the rule). Return, for each fund, the daily out-of-sample
> portfolio returns and the weights at each rebalance, and write them to
> `results/data/fund_returns.csv` and `results/data/fund_weights.csv` (exact
> names). Add a look-ahead probe: shift the signal forward one day and confirm
> performance changes as it should. Show me the plan and the NaN rule before
> coding.

**Done when:** both funds backtest, the two exact CSVs exist, and the look-ahead
probe behaves.

---

## Step 3 — Fact-sheet metrics and the fund figures

Turn the backtest output into the performance table and the required fund
figures.

**Produces:** `results/tables/performance_metrics.csv`; figures for growth of $1,
drawdown, weights-over-time, and a Sharpe barplot.

**Proxy prompt:**
> Add `performance_metrics` to `src/portfolios.py`: annualised return, annualised
> volatility, Sharpe (risk-free 0), and maximum drawdown, per fund, annualising
> with the correct factor. Write the table to
> `results/tables/performance_metrics.csv` (exact name). Then build the required
> figures from the committed artifacts using my Part A house style
> (`src/plot_style.py`): growth of $1 comparing the two methods, a drawdown
> figure for at least one fund, a weights-over-time figure for at least one fund,
> and a Sharpe barplot across funds. Each figure self-contained: title, axes,
> units, sample period.

**Done when:** `performance_metrics.csv` and all four figures reproduce from
`run_part_b.py`.

---

## Step 4 — The sentiment model and the sector index

Score the assembled headlines with VADER and build the equal-weight sector index,
lagged.

**Produces:** `src/sentiment.py` filled in;
`results/data/sector_sentiment_index.csv`; the sentiment time-series figure.

**Proxy prompt:**
> Implement `src/sentiment.py`. Reuse Part A's headline assembly
> (`features.assemble_headline_panel`). Score each headline with VADER (one-time
> `nltk.download('vader_lexicon')` as a build step — it must NOT run in the
> deployed app), aggregate to a per-ticker-day score, then to an equal-weight
> **sector** index across the ten sectors. Apply the Step 0 no-headline-day rule
> and the Step 0 lag (≥1 trading day). Do not strip casing, punctuation, or
> negation — VADER needs them. Write
> `results/data/sector_sentiment_index.csv` (exact name) and a sector sentiment
> time-series figure in the house style. Trace one headline through to its sector
> index value on the day it becomes tradeable as a hand-check.

**Done when:** the index CSV and figure reproduce, and the lag is verified (day
*t* uses only *t−1* or earlier).

---

## Step 5 — The basic sentiment fusion (before vs after)

Fold equity sentiment into the equity sleeve of a fund and report the effect
honestly. Basic is fine; a negative result explained is good work.

**Produces:** `src/fusion.py` filled in; a before-vs-after table and figure.

**Proxy prompt:**
> Implement `src/fusion.py`: a basic, look-ahead-safe sentiment tilt that nudges
> the equity weights toward higher-sentiment names using the lagged sector index,
> then re-run the backtest with the tilt on. Produce a before-vs-after comparison
> — base fund vs sentiment-augmented — as both a table and a figure, reporting
> whether it added value. Sentiment applies to equities only (crypto has no
> headlines). If it underperforms, say so plainly; do not tune it to win — tuning
> is Step 10.

**Done when:** the before-vs-after table and figure reproduce and the result is
stated honestly.

---

## Step 6 — Orchestrate and test

One command rebuilds everything; a smoke test guards the counts and the
no-look-ahead rules.

**Produces:** a complete `scripts/run_part_b.py`; `tests/` smoke checks;
`scripts/check_handin.py` passing.

**Proxy prompt:**
> Finish `scripts/run_part_b.py` so one run rebuilds every table, figure, and app
> artifact from a clean `results/`, printing each key count beside its expected
> value and exiting non-zero on drift (the Part A pattern). Add a smoke test in
> `tests/` covering: the four exact output filenames exist, the panel row count,
> the no-look-ahead probe, and that the sentiment index is lagged. Run
> `scripts/check_handin.py` and fix what it flags.

**Done when:** `run_part_b.py`, the smoke test, and `check_handin.py` all pass
from a clean `results/`.

---

## Step 7 — The report (core draft)

Author in Word, methodology carries its equations, every core exhibit
interpreted. Written now on the core results; Step 8 extends it with any
innovation exhibits.

**Produces:** `report/report.docx` (core draft) → `report/report.pdf` at the end.

**Proxy prompt:**
> Draft the Part B report in `report/report.docx` following `report/OUTLINE.md`
> and the writing rules in `.claude/rules/`. Cover the core results only for now
> (two combined funds, the sentiment index, the basic fusion) — innovation goes in
> after Step 8. Methodology must write out every equation (returns and
> annualisation, Sharpe, max drawdown, minimum-variance and maximum-Sharpe
> objectives with constraints, the covariance estimator and window, the sentiment
> aggregation and lag, the fusion rule) and define every symbol. State the
> walk-forward design in full: initial window, first live date, rebalance rule,
> counts. Reference and interpret every required exhibit. Leave
> `[YOUR INTERPRETATION: …]` stubs where the economic reasoning is mine. Do not
> invent citations.

**Done when:** the core draft holds every required exhibit and every equation is
defined. (PDF export waits until after Step 8 so innovation is included.)

---

## Step 8 — Innovation

Only after Steps 0–7 are working and tested. The candidates and the recommended
slate live in `CLAUDE.md` → "Innovation candidates"; each one adopted must be
motivated and shown out-of-sample, and the report is extended to cover it. A
careful extension beats several shallow ones.

**Produces:** the chosen extensions (extra funds/methods, sentiment extension,
etc.), their exhibits, and the report sections that interpret them.

**Proxy prompt:**
> We are starting the innovation phase. From the CLAUDE.md "Innovation candidates"
> list, here is the slate I have chosen: [FILL IN]. For each, remind me of its
> motivation, implement it against the same no-look-ahead and exact-filename
> rules as the core, show its out-of-sample before-vs-after effect, and add the
> exhibit and the interpreting section to `report/report.docx`. Build them one at
> a time and stop after each so I can check it. Do not touch the app yet.

**Done when:** each chosen extension is built, shown out-of-sample, and written up;
the report now covers core plus innovation.

---

## Step 9 — The Streamlit app (minimum standard)

Built last, once, so it renders the final fund set — core plus whatever
innovation landed. Reads precomputed artifacts only.

**Produces:** `streamlit_app.py` and `.streamlit/` meeting the CLAUDE.md app
acceptance floor.

**Proxy prompt:**
> Build `streamlit_app.py` to the CLAUDE.md app minimum standard, reading only the
> committed CSVs in `results/` — no backtest, no VADER, no nltk, no download at
> runtime. Four tasks a first-timer can do without help: (1) compare funds — a
> metrics table and a Sharpe chart across whatever funds exist in the artifacts
> (core plus any innovation funds); (2) read a fact sheet — growth, drawdown,
> current holdings for a chosen fund; (3) read the sentiment analytics — the
> sector index over time and the before-vs-after fusion result; (4) build an
> allocation — sliders to blend funds and see the net growth of the blend. Use my
> house design system, plain language, and keep it light. Confirm it runs with
> `streamlit run streamlit_app.py`.

**Done when:** all four tasks work locally and the app reads only precomputed
files.

---

## Step 10 — Deploy and hand in

Export the final report PDF (now including innovation), then deploy.

**Proxy prompt:**
> Export `report/report.pdf` from the finished Word report. Then run
> `scripts/check_handin.py`, confirm the committed `results/` artifacts are
> present, and prepare the repo for deploy: git init here, commit, and get it
> ready to push to a new private GitHub repo with `streamlit_app.py` at the root.
> Walk me through the browser steps I must do myself (push auth, connecting the
> repo on share.streamlit.io, making it public at hand-in). Do not attempt the
> browser deploy.

**Done when:** the PDF is exported, the repo is pushed, the app is live, and the
checklist in `SUBMISSION_CHECKLIST.md` is fully ticked.

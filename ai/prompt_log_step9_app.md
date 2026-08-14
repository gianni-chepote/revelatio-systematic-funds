# Prompt log - Step 9: the Streamlit app

## What I wanted

The app to the CLAUDE.md minimum standard: a first-time investor can, without help,
(1) compare funds, (2) read a per-fund fact sheet, (3) read the sentiment analytics,
and (4) build an allocation - reading precomputed results/ artifacts only, no
backtest, no sentiment scoring, no download at runtime.

## Prompt

- "build the app"

## What the assistant produced

- `streamlit_app.py` (root entrypoint, per this project's convention) with four
  tabs, Plotly charts in the Revelatio palette, reading only results/ CSVs:
  - **Compare**: performance table for all four app funds plus a market row, a
    return-vs-risk scatter, and the "N of 4 beat the market" headline.
  - **Fact sheet**: a fund picker that works for EVERY fund (fixes the earlier gap
    where weights-over-time existed only for MaxSharpe) - metric cards, growth vs
    market, drawdown, and current holdings from the latest rebalance.
  - **Sentiment**: a fear-and-greed gauge (plain-English reading of the sector
    index), the sector index over time, and the fusion before-vs-after bars.
  - **Allocate**: fund-blend sliders + a stated management fee, showing net growth.
- `plotly>=5.20` added to requirements.txt.
- `tests/test_app_smoke.py` using streamlit.testing.v1.AppTest - drives every tab,
  switches the fact-sheet fund, and moves an allocation slider (4 tests pass).

## Decisions and what was risky

- **The management fee.** The app floor requires a NET-of-fee blend, but the full
  fee-model innovation was never built (it is reserve). I added a simple, stated
  flat management fee (default 0.75%/yr, capped at 1%, accrued daily) as arithmetic
  over precomputed returns - enough to satisfy the floor honestly, labelled on
  screen as a simple management fee, not a performance fee. [YOUR INTERPRETATION:
  the fee rate is yours to set.]
- **Root entrypoint, not app/.** `tools/workflow.py check-app-submission` expects
  `app/streamlit_app.py`, but this project's own `check_handin.py`, STUDENT_DEPLOY,
  and CLAUDE.md all use `streamlit_app.py` at the folder root. check_handin passes;
  the generic tool's "blocking issues" (app/ path, unclean tree) are about the
  monorepo context and resolve at Step 10 when prepare-app-repo builds the
  standalone deploy repo with the root entrypoint.
- **False nltk warning.** check_handin greps the literal "nltk"; my docstring said
  "no nltk". Reworded so the app text has zero nltk references - the app imports
  neither nltk nor VADER.

## Verification

| Check | Result |
|---|---|
| app runs headless (AppTest) | 4 app smoke tests pass |
| every tab renders, no exception | yes (compare/factsheet/sentiment/allocate) |
| fact sheet works for all 4 funds | yes (picker + per-fund holdings) |
| reads results/ only | yes - no data_access, no nltk, no download |
| full test suite | 17 passed |
| check_handin.py | 22 passed |

## Screenshots captured (2026-08-14)

Launched the app locally and drove Chrome to capture all four tabs into
`results/app/`: 01_home, 02_compare_funds, 03_fact_sheet, 04_fact_sheet_holdings,
05_market_sentiment, 06_build_allocation (.jpg). Ready to drop into report
Section 7 in Word, or re-capture from the live URL after deploy.

## Still to do

- Step 10: export report.pdf, then prepare-app-repo + browser deploy on
  share.streamlit.io (Gianni's own GitHub/Streamlit login).

[YOUR WORDS: my read of the app before deploy.]

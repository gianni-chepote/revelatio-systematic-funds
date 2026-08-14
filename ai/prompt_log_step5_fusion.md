# Prompt log - Step 5: sentiment fusion (before vs after)

*Milestone: fold equity sentiment into the funds and report the before-vs-after
effect - the last core step. `[YOUR WORDS]` marks where I add my own words.*

## What I wanted

A basic, look-ahead-safe sentiment tilt on the equity sleeve of each combined
fund, and an honest before-vs-after comparison (table and figure), per the brief
(a naive attempt that underperforms is acceptable as the baseline).

## Prompt(s)

- "Run Step 5."

## What the assistant produced

- Added a general `weight_fn` hook to `portfolios.oos_backtest` (keeps the
  sentiment logic out of the optimiser).
- `src/fusion.py`: `build_sentiment_tilt` - at each rebalance, each equity name
  takes its sector's trailing 21-day sentiment (read strictly before the
  rebalance date, so lag >= 1 day), cross-sectionally z-scored, weight multiplied
  by max(0, 1 + 0.5*z), equity sleeve renormalised to its original total, crypto
  untouched.
- Wired Step 5 into `scripts/run_part_b.py`: `results/tables/fusion_comparison.csv`
  and a base-vs-tilted growth figure for the fund whose Sharpe moved most.

## What was wrong or risky

- **The tilt made both funds worse - and that is the honest, expected result.**
  MinVariance Sharpe 0.49 -> 0.31, MaxSharpe 1.03 -> 0.91. Step 4 already showed
  VADER headline sentiment is weak and sticky (barely moved through a -26%
  selloff), so a naive tilt on it adds noise, not signal. The brief treats a
  losing baseline as fine; tuning it (better signal, tuned lambda, a sentiment
  factor) is where innovation marks are, and that is Step 8.
  [YOUR WORDS: my economic reading of why sentiment hurt here.]
- **A nuance worth reporting:** MaxSharpe's max drawdown IMPROVED under the tilt
  (-26.3% -> -22.8%) even as return fell - the tilt shed some risk with the
  return, it did not only destroy value.
- **Parameters are fixed and untuned** (lambda=0.5, 21-day window) and stated on
  the figure and in the table, so the result is not mistaken for a tuned one.

## What I changed and why

- Kept the basic tilt as the core baseline; deferred tuning to innovation.
- Titled the figure with the computed Sharpe change so the claim matches the data.

**Verification performed (this run):**

| Check | Result |
|---|---|
| fusion_comparison.csv + figure written | yes |
| tilted weights sum to 1, no shorts | True |
| crypto sleeve unchanged by the tilt (equity-only) | base 0.0104 = tilted 0.0104 |
| look-ahead: future-shifted sentiment changes the series | True (uses only pre-rebalance data) |
| figure title matches the computed Sharpe change | yes |

*Result: MinVariance Sharpe 0.49->0.31 ($1.18->$1.10); MaxSharpe 1.03->0.91,
maxDD -26.3%->-22.8%. An honest negative baseline.*

[YOUR WORDS: what this tells me to try in the innovation phase to make sentiment pay.]

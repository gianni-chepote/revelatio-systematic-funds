# Prompt log - Step 2: walk-forward backtest + two optimisers

*Milestone: build the two core combined funds (minimum-variance, maximum-Sharpe)
and their out-of-sample backtest. `[YOUR WORDS]` marks where I add my own words.*

## What I wanted

Two long-only combined equity-plus-crypto funds - minimum-variance and
maximum-Sharpe - backtested walk-forward with no look-ahead, using the Step 0
parameters, producing `fund_returns.csv` and `fund_weights.csv`.

## Prompt(s)

- "Run Step 2." (The assistant first presented the design, the equations, and the
  NaN rule for approval, per commandment 9.)
- Clarifying exchange: long-only vs long-short, and the short cap -> confirmed
  long-only is core (Step 0), the ~20% short budget is a Step 8 innovation, not
  relevant now.
- Clarifying exchange on the one open choice - between-rebalance weight behaviour
  - resolved to constant-weight to target.
- "Lock constant-weight to target and start coding Step 2."

## What the assistant produced

- `src/portfolios.py`: `_min_variance_weights` and `_max_sharpe_weights` (SLSQP,
  long-only `w>=0`, fully invested `sum(w)=1`), `optimize_weights` (with the NaN
  safety net), `rebalance_dates` (first trading day of each month), `oos_backtest`
  (rolling 252-day window, constant-weight to target, a `peek` arg for the probe),
  `performance_metrics`, and `lookahead_probe`.
- Wired Step 2 into `scripts/run_part_b.py`: writes `fund_returns.csv` (wide) and
  `fund_weights.csv` (tidy long), runs the look-ahead probe, and self-checks that
  weights sum to 1 with no shorts.

## What was wrong or risky

- **`match=False` on the first hand-check looked like a bug; it was rounding.**
  Recomputing the fund return from the 6-dp weights in `fund_weights.csv` differed
  from the stored full-precision return by 4.3e-8. Re-checking with the
  unrounded weights gave an EXACT match, proving the backtest logic is right and
  the tiny gap is only the artifact's display rounding. [YOUR WORDS: my take.]
- **Max-Sharpe is non-convex and solved from a single start** - a local optimum
  is possible. Acceptable for core under long-only; the estimation-error fix
  (covariance shrinkage / multi-start) is innovation, not core. Flagged.
- **Thin obs:asset ratio (252:60)** noted as a known weakness the long-only
  constraint absorbs.
- No look-ahead: the probe (shift the window one day into the future) confirmed
  the honest and peeking return series differ, so weights genuinely use only
  past data.

## What I changed and why

- Locked **constant-weight to target** between rebalances (recorded in CLAUDE.md).
- Rounded the weights artifact to 6 dp for a clean file, accepting the ~1e-8
  reconstruction gap (documented, not a bug).

**Verification performed (this run):**

| Check | Result |
|---|---|
| first live date / rebalances / OOS days | 2021-01-04 / 36 / 753 |
| OOS period | 2021-01-04 to 2023-12-29 |
| weights sum to 1 (all rebalances, both funds) | True |
| no short weights | True |
| look-ahead probe (series differ when peeking) | True |
| hand-check MinVar return, full-precision weights | exact match (<1e-12) |
| hand-check via 6-dp CSV weights | delta 4.3e-8 (rounding floor) |
| MinVar first-rebalance holdings | 11 names, 0 crypto, top-5 = 73.7% (defensive tilt, sensible) |

*Preview metrics (official table is Step 3): MinVariance ann 6.3% / vol 12.8% /
Sharpe 0.49 / maxDD -15.6%; MaxSharpe ann 25.5% / vol 24.7% / Sharpe 1.03 /
maxDD -26.3%.*

[YOUR WORDS: whether the fund behaviour matches what I expected economically.]

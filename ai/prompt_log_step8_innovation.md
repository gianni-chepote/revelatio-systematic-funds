# Prompt log - Step 8: innovation

Slate locked 2026-08-13 (depth over breadth): **(1) covariance shrinkage,
(2) two-stage portfolio-of-portfolios, (3) sentiment decay on no-news days.**
Built one at a time, stopping after each. `[YOUR INTERPRETATION]` marks the
economic reasoning graded as mine.

## Step 8a - covariance shrinkage (Ledoit-Wolf)

### What I wanted

Replace the 60x60 sample covariance with a Ledoit-Wolf shrinkage estimator and
show the effect out-of-sample as an honest before-vs-after, without touching the
two core funds or the four marker files. Report the shrinkage intensity and the
change in weight dispersion - the mechanism - not just the Sharpe.

### Decisions I made (assistant proposed, I chose)

- **Shrink target: sklearn identity target**, not a hand-coded constant-correlation
  target. delta is estimated analytically per window, so there is no tuned
  parameter, and it is library code I do not have to re-verify. The
  constant-correlation target is a stretch to add later, not a starting point.
- **Report-only exhibit**, not extra app funds. Shrinkage is an estimator swap
  that strengthens the funds I have; it was never meant to add to the app lineup
  (CLAUDE.md: the app "reaches twelve only if the two-stage family is approved").
  Keeping it report-only leaves the core funds, the four marker files, and the
  frozen smoke-test fund assertion untouched.

### Prompt(s)

- "lock in shrinkage, two-stage, and decay - start with shrinkage"
- Plan-first: I made the assistant state the plan and its risks before any code.

### What the assistant produced

- A backwards-compatible `cov_estimator` hook on `portfolios.optimize_weights`
  and `oos_backtest` (default `None` -> sample covariance, so the core path is
  byte-for-byte unchanged - verified: core Sharpes still 0.49 / 1.03).
- `src/shrinkage.py`: a `LedoitWolfEstimator` that records each window's delta,
  and `run_shrinkage(panel)` that backtests both methods sample-vs-shrunk and
  assembles the comparison, the weight diagnostics, and the shrunk return panel.
- `run_part_b.py` Step 8a block writing `shrinkage_comparison.csv`,
  `shrinkage_diagnostics.csv`, `shrinkage_fund_returns.csv`, and two house-style
  figures (before-vs-after growth; effective-N dispersion). Self-check gates delta
  in (0, 1].
- A `test_shrinkage_exhibit` smoke test (10 pass, was 9).

### The result (out of sample, 2021-01-04 to 2023-12-29)

| Fund | Sharpe sample -> shrunk | maxDD | effective N | turnover | mean delta |
|---|---|---|---|---|---|
| MinVariance | 0.49 -> **0.55** | -15.6% (flat) | 9.8 -> **12.7** | 15.2% -> **12.8%** | 0.05 |
| MaxSharpe | 1.03 -> 1.01 | -26.3% -> **-25.2%** | 4.3 -> 5.2 | 33.7% -> 32.6% | 0.05 |

The mechanism showed cleanly: shrinkage raised effective N and cut turnover for
both funds. As predicted, min-variance (a pure covariance play) improved on
Sharpe; max-Sharpe barely moved because its noisy sample MEAN, which we do not
shrink, drives the tangency solve - it did shave the drawdown, though.

### What was wrong or risky

- **We shrink covariance only, not the mean.** This is the candidate's spec and
  standard, and it is exactly why max-Sharpe barely moved. Reported straight, not
  hidden. [YOUR INTERPRETATION: whether the modest, honest gain is worth adding
  shrinkage to the fund, and to which fund it matters.]
- **delta is small (~0.05).** On this window the sample covariance is not as
  ill-conditioned as feared, so the estimator only leans lightly on the target.
  That is the estimator working as intended, not a bug - but it caps how large the
  effect can be. [YOUR INTERPRETATION: read on why delta is small here.]
- sklearn LedoitWolf normalises by n (MLE), the sample cov by n-1; immaterial
  next to the shrinkage, noted in the methodology.

### Verification performed (this run)

| Check | Result |
|---|---|
| core funds unchanged | MinVar 0.49, MaxSharpe 1.03 identical to Step 3 |
| shrinkage delta in (0, 1] | 0.05 both methods, gated in run_part_b |
| dispersion mechanism | effective N up, turnover down, both funds |
| smoke tests | 10 passed |
| check_handin.py | 22 passed |

[YOUR WORDS: my read of the shrinkage result before it goes in the report.]

## Step 8b - two-stage portfolio of portfolios

### What I wanted

Build the equity-only and crypto-only funds first, then allocate across those two
sleeves, and compare the two-stage fund against the one-stage combined fund
like-for-like. The mechanism to report is the estimation-error trade: one 60x60
covariance (1,830 params) versus a 2x2 across sleeves (3 params), against the loss
of the equity-crypto cross-covariance the one-stage fund uses.

### Decision I made

- **Two-stage funds go INTO the core files** (fund_returns / fund_weights /
  performance_metrics expand to four funds), not into parallel files. This is the
  one extension that earns a real fund family in the app, so I updated the frozen
  smoke-test fund set deliberately - CORE_FUNDS (2) for fusion, FUNDS (4) for the
  fund files. The core FIGURES (growth, drawdown, weights) stay on the two
  combined funds for legibility; the Sharpe barplot spans all four.

### What the assistant produced

- A `weights_builder` hook on `oos_backtest` (default `None` -> single-stage, core
  unchanged), plus `src/two_stage.py`: per rebalance, stage-1 equity-only (50) and
  crypto-only (10) solves, a synthetic sleeve return series, a stage-2 2x2 solve,
  combined into a 60-asset long-only weight. Same window, rebalance, method, and
  OOS period as the one-stage funds.
- `two_stage_comparison.csv` and two figures (one-stage vs two-stage growth;
  realised equity-sleeve share). Self-checks: two-stage funds present, cross-asset
  cov is 3 params. Smoke test 10 -> 11.

### The result (out of sample, 2021-01-04 to 2023-12-29)

| Method | Sharpe one-stage -> two-stage | Two-stage crypto share (mean / max) |
|---|---|---|
| MinVariance | 0.49 -> **0.50** | 0.3% / 2.3% |
| MaxSharpe | 1.03 -> **0.98** | 9.5% / 65.6% |

Two-stage **matched** one-stage on minimum-variance and **trailed slightly** on
maximum-Sharpe. The cross-asset covariance the one-stage fund keeps is worth a
little to max-Sharpe and nothing to min-variance here - a clean either-way result,
not a win to trumpet. The sleeve figure shows why: min-variance sits ~99.7% in
equities (crypto's volatility prices it out), while max-Sharpe swings up to 66%
crypto when chasing return.

### What was wrong or risky

- **First figure headline over-claimed** "crypto only a sliver" - true for
  min-variance, false for max-Sharpe (up to 66%). Checked the realised shares and
  rewrote the headline to state both funds honestly. The habit: measure the claim
  against the output before writing it.
- **Synthetic sleeve series uses end-of-window stage-1 weights across the window**
  (assumes current sleeve composition to price sleeve risk). Strictly in-window,
  no look-ahead; stated in the methodology.
- [YOUR INTERPRETATION: whether "two-stage roughly ties one-stage" is the finding
  you want to lead with, and what the small max-Sharpe gap says about cross-asset
  covariance being mostly noise on this sample.]

### Verification performed (this run)

| Check | Result |
|---|---|
| like-for-like OOS period | two-stage first live date = one-stage (both 2021-01-04) |
| core funds unchanged | MinVar 0.49, MaxSharpe 1.03 identical |
| weights sum to 1 / no shorts | True across all 4 funds |
| cross-asset cov params | 3 (two-stage) vs 1,830 (one-stage) |
| smoke tests | 11 passed |
| check_handin.py | 22 passed |

[YOUR WORDS: my read of the two-stage result before it goes in the report.]

## Step 8c - sentiment decay on no-news days

### What I wanted

The core rule snaps a ticker's sentiment to 0 the day its news stops. This
extension carries the last score forward and decays it toward 0 over a half-life,
keeping its sign - the general case of which instant-decay (core) and pure
carry-forward are the two extremes. The exhibit is the effect on the FUSION, not
the index, as a before-vs-after against the neutral-0 baseline, plus a half-life
sweep so nothing is tuned to win.

### Decision I made

- **Half-life = 5 trading days (~1 week)**, chosen ex ante for the economic reason
  (a headline's grip on trading fades over about a week), not picked from the
  sweep. It is also fast relative to the fusion's 21-day trailing window, so the
  decay's effect is attributable rather than stacking two slow filters. Sweep
  {2, 5, 10, 21} reported for sensitivity.

### What the assistant produced

- `sentiment.sector_sentiment_index_decay` (per-ticker forward-fill-with-decay via
  `_decay_fill`, then the same sector aggregation) and `ticker_decay_example` for
  the mechanism figure. Look-ahead safe: each value uses only a past score and
  trading days elapsed, behind the existing >=1-day fusion lag.
- `run_part_b` Step 8c block: `sector_sentiment_index_decay.csv`,
  `decay_comparison.csv` (base / neutral-0 / decay per fund), `decay_halflife_sweep.csv`,
  and two figures (the mechanism on ticker MMM; the fusion before-vs-after).
  Smoke test 11 -> 12.

### The result (out of sample, half-life 5d)

| Fund | Sharpe base / neutral-0 / decay |
|---|---|
| MinVariance | 0.49 / 0.31 / **0.33** |
| MaxSharpe | 1.03 / 0.91 / **0.93** |

Sweep (Sharpe): MaxSharpe 0.92 / 0.93 / 0.94 / 0.94 across half-lives 2/5/10/21;
MinVariance flat at 0.31-0.33. The honest read: the sentiment tilt destroys value
on this sample, and **decay softens the damage a little but does not rescue it** -
persisting a fading signal is less noisy than snapping to zero, yet sentiment
still does not add value here. Longer half-lives help max-Sharpe marginally,
reported as sensitivity, not chosen after the fact.

### What was wrong or risky

- The gain is small (+0.02 Sharpe) and could read as noise. It is presented as
  "less bad", not a win. [YOUR INTERPRETATION: whether the decay's small,
  consistent softening is a real effect worth keeping, and what it says about news
  half-life on this corpus.]
- Decay is look-ahead safe by construction; I confirmed it uses only past scores.

### Verification performed (this run)

| Check | Result |
|---|---|
| decayed index in [-1, 1], 10 sectors | yes |
| variants present | base, sentiment_neutral0, sentiment_decay |
| sweep half-lives | {2, 5, 10, 21} |
| core funds / fusion unchanged | yes (decay is a separate index + tilt) |
| smoke tests | 12 passed |
| check_handin.py | 22 passed |

[YOUR WORDS: my read of the decay result before it goes in the report.]

## Step 8d - passive benchmark (equal-weight 50-stock market)

### What I wanted

A same-universe passive baseline so the funds' absolute Sharpes mean something.
Equal-weight 50-stock "market", reset to 1/N on the funds' monthly schedule and
over the same OOS window, from our own data. Every fund scored on excess return
and Sharpe gap; the market drawn on the growth and Sharpe figures. External
indices (S&P 500) are report-only, at most once, never in the app.

### The result (out of sample, 2021-01-04 to 2023-12-29)

Benchmark EW-50: annRet 13.2%, Sharpe **0.82**, maxDD -20.3%.

| Fund | Excess ann return | Sharpe - market | Beats market? |
|---|---|---|---|
| MinVariance | -6.9% | -0.33 | **No** |
| MaxSharpe | +12.3% | +0.22 | Yes |
| TwoStage_MinVariance | -6.9% | -0.32 | **No** |
| TwoStage_MaxSharpe | +11.0% | +0.17 | Yes |

**Only 2 of 4 funds beat simply owning the equal-weight market**, and this is the
headline honesty of the whole project: the minimum-variance funds do NOT beat
1/N - a real, reportable finding. The equal-weight 50-stock market at Sharpe 0.82
is a strong bar because the universe did well over 2021-2023; that is also why an
S&P 500 comparison (~8%/yr) would flatter the funds and is the wrong yardstick.

### Note on the S&P 500

Gianni guessed the S&P would show the funds as underperformers; measured against
the same-universe EW-50 it is the opposite for max-Sharpe. The honest comparison
is the same universe, not a broad equity index we do not hold. [YOUR INTERPRETATION:
whether to include the S&P once as external context, and how to frame min-variance
losing to 1/N.]

### Verification

| Check | Result |
|---|---|
| benchmark aligns with funds | 753 OOS days, same first live date |
| every app fund scored | 4 rows, excess + Sharpe gap + beats flag |
| figures carry the market | growth (dashed EW-50) + Sharpe bar (reference line) |
| smoke tests | 13 passed |
| check_handin.py | 22 passed |

---

## Step 8 status

All three approved extensions built, tested, and shown out-of-sample: shrinkage
(8a), two-stage (8b), decay (8c). 12 smoke tests, check_handin 22 passed. Next:
write the three innovation sections into report/report.docx in one pass, then the
app (Step 9) and deploy (Step 10).

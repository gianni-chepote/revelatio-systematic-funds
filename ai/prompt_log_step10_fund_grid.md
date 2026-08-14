# Prompt log - HD funds upgrade: single-asset families + risk parity

## Why

The Part B "Funds" criterion (15%) HD band asks for **equity-only, crypto-only AND
combined funds across several methods**. The build had combined funds only, across
two methods - solid C/D, not HD. This closes that gap.

## What I wanted

Expand to a full grid: three families (equity-only, crypto-only, combined) x three
methods (minimum-variance, maximum-Sharpe, and a new third method, risk parity) =
nine funds, plus the two two-stage funds = eleven. Keep the pipeline green, keep
fusion/shrinkage scoped to the two combined core funds so the core narrative is
unchanged, and reflect the offering in the report and the app.

## What the assistant produced

- `src/portfolios.py`: `_risk_parity_weights` (Spinu 2013 convex log-barrier ERC
  solve), wired into `optimize_weights`; `ALL_METHODS` and `METHOD_LABEL` so the
  grid names funds `{Family}_{Method}`. `oos_backtest` now names funds via a safe
  fallback (run_part_b overrides per family/method).
- `scripts/run_part_b.py`: Step 2 rebuilt as a family x method grid over restricted
  column sets (`panel[equity_cols]`, `panel[crypto_cols]`, all 60). The growth
  figure now compares the three combined methods; the Sharpe barplot spans all 11,
  coloured by family, against the market.
- `scripts/build_report.py`: Table 1 shows all 11 with readable labels; the risk-
  parity equation added to the methodology (12 equations); §3 describes the grid
  and the combined-beats-single-asset / crypto high-return-low-Sharpe patterns.
- `streamlit_app.py`: fund metadata generated for the grid + hand-written flagships;
  Funds page groups cards by family; the blender uses the three multi-asset funds.
- Smoke tests updated for the 11-fund set (13 core + 8 app = 21 pass).

## What was right or risky

- **The two combined core funds are byte-for-byte unchanged** (MinVar 0.49,
  MaxSharpe 1.03) - verified. Building the combined family on a reordered column
  set gives identical optimisation results.
- **Risk parity checks out**: weights sum to 1, no shorts, risk contributions equal
  (0.20 each on a 5-asset test). As a combined fund it earns Sharpe 0.90 and beats
  the market - a genuine third method, not filler.
- **The results tell an honest story**: crypto-only funds post the highest raw
  returns (up to 33%/yr) but the worst risk-adjusted ones (crypto max-Sharpe went
  to -0.20 Sharpe, -91% drawdown); combining lifts every method's Sharpe. That is
  the diversification case, shown not asserted.
- Fusion and shrinkage stay on the two combined core funds by design, so those
  exhibits and the baked interpretations did not change.

## Verification

| Check | Result |
|---|---|
| funds built | 11 (3 families x 3 methods + 2 two-stage) |
| combined core unchanged | MinVar 0.49, MaxSharpe 1.03 |
| risk parity valid | sum 1, no shorts, equal risk contributions |
| smoke tests | 21 passed |
| check_handin.py | 22 passed |

[YOUR WORDS: my read of the wider fund grid before it goes in the report.]

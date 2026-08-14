# Prompt log - Step 3: fact-sheet metrics + fund figures

*Milestone: turn the backtest output into the performance table and the four
required fund figures. `[YOUR WORDS]` marks where I add my own words.*

## What I wanted

The fact-sheet numbers and the required exhibits: a performance-metrics table
(annualised return, volatility, Sharpe, max drawdown) and four figures - growth
of $1, drawdown, weights over time, and a Sharpe barplot - in my Part A house
style.

## Prompt(s)

- "Run Step 3."

## What the assistant produced

- Vendored `src/plot_style.py` from Part A, made SELF-CONTAINED: the fintools
  figure-spec and rcParams values are inlined so the standalone Part B repo has no
  external dependency (extracted the exact numbers from fintools first so the look
  is unchanged).
- Wrote `results/tables/performance_metrics.csv` (exact name) from the Step 2
  metrics.
- Added four figure builders to `scripts/run_part_b.py`: growth of $1, drawdown,
  weights-over-time (MaxSharpe), and a Sharpe barplot.

## What was wrong or risky

- **plot_style imported fintools, which the standalone repo would not have.** Part
  A ran inside fins-agent where fintools exists; Part B is its own deployable repo
  and fintools is not in its requirements. Caught before shipping and vendored a
  self-contained copy. [YOUR WORDS: why a standalone repo matters for hand-in.]
- **The weights stackplot reused colours** - nine bands overran the restrained
  house palette, so BTC-USD/OXY were both gold and NVDA/Other both grey,
  indistinguishable. Caught by LOOKING at the rendered figure, not just trusting
  the file existed. Fixed by capping at six named holdings + "Other" with six
  distinct colours.
- **Drawdown title double-negative** ("fell -26%"). Fixed to "fell 26%" with an
  absolute value; the on-chart labels still show the signed drawdown.

## What I changed and why

- Kept the vendored, dependency-free plot_style.
- Reduced the weights figure to top-6 + Other for legibility.
- Reviewed all four figures by eye before accepting them.

**Verification performed (this run):**

| Check | Result |
|---|---|
| performance_metrics.csv written (exact name) | yes |
| 4 figures written and visually inspected | growth, drawdown, weights, Sharpe |
| house style intact (parchment, gilt accent, captions) | yes |
| figure titles are computed assertions, not hard-coded | yes |
| every figure band/series distinguishable | yes (after colour fix) |

*Fact-sheet metrics (OOS 2021-01-04 to 2023-12-29): MinVariance ann 6.3% / vol
12.8% / Sharpe 0.49 / maxDD -15.6%; MaxSharpe ann 25.5% / vol 24.7% / Sharpe 1.03
/ maxDD -26.3%. $1 grew to $1.18 (MinVariance) and $1.96 (MaxSharpe).*

[YOUR WORDS: what the growth/drawdown contrast says about the two funds for my user.]

## Addendum - figure refinement pass (my design review)

After first render I reviewed the figures and directed several house-style
changes (all applied in `plot_style.py` and the figure builders):

- Vertical gridlines removed house-wide (horizontal only).
- Source note dropped from the plot; the sample period moved to the footer
  (provenance now lives in the Word caption).
- Bottom legend added to the multi-series charts (growth, drawdown, weights);
  end-of-line labels shrunk to the value only ($1.96 / $1.18, and the % on
  drawdown).
- **Drawdown:** two overlapping "underwater" fills muddied each other, so I fill
  only the deeper fund (MaxSharpe) and leave the shallower as a clean line; one
  trough label with its month, the other fund's -16% carried by the title.
- **Weights:** the solid "Other" band was the largest, least informative shape,
  so I removed it - the top 6 named holdings stack to a partial sum and the
  space above reads as the remainder (and as concentration).

[YOUR WORDS: my eye for the house style and why these read better.]

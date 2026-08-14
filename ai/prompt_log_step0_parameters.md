# Prompt log - Step 0: locking the core backtest parameters

*Milestone: decide the five core parameters (no code) before Step 1. Drafted from
the session; `[YOUR WORDS]` marks where I add my own reasoning before hand-in.*

## What I wanted

To fix the five core choices the funds and the sentiment index depend on:
estimation window, rebalance rule, risk-free rate, no-headline-day treatment, and
sentiment lag — with the trade-offs laid out, so I choose rather than accept a
silent default.

## Prompt(s)

- "Run Step 0."
- "On the estimation window: crypto trades every day, equities only on trading
  days — would a 365-day rolling window with equities forward-filled (park last
  trading-day price on non-trading days) be better, or am I overcomplicating?"
- "Lock rolling 252. What else do we need to determine?"
- "Would a decaying gradient of yesterday's news be good for no-news days —
  yesterday's sentiment persists and fades until the next headline?"
- "Lock neutral = 0 and add the decay idea to innovation."

## What the assistant produced

- Proposed all five parameters with trade-offs and a recommended default each,
  grounded in the sample (~1,006 equity trading days, 60-asset combined universe,
  badly conditioned covariance on a short window).
- Explained what a rolling window is and which calendar it is counted in.
- Recorded the locked decisions in `CLAUDE.md` and moved the decay idea to the
  "Sentiment model extensions" innovation list.

## What was wrong or risky

- **My forward-fill idea would have injected bias, and the assistant caught why.**
  Parking Friday's equity price across the weekend creates fake 0% equity return
  days (~104/year), which understates equity volatility and distorts the
  equity–crypto covariance the optimiser acts on — the same "invented 0% day"
  trap `DATA_GUIDE.md` and Part A's merge order warn about. The fix I was reaching
  for reintroduced the exact error Part A was built to avoid. [YOUR WORDS: what I
  took from that.]
- **I had the window's calendar backwards.** A 252-*trading-day* window already
  *is* one year; I don't need a 365-day calendar to get a one-year lookback. The
  combined fund lives on the equity trading calendar and annualises with 252.
- **Recommendations are not decisions.** The assistant recommended defaults; the
  actual choices below are mine.
- **The decay idea carries a tunable parameter** (the half-life), which is why it
  belongs in innovation with an out-of-sample justification, not in the core
  baseline.

## What I changed and why

Locked the five core parameters (recorded in `CLAUDE.md`):

| Parameter | Decision |
|---|---|
| Estimation window | Rolling **252 trading days** (~1 yr), equity calendar, no forward-fill |
| Rebalance rule | **First trading day of each month** (~36 rebalances OOS) |
| Risk-free rate | **Zero**, stated |
| No-headline ticker-days | **Neutral = 0** (conservative anchor) |
| Sentiment lag | **1 trading day** |
| Constraints | **Long-only, fully invested**; combined fund annualises with 252 |

Moved the **sentiment decay/gradient** to the innovation list as the general case
that improves on the neutral-0 baseline (half-life is its one tunable parameter;
evidence is its OOS effect on the fusion).

[YOUR WORDS: why these choices fit a first-time-investor product, in my own words.]

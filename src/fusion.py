"""Station 3 (extension) - fuse sentiment into the funds.

A basic, look-ahead-safe sentiment tilt: at each rebalance, nudge the fund's
EQUITY weights toward names in higher-sentiment sectors and away from lower ones,
leave the crypto weights untouched (sentiment is equity-only), and preserve the
equity sleeve's total weight. Re-running the backtest with the tilted weights
gives the required before-vs-after comparison.

Design (basic, UNTUNED - tuning the tilt is innovation, Step 8):
  - signal: each equity name's sector sentiment, as a trailing ``window``-day mean
    taken STRICTLY BEFORE the rebalance date (lag >= 1 trading day - no same-day
    sentiment ever enters a weight),
  - cross-sectional z-score across the held equity names,
  - multiply each equity weight by max(0, 1 + lam * z), renormalise the equity
    sleeve back to its original total (crypto unchanged),
  - lam and window are fixed constants, stated in the report.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TILT_STRENGTH = 0.5     # lambda: weight multiplier is max(0, 1 + lam * z)
SENT_WINDOW = 21        # trailing trading days for the sentiment signal (~1 month)


def build_sentiment_tilt(
    sector_index: pd.DataFrame, equities: pd.DataFrame,
    lam: float = TILT_STRENGTH, window: int = SENT_WINDOW,
):
    """Return a ``weight_fn(weights, date)`` for portfolios.oos_backtest.

    The returned function tilts the equity sleeve by lagged sector sentiment and
    is safe to hand straight to the backtest.
    """
    ticker_sector = (
        equities[["ticker", "sector"]].drop_duplicates().set_index("ticker")["sector"]
    )
    # Trailing mean of the (contemporaneous) sector index. The LAG is enforced in
    # the closure by only ever reading rows strictly before the rebalance date.
    trailing = sector_index.rolling(window, min_periods=5).mean()

    def weight_fn(w: pd.Series, d: pd.Timestamp) -> pd.Series:
        prior = trailing.loc[trailing.index < d]          # strictly before d -> lag >= 1
        if prior.empty:
            return w
        s_sector = prior.iloc[-1]                          # sector -> trailing sentiment

        is_crypto = pd.Index(w.index).to_series().astype(str).str.endswith("-USD").to_numpy()
        eq = pd.Index(w.index[~is_crypto])
        if len(eq) == 0:
            return w

        sent = pd.Series({t: s_sector.get(ticker_sector.get(t), np.nan) for t in eq}).dropna()
        if sent.empty or sent.std(ddof=0) == 0:
            return w

        z = (sent - sent.mean()) / sent.std(ddof=0)
        mult = (1.0 + lam * z).clip(lower=0.0)

        eq_total = float(w[eq].sum())
        tilted = w[sent.index] * mult
        if tilted.sum() <= 0:
            return w
        tilted = tilted / tilted.sum() * eq_total          # preserve equity sleeve total

        w_new = w.copy()
        w_new[sent.index] = tilted
        return w_new / w_new.sum()                         # sums to 1 (safety)

    return weight_fn

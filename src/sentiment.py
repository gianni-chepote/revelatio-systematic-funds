"""Station 3 - the sentiment model and the sector sentiment index.

Score each assembled headline with VADER's compound score, aggregate to a daily
per-ticker score, then to an equal-weight sector index across the ten equity
sectors. Headlines are a noisy proxy, so any TRADING use lags the signal (a
Station 3 / fusion concern, applied in fusion.py); the index written here is the
contemporaneous series - what sentiment was on each trading day - which is the
honest thing to plot.

Locked design (CLAUDE.md "Decided", Step 0):
  - VADER, vanilla lexicon (the finance-lexicon extension is innovation, Step 8),
  - text passes through unmodified: VADER reads casing, punctuation and negation,
  - a ticker-day with no headline scores 0 (neutral); the sector index then
    equal-weights the five tickers, so silent names dilute a thin sector toward 0,
  - any trading use lags by >= 1 trading day (applied downstream in fusion.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# The ten sectors, five tickers each (context/DATA_GUIDE.md). Derived from the
# equities panel at runtime; listed here only for reference.
N_SECTORS = 10


def _get_analyzer():
    """Return a VADER analyzer, downloading its lexicon once if missing.

    The download is a BUILD step (scripts/run_part_b.py). The deployed app never
    imports nltk - it reads the precomputed sector_sentiment_index.csv.
    """
    from nltk.sentiment import SentimentIntensityAnalyzer
    try:
        return SentimentIntensityAnalyzer()
    except LookupError:
        import nltk
        nltk.download("vader_lexicon")
        return SentimentIntensityAnalyzer()


def score_headlines(panel: pd.DataFrame, analyzer=None) -> pd.DataFrame:
    """Add a VADER ``compound`` score in [-1, 1] to each headline.

    ``panel`` is the assembled headline panel from
    ``features.assemble_headline_panel`` (one row per headline, with a
    ``trading_day``). The title is scored byte-for-byte - no lowercasing, no
    punctuation or stopword stripping - because VADER's valence depends on all
    three. Rows with no ``trading_day`` (headlines after the last trading day)
    are kept but excluded from the index by the aggregation below.
    """
    if analyzer is None:
        analyzer = _get_analyzer()
    out = panel.copy()
    out["compound"] = out["title"].astype(str).map(
        lambda t: analyzer.polarity_scores(t)["compound"]
    )
    return out


def sector_sentiment_index(
    scored: pd.DataFrame, equities: pd.DataFrame
) -> tuple[pd.DataFrame, dict]:
    """Daily equal-weight sentiment index per sector (date x sector).

    Steps:
      1. average the headline compound scores to one score per (trading_day,
         ticker);
      2. build the full trading_day x ticker grid and fill missing cells with 0
         (neutral) - the Step 0 rule for ticker-days with no headline;
      3. average across the five tickers in each sector (equal weight).

    ``equities`` supplies the ticker->sector map and the trading calendar, so the
    index spans every equity trading day, not only days that carried news.
    """
    smap = equities[["ticker", "sector"]].drop_duplicates().reset_index(drop=True)
    calendar = pd.Index(sorted(equities["date"].unique()), name="trading_day")

    scored_td = scored.dropna(subset=["trading_day"])
    ticker_day = (
        scored_td.groupby(["trading_day", "ticker"])["compound"].mean()
    )

    # Full grid: every trading day x every ticker. Missing = no headline = 0.
    full = pd.MultiIndex.from_product(
        [calendar, smap["ticker"]], names=["trading_day", "ticker"]
    )
    grid = ticker_day.reindex(full).fillna(0.0).rename("sentiment").reset_index()
    grid = grid.merge(smap, on="ticker", how="left")

    index = (
        grid.groupby(["trading_day", "sector"])["sentiment"].mean()
        .unstack("sector").sort_index()
    )
    index.index.name = "date"

    # Coverage: share of ticker-days that actually carried a headline (the rest
    # entered as neutral 0). Reported so a reader knows how much of the index is
    # real signal versus neutral dilution.
    n_cells = len(calendar) * len(smap)
    n_headline_cells = len(ticker_day)
    issues = {
        "trading_days": len(calendar),
        "sectors": index.shape[1],
        "tickers": len(smap),
        "ticker_day_coverage_pct": round(100 * n_headline_cells / n_cells, 2),
        "date_min": index.index.min(),
        "date_max": index.index.max(),
        "mean_abs_index": round(float(index.abs().mean().mean()), 4),
    }
    return index, issues


# --- Step 8 innovation: sentiment decay on no-news days ------------------------

def _decay_fill(wide: pd.DataFrame, half_life: float) -> pd.DataFrame:
    """Carry each ticker's last headline score forward, decaying toward 0.

    ``wide`` is a (trading_day x ticker) frame of actual headline scores with NaN
    where a ticker had no headline. A missing cell takes the last actual score
    times 0.5 ** (trading_days_since_news / half_life), keeping its sign; cells
    before a ticker's first headline stay 0. The core rule (snap to 0 at once) and
    pure carry-forward (never decay) are the half_life -> 0 and half_life -> inf
    limits of this. Look-ahead safe: every value depends only on a past score and
    the number of trading days elapsed.
    """
    out = {}
    for tic, col in wide.items():
        obs = col.notna()
        grp = obs.cumsum()                              # increments on each headline day
        days_since = col.groupby(grp).cumcount()        # 0 on the headline day, 1, 2, ...
        decayed = col.ffill() * np.power(0.5, days_since / half_life)
        out[tic] = decayed.where(grp > 0, 0.0)          # before the first headline -> 0
    return pd.DataFrame(out, index=wide.index)


def sector_sentiment_index_decay(
    scored: pd.DataFrame, equities: pd.DataFrame, half_life: float = 5.0
) -> tuple[pd.DataFrame, dict]:
    """Sector sentiment index with no-news days decayed instead of snapped to 0.

    Same aggregation as ``sector_sentiment_index`` (per-ticker daily score, then
    an equal-weight sector average), but the ticker-day grid is filled by
    ``_decay_fill`` rather than neutral 0. Built as an innovation exhibit; the
    core neutral-0 index is unchanged.
    """
    smap = equities[["ticker", "sector"]].drop_duplicates().reset_index(drop=True)
    calendar = pd.Index(sorted(equities["date"].unique()), name="trading_day")

    scored_td = scored.dropna(subset=["trading_day"])
    ticker_day = scored_td.groupby(["trading_day", "ticker"])["compound"].mean()
    wide = ticker_day.unstack("ticker").reindex(index=calendar, columns=smap["ticker"])

    decayed = _decay_fill(wide, half_life)
    grid = decayed.stack().rename("sentiment").reset_index()
    grid.columns = ["trading_day", "ticker", "sentiment"]
    grid = grid.merge(smap, on="ticker", how="left")

    index = (grid.groupby(["trading_day", "sector"])["sentiment"].mean()
             .unstack("sector").sort_index())
    index.index.name = "date"

    issues = {
        "half_life": half_life,
        "sectors": index.shape[1],
        "date_min": index.index.min(),
        "date_max": index.index.max(),
        "mean_abs_index": round(float(index.abs().mean().mean()), 4),
    }
    return index, issues


def ticker_decay_example(
    scored: pd.DataFrame, equities: pd.DataFrame, ticker: str, half_life: float = 5.0
) -> pd.DataFrame:
    """One ticker's headline scores, neutral-0 fill, and decayed fill, for the
    mechanism figure. Columns: headline (NaN off days), neutral0, decayed."""
    calendar = pd.Index(sorted(equities["date"].unique()), name="date")
    s = (scored.dropna(subset=["trading_day"])
         .loc[scored["ticker"] == ticker]
         .groupby("trading_day")["compound"].mean())
    col = s.reindex(calendar)
    obs = col.notna()
    grp = obs.cumsum()
    days_since = col.groupby(grp).cumcount()
    decayed = (col.ffill() * np.power(0.5, days_since / half_life)).where(grp > 0, 0.0)
    return pd.DataFrame({"headline": col, "neutral0": col.fillna(0.0), "decayed": decayed})

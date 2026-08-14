"""Station 2 - your features: return features and headline text assembly.

Build your return (and optional risk) features here, and assemble the headlines
into a daily text panel. Part A is assembly only - scoring the text into sentiment
(and lagging the signal) is the Station 3 model, built in Part B, not here.

THE MERGE ORDER, and why it is not negotiable. Equities trade ~252 days a year;
crypto trades 365. Returns are therefore computed INSIDE each panel first, then
crypto returns are left-joined onto the equity trading calendar. Doing it the
other way - aligning price levels across the two calendars and differencing
afterwards - conjures returns that were never earned: BTC's Friday-to-Monday
move would be stamped on Monday as a one-day return while Saturday's and
Sunday's moves vanish, and any forward-fill of a missing Saturday would invent a
0% day that flatters crypto volatility. Returns first keeps every return on its
true one-day horizon; the join then simply drops the weekend observations.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Annualisation factors. A return series is annualised by ITS OWN calendar:
# 252 for anything on equity trading days (including crypto once joined to that
# calendar), 365 for crypto on its native calendar. The brief says it plainly -
# "annualise with the right factor" (brief:209) - and the Part B rubric marks
# "correct 252 vs 365 annualisation" by name (brief:237). An earlier version
# applied 252 to all three rows and understated the crypto-native annual mean
# by 45%; caught by the Steps 0-3 audit (item 3.1).
TRADING_DAYS = 252
CRYPTO_DAYS = 365


def daily_returns(prices: pd.DataFrame, price_col: str = "adjClose") -> pd.DataFrame:
    """Simple daily returns per ticker, computed within each ticker only.

    ``pct_change`` runs inside a ``groupby(ticker)`` so the series never steps
    across a ticker boundary (which would difference the last day of AAPL
    against the first day of ABBV). Each ticker's first row is NaN by
    construction and is kept, not dropped - the caller decides.

    Returns a long frame: ticker, date, <price_col>, ret, plus sector when the
    source panel carries one (equities do, crypto does not).
    """
    keep = ["ticker", "date", price_col]
    if "sector" in prices.columns:
        keep.append("sector")

    out = prices[keep].sort_values(["ticker", "date"]).reset_index(drop=True)
    out["ret"] = out.groupby("ticker")[price_col].pct_change()
    return out


def combined_return_panel(
    equities: pd.DataFrame, crypto: pd.DataFrame, price_col: str = "adjClose"
) -> tuple[pd.DataFrame, dict]:
    """Wide daily-return panel (date x ticker) on the EQUITY trading calendar.

    Returns are computed within each panel first (see the module docstring),
    then the crypto columns are left-joined onto the equity dates. Weekend and
    holiday crypto observations are dropped by that join - intended, and worth
    one sentence in the report: the combined panel measures crypto only on the
    days an equity investor could have traded alongside it.

    Nothing is forward-filled. A crypto column that is NaN on an equity trading
    day means the coin genuinely had no observation that day, not a weekend.
    """
    eq_ret = daily_returns(equities, price_col)
    cr_ret = daily_returns(crypto, price_col)

    eq_wide = eq_ret.pivot(index="date", columns="ticker", values="ret")
    cr_wide = cr_ret.pivot(index="date", columns="ticker", values="ret")

    calendar = eq_wide.index  # the equity trading calendar, and the only calendar
    panel = eq_wide.join(cr_wide, how="left")
    panel.columns.name = None

    crypto_days_dropped = int(len(cr_wide.index.difference(calendar)))
    issues = {
        "rows": len(panel),
        "equity_trading_days": len(calendar),
        "n_equity_tickers": eq_wide.shape[1],
        "n_crypto_tickers": cr_wide.shape[1],
        "crypto_dates_dropped_by_join": crypto_days_dropped,
        "crypto_native_dates": len(cr_wide.index),
        "date_min": panel.index.min(),
        "date_max": panel.index.max(),
        # Every ticker's first return is NaN by construction - but only the
        # EQUITY columns are NaN on the panel's first date. Crypto traded on
        # 2020-01-01, a date the equity calendar does not have, so each coin's
        # NaN was consumed there and its 2020-01-02 return is real.
        "first_row_equity_all_nan": bool(panel.iloc[0][eq_wide.columns].isna().all()),
        "first_row_crypto_nan": int(panel.iloc[0][cr_wide.columns].isna().sum()),
        "nan_cells_after_first_row": int(panel.iloc[1:].isna().sum().sum()),
    }
    return panel, issues


def describe_returns_by_class(
    equities: pd.DataFrame,
    crypto: pd.DataFrame,
    price_col: str = "adjClose",
) -> tuple[pd.DataFrame, dict]:
    """Descriptive statistics per asset class - this becomes descriptive_stats_returns.csv.

    Three rows, deliberately. Equities and crypto are described on their NATIVE
    calendars, and crypto is described a second time on the equity calendar. The
    third row is what the combined panel actually contains, and comparing it
    with the second shows what the calendar join costs - dropping weekends
    removes the sessions when thin crypto books move most.

    Statistics are pooled across the tickers in each class (every ticker-day is
    one observation), so ``mean`` is the average daily return of a randomly
    chosen coin or stock on a randomly chosen day.

    RETURN CONVENTION (founder decision, 2026-07-24): SIMPLE returns are the
    published convention - they are what an investor earns, they aggregate
    exactly across a portfolio (Part B's optimisers need w'r), and the extreme
    screen's thresholds live in the same space. The ``skew_log`` and
    ``kurtosis_log`` columns describe the same series in log (compounding)
    space, because the shape claims differ: crypto's skew is +1.06 in simple
    (dollar-outcome) space and flips to -0.32 under logs - the fat right tail
    is a dollar-outcome feature, not a compounding one. Publishing both spaces
    makes the exhibit state that instead of the caption having to.
    """
    eq_ret = daily_returns(equities, price_col)
    cr_ret = daily_returns(crypto, price_col)

    eq_calendar = pd.Index(sorted(eq_ret["date"].unique()))
    cr_on_eq = cr_ret[cr_ret["date"].isin(eq_calendar)]

    def _stats(label: str, frame: pd.DataFrame, calendar: str, periods: int) -> dict:
        r = frame["ret"].dropna()
        lg = np.log1p(r)  # log-space view of the same series, shape columns only
        return {
            "asset_class": label,
            "calendar": calendar,
            "periods_per_year": periods,  # the exhibit states its own convention
            "n_tickers": frame["ticker"].nunique(),
            "n_obs": len(r),
            "mean_daily": r.mean(),
            "vol_daily": r.std(),
            "mean_annual": r.mean() * periods,
            "vol_annual": r.std() * (periods ** 0.5),
            "min": r.min(),
            "max": r.max(),
            "skew": r.skew(),
            "skew_log": lg.skew(),
            "kurtosis": r.kurtosis(),  # excess: 0 is normal
            "kurtosis_log": lg.kurtosis(),
        }

    table = pd.DataFrame([
        _stats("equities", eq_ret, "equity trading days", TRADING_DAYS),
        _stats("crypto", cr_ret, "365-day", CRYPTO_DAYS),
        _stats("crypto", cr_on_eq, "equity trading days", TRADING_DAYS),
    ])

    issues = {
        "rows": len(table),
        "crypto_obs_lost_to_calendar": int(
            table.loc[1, "n_obs"] - table.loc[2, "n_obs"]
        ),
        "equity_excess_kurtosis": round(float(table.loc[0, "kurtosis"]), 2),
        "crypto_excess_kurtosis_native": round(float(table.loc[1, "kurtosis"]), 2),
    }
    return table, issues


def assemble_headline_panel(
    headlines: pd.DataFrame, equities: pd.DataFrame
) -> tuple[pd.DataFrame, dict]:
    """Align every headline to the equity trading day that can act on it.

    Station 2 (Part A) is assembly only: structure the text and date-align it to
    the trading calendar (a weekend headline maps to the next trading day).
    Scoring the text - and lagging the signal - is the Station 3 sentiment model,
    built in Part B, not here.

    The mapping is FORWARD, never backward: a headline published on Saturday
    could not have been traded until Monday, so it belongs to Monday. Mapping
    backward - or rounding to the nearest trading day - would hand Friday's
    price a Saturday fact and build look-ahead into the foundation.

    ``title`` is passed through byte-identical. No lowercasing, no punctuation
    stripping, no stopword removal: VADER reads negation, intensifiers and
    capitalisation in Part B, and a cleaned corpus cannot be uncleaned.

    A NOTE THE REPORT OWES ITS READER: 99.6% of the source timestamps are exactly
    00:00:00, so the data carries no usable publication *time*. Same-day
    alignment therefore cannot distinguish a headline that broke before the open
    from one that broke after the close. Part B must lag the signal by a full
    trading day to be safe - that is a Station 3 decision, flagged here because
    this is where the information is lost.

    Returns one row per headline (never aggregated - the raw text must survive)
    with a ``trading_day`` column, plus ``days_shifted`` recording how far each
    headline had to travel.
    """
    calendar = pd.Index(sorted(equities["date"].unique()), name="trading_day")

    panel = headlines.sort_values("date").reset_index(drop=True)
    # merge_asof demands identical datetime resolutions and the two sources do
    # not agree: news loads as datetime64[us], prices as datetime64[s]. Cast the
    # calendar to match rather than touching either cleaned panel - both are
    # already tz-naive and normalised to midnight, so this is a resolution cast
    # only, with no value moved.
    cal_frame = pd.DataFrame({"trading_day": calendar.astype(panel["date"].dtype)})
    panel = pd.merge_asof(
        panel,
        cal_frame,
        left_on="date",
        right_on="trading_day",
        direction="forward",  # never backward: no look-ahead
    )
    panel["days_shifted"] = (panel["trading_day"] - panel["date"]).dt.days

    unmapped = panel["trading_day"].isna()
    on_trading_day = panel["days_shifted"] == 0

    issues = {
        "rows_in": len(headlines),
        "rows_out": len(panel),
        "trading_days_covered": int(panel["trading_day"].nunique()),
        "already_on_a_trading_day": int(on_trading_day.sum()),
        "shifted_forward": int((panel["days_shifted"] > 0).sum()),
        "max_days_shifted": int(panel["days_shifted"].max()) if len(panel) else 0,
        # Headlines dated after the LAST equity trading day (2023-12-29) have no
        # next trading day inside the sample. They are kept with a null
        # trading_day and counted, never silently dropped.
        "unmappable_after_last_trading_day": int(unmapped.sum()),
        "titles_unchanged": bool(
            panel["title"].reset_index(drop=True)
            .equals(headlines.sort_values("date")["title"].reset_index(drop=True))
        ),
    }
    return panel, issues


def daily_headline_counts(panel: pd.DataFrame) -> pd.DataFrame:
    """Headline volume per ticker per trading day - feeds the articles-over-time figure.

    Built from the aligned panel, so a Monday carries its own headlines plus the
    weekend's. Rows with no trading day (the post-2023-12-29 tail) are excluded
    from the counts but remain in the panel they came from.
    """
    counted = panel.dropna(subset=["trading_day"])
    return (
        counted.groupby(["trading_day", "ticker", "sector"], observed=True)
        .size()
        .reset_index(name="n_headlines")
        .sort_values(["trading_day", "ticker"])
        .reset_index(drop=True)
    )


# --- Naive sentiment vocabulary ------------------------------------------------
# The BASELINE, and deliberately plain: everyday emotion words any general-purpose
# lexicon carries. Finance-specific terms ("downgrade", "guidance cut", "probe",
# "recall", "beat") are POINTEDLY ABSENT - catching what this list misses is the
# Step 5 innovation, and seeding it here would flatter that comparison.
#
# Counting is descriptive and allowed in Part A. Scoring - turning these hits
# into a sentiment value - is Station 3, Part B.
NAIVE_POSITIVE = [
    "good", "great", "strong", "strength", "rise", "rises", "rising", "gain",
    "gains", "win", "wins", "boost", "high", "higher", "best", "positive",
    "success", "successful", "improve", "improved", "growth", "surge", "jump",
    "soar", "optimistic", "confident", "better", "record", "rally", "hope",
]
NAIVE_NEGATIVE = [
    "bad", "weak", "weakness", "fall", "falls", "falling", "drop", "drops",
    "loss", "losses", "decline", "low", "lower", "worst", "negative", "fail",
    "fails", "failure", "concern", "concerns", "fear", "fears", "risk", "risks",
    "warn", "warns", "slump", "plunge", "crash", "worry", "worries", "trouble",
]


def _word_pattern(words: list[str]) -> str:
    """Case-insensitive whole-word alternation. Matching never mutates the title."""
    return r"\b(?:" + "|".join(sorted(set(words), key=len, reverse=True)) + r")\b"


def sentiment_vocab_counts(
    panel: pd.DataFrame,
    by: str = "sector",
    positive: list[str] | None = None,
    negative: list[str] | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Count headlines containing sentiment-bearing words. COUNTING ONLY.

    This is the naive baseline: does a headline contain at least one everyday
    sentiment word? No polarity is assigned, no score is computed, no net
    sentiment is implied - a headline hitting both lists counts in both columns
    and is not netted off. Part A describes the vocabulary; Part B scores it.

    ``by`` cuts the table by ``"sector"`` (default) or ``"month"``. The headline
    text is read with a case-insensitive regex and never modified.

    The number Step 5 has to beat is ``share_no_hit_pct`` in the issues dict:
    the share of headlines this plain vocabulary calls empty.
    """
    pos = positive if positive is not None else NAIVE_POSITIVE
    neg = negative if negative is not None else NAIVE_NEGATIVE

    flags = pd.DataFrame(index=panel.index)
    flags["hit_pos"] = panel["title"].str.contains(_word_pattern(pos), case=False, regex=True)
    flags["hit_neg"] = panel["title"].str.contains(_word_pattern(neg), case=False, regex=True)
    flags["hit_any"] = flags["hit_pos"] | flags["hit_neg"]
    flags["hit_both"] = flags["hit_pos"] & flags["hit_neg"]

    if by == "sector":
        key = panel["sector"]
    elif by == "month":
        key = panel["date"].dt.to_period("M").astype(str).rename("month")
    else:
        raise ValueError(f"by must be 'sector' or 'month', got {by!r}")

    grouped = flags.groupby(key, observed=True)
    table = pd.DataFrame({
        "n_headlines": grouped.size(),
        "n_positive_hit": grouped["hit_pos"].sum(),
        "n_negative_hit": grouped["hit_neg"].sum(),
        "n_any_hit": grouped["hit_any"].sum(),
        "n_both_hit": grouped["hit_both"].sum(),
    })
    table["share_any_hit_pct"] = (100 * table["n_any_hit"] / table["n_headlines"]).round(2)
    table = table.reset_index()

    n = len(panel)
    issues = {
        "grouped_by": by,
        "n_headlines": n,
        "n_positive_terms": len(set(pos)),
        "n_negative_terms": len(set(neg)),
        "share_any_hit_pct": round(100 * int(flags["hit_any"].sum()) / n, 2) if n else 0.0,
        # The headroom the Step 5 finance lexicon is measured against.
        "share_no_hit_pct": round(100 * int((~flags["hit_any"]).sum()) / n, 2) if n else 0.0,
        "share_both_lists_pct": round(100 * int(flags["hit_both"].sum()) / n, 2) if n else 0.0,
    }
    return table, issues


if __name__ == "__main__":
    # Quick self-check: run `python -m src.features` from the project root.
    from src import etl

    eq, _ = etl.load_clean_equities()
    cr, _ = etl.load_clean_crypto()

    nw, _ = etl.load_clean_news()

    panel, panel_issues = combined_return_panel(eq, cr)
    stats, stats_issues = describe_returns_by_class(eq, cr)
    print("combined panel:", panel_issues)
    print("descriptive stats:", stats_issues)
    print(stats.to_string(index=False))

    text, text_issues = assemble_headline_panel(nw, eq)
    vocab, vocab_issues = sentiment_vocab_counts(text)
    print()
    print("headline panel:", text_issues)
    print("vocab counts  :", vocab_issues)
    print(vocab.to_string(index=False))

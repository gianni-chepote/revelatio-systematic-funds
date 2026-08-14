"""Station 1 - ETL: load, clean, and quality-check the three datasets.

Everything enters through ``src.data_access`` (never edited, never re-downloaded
by hand). Each cleaning function returns ``(clean_frame, issues)`` so
``scripts/run_part_a.py`` can assemble the data-integrity summary from one place.

Part A scope only: this module cleans and audits. It does not compute the return
feature panel (that is ``features.py``), score sentiment, or optimise anything.
The one place returns appear here is the *extreme-return screen*, an integrity
check that flags — and keeps — genuine extremes; that return is thrown away, not
exported.
"""
from __future__ import annotations

import pandas as pd

from src import data_access

# Every panel ends here. Crypto carries 10 stray rows dated 2024-01-01; equities
# and news already stop inside 2023, so the cap should only bite crypto.
CUTOFF = pd.Timestamp("2023-12-31")

# Extreme-return flag. FOUNDER DECISION (2026-07-23, Step 2): run BOTH rules —
# |r| > 25% is the headline because it is absolute, asset-class-neutral, and
# explainable to a non-technical reader; the z-score rides along as a column so
# the report can show where the two rules disagree. Both stay parameters.
EXTREME_THRESHOLD = 0.25
EXTREME_Z = 5.0


def _cap_to_cutoff(df: pd.DataFrame, cutoff: pd.Timestamp = CUTOFF) -> tuple[pd.DataFrame, int]:
    """Drop rows after ``cutoff`` and count what fell."""
    before = len(df)
    out = df[df["date"] <= cutoff].copy()
    return out, before - len(out)


def _ohlc_violations(df: pd.DataFrame) -> int:
    """Count rows where the OHLC bar is internally inconsistent or volume < 0.

    A valid bar has low <= open,close <= high and non-negative volume. Rows that
    fail are reported and KEPT (Part A: confirm consistency, do not delete).
    """
    lo, hi = df["low"], df["high"]
    bad = (
        (lo > df["open"]) | (lo > df["close"]) | (lo > hi)
        | (hi < df["open"]) | (hi < df["close"])
        | (df["volume"] < 0)
    )
    return int(bad.sum())


def _clean_price_panel(df: pd.DataFrame, name: str) -> tuple[pd.DataFrame, dict]:
    """Shared price cleaning: cap, assert (ticker, date) uniqueness, OHLC sanity.

    The issues dict records the RAW dimensions as received (rows, columns, date
    span) before any cleaning touches them - provenance the dataset-inventory
    exhibit reports, and the first thing to check if the hosted data is ever
    reissued. Founder decision (2026-07-24): raw dimensions are kept in a graded
    exhibit, overruling the scaffold's discard-the-smoke-test convention.
    """
    rows_in = len(df)
    columns_in = df.shape[1]
    raw_date_min, raw_date_max = df["date"].min(), df["date"].max()
    df, dropped = _cap_to_cutoff(df)

    dup_mask = df.duplicated(subset=["ticker", "date"], keep="first")
    n_dups = int(dup_mask.sum())
    if n_dups:
        df = df[~dup_mask].copy()

    ohlc_bad = _ohlc_violations(df)
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    issues = {
        "dataset": name,
        "rows_in": rows_in,
        "columns_in": columns_in,
        "raw_date_min": raw_date_min,
        "raw_date_max": raw_date_max,
        "rows_out": len(df),
        "dropped_after_cutoff": dropped,
        "duplicate_ticker_date": n_dups,
        "ohlc_violations_kept": ohlc_bad,
        "n_tickers": df["ticker"].nunique(),
        "date_min": df["date"].min(),
        "date_max": df["date"].max(),
    }
    return df, issues


def load_clean_equities() -> tuple[pd.DataFrame, dict]:
    """Clean equity prices: cap at 2023-12-31, unique (ticker, date), OHLC sanity.

    Expected: 0 rows capped (equities already end 2023-12-29), 0 duplicates.
    """
    return _clean_price_panel(data_access.load_equity_prices(), "equities")


def load_clean_crypto() -> tuple[pd.DataFrame, dict]:
    """Clean crypto prices (365-day calendar, no sector column).

    Success test: exactly 10 rows dropped (the 2024-01-01 strays).
    """
    df, issues = _clean_price_panel(data_access.load_crypto_prices(), "crypto")
    assert issues["dropped_after_cutoff"] == 10, (
        f"expected 10 stray 2024 crypto rows, dropped {issues['dropped_after_cutoff']}"
    )
    return df, issues


def load_clean_news() -> tuple[pd.DataFrame, dict]:
    """Clean news headlines: strip UTC to tz-naive, cap, dedup on (ticker, date, title).

    Success test: ~2,847 exact-duplicate headlines removed. Dedup is on the full
    (ticker, date, title) key ONLY - many rows per ticker-day is the natural
    state of news, so a (ticker, date) key would flag everything.
    """
    df = data_access.load_news_headlines()
    rows_in = len(df)
    columns_in = df.shape[1]

    # UTC -> naive so the news calendar can align with the tz-naive price dates.
    df = df.copy()
    df["date"] = df["date"].dt.tz_localize(None).dt.normalize()

    # Raw span recorded after the tz-strip (same calendar dates, comparable dtype).
    raw_date_min, raw_date_max = df["date"].min(), df["date"].max()
    df, dropped = _cap_to_cutoff(df)

    dup_mask = df.duplicated(subset=["ticker", "date", "title"], keep="first")
    n_dups = int(dup_mask.sum())
    df = df[~dup_mask].copy()
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    issues = {
        "dataset": "news",
        "rows_in": rows_in,
        "columns_in": columns_in,
        "raw_date_min": raw_date_min,
        "raw_date_max": raw_date_max,
        "rows_out": len(df),
        "dropped_after_cutoff": dropped,
        "exact_duplicates_removed": n_dups,
        "n_tickers": df["ticker"].nunique(),
        "blank_publisher": int(df["publisher"].isna().sum() + (df["publisher"] == "").sum()),
        "date_min": df["date"].min(),
        "date_max": df["date"].max(),
    }
    return df, issues


def missing_date_audit(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Per-ticker missing-date audit against the panel's own market calendar.

    The union of all dates present is treated as the calendar; a ticker is
    "missing" a date if the calendar has it but the ticker does not. Balanced
    panels (every ticker on every date) return 0 missing.
    """
    calendar = pd.Index(sorted(df["date"].unique()))
    n_dates = len(calendar)
    per_ticker = df.groupby("ticker")["date"].nunique()

    rows = [
        {"ticker": t, "dates_present": int(n), "dates_missing": int(n_dates - n)}
        for t, n in per_ticker.items()
        if n < n_dates
    ]
    audit = pd.DataFrame(rows, columns=["ticker", "dates_present", "dates_missing"])

    issues = {
        "calendar_dates": n_dates,
        "tickers_with_gaps": len(audit),
        "total_missing_cells": int(audit["dates_missing"].sum()) if len(audit) else 0,
    }
    return audit, issues


def extreme_return_screen(
    prices: pd.DataFrame,
    threshold: float = EXTREME_THRESHOLD,
    z_threshold: float = EXTREME_Z,
    top_n: int | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Flag daily returns beyond ``threshold`` in absolute value - and KEEP them.

    These are real events (the March-2020 crash, earnings gaps), so the screen
    reports them for the report's integrity table; it never deletes a row. The
    return computed here is a throwaway for screening only - the exported return
    feature is built in features.py.

    Two rules run side by side. ``|r| > threshold`` is the headline flag; the
    z-score is standardised on THIS panel's own return distribution, never a
    pooled one - crypto's ordinary Tuesday would clear an equity-calibrated
    sigma and the table would say nothing. The returned frame is the UNION of
    the two rules, with ``rule_hit`` naming which fired, so the report can show
    where an absolute cut and a relative one disagree.

    ``top_n`` truncates the returned frame (largest |r| first) for exhibits that
    must stay short; the issues dict always counts the full set.
    """
    px = prices.sort_values(["ticker", "date"]).copy()
    px["ret"] = px.groupby("ticker")["adjClose"].pct_change()

    ret = px["ret"].dropna()
    mu, sd = ret.mean(), ret.std()
    px["z_within_class"] = (px["ret"] - mu) / sd

    by_pct = px["ret"].abs() > threshold
    by_z = px["z_within_class"].abs() > z_threshold

    flagged = (
        px.loc[by_pct | by_z, ["ticker", "date", "adjClose", "ret", "z_within_class"]]
        .assign(
            rule_hit=lambda d: pd.Series(
                ["both" if p and zz else "pct" if p else "z"
                 for p, zz in zip(by_pct[d.index], by_z[d.index])],
                index=d.index,
            ),
            abs_ret=lambda d: d["ret"].abs(),
        )
        .sort_values("abs_ret", ascending=False)
        .drop(columns="abs_ret")
        .reset_index(drop=True)
    )
    n_flagged = len(flagged)
    if top_n is not None:
        flagged = flagged.head(top_n).copy()

    issues = {
        "threshold": threshold,
        "z_threshold": z_threshold,
        "n_flagged": n_flagged,  # union of both rules
        "n_flagged_kept": n_flagged,  # kept == flagged, always
        "n_flagged_pct_rule": int(by_pct.sum()),
        "n_flagged_z_rule": int(by_z.sum()),
        "n_flagged_both_rules": int((by_pct & by_z).sum()),
        "share_flagged_pct": round(100 * n_flagged / len(ret), 3) if len(ret) else 0.0,
        "max_abs_return": round(float(ret.abs().max()), 4) if len(ret) else None,
        "smallest_abs_return_flagged_by_z": (
            round(float(ret[by_z.reindex(ret.index, fill_value=False)].abs().min()), 4)
            if int(by_z.sum()) else None
        ),
    }
    return flagged, issues


if __name__ == "__main__":
    # Quick self-check: run `python -m src.etl` from the project root.
    eq, eq_i = load_clean_equities()
    cr, cr_i = load_clean_crypto()
    nw, nw_i = load_clean_news()
    print("equities:", eq_i)
    print("crypto  :", cr_i)
    print("news    :", nw_i)
    for name, df in [("equities", eq), ("crypto", cr)]:
        _, ma = missing_date_audit(df)
        _, ex = extreme_return_screen(df)
        print(f"{name} missing-date audit:", ma)
        print(f"{name} extreme-return screen:", ex)

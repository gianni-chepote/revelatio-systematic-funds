"""Build the S&P 500 benchmark artifact the app reads.

    python scripts/build_sp500_benchmark.py

Downloads SPY (the S&P 500 ETF) daily adjusted closes from Yahoo Finance, so the
series includes dividends the same way the funds' adjClose returns do. Returns are
computed on SPY's own calendar first, then aligned to the funds' out-of-sample
dates (2021-01-04 to 2023-12-29). The app never downloads anything: it reads the
CSV this script writes.

Writes results/data/sp500_returns.csv (one column, "SP500").
"""
from __future__ import annotations

import pathlib
import sys

import pandas as pd
import yfinance as yf

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "results" / "data"
TICKER = "SPY"


def main() -> int:
    funds = pd.read_csv(DATA / "fund_returns.csv", index_col=0, parse_dates=True)
    oos = funds.dropna(how="all").index
    # Start a month early so the first OOS day has a prior close to difference from.
    px = yf.download(TICKER, start=oos[0] - pd.Timedelta(days=31),
                     end=oos[-1] + pd.Timedelta(days=5), auto_adjust=True,
                     progress=False)["Close"][TICKER]
    px.index = pd.to_datetime(px.index).tz_localize(None)
    r = px.pct_change().reindex(oos).rename("SP500")

    missing = int(r.isna().sum())
    if missing:
        print(f"FAIL: {missing} OOS days have no SPY return")
        return 1
    r.to_frame().rename_axis("date").to_csv(DATA / "sp500_returns.csv")
    g = (1 + r).prod()
    print(f"wrote sp500_returns.csv: {len(r)} days {r.index[0]:%Y-%m-%d} to "
          f"{r.index[-1]:%Y-%m-%d}, growth of $1 = {g:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Step 8 innovation - a passive benchmark.

An equal-weight 50-stock "market": hold every equity at 1/N, reset to equal weight
on the same monthly schedule and over the same out-of-sample window as the funds,
so growth-of-$1 lines and Sharpe ratios are directly comparable. Built from our own
data on our own trading calendar - the honest same-universe baseline. Excess return
over it answers the question the absolute Sharpe cannot: did the optimiser beat
simply owning the market?

The benchmark is equity-only by construction (the stated 50-stock market); the
combined funds also hold crypto, so part of any fund-vs-benchmark gap is crypto
exposure rather than optimisation - stated plainly in the report. An external index
(e.g. the S&P 500) may appear at most once as report validation and never in the
app (CLAUDE.md "parked at the gates").
"""
from __future__ import annotations

import pandas as pd

from src import portfolios

BENCHMARK_NAME = "EqualWeight50"


def _equal_weight_builder(equity_cols):
    """A weights_builder for oos_backtest: 1/N over the equities in the window.

    Ignores the estimation entirely (there is nothing to estimate for equal
    weight), but running it through oos_backtest gives it the SAME rebalance dates
    and out-of-sample start as the funds, which is what makes the comparison fair.
    """
    eqset = set(equity_cols)

    def builder(window_returns, method):
        cols = window_returns.columns[window_returns.notna().all()]
        eq = [c for c in cols if c in eqset]
        w = pd.Series(1.0 / len(eq), index=eq)
        return w.reindex(cols).fillna(0.0)

    return builder


def equal_weight_benchmark(panel: pd.DataFrame, equity_cols: list[str]):
    """Daily OOS returns of the equal-weight 50-stock market, plus weights/meta."""
    dr, wdf, meta = portfolios.oos_backtest(
        panel, "min_variance", weights_builder=_equal_weight_builder(equity_cols))
    dr = dr.rename(BENCHMARK_NAME)
    return dr, wdf, {**meta, "fund": BENCHMARK_NAME}


def compare_to_benchmark(fund_metrics: dict, bench_metrics: dict) -> pd.DataFrame:
    """Each fund's excess return and Sharpe gap over the benchmark."""
    rows = []
    for fund, m in fund_metrics.items():
        rows.append({
            "fund": fund,
            "ann_return": m["ann_return"],
            "sharpe": m["sharpe"],
            "bench_ann_return": bench_metrics["ann_return"],
            "bench_sharpe": bench_metrics["sharpe"],
            "excess_ann_return": m["ann_return"] - bench_metrics["ann_return"],
            "sharpe_minus_bench": m["sharpe"] - bench_metrics["sharpe"],
            "beats_benchmark": bool(m["sharpe"] > bench_metrics["sharpe"]),
        })
    return pd.DataFrame(rows)

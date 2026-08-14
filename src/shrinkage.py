"""Step 8 innovation - covariance shrinkage (Ledoit-Wolf).

The 60-asset sample covariance on a 252-day window is badly conditioned, and the
optimiser pours that estimation error into a few extreme weights. This extension
replaces the sample covariance with a Ledoit-Wolf estimator that shrinks it
toward a scaled-identity target (constant variance, zero correlation):

    Sigma_hat = (1 - delta) * S + delta * (mu_var * I)

where S is the sample covariance, mu_var the average sample variance, and delta
in [0, 1] the shrinkage intensity chosen ANALYTICALLY per window by
sklearn.covariance.LedoitWolf to minimise expected Frobenius loss. There is no
tuned parameter - delta is estimated, not picked - so the no-tuning rule holds.

Everything else is inherited unchanged from ``portfolios.oos_backtest`` through
the ``cov_estimator`` hook: the 252-day rolling window, the first-of-month
rebalance, long-only fully-invested constraints, risk-free 0, the no-look-ahead
rule, the NaN rule, and 252-day annualisation. Only the covariance estimator
moves, so the comparison is like-for-like.

Shrinkage acts on the COVARIANCE ONLY; the sample mean still drives the
max-Sharpe tangency solve. Minimum-variance is a pure covariance play, so
shrinkage should help it more than max-Sharpe - reported honestly, not tuned.

This is a self-contained before-vs-after exhibit. The two core funds and the four
marker files are never touched; the shrunk funds live in their own artifacts.

sklearn's LedoitWolf normalises the covariance by n (MLE) rather than n-1; the
difference is immaterial next to the shrinkage and is noted in the report.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from src import portfolios

SHRUNK_NAME = {
    "min_variance": "Combined_MinVariance_Shrunk",
    "max_sharpe": "Combined_MaxSharpe_Shrunk",
}


class LedoitWolfEstimator:
    """Callable covariance estimator that records each window's shrinkage delta.

    Passed to ``portfolios.oos_backtest(cov_estimator=...)``; called once per
    rebalance on that window's clean return matrix. It appends the fitted
    ``shrinkage_`` so the report can trace the average intensity, and returns the
    shrunk covariance for the optimiser.
    """

    def __init__(self) -> None:
        self.deltas: list[float] = []

    def __call__(self, R: pd.DataFrame) -> np.ndarray:
        lw = LedoitWolf().fit(R.to_numpy())
        self.deltas.append(float(lw.shrinkage_))
        return lw.covariance_


def _dispersion(weights_long: pd.DataFrame) -> dict:
    """Weight-concentration diagnostics averaged over the rebalances.

    effective_n = 1 / sum(w^2) is the number of equally weighted names the fund
    behaves like (higher = more diversified); turnover is the one-way weight
    change between consecutive rebalances. These are the mechanism evidence:
    shrinkage should raise effective N and cut turnover.
    """
    piv = (weights_long.pivot(index="rebalance_date", columns="ticker", values="weight")
           .fillna(0.0).sort_index())
    eff_n = float((1.0 / (piv ** 2).sum(axis=1)).mean())
    max_w = float(piv.max(axis=1).mean())
    top5 = float(piv.apply(lambda r: r.nlargest(5).sum(), axis=1).mean())
    turnover = float(piv.diff().abs().sum(axis=1).div(2.0).iloc[1:].mean())
    return {"effective_n": eff_n, "mean_max_weight": max_w,
            "mean_top5_weight": top5, "mean_turnover": turnover}


def run_shrinkage(panel: pd.DataFrame) -> dict:
    """Backtest both methods with sample vs Ledoit-Wolf covariance.

    Returns a dict with the before-vs-after ``comparison`` table, the weight
    ``diagnostics`` (including mean delta), the ``shrunk_returns`` panel for the
    two shrunk funds, and per-method ``series`` for the growth figure. The base
    run here reproduces Step 2 exactly (same code path, cov_estimator=None).
    """
    comparison_rows, diag_rows = [], []
    shrunk_returns, series = {}, {}

    for method in portfolios.METHODS:
        base_name = portfolios.FUND_NAME[method]
        shrunk_name = SHRUNK_NAME[method]

        base_dr, base_w, _ = portfolios.oos_backtest(panel, method)
        est = LedoitWolfEstimator()
        shr_dr, shr_w, _ = portfolios.oos_backtest(panel, method, cov_estimator=est)

        mb = portfolios.performance_metrics(base_dr)
        ms = portfolios.performance_metrics(shr_dr)
        for variant, name, m in (("sample", base_name, mb), ("shrunk", shrunk_name, ms)):
            comparison_rows.append({
                "method": method, "variant": variant, "fund": name,
                "ann_return": m["ann_return"], "ann_vol": m["ann_vol"],
                "sharpe": m["sharpe"], "max_drawdown": m["max_drawdown"],
            })

        db, ds = _dispersion(base_w), _dispersion(shr_w)
        diag_rows.append({"method": method, "variant": "sample",
                          "mean_delta": np.nan, **db})
        diag_rows.append({"method": method, "variant": "shrunk",
                          "mean_delta": float(np.mean(est.deltas)), **ds})

        shrunk_returns[shrunk_name] = shr_dr
        series[method] = {
            "base": base_dr, "shrunk": shr_dr,
            "base_sharpe": mb["sharpe"], "shrunk_sharpe": ms["sharpe"],
            "base_name": base_name, "shrunk_name": shrunk_name,
        }

    return {
        "comparison": pd.DataFrame(comparison_rows),
        "diagnostics": pd.DataFrame(diag_rows),
        "shrunk_returns": pd.DataFrame(shrunk_returns),
        "series": series,
    }

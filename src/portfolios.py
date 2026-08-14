"""Station 3 - the funds: long-only optimal portfolios + walk-forward OOS backtest.

Two combined equity-plus-crypto funds, both over all 60 assets, long-only and
fully invested:
  - Combined_MinVariance : minimise portfolio variance
  - Combined_MaxSharpe   : maximise the (tangency) Sharpe ratio

Locked design (CLAUDE.md "Decided", Step 0/2):
  - rolling 252-trading-day estimation window on the equity calendar,
  - rebalance the FIRST trading day of each month,
  - risk-free rate = 0,
  - constraints w_i >= 0 and sum(w) = 1 (long-only, fully invested),
  - constant-weight to target between rebalances: the daily portfolio return is
    w'r using the current month's target weights,
  - annualise the combined fund with 252.

NO LOOK-AHEAD. Weights at rebalance date t are estimated from the 252 returns
STRICTLY BEFORE t (positions [t-252, t-1]); the return on day t is then earned
with weights held entering that day. The estimation never sees day t or later.
The ``peek`` argument exists only for the look-ahead probe - it deliberately
shifts the window into the future to prove the honest run depends on not peeking.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

WINDOW = 252            # rolling estimation window, equity trading days (~1 year)
TRADING_DAYS = 252      # the combined fund lives on the equity calendar
RISK_FREE = 0.0         # stated assumption; Sharpe = mean_ann / vol_ann

# METHODS is the two core combined methods that carry the core narrative (fusion,
# shrinkage). ALL_METHODS adds risk parity, the third method used to build the full
# fund grid (equity-only / crypto-only / combined) in run_part_b.
METHODS = ("min_variance", "max_sharpe")
ALL_METHODS = ("min_variance", "max_sharpe", "risk_parity")
METHOD_LABEL = {"min_variance": "MinVariance", "max_sharpe": "MaxSharpe",
                "risk_parity": "RiskParity"}
FUND_NAME = {
    "min_variance": "Combined_MinVariance",
    "max_sharpe": "Combined_MaxSharpe",
}


# --- The optimisers ------------------------------------------------------------

def _min_variance_weights(cov: np.ndarray) -> np.ndarray:
    """min_w  w'Cov w   s.t.  sum(w) = 1,  w >= 0."""
    n = cov.shape[0]
    w0 = np.repeat(1.0 / n, n)
    bounds = [(0.0, 1.0)] * n
    cons = ({"type": "eq", "fun": lambda w: w.sum() - 1.0},)
    res = minimize(
        lambda w: float(w @ cov @ w),
        w0, method="SLSQP", bounds=bounds, constraints=cons,
        options={"maxiter": 1000, "ftol": 1e-12},
    )
    return res.x


def _risk_parity_weights(cov: np.ndarray) -> np.ndarray:
    """Equal-risk-contribution (risk parity) weights, long-only, fully invested.

    Convex log-barrier formulation (Spinu, 2013): minimise
    0.5 w'Cov w - (1/n) sum(ln w_i) over w > 0, then normalise to sum 1. At the
    optimum every asset contributes an equal share of portfolio variance - a
    diversification-by-risk rule that ignores the mean, so it sidesteps the noisy
    expected-return estimate the max-Sharpe fund depends on.
    """
    n = cov.shape[0]
    w0 = np.repeat(1.0 / n, n)

    def obj(w):
        return 0.5 * float(w @ cov @ w) - np.mean(np.log(w))

    def grad(w):
        return cov @ w - 1.0 / (n * w)

    res = minimize(obj, w0, jac=grad, method="L-BFGS-B",
                   bounds=[(1e-9, None)] * n, options={"maxiter": 10_000, "ftol": 1e-15})
    w = np.clip(res.x, 1e-12, None)
    return w / w.sum()


def _max_sharpe_weights(mu: np.ndarray, cov: np.ndarray, rf: float = RISK_FREE) -> np.ndarray:
    """max_w  (w'mu - rf) / sqrt(w'Cov w)   s.t.  sum(w) = 1,  w >= 0.

    Solved by minimising the negative Sharpe ratio. The objective is non-convex,
    so this is a single equal-weight-start local solve - adequate under the
    long-only constraint, and the estimation-error robustness (shrinkage) is an
    innovation, not core.
    """
    n = len(mu)
    w0 = np.repeat(1.0 / n, n)
    bounds = [(0.0, 1.0)] * n
    cons = ({"type": "eq", "fun": lambda w: w.sum() - 1.0},)

    def neg_sharpe(w: np.ndarray) -> float:
        vol = np.sqrt(w @ cov @ w)
        if vol <= 0:
            return 0.0
        return -float((w @ mu - rf) / vol)

    res = minimize(
        neg_sharpe, w0, method="SLSQP", bounds=bounds, constraints=cons,
        options={"maxiter": 1000, "ftol": 1e-12},
    )
    return res.x


def optimize_weights(window_returns: pd.DataFrame, method: str, cov_estimator=None) -> pd.Series:
    """Long-only, fully-invested weights from one window of daily returns.

    NaN rule (the stated safety net): only assets with a COMPLETE history over the
    window enter the optimisation; any asset carrying a NaN in the window is
    dropped from that estimation. With the full Part B panel this drops nothing -
    every asset has a return on every trading day after row 0 - but it is an
    explicit rule, not a silent fillna.

    ``cov_estimator(R) -> np.ndarray`` optionally replaces the sample covariance
    with another estimator on the same clean window (the Step 8 covariance
    shrinkage innovation uses it). ``None`` keeps the sample covariance, so the
    two core funds and the look-ahead probe are byte-for-byte unchanged. The mean
    ``mu`` is never shrunk - shrinkage acts on the covariance only.
    """
    cols = window_returns.columns[window_returns.notna().all()]
    R = window_returns[cols]
    mu = R.mean().to_numpy()
    cov = R.cov().to_numpy() if cov_estimator is None else np.asarray(cov_estimator(R))

    if method == "min_variance":
        w = _min_variance_weights(cov)
    elif method == "max_sharpe":
        w = _max_sharpe_weights(mu, cov)
    elif method == "risk_parity":
        w = _risk_parity_weights(cov)
    else:
        raise ValueError(f"method must be one of {ALL_METHODS}, got {method!r}")

    w = np.clip(w, 0.0, None)          # scrub tiny negative numerical dust
    w = w / w.sum()                    # renormalise to sum exactly 1
    return pd.Series(w, index=cols, name=method)


# --- The walk-forward backtest -------------------------------------------------

def rebalance_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """The first trading day of each month present in ``index``."""
    idx = pd.DatetimeIndex(index)
    firsts = pd.Series(idx, index=idx.to_period("M")).groupby(level=0).min()
    return pd.DatetimeIndex(sorted(firsts.to_numpy()))


def oos_backtest(
    panel: pd.DataFrame, method: str, window: int = WINDOW, peek: int = 0,
    weight_fn=None, cov_estimator=None, weights_builder=None,
) -> tuple[pd.Series, pd.DataFrame, dict]:
    """Walk-forward out-of-sample backtest of one fund.

    Returns (daily_oos_returns, weights_long, meta). ``peek`` is 0 for the honest
    run; a positive ``peek`` shifts the estimation window forward by that many
    days (into the future) and is used ONLY by the look-ahead probe.

    ``weight_fn(weights, date) -> weights`` is an optional hook applied to each
    rebalance's target weights before they are held - the sentiment fusion
    (fusion.py) uses it to tilt the equity sleeve. It must return a long-only,
    fully-invested weight Series; this keeps the sentiment logic out of the
    optimiser.

    ``weights_builder(window_returns, method) -> weights`` optionally REPLACES the
    single-stage ``optimize_weights`` call with another rule on the same clean
    window (the Step 8 two-stage portfolio-of-portfolios uses it to build a
    60-asset weight from a nested equity/crypto/sleeve solve). ``None`` keeps the
    default single-stage optimiser, so the core funds are unchanged. It must
    return a long-only, fully-invested weight Series over the window's assets.
    """
    panel = panel.sort_index()
    idx = panel.index
    n = len(idx)

    # Target weights active from each rebalance date that has a full clean window.
    schedule: dict[pd.Timestamp, pd.Series] = {}
    for d in rebalance_dates(idx):
        i = idx.get_loc(d)
        start, end = i - window + peek, i + peek
        # start >= 1 keeps row 0 (the all-NaN first-return row) out of the window;
        # end <= n guards the shifted probe near the end of the sample.
        if start < 1 or end > n:
            continue
        window_returns = panel.iloc[start:end]
        if weights_builder is None:
            w = optimize_weights(window_returns, method, cov_estimator=cov_estimator)
        else:
            w = weights_builder(window_returns, method)
        if weight_fn is not None:
            w = weight_fn(w, d)
        schedule[d] = w

    if not schedule:
        raise RuntimeError(f"{method}: no rebalance had a full {window}-day window")

    # Daily OOS returns, constant-weight to target between rebalances.
    daily: dict[pd.Timestamp, float] = {}
    active: pd.Series | None = None
    for d in idx:
        if d in schedule:
            active = schedule[d]
        if active is None:
            continue
        r = panel.loc[d, active.index].fillna(0.0).to_numpy()   # fillna is a no-op here
        daily[d] = float(active.to_numpy() @ r)

    # Default combined name; run_part_b overrides it per (family, method).
    default_name = FUND_NAME.get(method, f"Combined_{METHOD_LABEL.get(method, method)}")
    daily_returns = pd.Series(daily, name=default_name).sort_index()
    daily_returns.index.name = "date"

    weights_long = (
        pd.concat({d: w for d, w in schedule.items()}, names=["rebalance_date", "ticker"])
        .rename("weight").reset_index().round({"weight": 6})
    )

    live = pd.DatetimeIndex(sorted(schedule))
    meta = {
        "method": method,
        "fund": default_name,
        "n_rebalances": len(schedule),
        "first_live_date": live[0],
        "last_rebalance": live[-1],
        "n_oos_days": len(daily_returns),
        "oos_start": daily_returns.index.min(),
        "oos_end": daily_returns.index.max(),
    }
    return daily_returns, weights_long, meta


def performance_metrics(
    daily_returns: pd.Series, periods_per_year: int = TRADING_DAYS, rf: float = RISK_FREE
) -> dict:
    """Annualised return, annualised volatility, Sharpe, and maximum drawdown.

    (Step 2 uses this for the look-ahead probe and a preview; Step 3 writes the
    official performance_metrics.csv.)
    """
    r = daily_returns.dropna()
    mean_ann = float(r.mean() * periods_per_year)
    vol_ann = float(r.std() * np.sqrt(periods_per_year))
    sharpe = (mean_ann - rf) / vol_ann if vol_ann > 0 else float("nan")
    growth = (1.0 + r).cumprod()
    drawdown = growth / growth.cummax() - 1.0
    return {
        "ann_return": mean_ann,
        "ann_vol": vol_ann,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
        "n_days": int(len(r)),
    }


def lookahead_probe(panel: pd.DataFrame, method: str = "min_variance", peek: int = 1) -> dict:
    """Prove the honest backtest uses only past data.

    Re-run the fund with the estimation window shifted ``peek`` days into the
    future. If the honest and peeking return series are identical, weights did not
    actually depend on the window boundary - a look-ahead leak. They must differ.
    """
    honest, _, _ = oos_backtest(panel, method, peek=0)
    cheat, _, _ = oos_backtest(panel, method, peek=peek)
    common = honest.index.intersection(cheat.index)
    differ = not np.allclose(honest.loc[common].to_numpy(), cheat.loc[common].to_numpy())
    return {
        "method": method,
        "peek_days": peek,
        "honest_sharpe": performance_metrics(honest)["sharpe"],
        "peek_sharpe": performance_metrics(cheat)["sharpe"],
        "series_differ": differ,
    }

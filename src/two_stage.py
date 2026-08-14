"""Step 8 innovation - two-stage portfolio of portfolios.

The core funds optimise over all 60 assets at once, estimating a single 60x60
covariance (1,830 free parameters). This extension asks a structural question
instead of adding a variant: build an equity-only fund and a crypto-only fund
first, then allocate across just those two sleeves. The cross-asset decision then
rests on a 2x2 covariance - three parameters - so it carries far less estimation
error, but it discards the equity-crypto cross-covariance the one-stage fund
uses. Which effect wins out of sample is not obvious in advance, and either
answer is a result worth reporting.

The comparison is like-for-like: same 252-day rolling window, same first-of-month
rebalance, the SAME method at both stages, and the same out-of-sample period as
the one-stage fund (both need one 252-day window before the first live date).
Only the one-stage-vs-two-stage structure moves.

Per rebalance date t, using only returns strictly before t:
  1. stage 1 - optimise equity-only weights (50 assets) and crypto-only weights
     (10 assets) under the method;
  2. build each sleeve's synthetic return series over the window from those
     weights;
  3. stage 2 - optimise the 2x2 over the two sleeves under the method, giving the
     sleeve allocation (a_eq, a_cr);
  4. combine to a 60-asset long-only weight vector, a_eq * w_eq for equities and
     a_cr * w_cr for crypto, which sums to 1.

The synthetic sleeve series in step 2 applies each rebalance's stage-1 weights
across the whole estimation window (it assumes the current sleeve composition to
measure the sleeve's own risk). Everything used is strictly inside [t-252, t-1],
so there is no look-ahead; the assumption is stated in the report.
"""
from __future__ import annotations

import pandas as pd

from src import portfolios

TWO_STAGE_NAME = {
    "min_variance": "Combined_TwoStage_MinVariance",
    "max_sharpe": "Combined_TwoStage_MaxSharpe",
}


def two_stage_weights(
    window_returns: pd.DataFrame, method: str,
    equity_cols: list[str], crypto_cols: list[str],
) -> pd.Series:
    """One rebalance's 60-asset weights from the nested equity/crypto/sleeve solve."""
    cols = window_returns.columns[window_returns.notna().all()]
    R = window_returns[cols]
    eq = [c for c in equity_cols if c in cols]
    cr = [c for c in crypto_cols if c in cols]

    w_eq = portfolios.optimize_weights(R[eq], method)   # sums to 1 over equities
    w_cr = portfolios.optimize_weights(R[cr], method)   # sums to 1 over crypto

    sleeve = pd.DataFrame({
        "equity": R[eq].to_numpy() @ w_eq.to_numpy(),
        "crypto": R[cr].to_numpy() @ w_cr.to_numpy(),
    }, index=R.index)
    a = portfolios.optimize_weights(sleeve, method)     # [equity, crypto] sleeve split

    combined = pd.concat([w_eq * a["equity"], w_cr * a["crypto"]])
    return combined.reindex(cols).fillna(0.0)


def _cov_param_counts(n_all: int, n_eq: int, n_cr: int) -> dict:
    """Free parameters in each structure's covariance estimate(s).

    A k-asset covariance has k*(k+1)/2 distinct entries. The headline contrast is
    the cross-asset decision: one 60x60 for the one-stage fund versus a single 2x2
    across the sleeves for the two-stage fund.
    """
    tri = lambda k: k * (k + 1) // 2
    return {
        "one_stage_total": tri(n_all),
        "one_stage_cross": tri(n_all),
        "two_stage_total": tri(n_eq) + tri(n_cr) + tri(2),
        "two_stage_cross": tri(2),
    }


def run_two_stage(
    panel: pd.DataFrame, equity_cols: list[str], crypto_cols: list[str],
) -> dict:
    """Backtest both methods as two-stage funds, like-for-like with the core.

    Returns a dict keyed by method, each with the two-stage fund name, daily OOS
    returns, long weights, meta, and the covariance parameter counts for the
    report's mechanism line.
    """
    counts = _cov_param_counts(len(equity_cols) + len(crypto_cols),
                               len(equity_cols), len(crypto_cols))
    out = {}
    for method in portfolios.METHODS:
        def builder(wr, m, eq=equity_cols, cr=crypto_cols):
            return two_stage_weights(wr, m, eq, cr)

        dr, wdf, meta = portfolios.oos_backtest(panel, method, weights_builder=builder)
        out[method] = {
            "name": TWO_STAGE_NAME[method],
            "returns": dr,
            "weights": wdf,
            "meta": meta,
        }
    out["_param_counts"] = counts
    return out

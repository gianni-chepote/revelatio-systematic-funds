"""Smoke test for Part B: imports resolve, artifacts exist, invariants hold.

    python tests/test_smoke.py

The invariant checks read the committed results/ artifacts (fast, offline). The
final check re-runs the look-ahead probe and is skipped gracefully if the raw
data is not reachable (needs network or FINS_DATA_ZIP on first load).
"""
import sys
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import data_access, etl, features, portfolios, sentiment, fusion  # noqa: E402
from src import plot_style as ps  # noqa: E402

DATA = ROOT / "results" / "data"
TABLES = ROOT / "results" / "tables"
FIGURES = ROOT / "results" / "figures"

REQUIRED = [
    DATA / "fund_returns.csv", DATA / "fund_weights.csv",
    DATA / "sector_sentiment_index.csv", TABLES / "performance_metrics.csv",
]
SECTORS = 10
PANEL_ROWS = 1_006
OOS_DAYS = 753
# The fund grid: three families x three methods, plus the two Step 8b two-stage
# funds. Fusion (Step 5) and the two-stage comparison run on the combined core only.
GRID_FUNDS = {f"{fam}_{m}" for fam in ("Equity", "Crypto", "Combined")
              for m in ("MinVariance", "MaxSharpe", "RiskParity")}
CORE_FUNDS = {"Combined_MinVariance", "Combined_MaxSharpe"}
TWO_STAGE_FUNDS = {"Combined_TwoStage_MinVariance", "Combined_TwoStage_MaxSharpe"}
TWO_STAGE_TABLE_FUNDS = CORE_FUNDS | TWO_STAGE_FUNDS   # one-stage vs two-stage pairs
FUNDS = GRID_FUNDS | TWO_STAGE_FUNDS


def test_imports():
    for mod, attr in [(data_access, "load_equity_prices"), (etl, "load_clean_equities"),
                      (features, "combined_return_panel"), (portfolios, "oos_backtest"),
                      (sentiment, "sector_sentiment_index"), (fusion, "build_sentiment_tilt"),
                      (ps, "revelatio_style")]:
        assert hasattr(mod, attr), f"{mod.__name__}.{attr} missing"


def test_required_outputs_exist():
    missing = [str(p.relative_to(ROOT)) for p in REQUIRED if not p.exists()]
    assert not missing, f"missing required outputs (run scripts/run_part_b.py): {missing}"


def test_combined_panel():
    panel = pd.read_csv(DATA / "combined_returns_panel.csv", index_col=0)
    assert panel.shape == (PANEL_ROWS, 60), f"panel shape {panel.shape} != ({PANEL_ROWS}, 60)"


def test_fund_returns():
    fr = pd.read_csv(DATA / "fund_returns.csv", index_col=0)
    assert set(fr.columns) == FUNDS, f"funds {set(fr.columns)} != {FUNDS}"
    assert len(fr) == OOS_DAYS, f"OOS days {len(fr)} != {OOS_DAYS}"


def test_fund_weights_valid():
    fw = pd.read_csv(DATA / "fund_weights.csv")
    assert set(fw.fund.unique()) == FUNDS
    wsum = fw.groupby(["fund", "rebalance_date"])["weight"].sum()
    assert np.allclose(wsum.to_numpy(), 1.0, atol=1e-6), "weights do not sum to 1"
    assert (fw.weight >= -1e-9).all(), "found a short weight (long-only violated)"


def test_sentiment_index():
    si = pd.read_csv(DATA / "sector_sentiment_index.csv", index_col=0)
    assert si.shape[1] == SECTORS, f"{si.shape[1]} sectors != {SECTORS}"
    assert si.to_numpy().min() >= -1 and si.to_numpy().max() <= 1, "VADER compound out of [-1, 1]"


def test_performance_metrics():
    m = pd.read_csv(TABLES / "performance_metrics.csv")
    assert set(m.fund) == FUNDS
    for col in ("ann_return", "ann_vol", "sharpe", "max_drawdown"):
        assert col in m.columns, f"performance_metrics missing {col}"


def test_fusion_comparison():
    f = pd.read_csv(TABLES / "fusion_comparison.csv")
    assert set(f.variant.unique()) == {"base", "sentiment"}, "fusion table needs base + sentiment"
    assert set(f.fund.unique()) == CORE_FUNDS, "fusion is core-only (sentiment tilts the equity sleeve)"


def test_two_stage_comparison():
    """Step 8b innovation: one-stage vs two-stage, like-for-like."""
    t = pd.read_csv(TABLES / "two_stage_comparison.csv")
    assert set(t.structure.unique()) == {"one_stage", "two_stage"}
    assert set(t.fund.unique()) == TWO_STAGE_TABLE_FUNDS, "pairs both core funds with their two-stage twins"
    # The two-stage cross-asset decision rests on a 2x2 (3 params); one-stage on 60x60.
    two = t[t.structure == "two_stage"]
    assert (two.cross_asset_cov_params == 3).all(), "two-stage cross-asset cov must be 2x2 (3 params)"


def test_shrinkage_exhibit():
    """Step 8a innovation: the before-vs-after artifacts exist and are sane."""
    comp = pd.read_csv(TABLES / "shrinkage_comparison.csv")
    assert set(comp.variant.unique()) == {"sample", "shrunk"}, "need sample + shrunk"
    diag = pd.read_csv(TABLES / "shrinkage_diagnostics.csv")
    shrunk = diag[diag.variant == "shrunk"]
    assert ((shrunk.mean_delta > 0) & (shrunk.mean_delta <= 1)).all(), \
        "shrinkage intensity delta must lie in (0, 1]"
    sr = pd.read_csv(DATA / "shrinkage_fund_returns.csv", index_col=0)
    assert set(sr.columns) == {"Combined_MinVariance_Shrunk", "Combined_MaxSharpe_Shrunk"}


def test_decay_exhibit():
    """Step 8c innovation: decay before-vs-after and sweep exist and are sane."""
    d = pd.read_csv(TABLES / "decay_comparison.csv")
    assert set(d.variant.unique()) == {"base", "sentiment_neutral0", "sentiment_decay"}
    assert set(d.fund.unique()) == CORE_FUNDS, "decay fusion is core-only"
    sw = pd.read_csv(TABLES / "decay_halflife_sweep.csv")
    assert set(sw.half_life.unique()) == {2, 5, 10, 21}, "sweep needs all four half-lives"
    di = pd.read_csv(DATA / "sector_sentiment_index_decay.csv", index_col=0)
    assert di.shape[1] == SECTORS
    assert di.to_numpy().min() >= -1 and di.to_numpy().max() <= 1, "decayed index out of [-1, 1]"


def test_benchmark():
    """Step 8d: the passive benchmark aligns with the funds and scores them."""
    b = pd.read_csv(DATA / "benchmark_returns.csv", index_col=0)
    assert list(b.columns) == ["EqualWeight50"], f"benchmark cols {list(b.columns)}"
    assert len(b) == OOS_DAYS, f"benchmark days {len(b)} != {OOS_DAYS} (must match funds)"
    bc = pd.read_csv(TABLES / "benchmark_comparison.csv")
    assert set(bc.fund.unique()) == FUNDS, "every app fund is scored against the benchmark"
    for col in ("excess_ann_return", "sharpe_minus_bench", "beats_benchmark"):
        assert col in bc.columns, f"benchmark_comparison missing {col}"


def test_no_lookahead_probe():
    """Re-run the look-ahead probe end to end. Skipped if data is unreachable."""
    try:
        eq, _ = etl.load_clean_equities()
        cr, _ = etl.load_clean_crypto()
    except Exception as e:  # noqa: BLE001
        print(f"  [skip] test_no_lookahead_probe (data unreachable: {e})")
        return
    panel, _ = features.combined_return_panel(eq, cr)
    probe = portfolios.lookahead_probe(panel, "min_variance", peek=1)
    assert probe["series_differ"], "look-ahead probe: peeking did not change the series"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        t()
        print(f"  OK  {t.__name__}")
        passed += 1
    print(f"\n{passed} smoke tests passed.")

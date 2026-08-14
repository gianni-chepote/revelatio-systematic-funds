"""Smoke test for the Streamlit app: every page renders without a runtime error.

    python -m pytest tests/test_app_smoke.py

Uses streamlit.testing.v1.AppTest headless. The app routes on
st.session_state["page"], so each page (and the fund-detail drill-down) is driven
by setting session_state and re-running - default-page tests alone would miss
runtime errors hidden on the other pages. Skipped gracefully if the app artifacts
are missing (run scripts/run_part_b.py first).
"""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "streamlit_app.py"
REQUIRED = [
    ROOT / "results" / "data" / "fund_returns.csv",
    ROOT / "results" / "data" / "benchmark_returns.csv",
    ROOT / "results" / "data" / "fund_weights.csv",
    ROOT / "results" / "tables" / "performance_metrics.csv",
]

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in REQUIRED),
    reason="app artifacts missing - run scripts/run_part_b.py first",
)

PAGES = ["Home", "Funds", "Sentiment", "Build portfolio", "About"]


def _run(page=None, selected_fund=None):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    if page is not None:
        at.session_state["page"] = page
        at.session_state["selected_fund"] = selected_fund
        at.run()
    return at


def test_home_loads():
    at = _run()
    assert not at.exception, at.exception


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders(page):
    at = _run(page=page)
    assert not at.exception, f"{page}: {at.exception}"


def test_fund_detail_renders():
    at = _run(page="Funds", selected_fund="Combined_TwoStage_MaxSharpe")
    assert not at.exception, at.exception
    # the detail view has an Overview/Performance/Holdings tab set
    assert len(at.tabs) >= 3, "fund detail should show three tabs"


def test_allocation_has_sliders():
    at = _run(page="Build portfolio")
    assert len(at.slider) >= 3, "allocation needs a slider per multi-asset fund"
    at.slider[0].set_value(50).run()
    assert not at.exception, at.exception

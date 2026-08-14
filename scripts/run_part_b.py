"""Reproduce every Part B result with one command. Run from the project root:

    python scripts/run_part_b.py

Writes app/report artifacts under results/data/, results/tables/, and
results/figures/. The three datasets arrive through src/data_access.py; no raw
data is read or committed.

The script self-verifies as Part A did: it prints the counts that matter beside
their expected values from context/DATA_GUIDE.md and exits non-zero on drift, so
a clean run is itself the evidence that the foundation is current.

Build order (BUILD_PLAN.md):
  Step 1  data foundation  -> results/data/combined_returns_panel.csv   [DONE]
  Step 2  funds + backtest -> results/data/fund_returns.csv, fund_weights.csv
  Step 3  fact-sheet stats -> results/tables/performance_metrics.csv + figures
  Step 4  sentiment index  -> results/data/sector_sentiment_index.csv
  Step 5  fusion           -> before/after table + figure
"""
from __future__ import annotations

import sys
import pathlib

import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import etl, features, portfolios, sentiment, fusion, shrinkage, two_stage, benchmark  # noqa: E402
from src import plot_style as ps  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
TABLES = ROOT / "results" / "tables"
FIGURES = ROOT / "results" / "figures"
DATA = ROOT / "results" / "data"

# Fund colours: one gilded series carries the point; the other is a genuine
# second category (verdigris), never a third saturated colour.
FUND_COLOR = {
    "Combined_MaxSharpe": ps.REVELATIO["gilt"],
    "Combined_MinVariance": ps.REVELATIO["verdigris"],
}
OOS_SAMPLE = "2021-01-04 to 2023-12-29"


def _short(fund: str) -> str:
    return fund.replace("Combined_", "")


def _flabel(fund: str) -> str:
    """Readable label for a fund key: 'Combined_MaxSharpe' -> 'Max-Sharpe',
    'Equity_RiskParity' -> 'Equity Risk Parity', two-stage names handled too."""
    fam = ""
    for f in ("Equity_", "Crypto_", "Combined_"):
        if fund.startswith(f):
            fam, rest = f[:-1], fund[len(f):]
            break
    else:
        rest = fund
    rest = (rest.replace("TwoStage_", "Two-Stage ").replace("MinVariance", "Min-Variance")
            .replace("MaxSharpe", "Max-Sharpe").replace("RiskParity", "Risk Parity"))
    return rest if fam in ("", "Combined") else f"{fam} {rest}"


# --- Step 3 figures ------------------------------------------------------------

def figure_growth(fund_returns: pd.DataFrame, path: pathlib.Path,
                  benchmark_returns: pd.Series | None = None) -> pathlib.Path:
    """Growth of $1 from the first out-of-sample rebalance, comparing the methods.

    Generic over whatever funds are passed (the combined family's three methods by
    default). The best-ending fund carries the accent; ``benchmark_returns`` adds
    the equal-weight market as a dashed reference.
    """
    growth = (1 + fund_returns).cumprod()
    finals = {c: growth[c].iloc[-1] for c in growth.columns}
    hero = max(finals, key=finals.get)
    palette = [ps.REVELATIO["verdigris"], ps.REVELATIO["rubric"], ps.REVELATIO["ink_soft"],
               ps.REVELATIO["gilt_light"]]
    color = {c: (ps.REVELATIO["gilt"] if c == hero else palette[i % len(palette)])
             for i, c in enumerate(growth.columns)}
    with ps.revelatio_style():
        fig, ax = ps.new_figure("full_width")
        if benchmark_returns is not None:
            bg = (1 + benchmark_returns.reindex(fund_returns.index).fillna(0.0)).cumprod()
            ax.plot(bg.index, bg, color=ps.REVELATIO["muted"], linewidth=1.5,
                    linestyle="--", zorder=2, label="EW-50 market")
            ax.annotate(f"${bg.iloc[-1]:.2f}", (bg.index[-1], bg.iloc[-1]),
                        xytext=(6, 0), textcoords="offset points", fontsize=8.5,
                        color=ps.REVELATIO["muted"], va="center",
                        fontweight="bold", annotation_clip=False)
        for col in growth.columns:
            ax.plot(growth.index, growth[col], color=color[col],
                    linewidth=2.4 if col == hero else 1.9,
                    zorder=5 if col == hero else 3, label=_flabel(col))
        ax.set_ylabel("Value of $1 invested")
        ps.date_axis(ax)
        span = growth.index[-1] - growth.index[0]
        ax.set_xlim(growth.index[0] - span * 0.01, growth.index[-1] + span * 0.05)
        for col, end in finals.items():
            ax.annotate(f"${end:.2f}", (growth.index[-1], end),
                        xytext=(6, 0), textcoords="offset points", fontsize=8.5,
                        color=color[col], va="center", fontweight="bold", annotation_clip=False)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10),
                  ncol=len(growth.columns) + (benchmark_returns is not None), fontsize=8.5)
        bench_note = ""
        if benchmark_returns is not None:
            bg = (1 + benchmark_returns.reindex(fund_returns.index).fillna(0.0)).cumprod()
            bench_note = f", vs ${bg.iloc[-1]:.2f} for the equal-weight market"
        ps.stamp(
            fig, ax,
            f"$1 grew to ${finals[hero]:.2f} at {_flabel(hero)}, the best of the "
            f"{len(growth.columns)} combined methods{bench_note}",
            "Growth of $1 at the first out-of-sample rebalance, combined funds by "
            "method and the equal-weight market",
            units="index, $1 at 2021-01-04", sample=OOS_SAMPLE, source_y=-48,
        )
        return ps.save(fig, path)


def figure_drawdown(fund_returns: pd.DataFrame, path: pathlib.Path) -> pathlib.Path:
    """Drawdown paths (peak-to-trough decline) for both funds."""
    growth = (1 + fund_returns).cumprod()
    dd = growth / growth.cummax() - 1.0
    troughs = {c: dd[c].min() for c in dd.columns}
    with ps.revelatio_style():
        fig, ax = ps.new_figure("full_width")
        # Fill only the deeper fund (MaxSharpe) - two overlapping "underwater"
        # fills on one baseline muddy each other, so the shallower fund is a
        # clean line above the shaded region.
        for col in dd.columns:
            c = FUND_COLOR.get(col, ps.REVELATIO["muted"])
            is_hero = col == "Combined_MaxSharpe"
            ax.plot(dd.index, dd[col], color=c, linewidth=2.2 if is_hero else 1.6,
                    zorder=6 if is_hero else 5, label=_short(col))
            if is_hero:
                ax.fill_between(dd.index, dd[col], 0, color=c, alpha=0.15, zorder=1)
        ax.axhline(0, color=ps.REVELATIO["rule"], linewidth=0.8)
        ax.set_ylabel("Drawdown")
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
        ps.date_axis(ax)
        # Annotate only the filled hero fund's trough; the shallower fund's -16%
        # is in the title, and a second label lands in the busy mid-chart scribble.
        hero = "Combined_MaxSharpe"
        h_date = dd[hero].idxmin()
        ax.annotate(f"{troughs[hero]:.0%} ({h_date:%b %Y})", (h_date, troughs[hero]),
                    xytext=(4, -3), textcoords="offset points", fontsize=8.5,
                    color=FUND_COLOR[hero], va="top", fontweight="bold")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2, fontsize=9)
        ps.stamp(
            fig, ax,
            f"Maximum-Sharpe fell {abs(troughs['Combined_MaxSharpe']):.0%} at its worst, "
            f"minimum-variance {abs(troughs['Combined_MinVariance']):.0%}",
            "Drawdown from the running peak, two combined funds",
            units="peak-to-trough decline", sample=OOS_SAMPLE, source_y=-48,
        )
        return ps.save(fig, path)


def figure_weights(fund_weights: pd.DataFrame, fund: str, path: pathlib.Path) -> pathlib.Path:
    """Portfolio weights over time for one fund: top holdings, rest as 'Other'."""
    w = (fund_weights[fund_weights.fund == fund]
         .pivot(index="rebalance_date", columns="ticker", values="weight").fillna(0.0))
    # Six named holdings only. The space above the stack is the remainder held
    # across other names (weights still sum to 1); a solid "Other" band would be
    # the largest, least informative shape on the chart, so it is left blank.
    # The wiggling top edge then reads as concentration in the top names.
    top = w.mean().sort_values(ascending=False).head(6).index.tolist()
    stack = w[top]
    colors = [
        ps.REVELATIO["gilt"], ps.REVELATIO["verdigris"], ps.REVELATIO["rubric"],
        ps.REVELATIO["ink_soft"], ps.REVELATIO["gilt_light"], ps.REVELATIO["ink"],
    ][:len(top)]
    with ps.revelatio_style():
        fig, ax = ps.new_figure("full_width")
        ax.stackplot(stack.index, stack.T.to_numpy(), labels=list(stack.columns), colors=colors)
        ax.set_ylabel("Portfolio weight")
        ax.set_ylim(0, 1)
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
        ps.date_axis(ax)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=6, fontsize=8)
        ps.stamp(
            fig, ax,
            f"{_short(fund)} concentrates in a handful of names, rotating them each rebalance",
            f"Target weights over time, {_short(fund)} fund - top 6 holdings "
            "(space above the stack = held across other names)",
            units="weight; portfolio sums to 1", sample=OOS_SAMPLE, source_y=-48,
        )
        return ps.save(fig, path)


def figure_sentiment(sector_index: pd.DataFrame, path: pathlib.Path) -> pathlib.Path:
    """Sector sentiment over time: the market average gilded, sectors faint behind.

    Daily sector sentiment is noisy, so the exhibit shows a monthly average for
    legibility (the CSV keeps the daily series). The market line is the mean
    across the ten sectors.
    """
    monthly = sector_index.resample("ME").mean()
    market = monthly.mean(axis=1)
    with ps.revelatio_style():
        fig, ax = ps.new_figure("full_width")
        for col in monthly.columns:
            ax.plot(monthly.index, monthly[col], color=ps.REVELATIO["muted"],
                    linewidth=0.9, alpha=0.55, zorder=2)
        ax.plot(market.index, market, color=ps.REVELATIO["gilt"], linewidth=2.6,
                zorder=6, label="Equity-market average")
        ax.axhline(0, color=ps.REVELATIO["rule"], linewidth=0.8, zorder=1)
        ax.set_ylabel("VADER compound sentiment")
        ps.date_axis(ax)
        ax.annotate("10 sectors", (monthly.index[1], monthly.iloc[1].max()),
                    xytext=(4, 6), textcoords="offset points", fontsize=8,
                    color=ps.REVELATIO["muted"])
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=1, fontsize=9)
        ps.stamp(
            fig, ax,
            f"Headline sentiment held mildly positive ({market.min():.2f}-{market.max():.2f}), "
            "barely reacting to the 2022 selloff",
            "Monthly equal-weight sentiment index, ten equity sectors (faint) and their "
            "average (gilded)",
            units="VADER compound in [-1, 1]; 0 = neutral",
            sample="2020-01-02 to 2023-12-29", source_y=-48,
        )
        return ps.save(fig, path)


def figure_fusion(base_dr: pd.Series, aug_dr: pd.Series, fund: str,
                  base_sharpe: float, aug_sharpe: float, path: pathlib.Path) -> pathlib.Path:
    """Growth of $1: base fund vs its sentiment-augmented variant."""
    common = base_dr.index.intersection(aug_dr.index)
    g_base = (1 + base_dr.loc[common]).cumprod()
    g_aug = (1 + aug_dr.loc[common]).cumprod()
    with ps.revelatio_style():
        fig, ax = ps.new_figure("full_width")
        ax.plot(g_base.index, g_base, color=ps.REVELATIO["muted"], linewidth=1.9,
                zorder=3, label="Base")
        ax.plot(g_aug.index, g_aug, color=ps.REVELATIO["gilt"], linewidth=2.4,
                zorder=6, label="Sentiment-tilted")
        ax.set_ylabel("Value of $1 invested")
        ps.date_axis(ax)
        span = g_base.index[-1] - g_base.index[0]
        ax.set_xlim(g_base.index[0] - span * 0.01, g_base.index[-1] + span * 0.05)
        for series, col, lab in ((g_base, ps.REVELATIO["muted"], "base"),
                                 (g_aug, ps.REVELATIO["gilt"], "aug")):
            ax.annotate(f"${series.iloc[-1]:.2f}", (series.index[-1], series.iloc[-1]),
                        xytext=(6, 0), textcoords="offset points", fontsize=8.5,
                        color=col, va="center", fontweight="bold", annotation_clip=False)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2, fontsize=9)
        delta = aug_sharpe - base_sharpe
        verdict = "lifted" if delta > 0.01 else "barely moved" if abs(delta) <= 0.01 else "dragged on"
        ps.stamp(
            fig, ax,
            f"The sentiment tilt {verdict} {_short(fund)}: Sharpe {base_sharpe:.2f} -> {aug_sharpe:.2f}",
            f"Growth of $1, {_short(fund)} base vs sentiment-tilted (equity sleeve, lambda=0.5, "
            "lagged >= 1 day)",
            units="index, $1 at 2021-01-04", sample=OOS_SAMPLE, source_y=-48,
        )
        return ps.save(fig, path)


FAMILY_COLOR = {"Equity": None, "Crypto": None, "Combined": None}   # filled at call time


def _family_of(fund: str) -> str:
    for f in ("Equity", "Crypto", "Combined"):
        if fund.startswith(f):
            return f
    return "Combined"


def figure_sharpe_bar(metrics: pd.DataFrame, path: pathlib.Path,
                      bench_sharpe: float | None = None) -> pathlib.Path:
    """Sharpe ratio across every fund and method, coloured by family, with the
    market Sharpe as a reference line. Funds are ordered family, then method."""
    order = {"Equity": 0, "Crypto": 1, "Combined": 2}
    m = metrics.set_index("fund")["sharpe"]
    m = m.reindex(sorted(m.index, key=lambda f: (order.get(_family_of(f), 3), -m[f])))
    fam_col = {"Equity": ps.REVELATIO["verdigris"], "Crypto": ps.REVELATIO["rubric"],
               "Combined": ps.REVELATIO["gilt"]}
    with ps.revelatio_style():
        fig, ax = ps.new_figure("full_width")
        colors = [fam_col[_family_of(f)] for f in m.index]
        bars = ax.bar([_flabel(f) for f in m.index], m.to_numpy(), color=colors, width=0.7)
        ax.set_ylabel("Sharpe ratio (annualised, rf = 0)")
        ax.grid(axis="x", visible=False)
        for lab in ax.get_xticklabels():
            lab.set_rotation(40)
            lab.set_ha("right")
            lab.set_fontsize(7.5)
        for b, v in zip(bars, m.to_numpy()):
            ax.annotate(f"{v:.2f}", (b.get_x() + b.get_width() / 2, v),
                        xytext=(0, 2), textcoords="offset points", ha="center",
                        fontsize=7, fontweight="bold", color=ps.REVELATIO["ink"])
        n_beat = None
        if bench_sharpe is not None:
            ax.axhline(bench_sharpe, color=ps.REVELATIO["ink"], linewidth=1.3,
                       linestyle="--", zorder=6)
            ax.annotate(f"EW-50 market  {bench_sharpe:.2f}", (len(m) - 0.5, bench_sharpe),
                        xytext=(0, 3), textcoords="offset points", ha="right",
                        fontsize=8, color=ps.REVELATIO["ink"], fontweight="bold")
            n_beat = int((m > bench_sharpe).sum())
        # legend by family colour
        from matplotlib.patches import Patch
        ax.legend(handles=[Patch(color=fam_col[k], label=k) for k in ("Equity", "Crypto", "Combined")],
                  loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=3, fontsize=8, frameon=False)
        headline = (f"{n_beat} of {len(m)} funds beat the equal-weight market's Sharpe"
                    if n_beat is not None else "Sharpe ratio by fund and method")
        ps.stamp(
            fig, ax, headline,
            "Annualised Sharpe ratio by fund and method, coloured by family, "
            "against the equal-weight market",
            units="Sharpe, rf = 0", sample=OOS_SAMPLE, source_y=-64,
        )
        return ps.save(fig, path)


# --- Step 8a figures: covariance shrinkage (innovation) ------------------------

def figure_shrinkage_growth(entry: dict, path: pathlib.Path) -> pathlib.Path:
    """Growth of $1: one fund under the sample vs Ledoit-Wolf covariance."""
    base, shrunk = entry["base"], entry["shrunk"]
    common = base.index.intersection(shrunk.index)
    g_base = (1 + base.loc[common]).cumprod()
    g_shr = (1 + shrunk.loc[common]).cumprod()
    method_label = _short(entry["base_name"])
    with ps.revelatio_style():
        fig, ax = ps.new_figure("full_width")
        ax.plot(g_base.index, g_base, color=ps.REVELATIO["muted"], linewidth=1.9,
                zorder=3, label="Sample covariance")
        ax.plot(g_shr.index, g_shr, color=ps.REVELATIO["gilt"], linewidth=2.4,
                zorder=6, label="Ledoit-Wolf shrunk")
        ax.set_ylabel("Value of $1 invested")
        ps.date_axis(ax)
        span = g_base.index[-1] - g_base.index[0]
        ax.set_xlim(g_base.index[0] - span * 0.01, g_base.index[-1] + span * 0.05)
        for series, col in ((g_base, ps.REVELATIO["muted"]), (g_shr, ps.REVELATIO["gilt"])):
            ax.annotate(f"${series.iloc[-1]:.2f}", (series.index[-1], series.iloc[-1]),
                        xytext=(6, 0), textcoords="offset points", fontsize=8.5,
                        color=col, va="center", fontweight="bold", annotation_clip=False)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2, fontsize=9)
        delta = entry["shrunk_sharpe"] - entry["base_sharpe"]
        verdict = "lifted" if delta > 0.01 else "barely moved" if abs(delta) <= 0.01 else "dragged on"
        ps.stamp(
            fig, ax,
            f"Shrinkage {verdict} {method_label}: Sharpe "
            f"{entry['base_sharpe']:.2f} -> {entry['shrunk_sharpe']:.2f}",
            f"Growth of $1, {method_label} under sample vs Ledoit-Wolf covariance",
            units="index, $1 at 2021-01-04", sample=OOS_SAMPLE, source_y=-48,
        )
        return ps.save(fig, path)


def figure_shrinkage_dispersion(diagnostics: pd.DataFrame, path: pathlib.Path) -> pathlib.Path:
    """Effective number of holdings, sample vs shrunk, for both methods.

    effective N = 1 / sum(w^2): the count of equally weighted names the fund
    behaves like. Shrinkage pulls the extreme weights in, so the bars should
    rise - the mechanism behind any Sharpe change.
    """
    piv = diagnostics.pivot(index="method", columns="variant", values="effective_n")
    piv = piv.reindex(["min_variance", "max_sharpe"])
    labels = [portfolios.FUND_NAME[m].replace("Combined_", "") for m in piv.index]
    x = np.arange(len(piv))
    w = 0.36
    with ps.revelatio_style():
        fig, ax = ps.new_figure("full_width")
        b1 = ax.bar(x - w / 2, piv["sample"].to_numpy(), w, color=ps.REVELATIO["muted"],
                    label="Sample covariance")
        b2 = ax.bar(x + w / 2, piv["shrunk"].to_numpy(), w, color=ps.REVELATIO["gilt"],
                    label="Ledoit-Wolf shrunk")
        ax.set_ylabel("Effective number of holdings (1 / sum w²)")
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.grid(axis="x", visible=False)
        for bars in (b1, b2):
            for b in bars:
                ax.annotate(f"{b.get_height():.1f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                            xytext=(0, 3), textcoords="offset points", ha="center",
                            fontsize=9, fontweight="bold", color=ps.REVELATIO["ink"])
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2, fontsize=9)
        ps.stamp(
            fig, ax,
            "Shrinkage spreads each fund across more names",
            "Effective number of holdings by fund, sample vs Ledoit-Wolf covariance",
            units="1 / sum of squared weights, averaged over rebalances",
            sample=OOS_SAMPLE,
        )
        return ps.save(fig, path)


# --- Step 8b figures: two-stage portfolio of portfolios (innovation) -----------

def figure_two_stage_growth(one_dr: pd.Series, two_dr: pd.Series, method_label: str,
                            one_sharpe: float, two_sharpe: float,
                            path: pathlib.Path) -> pathlib.Path:
    """Growth of $1: the one-stage combined fund vs its two-stage counterpart."""
    common = one_dr.index.intersection(two_dr.index)
    g_one = (1 + one_dr.loc[common]).cumprod()
    g_two = (1 + two_dr.loc[common]).cumprod()
    with ps.revelatio_style():
        fig, ax = ps.new_figure("full_width")
        ax.plot(g_one.index, g_one, color=ps.REVELATIO["muted"], linewidth=1.9,
                zorder=3, label="One-stage (60 assets)")
        ax.plot(g_two.index, g_two, color=ps.REVELATIO["gilt"], linewidth=2.4,
                zorder=6, label="Two-stage (sleeves)")
        ax.set_ylabel("Value of $1 invested")
        ps.date_axis(ax)
        span = g_one.index[-1] - g_one.index[0]
        ax.set_xlim(g_one.index[0] - span * 0.01, g_one.index[-1] + span * 0.05)
        for series, col in ((g_one, ps.REVELATIO["muted"]), (g_two, ps.REVELATIO["gilt"])):
            ax.annotate(f"${series.iloc[-1]:.2f}", (series.index[-1], series.iloc[-1]),
                        xytext=(6, 0), textcoords="offset points", fontsize=8.5,
                        color=col, va="center", fontweight="bold", annotation_clip=False)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2, fontsize=9)
        delta = two_sharpe - one_sharpe
        verdict = "beat" if delta > 0.01 else "matched" if abs(delta) <= 0.01 else "trailed"
        ps.stamp(
            fig, ax,
            f"Two-stage {verdict} one-stage on {method_label}: Sharpe "
            f"{one_sharpe:.2f} -> {two_sharpe:.2f}",
            f"Growth of $1, {method_label} built in one stage vs two stages",
            units="index, $1 at 2021-01-04", sample=OOS_SAMPLE, source_y=-48,
        )
        return ps.save(fig, path)


def figure_two_stage_sleeve(fund_weights: pd.DataFrame, ts_funds: list[str],
                            equity_cols: list[str], path: pathlib.Path) -> pathlib.Path:
    """Realised equity-sleeve share over time for the two two-stage funds.

    The equity share at each rebalance is the sum of weight on equity tickers;
    the remainder (to 1) sits in crypto. Crypto's far higher volatility pushes the
    minimum-variance split hard toward equities - the point of showing it.
    """
    eq_set = set(equity_cols)
    with ps.revelatio_style():
        fig, ax = ps.new_figure("full_width")
        colors = {ts_funds[0]: ps.REVELATIO["verdigris"], ts_funds[1]: ps.REVELATIO["gilt"]}
        for fund in ts_funds:
            w = fund_weights[fund_weights.fund == fund]
            share = (w.assign(is_eq=w.ticker.isin(eq_set))
                     .groupby("rebalance_date")
                     .apply(lambda g: g.loc[g.is_eq, "weight"].sum(), include_groups=False))
            share.index = pd.to_datetime(share.index)
            ax.plot(share.index, share, color=colors[fund], linewidth=2.2,
                    label=_short(fund).replace("TwoStage_", ""))
        ax.axhline(1.0, color=ps.REVELATIO["rule"], linewidth=0.8)
        ax.set_ylabel("Equity sleeve share")
        ax.set_ylim(0, 1.05)
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
        ps.date_axis(ax)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2, fontsize=9)
        ps.stamp(
            fig, ax,
            "Minimum-variance holds almost only equities; maximum-Sharpe swings "
            "into crypto when it chases return",
            "Realised equity-sleeve share over time, two-stage funds "
            "(remainder to 100% held in crypto)",
            units="share of portfolio in the equity sleeve", sample=OOS_SAMPLE, source_y=-48,
        )
        return ps.save(fig, path)


# --- Step 8c figures: sentiment decay on no-news days (innovation) -------------

def figure_decay_mechanism(example: pd.DataFrame, ticker: str, half_life: float,
                           path: pathlib.Path) -> pathlib.Path:
    """One ticker: headline days, the neutral-0 fill, and the decayed fill.

    Shows the mechanism directly - the core rule snaps to 0 between headlines,
    while decay leaves a fading tail that keeps the last score's sign.
    """
    ex = example.dropna(how="all")
    # A representative window where the ticker goes quiet, so the tail is visible.
    hits = ex.index[ex["headline"].notna()]
    if len(hits) >= 2:
        lo = hits[len(hits) // 3]
        win = ex.loc[lo: lo + pd.Timedelta(days=180)]
    else:
        win = ex
    with ps.revelatio_style():
        fig, ax = ps.new_figure("full_width")
        ax.axhline(0, color=ps.REVELATIO["rule"], linewidth=0.8, zorder=1)
        ax.plot(win.index, win["decayed"], color=ps.REVELATIO["gilt"], linewidth=2.2,
                zorder=5, label=f"Decayed (half-life {half_life:.0f}d)")
        ax.step(win.index, win["neutral0"], where="post", color=ps.REVELATIO["muted"],
                linewidth=1.5, zorder=4, label="Neutral-0 (core rule)")
        h = win["headline"].dropna()
        ax.scatter(h.index, h.to_numpy(), s=28, color=ps.REVELATIO["rubric"], zorder=6,
                   label="Headline day")
        ax.set_ylabel("VADER compound sentiment")
        ps.date_axis(ax)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=3, fontsize=8.5)
        ps.stamp(
            fig, ax,
            "Decay keeps yesterday's news alive with a fading tail; the core rule "
            "drops it to zero at once",
            f"Sentiment fill for {ticker}: headline days, the neutral-0 rule, and "
            f"the decayed rule (half-life {half_life:.0f} trading days)",
            units="VADER compound in [-1, 1]; 0 = neutral",
            sample=f"{win.index.min():%b %Y} to {win.index.max():%b %Y}", source_y=-48,
        )
        return ps.save(fig, path)


def figure_decay_fusion(base: pd.Series, neutral: pd.Series, decay: pd.Series,
                        fund: str, sharpes: dict, path: pathlib.Path) -> pathlib.Path:
    """Growth of $1: base fund vs neutral-0 tilt vs decayed tilt."""
    common = base.index.intersection(neutral.index).intersection(decay.index)
    g = {k: (1 + s.loc[common]).cumprod()
         for k, s in (("base", base), ("neutral", neutral), ("decay", decay))}
    styles = {"base": (ps.REVELATIO["ink_soft"], 1.6, "Base (no sentiment)"),
              "neutral": (ps.REVELATIO["muted"], 1.8, "Neutral-0 tilt"),
              "decay": (ps.REVELATIO["gilt"], 2.4, "Decayed tilt")}
    with ps.revelatio_style():
        fig, ax = ps.new_figure("full_width")
        for k, (col, lw, lab) in styles.items():
            ax.plot(g[k].index, g[k], color=col, linewidth=lw,
                    zorder=6 if k == "decay" else 3, label=lab)
        ax.set_ylabel("Value of $1 invested")
        ps.date_axis(ax)
        span = g["base"].index[-1] - g["base"].index[0]
        ax.set_xlim(g["base"].index[0] - span * 0.01, g["base"].index[-1] + span * 0.06)
        for k, (col, _lw, _lab) in styles.items():
            ax.annotate(f"${g[k].iloc[-1]:.2f}", (g[k].index[-1], g[k].iloc[-1]),
                        xytext=(6, 0), textcoords="offset points", fontsize=8.3,
                        color=col, va="center", fontweight="bold", annotation_clip=False)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=3, fontsize=8.5)
        ps.stamp(
            fig, ax,
            f"On {_short(fund)}, decay softens the sentiment tilt's drag: Sharpe "
            f"{sharpes['base']:.2f} base, {sharpes['neutral']:.2f} neutral-0, "
            f"{sharpes['decay']:.2f} decayed",
            f"Growth of $1, {_short(fund)}: base vs neutral-0 tilt vs decayed tilt",
            units="index, $1 at 2021-01-04", sample=OOS_SAMPLE, source_y=-48,
        )
        return ps.save(fig, path)


def main() -> None:
    for folder in (TABLES, FIGURES, DATA):
        folder.mkdir(parents=True, exist_ok=True)

    # --- Step 1: the data foundation (reused from Part A) --------------------
    # Returns are computed WITHIN each panel, then crypto is left-joined onto the
    # equity trading calendar (features.combined_return_panel). The whole panel is
    # written - not a sample - because Step 2's walk-forward backtest needs every
    # trading day for its rolling 252-day estimation window.
    eq, eq_i = etl.load_clean_equities()
    cr, cr_i = etl.load_clean_crypto()

    panel, panel_i = features.combined_return_panel(eq, cr)
    panel.to_csv(DATA / "combined_returns_panel.csv", index=True)

    # --- Step 2: the fund grid - families x methods (walk-forward OOS) -------
    # Three families (equity-only, crypto-only, combined) x three methods
    # (minimum-variance, maximum-Sharpe, risk parity) = nine funds. Each family is
    # the same backtest on a restricted column set, so there is no look-ahead or
    # calendar difference - only the investable universe and the objective move.
    equity_cols = sorted(eq["ticker"].unique())
    crypto_cols = sorted(cr["ticker"].unique())
    FAMILIES = [("Equity", equity_cols), ("Crypto", crypto_cols),
                ("Combined", equity_cols + crypto_cols)]

    fund_returns = {}
    weights_frames = []
    metas, metrics_preview, fund_family = {}, {}, {}
    for family, cols in FAMILIES:
        subpanel = panel[cols]
        for method in portfolios.ALL_METHODS:
            dr, wdf, meta = portfolios.oos_backtest(subpanel, method)
            name = f"{family}_{portfolios.METHOD_LABEL[method]}"
            fund_returns[name] = dr
            weights_frames.append(wdf.assign(fund=name))
            metas[name] = {**meta, "fund": name, "family": family, "method": method}
            metrics_preview[name] = portfolios.performance_metrics(dr)
            fund_family[name] = family

    # The two combined core funds keep their exact names, so fusion, shrinkage and
    # the report narrative are unchanged. The three combined methods drive the
    # method-comparison exhibits.
    CORE_FUNDS = [portfolios.FUND_NAME[m] for m in portfolios.METHODS]
    COMBINED_FUNDS = [f"Combined_{portfolios.METHOD_LABEL[m]}" for m in portfolios.ALL_METHODS]

    # --- Step 8d: passive benchmark (innovation) -----------------------------
    # Equal-weight 50-stock market on the same schedule and OOS window as the
    # funds, so every fund can be scored against simply owning the market.
    bench_dr, _, bench_meta = benchmark.equal_weight_benchmark(panel, equity_cols)
    bench_metrics = portfolios.performance_metrics(bench_dr)
    bench_dr.to_frame().to_csv(DATA / "benchmark_returns.csv", index=True)

    # --- Step 8b: two-stage portfolio-of-portfolios (innovation) -------------
    # A fourth fund family, so its funds join the core files (Gianni's call): they
    # appear in fund_returns/fund_weights/performance_metrics and the app lineup.
    # Same window, rebalance, method, and OOS period as the one-stage funds - only
    # the structure moves. Built before the CSV writes so the funds are included.
    ts = two_stage.run_two_stage(panel, equity_cols, crypto_cols)
    TWO_STAGE_FUNDS = [ts[m]["name"] for m in portfolios.METHODS]
    for method in portfolios.METHODS:
        r = ts[method]
        fund_returns[r["name"]] = r["returns"]
        weights_frames.append(r["weights"].assign(fund=r["name"]))
        metas[r["name"]] = r["meta"]
        metrics_preview[r["name"]] = portfolios.performance_metrics(r["returns"])

    fund_returns = pd.DataFrame(fund_returns)
    fund_returns.to_csv(DATA / "fund_returns.csv", index=True)         # EXACT NAME
    fund_weights = pd.concat(weights_frames, ignore_index=True)[
        ["fund", "rebalance_date", "ticker", "weight"]
    ]
    fund_weights.to_csv(DATA / "fund_weights.csv", index=False)        # EXACT NAME

    probe = portfolios.lookahead_probe(panel, "min_variance", peek=1)

    # Weight sanity: every rebalance sums to 1 and has no shorts.
    wsum = fund_weights.groupby(["fund", "rebalance_date"])["weight"].sum()
    weights_sum_to_one = bool(np.allclose(wsum.to_numpy(), 1.0, atol=1e-6))
    no_shorts = bool((fund_weights["weight"] >= -1e-9).all())

    # --- Step 3: fact-sheet metrics + fund figures --------------------------
    metrics = pd.DataFrame([
        {"fund": fund, "ann_return": m["ann_return"], "ann_vol": m["ann_vol"],
         "sharpe": m["sharpe"], "max_drawdown": m["max_drawdown"],
         "oos_days": m["n_days"], "first_live_date": metas[fund]["first_live_date"].date()}
        for fund, m in metrics_preview.items()
    ])
    metrics.to_csv(TABLES / "performance_metrics.csv", index=False)   # EXACT NAME

    # Core growth/drawdown/weights stay on the two combined funds for legibility;
    # the Sharpe barplot spans every fund (core + two-stage) as the cross-fund view.
    # Both the growth and the Sharpe figure carry the equal-weight market reference.
    figure_growth(fund_returns[COMBINED_FUNDS], FIGURES / "growth_of_dollar.png",
                  benchmark_returns=bench_dr)
    figure_drawdown(fund_returns[CORE_FUNDS], FIGURES / "drawdown.png")
    figure_weights(fund_weights, "Combined_MaxSharpe", FIGURES / "weights_over_time.png")
    figure_sharpe_bar(metrics, FIGURES / "sharpe_barplot.png",
                      bench_sharpe=bench_metrics["sharpe"])

    # Benchmark comparison across every app fund (excess return and Sharpe gap).
    benchmark_tbl = benchmark.compare_to_benchmark(metrics_preview, bench_metrics)
    benchmark_tbl.to_csv(TABLES / "benchmark_comparison.csv", index=False)
    benchmark_ok = (
        (DATA / "benchmark_returns.csv").exists()
        and (TABLES / "benchmark_comparison.csv").exists()
        and len(bench_dr) == len(fund_returns)
    )

    step3_files = [
        TABLES / "performance_metrics.csv",
        FIGURES / "growth_of_dollar.png", FIGURES / "drawdown.png",
        FIGURES / "weights_over_time.png", FIGURES / "sharpe_barplot.png",
    ]
    step3_ok = all(p.exists() for p in step3_files)

    # --- Step 4: sentiment model + sector index -----------------------------
    nw, _ = etl.load_clean_news()
    headline_panel, _ = features.assemble_headline_panel(nw, eq)
    scored = sentiment.score_headlines(headline_panel)
    sector_index, sent_i = sentiment.sector_sentiment_index(scored, eq)
    sector_index.round(6).to_csv(DATA / "sector_sentiment_index.csv")   # EXACT NAME

    # Small stats file so the report can trace the coverage/level numbers.
    pd.DataFrame([{
        "ticker_day_coverage_pct": sent_i["ticker_day_coverage_pct"],
        "overall_mean": round(float(sector_index.mean().mean()), 4),
        "min": round(float(sector_index.min().min()), 4),
        "max": round(float(sector_index.max().max()), 4),
        "date_min": sent_i["date_min"].date(), "date_max": sent_i["date_max"].date(),
    }]).to_csv(TABLES / "sentiment_stats.csv", index=False)

    figure_sentiment(sector_index, FIGURES / "sector_sentiment.png")

    # Hand-check: the contemporaneous index is never lagged here; fusion (Step 5)
    # applies the >=1-day lag. Confirm the index has one column per sector and no
    # look-ahead was baked in (row t depends only on day-t headlines).
    sentiment_ok = (
        (DATA / "sector_sentiment_index.csv").exists()
        and sector_index.shape[1] == 10
        and (FIGURES / "sector_sentiment.png").exists()
    )

    # --- Step 5: sentiment fusion (before vs after) -------------------------
    tilt = fusion.build_sentiment_tilt(sector_index, eq)
    fusion_rows, fusion_series = [], {}
    for method in portfolios.METHODS:
        name = portfolios.FUND_NAME[method]
        base_dr = fund_returns[name]
        aug_dr, _, _ = portfolios.oos_backtest(panel, method, weight_fn=tilt)
        bm, am = portfolios.performance_metrics(base_dr), portfolios.performance_metrics(aug_dr)
        for variant, m in (("base", bm), ("sentiment", am)):
            fusion_rows.append({"fund": name, "variant": variant, "ann_return": m["ann_return"],
                                "ann_vol": m["ann_vol"], "sharpe": m["sharpe"],
                                "max_drawdown": m["max_drawdown"]})
        fusion_series[name] = {"base": base_dr, "aug": aug_dr,
                               "base_sharpe": bm["sharpe"], "aug_sharpe": am["sharpe"]}
    fusion_tbl = pd.DataFrame(fusion_rows)
    fusion_tbl.to_csv(TABLES / "fusion_comparison.csv", index=False)

    # Figure for the fund whose Sharpe moved most under the tilt.
    fig_fund = max(fusion_series, key=lambda f: abs(
        fusion_series[f]["aug_sharpe"] - fusion_series[f]["base_sharpe"]))
    fs = fusion_series[fig_fund]
    figure_fusion(fs["base"], fs["aug"], fig_fund, fs["base_sharpe"], fs["aug_sharpe"],
                  FIGURES / "fusion_before_after.png")

    fusion_ok = ((TABLES / "fusion_comparison.csv").exists()
                 and (FIGURES / "fusion_before_after.png").exists())

    # --- Step 8a: covariance shrinkage (innovation) -------------------------
    # Self-contained before-vs-after: the shrunk funds and their diagnostics
    # live in their own files; the four marker files above are untouched.
    shrink = shrinkage.run_shrinkage(panel)
    shrink["comparison"].to_csv(TABLES / "shrinkage_comparison.csv", index=False)
    shrink["diagnostics"].round(6).to_csv(TABLES / "shrinkage_diagnostics.csv", index=False)
    shrink["shrunk_returns"].to_csv(DATA / "shrinkage_fund_returns.csv", index=True)

    # Growth figure for the method whose Sharpe moved most under shrinkage.
    shrink_fig_method = max(shrink["series"], key=lambda mth: abs(
        shrink["series"][mth]["shrunk_sharpe"] - shrink["series"][mth]["base_sharpe"]))
    figure_shrinkage_growth(shrink["series"][shrink_fig_method],
                            FIGURES / "shrinkage_growth.png")
    figure_shrinkage_dispersion(shrink["diagnostics"], FIGURES / "shrinkage_dispersion.png")

    shrunk_delta = shrink["diagnostics"].loc[
        shrink["diagnostics"]["variant"] == "shrunk", "mean_delta"]
    delta_in_range = bool(((shrunk_delta > 0) & (shrunk_delta <= 1)).all())
    shrinkage_ok = (
        delta_in_range
        and (TABLES / "shrinkage_comparison.csv").exists()
        and (TABLES / "shrinkage_diagnostics.csv").exists()
        and (DATA / "shrinkage_fund_returns.csv").exists()
        and (FIGURES / "shrinkage_growth.png").exists()
        and (FIGURES / "shrinkage_dispersion.png").exists()
    )

    # --- Step 8b: two-stage vs one-stage comparison + figures ---------------
    pc = ts["_param_counts"]
    ts_rows = []
    for method in portfolios.METHODS:
        one_name = portfolios.FUND_NAME[method]
        two_name = ts[method]["name"]
        for structure, fund, tot, cross in (
            ("one_stage", one_name, pc["one_stage_total"], pc["one_stage_cross"]),
            ("two_stage", two_name, pc["two_stage_total"], pc["two_stage_cross"]),
        ):
            m = metrics_preview[fund]
            ts_rows.append({
                "method": method, "structure": structure, "fund": fund,
                "ann_return": m["ann_return"], "ann_vol": m["ann_vol"],
                "sharpe": m["sharpe"], "max_drawdown": m["max_drawdown"],
                "cov_params_total": tot, "cross_asset_cov_params": cross,
            })
    two_stage_tbl = pd.DataFrame(ts_rows)
    two_stage_tbl.to_csv(TABLES / "two_stage_comparison.csv", index=False)

    # Growth figure for the method whose Sharpe moved most between structures.
    ts_fig_method = max(portfolios.METHODS, key=lambda mth: abs(
        metrics_preview[ts[mth]["name"]]["sharpe"]
        - metrics_preview[portfolios.FUND_NAME[mth]]["sharpe"]))
    figure_two_stage_growth(
        fund_returns[portfolios.FUND_NAME[ts_fig_method]],
        fund_returns[ts[ts_fig_method]["name"]],
        _short(portfolios.FUND_NAME[ts_fig_method]),
        metrics_preview[portfolios.FUND_NAME[ts_fig_method]]["sharpe"],
        metrics_preview[ts[ts_fig_method]["name"]]["sharpe"],
        FIGURES / "two_stage_growth.png")
    figure_two_stage_sleeve(fund_weights, TWO_STAGE_FUNDS, equity_cols,
                            FIGURES / "two_stage_sleeve_share.png")

    two_stage_ok = (
        set(TWO_STAGE_FUNDS).issubset(set(fund_returns.columns))
        and (TABLES / "two_stage_comparison.csv").exists()
        and (FIGURES / "two_stage_growth.png").exists()
        and (FIGURES / "two_stage_sleeve_share.png").exists()
    )

    # --- Step 8c: sentiment decay on no-news days (innovation) --------------
    # The core rule snaps a ticker's sentiment to 0 the day its news stops; decay
    # instead carries the last score forward, fading it over a half-life. The
    # exhibit is the effect on the FUSION, not the index. Half-life 5 is the
    # ex-ante choice; the sweep shows sensitivity without tuning to win.
    HALF_LIFE = 5.0
    SWEEP = [2, 5, 10, 21]

    decay_returns = {}      # (half_life, method) -> daily OOS returns of the decayed tilt
    for hl in SWEEP:
        idx_hl, ii = sentiment.sector_sentiment_index_decay(scored, eq, hl)
        if hl == HALF_LIFE:
            idx_hl.round(6).to_csv(DATA / "sector_sentiment_index_decay.csv")
        tilt_hl = fusion.build_sentiment_tilt(idx_hl, eq)
        for method in portfolios.METHODS:
            dr, _, _ = portfolios.oos_backtest(panel, method, weight_fn=tilt_hl)
            decay_returns[(hl, method)] = dr

    # Before-vs-after at the headline half-life: base vs neutral-0 tilt vs decay.
    decay_rows, decay_series = [], {}
    for method in portfolios.METHODS:
        name = portfolios.FUND_NAME[method]
        base_dr = fund_returns[name]
        neutral_dr = fusion_series[name]["aug"]                 # the Step 5 neutral-0 tilt
        decay_dr = decay_returns[(HALF_LIFE, method)]
        variants = {"base": base_dr, "sentiment_neutral0": neutral_dr, "sentiment_decay": decay_dr}
        sharpes = {}
        for variant, dr in variants.items():
            m = portfolios.performance_metrics(dr)
            sharpes[variant] = m["sharpe"]
            decay_rows.append({"fund": name, "variant": variant, "half_life": HALF_LIFE,
                               "ann_return": m["ann_return"], "ann_vol": m["ann_vol"],
                               "sharpe": m["sharpe"], "max_drawdown": m["max_drawdown"]})
        decay_series[name] = {"base": base_dr, "neutral": neutral_dr, "decay": decay_dr,
                              "sharpes": {"base": sharpes["base"],
                                          "neutral": sharpes["sentiment_neutral0"],
                                          "decay": sharpes["sentiment_decay"]}}
    decay_tbl = pd.DataFrame(decay_rows)
    decay_tbl.to_csv(TABLES / "decay_comparison.csv", index=False)

    sweep_rows = [{"half_life": hl, "fund": portfolios.FUND_NAME[method],
                   "sharpe": portfolios.performance_metrics(decay_returns[(hl, method)])["sharpe"]}
                  for hl in SWEEP for method in portfolios.METHODS]
    decay_sweep = pd.DataFrame(sweep_rows)
    decay_sweep.to_csv(TABLES / "decay_halflife_sweep.csv", index=False)

    # Mechanism figure: a median-coverage equity ticker, so there are both
    # headlines and quiet gaps to show the tail.
    hits = (scored.dropna(subset=["trading_day"])
            .groupby("ticker")["trading_day"].nunique())
    hits = hits[hits.index.isin(equity_cols)].sort_values()
    example_ticker = hits.index[len(hits) // 2]
    example = sentiment.ticker_decay_example(scored, eq, example_ticker, HALF_LIFE)
    figure_decay_mechanism(example, example_ticker, HALF_LIFE,
                           FIGURES / "decay_mechanism.png")

    # Fusion figure: the fund where decay moves Sharpe most vs the neutral-0 tilt.
    decay_fig_fund = max(decay_series, key=lambda f: abs(
        decay_series[f]["sharpes"]["decay"] - decay_series[f]["sharpes"]["neutral"]))
    ds = decay_series[decay_fig_fund]
    figure_decay_fusion(ds["base"], ds["neutral"], ds["decay"], decay_fig_fund,
                        ds["sharpes"], FIGURES / "decay_fusion.png")

    decay_ok = (
        (DATA / "sector_sentiment_index_decay.csv").exists()
        and (TABLES / "decay_comparison.csv").exists()
        and (TABLES / "decay_halflife_sweep.csv").exists()
        and set(decay_tbl.variant.unique()) == {"base", "sentiment_neutral0", "sentiment_decay"}
        and (FIGURES / "decay_mechanism.png").exists()
        and (FIGURES / "decay_fusion.png").exists()
    )

    # --- Self-verification (expected values from context/DATA_GUIDE.md) ------
    checks = [
        ("equity rows (clean)", eq_i["rows_out"], 50_300),
        ("crypto rows (after cap)", cr_i["rows_out"], 14_610),
        ("crypto rows capped (stray 2024)", cr_i["dropped_after_cutoff"], 10),
        ("combined panel rows (equity trading days)", panel_i["rows"], 1_006),
    ]

    print("\n" + "=" * 68)
    print("PART B - Step 1: data foundation (Revelatio, z5736927)")
    print("=" * 68)
    print("\nCounts (expected values from context/DATA_GUIDE.md):")
    ok = True
    for label, got, want in checks:
        flag = "OK " if got == want else "!! "
        ok &= got == want
        print(f"  {flag}{label:<44} {got:>8,}  expected {want:>8,}")

    print("\nCombined return panel:")
    print(f"     shape                         {panel.shape[0]:>6,} rows x {panel.shape[1]:>3} assets")
    print(f"     crypto dates dropped by join  {panel_i['crypto_dates_dropped_by_join']:>6,} (weekends/holidays, intended)")
    print(f"     date range                    {panel.index.min().date()} to {panel.index.max().date()}")

    # --- Step 2 report -------------------------------------------------------
    any_fund = next(iter(metas.values()))
    print("\nStep 2 - funds (walk-forward OOS backtest):")
    print(f"     estimation window             {portfolios.WINDOW} trading days (rolling)")
    print(f"     rebalance                     first trading day of each month")
    print(f"     first live date               {any_fund['first_live_date'].date()}")
    print(f"     rebalances / OOS days         {any_fund['n_rebalances']} / {any_fund['n_oos_days']}")
    print(f"     OOS period                    {any_fund['oos_start'].date()} to {any_fund['oos_end'].date()}")
    print(f"     weights sum to 1 (all)        {weights_sum_to_one}")
    print(f"     no short weights (all)        {no_shorts}")
    print(f"     look-ahead probe (min_var)    series differ when peeking: {probe['series_differ']}"
          f"  (honest Sharpe {probe['honest_sharpe']:.2f} vs peek {probe['peek_sharpe']:.2f})")
    # --- Step 3 report -------------------------------------------------------
    print("\nStep 3 - fact-sheet metrics (results/tables/performance_metrics.csv):")
    print(f"       {'fund':<22}{'annRet':>8}{'annVol':>8}{'Sharpe':>8}{'maxDD':>8}")
    for _, r in metrics.iterrows():
        print(f"       {r['fund']:<22}{r['ann_return']:>7.1%}{r['ann_vol']:>8.1%}"
              f"{r['sharpe']:>8.2f}{r['max_drawdown']:>8.1%}")
    print(f"     figures written               {sum(p.suffix == '.png' for p in step3_files)} "
          f"(growth, drawdown, weights-over-time, Sharpe barplot)")

    # --- Step 4 report -------------------------------------------------------
    print("\nStep 4 - sentiment index (results/data/sector_sentiment_index.csv):")
    print(f"     sectors x trading days        {sent_i['sectors']} x {sent_i['trading_days']:,}")
    print(f"     ticker-day headline coverage  {sent_i['ticker_day_coverage_pct']:.1f}%"
          f"  (rest entered as neutral 0)")
    print(f"     index date range              {sent_i['date_min'].date()} to {sent_i['date_max'].date()}")
    print(f"     lag                           contemporaneous here; fusion (Step 5) lags >= 1 day")

    # --- Step 5 report -------------------------------------------------------
    print("\nStep 5 - sentiment fusion, before vs after (results/tables/fusion_comparison.csv):")
    print(f"       {'fund':<22}{'variant':<11}{'annRet':>8}{'Sharpe':>8}{'maxDD':>8}")
    for _, r in fusion_tbl.iterrows():
        print(f"       {r['fund']:<22}{r['variant']:<11}{r['ann_return']:>7.1%}"
              f"{r['sharpe']:>8.2f}{r['max_drawdown']:>8.1%}")
    for name, fs in fusion_series.items():
        d = fs["aug_sharpe"] - fs["base_sharpe"]
        print(f"     {name:<22} Sharpe change {d:+.3f} (tilt lambda=0.5, 21-day lagged signal)")

    # --- Step 8a report ------------------------------------------------------
    comp = shrink["comparison"]
    diag = shrink["diagnostics"]
    print("\nStep 8a - covariance shrinkage, sample vs Ledoit-Wolf "
          "(results/tables/shrinkage_comparison.csv):")
    print(f"       {'fund':<30}{'variant':<9}{'annRet':>8}{'Sharpe':>8}{'maxDD':>8}")
    for _, r in comp.iterrows():
        print(f"       {r['fund']:<30}{r['variant']:<9}{r['ann_return']:>7.1%}"
              f"{r['sharpe']:>8.2f}{r['max_drawdown']:>8.1%}")
    print(f"     {'method':<16}{'delta':>7}{'effN base->shrunk':>22}{'turnover base->shrunk':>26}")
    for method in portfolios.METHODS:
        s = diag[(diag.method == method) & (diag.variant == "sample")].iloc[0]
        h = diag[(diag.method == method) & (diag.variant == "shrunk")].iloc[0]
        print(f"     {method:<16}{h['mean_delta']:>7.2f}"
              f"{s['effective_n']:>10.1f} -> {h['effective_n']:<9.1f}"
              f"{s['mean_turnover']:>13.1%} -> {h['mean_turnover']:<.1%}")
    print(f"     shrinkage figure (largest Sharpe move)   {shrink_fig_method}")

    # --- Step 8b report ------------------------------------------------------
    print("\nStep 8b - two-stage vs one-stage (results/tables/two_stage_comparison.csv):")
    print(f"       {'fund':<32}{'struct':<11}{'annRet':>8}{'Sharpe':>8}{'maxDD':>8}")
    for _, r in two_stage_tbl.iterrows():
        print(f"       {r['fund']:<32}{r['structure']:<11}{r['ann_return']:>7.1%}"
              f"{r['sharpe']:>8.2f}{r['max_drawdown']:>8.1%}")
    print(f"     covariance params (cross-asset decision)  one-stage {pc['one_stage_cross']:,} "
          f"vs two-stage {pc['two_stage_cross']:,}")
    print(f"     two-stage growth figure (largest move)    {ts_fig_method}")

    # --- Step 8c report ------------------------------------------------------
    print("\nStep 8c - sentiment decay, base vs neutral-0 vs decay "
          "(results/tables/decay_comparison.csv, half-life 5d):")
    print(f"       {'fund':<22}{'variant':<20}{'annRet':>8}{'Sharpe':>8}{'maxDD':>8}")
    for _, r in decay_tbl.iterrows():
        print(f"       {r['fund']:<22}{r['variant']:<20}{r['ann_return']:>7.1%}"
              f"{r['sharpe']:>8.2f}{r['max_drawdown']:>8.1%}")
    print(f"     half-life sweep (Sharpe), mechanism ticker {example_ticker}:")
    sweep_piv = decay_sweep.pivot(index="half_life", columns="fund", values="sharpe")
    for hl, row in sweep_piv.iterrows():
        cells = "  ".join(f"{_short(f)} {row[f]:.2f}" for f in sweep_piv.columns)
        print(f"       half-life {hl:>2}d   {cells}")

    # --- Step 8d report ------------------------------------------------------
    print("\nStep 8d - passive benchmark, equal-weight 50-stock market "
          "(results/tables/benchmark_comparison.csv):")
    print(f"     benchmark (EW-50)             annRet {bench_metrics['ann_return']:.1%}  "
          f"Sharpe {bench_metrics['sharpe']:.2f}  maxDD {bench_metrics['max_drawdown']:.1%}")
    print(f"       {'fund':<32}{'excessRet':>10}{'Sharpe-mkt':>12}{'beats?':>8}")
    for _, r in benchmark_tbl.iterrows():
        print(f"       {r['fund']:<32}{r['excess_ann_return']:>9.1%} "
              f"{r['sharpe_minus_bench']:>+11.2f}{str(r['beats_benchmark']):>8}")
    n_beat = int(benchmark_tbl["beats_benchmark"].sum())
    print(f"     {n_beat} of {len(benchmark_tbl)} funds beat the market on Sharpe")

    print(f"\nWrote combined_returns_panel.csv, fund_returns.csv ({len(fund_returns.columns)} funds), "
          f"fund_weights.csv, performance_metrics.csv ({len(metrics)} funds), "
          "sector_sentiment_index.csv, fusion_comparison.csv, "
          "shrinkage_comparison.csv, shrinkage_diagnostics.csv, shrinkage_fund_returns.csv, "
          "two_stage_comparison.csv, sector_sentiment_index_decay.csv, decay_comparison.csv, "
          "decay_halflife_sweep.csv, benchmark_returns.csv, benchmark_comparison.csv "
          "+ 12 figures.")

    checks_ok = (ok and weights_sum_to_one and no_shorts and probe["series_differ"]
                 and step3_ok and sentiment_ok and fusion_ok and shrinkage_ok
                 and two_stage_ok and decay_ok and benchmark_ok)
    if not checks_ok:
        print("\n  FAILED: a self-check did not pass. Do not use these outputs.")
        sys.exit(1)
    print("\nSteps 1-5 core + Step 8 innovation (shrinkage, two-stage, decay) OK.\n")


if __name__ == "__main__":
    main()

"""Revelatio - systematically managed funds for the first-time investor.

An investor-facing app with an institutional, iShares-inspired look. It reads ONLY
the precomputed artifacts in results/ (committed to the repo): no backtest, no
sentiment scoring, no download at runtime. The one live computation is the
allocation blend, which is arithmetic over precomputed fund returns. Every number
on screen traces to a file in results/.

Run locally:   streamlit run streamlit_app.py

Structure: a custom top nav (black bar) drives a small session_state router across
five views - Home, Funds, Sentiment, Build portfolio, About - plus a fund-detail
drill-down. A custom router is used instead of st.navigation so the black top bar,
the accent pill, and the "click a fund card -> open its detail" routing all behave
exactly as designed.
"""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "results" / "data"
TABLES = ROOT / "results" / "tables"

st.set_page_config(page_title="Revelatio Funds", layout="wide", page_icon="")

# --- design tokens ------------------------------------------------------------
# ONE accent variable. Switch to gilt for report consistency by setting
# ACCENT = "#B8860B" (and ACCENT_DK = "#8A6608").
ACCENT = "#E8622C"
ACCENT_DK = "#C24E1F"
INK = "#1A1A1A"
MUTED = "#5A5A5A"
BAND = "#F5F2EC"
LINE = "#E4E0D8"
POS = "#1E824C"
NEG = "#C0392B"
BENCH_GREY = "#9A948A"
OOS = "Out-of-sample, 2021-01-04 to 2023-12-29"
MGMT_FEE = 0.75   # fixed annual management fee (%), accrued daily - not investor-chosen

# The offering: three families x three methods (nine funds), plus two two-stage
# funds. COMBINED_FUNDS are the multi-asset flagships used on Home and the blender.
GRID = [f"{fam}_{m}" for fam in ("Equity", "Crypto", "Combined")
        for m in ("MinVariance", "MaxSharpe", "RiskParity")]
TWO_STAGE_FUNDS = ["Combined_TwoStage_MinVariance", "Combined_TwoStage_MaxSharpe"]
FUNDS = GRID + TWO_STAGE_FUNDS
COMBINED_FUNDS = ["Combined_MinVariance", "Combined_MaxSharpe", "Combined_RiskParity"]
FAMILY_OF = {**{f: f.split("_")[0] for f in GRID},
             "Combined_TwoStage_MinVariance": "Combined",
             "Combined_TwoStage_MaxSharpe": "Combined"}
FAMILY_TITLE = {"Equity": "Equity funds", "Crypto": "Crypto funds",
                "Combined": "Multi-asset funds"}

_STYLE = {"MinVariance": ("Balanced", "BAL"), "MaxSharpe": ("High Growth", "HGF"),
          "RiskParity": ("Risk Parity", "RPY")}
_STYLE_BLURB = {"MinVariance": "targets the lowest volatility - the calmest ride.",
                "MaxSharpe": "chases the best risk-adjusted return - higher highs, deeper falls.",
                "RiskParity": "spreads risk evenly across holdings - diversified by volatility."}
_ASSET = {"Equity": ("Equity", "E", "US large-cap stocks only"),
          "Crypto": ("Crypto", "C", "cryptocurrencies only"),
          "Combined": ("", "M", "stocks and crypto combined")}


def _gen_meta(fund: str) -> dict:
    """Generate product metadata for a grid fund from its family and method."""
    fam, _, method = fund.partition("_")
    style, scode = _STYLE[method]
    asset, acode, adesc = _ASSET[fam]
    label = f"{asset + ' ' if asset else ''}{style}".strip()
    return dict(
        code=f"{acode}{scode}", name=f"Revelatio {label} Fund", short=label,
        eyebrow=("MULTI-ASSET" if fam == "Combined" else fam.upper()) + " · SYSTEMATIC",
        blurb=f"{adesc.capitalize()}; {_STYLE_BLURB[method]}",
        objective=(f"A {'multi-asset' if fam == 'Combined' else fam.lower()} fund "
                   f"({adesc}) that {_STYLE_BLURB[method]} Rebuilt on the first trading "
                   "day of each month from the trailing year of returns, out of sample."),
        good=[f"You want {adesc} exposure.",
              f"You prefer the {style.lower()} objective.",
              "You accept the fund's out-of-sample drawdown, shown on the Performance tab."])


# Generated metadata for every grid fund, then richer hand-written entries for the
# flagship combined funds and the two-stage funds override the generic ones.
META = {f: _gen_meta(f) for f in GRID}
META.update({
    "Combined_MinVariance": dict(
        code="RBAL", name="Revelatio Balanced Fund", short="Balanced",
        eyebrow="MULTI-ASSET · SYSTEMATIC",
        blurb="The calm ride: lowest volatility and the shallowest falls.",
        objective=("Minimise the portfolio's month-to-month swings. The fund holds "
                   "the mix of the 60 assets whose combined volatility is lowest, "
                   "rebuilt monthly. It aims for a smooth ride, not the highest return."),
        good=["You value a smooth ride over the highest possible return.",
              "You want the shallowest drawdowns on offer (about 16% at worst).",
              "You accept that a plain equal-weight basket beat this fund over the "
              "sample - it is chosen for stability, not outperformance."]),
    "Combined_MaxSharpe": dict(
        code="RHGF", name="Revelatio High Growth Fund", short="High Growth",
        eyebrow="MULTI-ASSET · SYSTEMATIC",
        blurb="The return seeker: highest risk-adjusted return, deeper falls.",
        objective=("Maximise return per unit of risk (the tangency portfolio). The "
                   "fund concentrates in the strongest risk-adjusted names and takes "
                   "meaningful crypto exposure, rebuilt monthly."),
        good=["You can tolerate a fall of around 26% in pursuit of higher returns.",
              "You are comfortable with a concentrated book and real crypto exposure.",
              "You want the fund that beat the equal-weight market on risk-adjusted "
              "return over the sample."]),
    "Combined_TwoStage_MinVariance": dict(
        code="REQS", name="Revelatio Equity Signals Fund", short="Equity Signals",
        eyebrow="MULTI-ASSET · SYSTEMATIC",
        blurb="Stocks and crypto balanced in two stages, low-risk objective.",
        objective=("Build a stock sleeve and a crypto sleeve separately, then blend "
                   "the two - a minimum-variance objective at both stages. Matched the "
                   "all-at-once fund while estimating far fewer numbers."),
        good=["You prefer the calm-ride objective, built with less estimation error.",
              "You accept the same stability-over-return trade as Minimum Variance.",
              "You are comfortable it, too, trailed a simple market basket."]),
    "Combined_TwoStage_MaxSharpe": dict(
        code="RMOP", name="Revelatio Multi-Opportunity Fund", short="Multi-Opportunity",
        eyebrow="MULTI-ASSET · SYSTEMATIC",
        blurb="Stocks and crypto balanced in two stages, return-seeking objective.",
        objective=("Build a stock sleeve and a crypto sleeve separately, then blend "
                   "the two - a maximum-Sharpe objective at both stages."),
        good=["You want the return-seeking objective built sleeve by sleeve.",
              "You can tolerate a drawdown near 26%.",
              "You want a fund that beat the equal-weight market on risk-adjusted "
              "return."]),
})


# --- CSS ----------------------------------------------------------------------

def inject_css() -> None:
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');

    :root {{
      --bg:#FFFFFF; --band:{BAND}; --ink:{INK}; --muted:{MUTED};
      --line:{LINE}; --accent:{ACCENT}; --accent-dk:{ACCENT_DK};
      --pos:{POS}; --neg:{NEG};
    }}
    /* hide default streamlit chrome */
    #MainMenu, header[data-testid="stHeader"], footer {{visibility:hidden; height:0;}}
    [data-testid="stToolbar"] {{display:none;}}
    .stApp {{background:var(--bg);}}
    .block-container {{max-width:1200px; padding-top:1rem; padding-bottom:4rem;}}

    html, body, [class*="css"] {{font-family:'Inter',system-ui,sans-serif; color:var(--ink);}}
    h1,h2,h3,h4 {{font-family:'Archivo','Inter',sans-serif; letter-spacing:-0.02em; color:var(--ink);}}
    h1 {{font-weight:800; font-size:2.9rem; line-height:1.04;}}
    h2 {{font-weight:700; font-size:1.7rem; margin-top:0.4rem;}}
    p, li, label, .stMarkdown {{color:var(--ink);}}

    /* top nav (black bar) */
    .topbar {{display:flex; align-items:center; justify-content:space-between;
      background:var(--ink); color:#fff; padding:0.7rem 1.3rem; border-radius:10px;
      margin-bottom:1.4rem;}}
    .topbar .wordmark {{font-family:'Archivo'; font-weight:800; font-size:1.25rem;
      letter-spacing:-0.02em; color:#fff;}}
    .topbar .pill {{background:var(--accent); color:#fff; padding:0.4rem 0.9rem;
      border-radius:999px; font-weight:600; font-size:0.85rem;}}

    /* eyebrow / badge / stat */
    .eyebrow {{text-transform:uppercase; letter-spacing:0.14em; font-size:0.72rem;
      font-weight:600; color:var(--muted);}}
    .badge {{display:inline-flex; align-items:center; justify-content:center;
      width:52px; height:52px; border-radius:12px; background:var(--accent);
      color:#fff; font-family:'Archivo'; font-weight:800; font-size:0.9rem;
      letter-spacing:0.02em;}}
    .stat-label {{font-size:0.74rem; color:var(--muted); text-transform:uppercase;
      letter-spacing:0.06em;}}
    .stat-value {{font-family:'Archivo'; font-weight:700; font-size:1.5rem; color:var(--ink);
      line-height:1.1;}}

    .pill-pos {{background:rgba(30,130,76,0.12); color:var(--pos); padding:0.25rem 0.7rem;
      border-radius:999px; font-weight:600; font-size:0.82rem;}}
    .pill-neg {{background:rgba(90,90,90,0.12); color:var(--muted); padding:0.25rem 0.7rem;
      border-radius:999px; font-weight:600; font-size:0.82rem;}}

    .card {{background:var(--band); border:1px solid var(--line); border-radius:14px;
      padding:1.1rem 1.2rem; height:100%;}}
    .rule {{border:none; border-top:1px solid var(--line); margin:1.6rem 0;}}
    .band {{background:var(--band); border-radius:16px; padding:1.6rem 1.8rem;}}
    .approp {{border:1px solid var(--line); border-radius:12px; padding:1rem 1.2rem;
      background:#fff;}}
    .approp h4 {{margin:0 0 0.4rem 0; font-size:1rem;}}
    .source {{font-size:0.75rem; color:var(--muted); margin-top:0.2rem;}}
    .descr {{color:var(--muted); font-size:0.92rem;}}
    .foot {{color:var(--muted); font-size:0.78rem; border-top:1px solid var(--line);
      padding-top:0.8rem; margin-top:1.6rem;}}

    /* buttons -> accent */
    .stButton > button {{background:var(--accent); color:#fff; border:none;
      border-radius:8px; font-weight:600; padding:0.42rem 1rem;}}
    .stButton > button:hover {{background:var(--accent-dk); color:#fff;}}
    /* secondary (nav / back) buttons: outline */
    div[data-testid="column"] .stButton > button {{width:100%;}}
    </style>
    """, unsafe_allow_html=True)


# --- data (precomputed artifacts only) ----------------------------------------

@st.cache_data(ttl=86_400, show_spinner="Loading funds...")
def load_all() -> dict:
    fr = pd.read_csv(DATA / "fund_returns.csv", index_col=0, parse_dates=True)
    bench = pd.read_csv(DATA / "benchmark_returns.csv", index_col=0, parse_dates=True)["EqualWeight50"]
    metrics = pd.read_csv(TABLES / "performance_metrics.csv").set_index("fund")
    bcomp = pd.read_csv(TABLES / "benchmark_comparison.csv").set_index("fund")
    weights = pd.read_csv(DATA / "fund_weights.csv", parse_dates=["rebalance_date"])
    sent = pd.read_csv(DATA / "sector_sentiment_index.csv", index_col=0, parse_dates=True)
    fus = pd.read_csv(TABLES / "fusion_comparison.csv")
    return {"fr": fr, "bench": bench, "metrics": metrics, "bcomp": bcomp,
            "weights": weights, "sent": sent, "fus": fus}


def annualise(r: pd.Series) -> dict:
    r = r.dropna()
    mean_ann = float(r.mean() * 252)
    vol_ann = float(r.std() * np.sqrt(252))
    g = (1 + r).cumprod()
    dd = g / g.cummax() - 1.0
    return {"ann_return": mean_ann, "ann_vol": vol_ann,
            "sharpe": mean_ann / vol_ann if vol_ann else float("nan"),
            "max_drawdown": float(dd.min()), "final": float(g.iloc[-1])}


# --- chart helpers ------------------------------------------------------------

def _style(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=6, r=6, t=28, b=6),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color=MUTED, size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified")
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=LINE)
    fig.update_yaxes(gridcolor=LINE, zeroline=False)
    return fig


PLOTLY_CFG = {"displayModeBar": False}


def growth_fig(fund: str, d: dict) -> go.Figure:
    r = d["fr"][fund].dropna()
    gf = (1 + r).cumprod()
    gm = (1 + d["bench"].reindex(r.index).fillna(0.0)).cumprod()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=gm.index, y=gm, name="Equal-weight market",
                             line=dict(color=BENCH_GREY, dash="dash", width=1.6)))
    fig.add_trace(go.Scatter(x=gf.index, y=gf, name=META[fund]["short"],
                             line=dict(color=ACCENT, width=2.6)))
    fig.update_yaxes(title="Value of $1", tickprefix="$")
    return _style(fig)


def drawdown_fig(fund: str, d: dict) -> go.Figure:
    r = d["fr"][fund].dropna()
    g = (1 + r).cumprod()
    dd = g / g.cummax() - 1.0
    fig = go.Figure(go.Scatter(x=dd.index, y=dd, fill="tozeroy", name="Drawdown",
                               line=dict(color=NEG, width=1.4),
                               fillcolor="rgba(192,57,43,0.12)"))
    fig.update_yaxes(title="Decline from peak", tickformat=".0%")
    return _style(fig)


def holdings_fig(fund: str, d: dict):
    w = d["weights"]
    wf = w[w.fund == fund]
    latest = wf["rebalance_date"].max()
    hold = (wf[wf.rebalance_date == latest][["ticker", "weight"]]
            .sort_values("weight", ascending=False))
    hold = hold[hold.weight > 0.0005].reset_index(drop=True)
    top = hold.head(12).iloc[::-1]
    fig = go.Figure(go.Bar(x=top.weight, y=top.ticker, orientation="h",
                           marker=dict(color=ACCENT)))
    fig.update_xaxes(title="Portfolio weight", tickformat=".0%")
    return _style(fig, 380), hold, latest


# --- small components ---------------------------------------------------------

def stat_block(col, label: str, value: str) -> None:
    col.markdown(f"<div class='stat-label'>{label}</div>"
                 f"<div class='stat-value'>{value}</div>", unsafe_allow_html=True)


def beats_pill(beats: bool) -> str:
    return (f"<span class='pill-pos'>Beats market</span>" if beats
            else f"<span class='pill-neg'>Trails market</span>")


def go_detail(fund: str) -> None:
    st.session_state["selected_fund"] = fund
    st.session_state["page"] = "Funds"


# --- pages --------------------------------------------------------------------

def page_home(d: dict) -> None:
    m, b = d["metrics"], d["bcomp"]
    n_beat = int(b["beats_benchmark"].sum())
    st.markdown("<div class='eyebrow'>SYSTEMATIC MULTI-ASSET FUNDS</div>",
                unsafe_allow_html=True)
    st.markdown("<h1>Rules-based funds<br>for the first-time investor.</h1>",
                unsafe_allow_html=True)
    st.markdown("<p class='descr' style='font-size:1.05rem;max-width:640px'>"
                "Stocks and crypto, balanced by a systematic rule and tested out of "
                "sample. Every figure is precomputed from the backtest and traceable "
                "to its source.</p>", unsafe_allow_html=True)
    st.markdown(f"<div class='band' style='margin-top:1rem'><b>{n_beat} of "
                f"{len(FUNDS)} funds beat the equal-weight market</b> "
                f"(Sharpe {annualise(d['bench'])['sharpe']:.2f}). {OOS}.</div>",
                unsafe_allow_html=True)

    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    st.markdown("<div class='eyebrow'>WHAT WE OFFER</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    for col, num, head, txt in (
        (c1, "01", "Transparent rules", "Each fund is a stated rule over the same "
         "60 assets - no discretion, no black box."),
        (c2, "02", "Out-of-sample record", "Every number is from a walk-forward "
         "backtest with no look-ahead, 2021-2023."),
        (c3, "03", "Benchmarked honestly", "Each fund is scored against simply "
         "owning the market, and we show when it loses.")):
        col.markdown(f"<div class='card'><div class='stat-value' style='color:var(--accent)'>"
                     f"{num}</div><h4 style='margin:.3rem 0'>{head}</h4>"
                     f"<p class='descr'>{txt}</p></div>", unsafe_allow_html=True)

    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    st.markdown("<div class='eyebrow'>OUR MULTI-ASSET FUNDS</div>", unsafe_allow_html=True)
    _fund_cards(d, COMBINED_FUNDS)
    st.markdown("<p class='descr'>Equity-only and crypto-only versions of each "
                "method are on the Funds page.</p>", unsafe_allow_html=True)


def page_funds(d: dict) -> None:
    if st.session_state.get("selected_fund"):
        page_detail(d, st.session_state["selected_fund"])
        return
    st.markdown("<div class='eyebrow'>THE OFFERING</div>", unsafe_allow_html=True)
    st.markdown("<h2>Compare the funds</h2>", unsafe_allow_html=True)
    m, b = d["metrics"], d["bcomp"]
    bench_m = annualise(d["bench"])
    rows = [{"Fund": META[f]["name"], "Annual return": m.loc[f, "ann_return"],
             "Annual volatility": m.loc[f, "ann_vol"], "Sharpe": m.loc[f, "sharpe"],
             "Max drawdown": m.loc[f, "max_drawdown"],
             "Beats market?": "Yes" if bool(b.loc[f, "beats_benchmark"]) else "No"}
            for f in FUNDS]
    rows.append({"Fund": "Equal-weight market", "Annual return": bench_m["ann_return"],
                 "Annual volatility": bench_m["ann_vol"], "Sharpe": bench_m["sharpe"],
                 "Max drawdown": bench_m["max_drawdown"], "Beats market?": "-"})
    st.dataframe(pd.DataFrame(rows).style.format(
        {"Annual return": "{:.1%}", "Annual volatility": "{:.1%}",
         "Sharpe": "{:.2f}", "Max drawdown": "{:.1%}"}),
        hide_index=True, width="stretch")
    st.markdown("<p class='source'>Source: results/tables/performance_metrics.csv, "
                "benchmark_comparison.csv.</p>", unsafe_allow_html=True)
    for family in ("Combined", "Equity", "Crypto"):
        st.markdown("<hr class='rule'>", unsafe_allow_html=True)
        st.markdown(f"<div class='eyebrow'>{FAMILY_TITLE[family].upper()}</div>",
                    unsafe_allow_html=True)
        _fund_cards(d, [f for f in FUNDS if FAMILY_OF[f] == family])


def _fund_cards(d: dict, funds: list[str]) -> None:
    m, b = d["metrics"], d["bcomp"]
    cols = st.columns(2)
    for i, f in enumerate(funds):
        with cols[i % 2]:
            meta = META[f]
            st.markdown(
                f"<div class='card'>"
                f"<div style='display:flex;gap:.8rem;align-items:center'>"
                f"<div class='badge'>{meta['code']}</div>"
                f"<div><div class='eyebrow'>{meta['eyebrow']}</div>"
                f"<div style='font-family:Archivo;font-weight:700;font-size:1.15rem'>{meta['name']}</div></div></div>"
                f"<p class='descr' style='margin:.6rem 0 .4rem'>{meta['blurb']}</p>"
                f"<div style='display:flex;gap:1.4rem'>"
                f"<div><div class='stat-label'>Ann. return</div><div class='stat-value' style='font-size:1.15rem'>{m.loc[f,'ann_return']:.1%}</div></div>"
                f"<div><div class='stat-label'>Sharpe</div><div class='stat-value' style='font-size:1.15rem'>{m.loc[f,'sharpe']:.2f}</div></div>"
                f"<div><div class='stat-label'>Max DD</div><div class='stat-value' style='font-size:1.15rem'>{m.loc[f,'max_drawdown']:.1%}</div></div>"
                f"<div style='margin-left:auto'>{beats_pill(bool(b.loc[f,'beats_benchmark']))}</div>"
                f"</div></div>", unsafe_allow_html=True)
            st.button(f"View {meta['name']} →", key=f"view_{f}",
                      on_click=go_detail, args=(f,))
            st.write("")


def page_detail(d: dict, fund: str) -> None:
    m, b = d["metrics"], d["bcomp"]
    meta = META[fund]
    st.button("← Back to funds", key="back",
              on_click=lambda: st.session_state.update(selected_fund=None))
    st.markdown(f"<div class='eyebrow'>{meta['eyebrow']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='display:flex;gap:1rem;align-items:center'>"
                f"<div class='badge'>{meta['code']}</div>"
                f"<h2 style='margin:0'>{meta['name']}</h2></div>", unsafe_allow_html=True)

    cols = st.columns(5)
    stat_block(cols[0], "Annual return", f"{m.loc[fund,'ann_return']:.1%}")
    stat_block(cols[1], "Annual volatility", f"{m.loc[fund,'ann_vol']:.1%}")
    stat_block(cols[2], "Sharpe", f"{m.loc[fund,'sharpe']:.2f}")
    stat_block(cols[3], "Max drawdown", f"{m.loc[fund,'max_drawdown']:.1%}")
    cols[4].markdown("<div class='stat-label'>Vs market</div>"
                     + beats_pill(bool(b.loc[fund, "beats_benchmark"])),
                     unsafe_allow_html=True)
    st.markdown("<hr class='rule'>", unsafe_allow_html=True)

    t_over, t_perf, t_hold = st.tabs(["Overview", "Performance", "Holdings"])
    with t_over:
        st.markdown("**Why this fund?**")
        st.markdown("\n".join(f"- {g}" for g in meta["good"]))
        st.markdown("**Investment objective**")
        st.markdown(f"<p class='descr'>{meta['objective']}</p>", unsafe_allow_html=True)
        st.markdown(f"<div class='approp'><h4>Is this fund right for you?</h4>"
                    + "".join(f"<div>• {g}</div>" for g in meta["good"])
                    + "</div>", unsafe_allow_html=True)
    with t_perf:
        st.markdown("**Growth of $1**")
        st.plotly_chart(growth_fig(fund, d), use_container_width=True, config=PLOTLY_CFG)
        st.markdown("**Drawdown**")
        st.plotly_chart(drawdown_fig(fund, d), use_container_width=True, config=PLOTLY_CFG)
        mm = m.loc[fund]
        st.dataframe(pd.DataFrame({
            "Metric": ["Annual return", "Annual volatility", "Sharpe", "Max drawdown"],
            "Value": [f"{mm['ann_return']:.1%}", f"{mm['ann_vol']:.1%}",
                      f"{mm['sharpe']:.2f}", f"{mm['max_drawdown']:.1%}"]}),
            hide_index=True, width="stretch")
        st.markdown("<p class='source'>Source: results/data/fund_returns.csv, "
                    "benchmark_returns.csv.</p>", unsafe_allow_html=True)
    with t_hold:
        fig, hold, latest = holdings_fig(fund, d)
        st.markdown(f"**Current holdings** (as at {latest:%d %b %Y}, {len(hold)} positions)")
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)
        st.dataframe(hold.assign(weight=(hold.weight).map("{:.1%}".format))
                     .rename(columns={"ticker": "Holding", "weight": "Weight"}),
                     hide_index=True, width="stretch", height=280)
        st.markdown("<p class='source'>Source: results/data/fund_weights.csv "
                    "(latest rebalance).</p>", unsafe_allow_html=True)

    st.markdown(f"<div class='foot'>{OOS}. Figures are precomputed and traceable to "
                "source. Past performance is not a reliable indicator of future results.</div>",
                unsafe_allow_html=True)


def page_sentiment(d: dict) -> None:
    st.markdown("<div class='eyebrow'>NEWS SIGNAL</div>", unsafe_allow_html=True)
    st.markdown("<h2>Market sentiment</h2>", unsafe_allow_html=True)
    sent = d["sent"]
    market = sent.mean(axis=1)
    recent = float(market.tail(21).mean())
    gauge = (recent + 1) / 2 * 100
    mood = "Fearful" if gauge < 40 else "Greedy" if gauge > 60 else "Neutral"
    as_of = market.index.max()

    g1, g2 = st.columns([1, 2])
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=round(gauge, 1), number={"suffix": " / 100"},
        title={"text": f"News mood: <b>{mood}</b>"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": ACCENT},
               "steps": [{"range": [0, 40], "color": NEG},
                         {"range": [40, 60], "color": LINE},
                         {"range": [60, 100], "color": POS}]}))
    g1.plotly_chart(_style(fig, 300), use_container_width=True, config=PLOTLY_CFG)
    g1.markdown(f"<p class='source'>Equal-weight sentiment across 10 sectors, 21-day "
                f"average as at {as_of:%d %b %Y}. 50 = neutral.</p>", unsafe_allow_html=True)

    monthly = sent.resample("ME").mean()
    mm = monthly.mean(axis=1)
    figs = go.Figure()
    for col in monthly.columns:
        figs.add_trace(go.Scatter(x=monthly.index, y=monthly[col], line=dict(color=LINE, width=1),
                                  opacity=0.7, showlegend=False, hoverinfo="skip"))
    figs.add_trace(go.Scatter(x=mm.index, y=mm, name="Market average",
                              line=dict(color=ACCENT, width=2.6)))
    figs.update_yaxes(title="VADER compound (-1 to 1)")
    g2.markdown("**Sector sentiment over time**")
    g2.plotly_chart(_style(figs, 320), use_container_width=True, config=PLOTLY_CFG)

    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    st.markdown("**Did folding sentiment into the funds help?**")
    piv = d["fus"].pivot(index="fund", columns="variant", values="sharpe")
    figb = go.Figure()
    figb.add_trace(go.Bar(x=[META[f]["short"] for f in piv.index], y=piv["base"],
                          name="Base fund", marker_color=BENCH_GREY))
    figb.add_trace(go.Bar(x=[META[f]["short"] for f in piv.index], y=piv["sentiment"],
                          name="With sentiment tilt", marker_color=ACCENT))
    figb.update_yaxes(title="Sharpe ratio")
    figb.update_layout(barmode="group")
    st.plotly_chart(_style(figb, 320), use_container_width=True, config=PLOTLY_CFG)
    st.markdown("<p class='source'>The tilt lowered the Sharpe of both funds - an "
                "honest negative result. Source: sector_sentiment_index.csv, "
                "fusion_comparison.csv.</p>", unsafe_allow_html=True)


def page_allocate(d: dict) -> None:
    st.markdown("<div class='eyebrow'>YOUR PORTFOLIO</div>", unsafe_allow_html=True)
    st.markdown("<h2>Build an allocation</h2>", unsafe_allow_html=True)
    st.markdown("<p class='descr'>Blend our three multi-asset funds into one "
                "portfolio, choose how much to invest, and see how it is deployed and "
                "what you would keep after our fixed management fee.</p>",
                unsafe_allow_html=True)
    fr = d["fr"]
    blend_funds = COMBINED_FUNDS

    st.markdown("**How much in each fund?**")
    cols = st.columns(len(blend_funds))
    raw = {f: cols[i].slider(META[f]["short"], 0, 100, 33, 1, key=f"al_{f}")
           for i, f in enumerate(blend_funds)}
    total = sum(raw.values())
    if total == 0:
        st.info("Move a slider to build a blend.")
        return
    w = {f: v / total for f, v in raw.items()}

    # Amount to invest (investor's choice) and the fixed fee (not their choice).
    a1, a2 = st.columns([2, 1])
    amount = a1.number_input("Amount to invest ($)", min_value=0, value=10_000, step=500)
    a2.markdown(f"<div class='stat-label'>Management fee</div>"
                f"<div class='stat-value'>{MGMT_FEE:.2f}% p.a.</div>"
                f"<div class='source'>Fixed, accrued daily. Not a performance fee.</div>",
                unsafe_allow_html=True)

    # How the amount is deployed across the funds, from the chosen weights.
    st.markdown("**How your money is deployed**")
    dep = pd.DataFrame({
        "Fund": [META[f]["name"] for f in blend_funds],
        "Allocation": [f"{w[f]:.0%}" for f in blend_funds],
        "Amount": [f"${amount * w[f]:,.0f}" for f in blend_funds],
    })
    st.dataframe(dep, hide_index=True, width="stretch")
    # Decorative call-to-action - this is an educational demo, not a real order.
    if st.button(f"Invest ${amount:,.0f}", key="invest_cta"):
        st.success("Educational demo - no funds are moved and no order is placed.")
    st.markdown("<p class='source'>Weights are rescaled to 100%. Deployment is "
                "illustrative; the button places no real order.</p>", unsafe_allow_html=True)

    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    st.markdown("**What you would have kept, net of the fixed fee**")
    blend = sum(fr[f].fillna(0.0) * wt for f, wt in w.items())
    net = blend - (MGMT_FEE / 100.0) / 252.0
    s = annualise(net)
    c = st.columns(4)
    stat_block(c[0], "Net annual return", f"{s['ann_return']:.1%}")
    stat_block(c[1], "Volatility", f"{s['ann_vol']:.1%}")
    stat_block(c[2], "Net Sharpe", f"{s['sharpe']:.2f}")
    stat_block(c[3], f"${amount:,.0f} became", f"${amount * s['final']:,.0f}")

    gg = (1 + blend).cumprod()
    gn = (1 + net).cumprod()
    gm = (1 + d["bench"].reindex(fr.index).fillna(0.0)).cumprod()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=gm.index, y=gm, name="Equal-weight market",
                             line=dict(color=BENCH_GREY, dash="dash", width=1.6)))
    fig.add_trace(go.Scatter(x=gg.index, y=gg, name="Your blend (gross)",
                             line=dict(color="#E0B89A", width=1.4)))
    fig.add_trace(go.Scatter(x=gn.index, y=gn, name="Your blend (net of fee)",
                             line=dict(color=ACCENT, width=2.6)))
    fig.update_yaxes(title="Value of $1", tickprefix="$")
    st.plotly_chart(_style(fig), use_container_width=True, config=PLOTLY_CFG)
    st.markdown("<p class='source'>Net line is what you would keep after the fixed "
                f"{MGMT_FEE:.2f}% fee. Source: fund_returns.csv, benchmark_returns.csv.</p>",
                unsafe_allow_html=True)


def page_about(d: dict) -> None:
    st.markdown("<div class='eyebrow'>ABOUT</div>", unsafe_allow_html=True)
    st.markdown("<h2>Methodology, in plain terms</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p class='descr' style='max-width:720px'>Each fund is a systematic rule over "
        "50 US large-cap stocks and 10 cryptocurrencies. Weights are rebuilt on the "
        "first trading day of each month from the trailing year of returns, using only "
        "data available before that date - a walk-forward, out-of-sample backtest with "
        "no look-ahead. Minimum-variance targets the smoothest ride; maximum-Sharpe "
        "targets the best return per unit of risk; the two-stage variants build a stock "
        "sleeve and a crypto sleeve separately, then blend them. Every fund is scored "
        "against an equal-weight basket of the same 50 stocks.</p>",
        unsafe_allow_html=True)
    st.markdown(f"<div class='band'>{OOS}. All figures are precomputed from the "
                "backtest and read from committed files.</div>",
                unsafe_allow_html=True)
    st.markdown("<p class='foot'>Educational project, not investment advice. Past "
                "performance is not a reliable indicator of future results.</p>",
                unsafe_allow_html=True)


PAGES = {"Home": page_home, "Funds": page_funds, "Sentiment": page_sentiment,
         "Build portfolio": page_allocate, "About": page_about}


def top_nav() -> None:
    st.markdown(
        "<div class='topbar'><span class='wordmark'>REVELATIO</span>"
        "<span class='pill'>Get started</span></div>", unsafe_allow_html=True)
    cols = st.columns(len(PAGES))
    for i, name in enumerate(PAGES):
        if cols[i].button(name, key=f"nav_{name}", use_container_width=True):
            st.session_state["page"] = name
            st.session_state["selected_fund"] = None


def main() -> None:
    inject_css()
    st.session_state.setdefault("page", "Home")
    st.session_state.setdefault("selected_fund", None)
    d = load_all()
    top_nav()
    PAGES.get(st.session_state["page"], page_home)(d)


if __name__ == "__main__":
    main()

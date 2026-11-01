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
from urllib.parse import quote

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "results" / "data"
TABLES = ROOT / "results" / "tables"

st.set_page_config(page_title="Revelatio Funds", layout="wide", page_icon="")

# --- design tokens ------------------------------------------------------------
# Dark navy ground, ONE indigo accent; green is reserved for ticks and positive
# figures, red for losses.
BG = "#07071F"
PANEL = "#10102E"
ACCENT = "#5B6CF0"
ACCENT_DK = "#4F63E8"
INK = "#F5F6FA"
MUTED = "#A3A7C2"
LINE = "rgba(255,255,255,0.08)"
POS = "#8BD17C"
NEG = "#F07A7A"
BENCH_GREY = "#6E7391"     # equal-weight market line - muted slate
SP500_TINT = "#9E9070"     # S&P 500 line - muted sand; both stay quiet beside the fund
FONT = "Poppins"
REPO_URL = "https://github.com/gianni-chepote/revelatio-systematic-funds"
LINKEDIN_URL = "https://www.linkedin.com/in/gianni-chepote"
AUTHOR = {"name": "Gianni Paolo Chepote Viluce", "initials": "GPCV",
          "lines": ["Master of Finance, UNSW Sydney · Specialising in FinTech · "
                    "Graduating Dec 2027"]}
GITHUB_SVG = ("<svg viewBox='0 0 16 16' aria-hidden='true'><path d='M8 0C3.58 0 0 3.58 0 "
              "8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01"
              ".37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01"
              " 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-"
              ".89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2"
              ".82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1"
              ".16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73"
              ".54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42"
              "-3.58-8-8-8z'/></svg>")
LINKEDIN_SVG = ("<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M20.45 20.45h-3.56"
                "v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41"
                "v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43"
                "a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zM7.12 20.45H3.56V9h3.56v11.45z"
                "M22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78"
                "-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z'/></svg>")

# Holdings colours, the bright dark-mode set from How's My Portfolio. Colour follows
# the sector, never its rank, so a sector looks the same on every fund page.
SECTOR_COLORS = {
    "Information Technology": "#5A54FF",  # violet
    "Financials": "#7FC765",              # green
    "Health Care": "#E6DD5A",             # yellow
    "Consumer Discretionary": "#EFC05B",  # amber
    "Industrials": "#EF986D",             # peach
    "Communication Services": "#ED7473",  # coral
    "Consumer Staples": "#E876A8",        # pink
    "Materials": "#A08BCE",               # lavender
    "Energy": "#4F82C8",                  # navy
    "Utilities": "#3CA694",               # teal
    "Real Estate": "#5EADE2",             # sky
    "Crypto": "#D06BDB",                  # magenta, a hue no sector uses
}
# Crypto-only funds have no sectors, so each coin takes the next colour in turn.
COIN_COLORS = list(SECTOR_COLORS.values())
TOP_N = 7   # bars on the Holdings tab; the full list is in the table beneath

# GICS sector per stock. The dataset's own sector field lumps KO, WMT, NKE, SBUX and
# DIS into "Consumer", so the holdings view uses the GICS classification instead.
GICS = {
    **dict.fromkeys(["CMCSA", "DIS", "EA", "T", "TMUS", "TTWO"], "Communication Services"),
    **dict.fromkeys(["NKE", "SBUX"], "Consumer Discretionary"),
    **dict.fromkeys(["KO", "WMT"], "Consumer Staples"),
    **dict.fromkeys(["COP", "CVX", "OXY", "SLB", "XOM"], "Energy"),
    **dict.fromkeys(["GS", "MS", "USB", "V", "WFC"], "Financials"),
    **dict.fromkeys(["ABBV", "ABT", "AMGN", "GILD", "MRK"], "Health Care"),
    **dict.fromkeys(["BA", "CAT", "GE", "MMM", "UPS"], "Industrials"),
    **dict.fromkeys(["ADBE", "AMD", "INTC", "NVDA", "QCOM"], "Information Technology"),
    **dict.fromkeys(["DD", "DOW", "NEM", "NUE", "SHW"], "Materials"),
    **dict.fromkeys(["AMT", "CCI", "O", "PLD", "PSA"], "Real Estate"),
    **dict.fromkeys(["AEP", "D", "DUK", "NEE", "SO"], "Utilities"),
}
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
        blurb=f"{adesc[0].upper()}{adesc[1:]}; {_STYLE_BLURB[method]}",
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
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');

    :root {{
      --bg:{BG}; --panel:{PANEL}; --panel-hi:#15153A; --ink:{INK}; --muted:{MUTED};
      --line:{LINE}; --line-accent:rgba(91,108,240,0.45); --accent:{ACCENT};
      --accent-dk:{ACCENT_DK}; --pos:{POS}; --neg:{NEG};
    }}
    /* hide default streamlit chrome */
    #MainMenu, header[data-testid="stHeader"], footer {{visibility:hidden; height:0;}}
    [data-testid="stToolbar"] {{display:none;}}
    /* navy ground with faint vertical grid lines and a soft indigo glow up top */
    .stApp {{background-color:var(--bg);
      background-image:
        radial-gradient(ellipse 70% 40% at 50% -8%, rgba(91,108,240,0.16), transparent 70%),
        linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
      background-size:100% 100%, 120px 100%;}}
    .block-container {{max-width:1200px; padding-top:0; padding-bottom:4rem;}}
    /* full-bleed hero bands must not cause sideways scroll */
    [data-testid="stMain"], .stMain {{overflow-x:clip;}}
    /* hide the link icon Streamlit adds beside markdown headings */
    [data-testid="stHeaderActionElements"], .stMarkdown h1 a, .stMarkdown h2 a {{display:none !important;}}

    html, body, .stApp, [class*="css"], .stMarkdown, .stDataFrame, button, input,
    textarea, select, label, p, li, span, div {{font-family:'{FONT}',system-ui,sans-serif;}}
    body, p, li, label {{font-weight:400;}}
    h1,h2,h3,h4 {{font-family:'{FONT}',sans-serif !important; font-weight:600 !important;
      letter-spacing:-0.02em; color:var(--ink);}}
    h1 {{font-size:3.1rem; line-height:1.08;}}
    h2 {{font-size:1.8rem; margin-top:0.4rem;}}
    p, li, label, .stMarkdown {{color:var(--ink);}}
    .stMarkdown p strong {{color:var(--ink); font-weight:700;}}

    /* sticky site header: one flat row, full-bleed translucent navy */
    /* Streamlit wraps the keyed container in a same-height stLayoutWrapper, so the
       wrapper is what must stick; the header itself carries the look. */
    [data-testid="stLayoutWrapper"]:has(> .st-key-site_header) {{position:sticky; top:0;
      z-index:1000;}}
    .st-key-site_header {{position:relative; padding:0.7rem 0; overflow:visible;}}
    /* full-bleed translucent band behind the header; a pseudo-element rather than
       box-shadow + clip-path, so the author drop-down can overflow below it */
    .st-key-site_header::before {{content:""; position:absolute; top:0; bottom:0;
      left:-100vmax; right:-100vmax; z-index:-1; background:rgba(7,7,31,0.78);
      backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
      border-bottom:1px solid rgba(255,255,255,0.06);}}
    .st-key-site_header [data-testid="stColumn"],
    .st-key-site_header [data-testid="stHorizontalBlock"],
    .st-key-site_header .stMarkdown, .st-key-site_header [data-testid="stElementContainer"]
      {{overflow:visible !important;}}
    /* Streamlit's -1rem markdown margin makes the row mis-centre the pill */
    .st-key-site_header [data-testid="stMarkdownContainer"] {{margin-bottom:0 !important;}}
    .st-key-site_header [data-testid="stMarkdownContainer"] p {{margin:0 !important;}}
    .st-key-site_header [data-testid="stHorizontalBlock"] {{flex-wrap:wrap !important;
      align-items:center; gap:0.2rem 1.6rem !important;}}
    .st-key-site_header [data-testid="stColumn"] {{flex:0 0 auto !important;
      width:auto !important; min-width:0 !important;}}
    .st-key-site_header [data-testid="stColumn"]:last-child {{margin-left:auto;}}
    .wordmark {{font-weight:700; font-size:1.3rem; letter-spacing:-0.01em;
      color:var(--ink); margin-right:1.2rem; white-space:nowrap;}}
    .wordmark span {{color:var(--accent);}}
    a.gh-pill, summary.gh-pill {{display:inline-flex; align-items:center; gap:0.45rem;
      background:var(--accent); color:#fff !important; padding:0.45rem 1.05rem;
      border-radius:999px; font-weight:500; font-size:0.82rem; text-decoration:none;
      white-space:nowrap; transition:background .2s ease, transform .2s ease;}}
    a.gh-pill:hover, summary.gh-pill:hover {{background:var(--accent-dk);
      transform:translateY(-1px);}}

    /* author drop-down and card */
    .author-menu {{position:relative; display:flex; flex-direction:column;
      align-items:flex-end; margin:0;}}
    .author-menu summary {{list-style:none; cursor:pointer; user-select:none;}}
    .author-menu summary::-webkit-details-marker {{display:none;}}
    .author-menu .chev {{font-size:0.7rem; transition:transform .2s ease;}}
    .author-menu[open] .chev {{transform:rotate(180deg);}}
    .author-menu > .author-card {{position:absolute; right:0; top:calc(100% + 0.7rem);
      width:430px; z-index:2000; box-shadow:0 18px 50px rgba(0,0,0,0.55);
      animation:pop .18s ease;}}
    @keyframes pop {{from {{opacity:0; transform:translateY(-6px);}}
                    to {{opacity:1; transform:none;}}}}
    .author-card {{background:var(--panel); border:1px solid var(--line-accent);
      border-radius:20px; padding:1.3rem 1.3rem 1.2rem; text-align:left;}}
    .author-top {{display:flex; gap:0.9rem; align-items:center;}}
    .avatar {{flex:none; width:56px; height:56px; border-radius:50%;
      display:flex; align-items:center; justify-content:center;
      background:linear-gradient(145deg, var(--accent), #3B47B8); color:#fff;
      font-weight:600; font-size:0.85rem; letter-spacing:0.04em;}}
    .author-card .nb {{white-space:nowrap;}}
    .author-name {{font-weight:600; font-size:1.02rem; color:var(--ink); line-height:1.3;}}
    .author-card p {{margin:0.15rem 0 0 !important; color:var(--muted); font-size:0.82rem;
      line-height:1.45;}}
    .author-actions {{display:flex; gap:0.5rem; margin-top:1.1rem;}}
    .author-actions a {{display:inline-flex; align-items:center; justify-content:center;
      gap:0.45rem; border-radius:999px; padding:0.5rem 1rem; font-size:0.84rem;
      font-weight:500; text-decoration:none !important; transition:background .2s ease;}}
    .author-actions svg {{width:15px; height:15px; fill:currentColor;}}
    .btn-in {{flex:1; background:var(--accent); color:#fff !important;}}
    .btn-in:hover {{background:var(--accent-dk);}}
    .btn-gh {{border:1px solid var(--line-accent); color:var(--ink) !important;}}
    .btn-gh:hover {{background:rgba(91,108,240,0.14);}}
    /* larger, centred version on About */
    .author-card.lg {{max-width:560px; margin:0 auto 1.6rem; padding:1.8rem 2rem 1.6rem;
      text-align:center;}}
    .author-card.lg .author-top {{flex-direction:column; gap:0.8rem;}}
    .author-card.lg .avatar {{width:84px; height:84px; font-size:1.15rem;}}
    .author-card.lg .author-name {{font-size:1.35rem;}}
    .author-card.lg p {{font-size:0.95rem;}}
    .author-card.lg .author-actions {{justify-content:center; margin-top:1.4rem;}}
    .author-card.lg .btn-in {{flex:none; padding:0.6rem 1.4rem;}}
    a.gh-pill svg {{width:15px; height:15px; fill:currentColor;}}
    @media (max-width: 640px) {{
      .author-menu {{align-items:flex-start;}}
      .author-menu > .author-card {{position:static; width:calc(100vw - 2rem);
        max-width:calc(100vw - 2rem); box-sizing:border-box; margin-top:0.7rem;
        box-shadow:none;}}
      .author-card .nb {{white-space:normal;}}
      .author-actions {{flex-wrap:wrap;}}
    }}

    /* nav items: plain text links, active page in indigo with a thin underline */
    .st-key-site_header .stButton > button,
    .st-key-site_header .stButton [data-testid^="stBaseButton"] {{background:transparent !important;
      border:none !important; border-radius:0 !important; box-shadow:none !important;
      color:var(--ink) !important; font-weight:400; font-size:0.95rem;
      padding:0.35rem 0.1rem !important; min-height:0; width:auto !important;
      transition:color .2s ease, box-shadow .2s ease;}}
    .st-key-site_header .stButton > button:hover,
    .st-key-site_header .stButton [data-testid^="stBaseButton"]:hover {{color:#C9CEFF !important;
      box-shadow:inset 0 -1px 0 rgba(91,108,240,0.6) !important;}}
    .st-key-site_header .stButton [data-testid="stBaseButton-primary"],
    .st-key-site_header .stButton > button[kind="primary"] {{color:var(--accent) !important;
      font-weight:500; box-shadow:inset 0 -2px 0 var(--accent) !important;}}

    /* page hero: deep-navy band with a faint chart drawn from the backtest */
    .hero {{position:relative; isolation:isolate; overflow:hidden; text-align:center;
      margin:-1rem calc(50% - 50vw) 2.4rem; padding:5.4rem 1.5rem 3.8rem;}}
    .hero::before {{content:""; position:absolute; inset:0; z-index:-2;
      background:radial-gradient(ellipse 55% 75% at 50% 0%, rgba(91,108,240,0.22), transparent 72%),
                 linear-gradient(180deg, rgba(12,12,46,0.95) 0%, rgba(7,7,31,0) 100%);}}
    .hero .art {{position:absolute; inset:0; z-index:-1; background-size:100% 100%;
      background-repeat:no-repeat; opacity:0.18;
      -webkit-mask-image:linear-gradient(180deg, transparent 0%, #000 30%, #000 60%, transparent 100%);
      mask-image:linear-gradient(180deg, transparent 0%, #000 30%, #000 60%, transparent 100%);}}
    .hero h1.page-title {{font-size:clamp(2.5rem, 5.4vw, 4.4rem) !important;
      line-height:1.08 !important; margin:1.2rem auto 1rem !important; padding:0 !important;
      max-width:1120px; color:var(--ink); text-wrap:balance;}}
    .hero .subtitle {{font-weight:300; font-size:1.15rem; line-height:1.6;
      color:rgba(245,246,250,0.72); max-width:700px; margin:0 auto;}}
    .section-head {{text-align:center; margin:0.4rem 0 1.8rem;}}
    .section-head h2.section-title {{font-size:clamp(1.8rem, 3.3vw, 2.5rem) !important;
      margin:0.35rem 0 0 !important; padding:0 !important;}}

    @media (max-width: 640px) {{
      [data-testid="stLayoutWrapper"]:has(> .st-key-site_header) {{position:relative;}}
      .st-key-site_header [data-testid="stHorizontalBlock"] {{gap:0.1rem 1rem !important;}}
      .st-key-site_header [data-testid="stColumn"]:last-child {{margin-left:0;}}
      .hero {{padding:3.2rem 1rem 2.6rem;}}
    }}

    /* eyebrow / hero badge / fund badge / stat */
    .eyebrow {{text-transform:uppercase; letter-spacing:0.14em; font-size:0.72rem;
      font-weight:700; color:var(--accent);}}
    .hero-badge {{display:inline-flex; align-items:center; gap:0.5rem;
      border:1px solid var(--line-accent); background:rgba(91,108,240,0.08);
      color:var(--ink); padding:0.35rem 0.9rem; border-radius:999px;
      font-size:0.8rem; font-weight:500;}}
    .hero-badge .dot {{width:7px; height:7px; border-radius:50%; background:var(--pos);
      box-shadow:0 0 0 3px rgba(139,209,124,0.18);}}
    .badge {{display:inline-flex; align-items:center; justify-content:center;
      width:52px; height:52px; border-radius:14px; flex:none;
      background:linear-gradient(145deg, var(--accent), #3B47B8);
      color:#fff; font-weight:600; font-size:0.85rem; letter-spacing:0.02em;}}
    .stat-label {{font-size:0.72rem; color:var(--muted); text-transform:uppercase;
      letter-spacing:0.07em; font-weight:500;}}
    .stat-value {{font-weight:600; font-size:1.5rem; color:var(--ink); line-height:1.15;}}
    .stat-value.pos {{color:var(--pos);}}
    .stat-value.neg {{color:var(--neg);}}

    .pill-pos, .pill-neg {{display:inline-flex; align-items:center; gap:0.35rem;
      padding:0.22rem 0.7rem; border-radius:999px; font-weight:600; font-size:0.76rem;
      white-space:nowrap;}}
    .pill-pos {{background:rgba(139,209,124,0.12); color:var(--pos);
      border:1px solid rgba(139,209,124,0.30);}}
    .pill-neg {{background:rgba(255,255,255,0.04); color:var(--muted);
      border:1px solid var(--line);}}
    .pills {{display:flex; gap:0.4rem; flex-wrap:wrap; margin-top:0.7rem;}}

    /* fund page: key metrics card */
    .metrics-card {{display:grid; grid-template-columns:repeat(5, minmax(0, 1fr));
      background:var(--panel); border:1px solid var(--line-accent); border-radius:20px;
      padding:0; margin:0.4rem 0 2.2rem; overflow:hidden;}}
    /* every column fills the card's full height (grid stretch) so dividers run
       top to bottom; content is top-aligned with identical padding, so all labels
       share one line and all figures (and the first pill) the next */
    .metrics-card .m {{display:flex; flex-direction:column; justify-content:flex-start;
      align-items:center; text-align:center; padding:1.35rem 0.8rem 1.2rem;
      border-left:1px solid var(--line); min-width:0;}}
    .metrics-card .m:first-child {{border-left:none;}}
    .metrics-card .stat-label {{margin:0 0 0.5rem; line-height:1.2; white-space:nowrap;}}
    .metrics-card .stat-value {{margin:0;}}
    .metrics-card .stat-value {{font-size:1.6rem; line-height:1.2;}}
    .metrics-card .m-sub {{font-size:0.75rem; color:var(--muted); margin-top:0.3rem;}}

    /* home: backtest timeline */
    .timeline {{display:flex; gap:6px; margin:0.2rem 0 0.4rem; border-radius:16px;
      overflow:hidden;}}
    .timeline .seg {{padding:0.9rem 1.1rem 1.1rem; display:flex; flex-direction:column;
      align-items:center; justify-content:flex-start; text-align:center; gap:0.15rem;
      position:relative;}}
    .timeline .seg b {{font-weight:600; font-size:0.9rem; color:var(--ink);}}
    .timeline .seg span {{font-size:0.8rem; color:var(--muted);}}
    .timeline .train {{flex:1; background:rgba(255,255,255,0.06);
      border:1px dashed rgba(255,255,255,0.18); border-radius:16px 0 0 16px;}}
    .timeline .live {{flex:3; background:rgba(91,108,240,0.18);
      border:1px solid var(--line-accent); border-radius:0 16px 16px 0;}}
    .timeline .live span {{color:#C9CEFF;}}
    .ticks-row {{display:flex; justify-content:space-between; margin-top:0.7rem;
      align-self:stretch;}}
    .ticks-row i {{width:2px; height:10px; border-radius:1px; background:rgba(201,206,255,0.55);}}

    /* home: study design grid */
    .spec-grid {{display:grid; grid-template-columns:repeat(4, minmax(0, 1fr));
      background:var(--panel); border:1px solid var(--line); border-radius:20px;
      overflow:hidden;}}
    .spec {{padding:1.2rem 1.3rem; border-left:1px solid var(--line);
      border-top:1px solid var(--line); text-align:center;}}
    .spec:nth-child(4n+1) {{border-left:none;}}
    .spec:nth-child(-n+4) {{border-top:none;}}
    .spec p {{margin:0.45rem 0 0; color:var(--ink); font-size:0.9rem; line-height:1.5;}}

    /* home: findings - equal-height cards, rows aligned across cards */
    .findings {{display:grid; grid-template-columns:repeat(3, minmax(0, 1fr));
      grid-template-rows:auto auto 1fr; column-gap:1rem;}}
    .finding {{display:grid; grid-row:span 3; grid-template-rows:subgrid; row-gap:0.5rem;
      background:var(--panel); border:1px solid var(--line); border-radius:20px;
      padding:1.4rem 1.4rem 1.5rem; text-align:center;
      transition:border-color .2s ease, transform .2s ease;}}
    .finding:hover {{border-color:var(--line-accent); transform:translateY(-2px);}}
    .finding .stat-value {{color:var(--accent);}}
    .finding h4 {{margin:0; padding:0; font-size:1.2rem; line-height:1.3; align-self:start;}}
    .finding p {{margin:0;}}

    .findings.two {{grid-template-columns:repeat(2, minmax(0, 1fr));}}
    .center-note {{text-align:center; max-width:820px; margin:1rem auto 0 !important;}}
    .pos {{color:var(--pos);}} .neg {{color:var(--neg);}}

    /* about: method cards (keyed Streamlit containers so st.latex sits inside) */
    [class*="st-key-method_"] {{background:var(--panel); border:1px solid var(--line);
      border-radius:20px; padding:1.3rem 1.2rem 0.6rem; min-height:11.5rem;
      justify-content:space-between;}}
    [class*="st-key-method_"] .stMarkdown, [class*="st-key-method_"] p,
    [class*="st-key-method_"] .stat-label {{text-align:center !important;}}
    [class*="st-key-method_"] .katex {{color:var(--ink); font-size:1.15em;}}
    .method-blurb {{min-height:3.2em; margin:0.5rem 0 0 !important;}}

    /* about: sentiment pipeline */
    .pipeline {{display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:0.8rem;}}
    .pipeline .step {{background:var(--panel); border:1px solid var(--line);
      border-radius:18px; padding:1.1rem 1rem; text-align:center; position:relative;}}
    .pipeline .step + .step::before {{content:"→"; position:absolute; left:-0.72rem;
      top:50%; transform:translateY(-50%); color:var(--accent); font-weight:600;}}
    .pipeline .n {{display:inline-flex; width:1.7rem; height:1.7rem; border-radius:50%;
      align-items:center; justify-content:center; background:rgba(91,108,240,0.18);
      color:#C9CEFF; font-size:0.8rem; font-weight:600;}}
    .pipeline b {{display:block; margin:0.5rem 0 0.3rem; font-weight:600;}}
    .pipeline p {{margin:0; color:var(--muted); font-size:0.85rem; line-height:1.5;}}

    /* about: extensions table */
    .ext-table {{background:var(--panel); border:1px solid var(--line); border-radius:20px;
      overflow:hidden;}}
    .ext-row {{display:grid; grid-template-columns:2.2fr 1fr 1fr 1.4fr; gap:1rem;
      align-items:center; padding:1rem 1.4rem; border-top:1px solid var(--line);}}
    .ext-row.head {{border-top:none; color:var(--muted); font-size:0.72rem;
      text-transform:uppercase; letter-spacing:0.07em; font-weight:500;}}
    .ext-row span:not(:first-child) {{text-align:center;}}
    .ext-row b {{display:block; font-weight:600;}}
    .ext-row em {{display:block; font-style:normal; color:var(--muted); font-size:0.85rem;
      margin-top:0.2rem;}}
    .ext-row .verdict {{color:var(--muted); font-size:0.88rem;}}

    /* about: limitations */
    .limits {{display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:0.9rem;}}
    .limit {{background:var(--panel); border:1px solid var(--line);
      border-left:3px solid var(--neg); border-radius:16px; padding:1.1rem 1.2rem;}}
    .limit b {{font-weight:600;}}
    .limit p {{margin:0.35rem 0 0; color:var(--muted); font-size:0.88rem; line-height:1.55;}}

    /* about: stack chips */
    .chips {{display:flex; flex-wrap:wrap; justify-content:center; gap:0.6rem;}}
    .chips span {{border:1px solid var(--line-accent); background:rgba(91,108,240,0.08);
      border-radius:999px; padding:0.4rem 1rem; font-size:0.88rem;}}

    /* fund cards: blurbs reserve two lines so stats, pills and buttons line up */
    .fund-blurb {{margin:0 !important; padding:0.7rem 0 0.5rem; min-height:4.4em;
      box-sizing:border-box;}}

    .pill-stack {{display:inline-grid; gap:0.25rem;}}
    .pill-stack span {{justify-content:center; font-size:0.68rem; padding:0.12rem 0.6rem;}}

    /* back button sits on top of the hero band, top-left */
    .st-key-back {{position:relative; z-index:5; margin-top:1.4rem;}}
    .hero.under-back {{margin-top:-5.9rem; padding-top:7rem;}}
    @media (max-width: 640px) {{
      .hero.under-back {{padding-top:5.6rem;}}
      .metrics-card {{grid-template-columns:repeat(2, minmax(0, 1fr));}}
      .metrics-card .m {{padding:1.1rem 0.6rem;}}
      .metrics-card .m:nth-child(n+3) {{border-top:1px solid var(--line);}}
      .metrics-card .m {{border-left:none;}}
      .metrics-card .m:nth-child(even) {{border-left:1px solid var(--line);}}
      .metrics-card .m:last-child:nth-child(odd) {{grid-column:1 / -1; border-left:none;}}
      .timeline {{flex-direction:column;}}
      .timeline .train, .timeline .live {{border-radius:16px;}}
      .spec-grid {{grid-template-columns:1fr;}}
      .findings {{grid-template-columns:1fr; grid-template-rows:none; row-gap:1rem;}}
      .finding {{grid-row:auto; grid-template-rows:none;}}
      .fund-blurb {{min-height:0;}}
      .findings.two, .limits, .pipeline {{grid-template-columns:1fr;}}
      .pipeline .step + .step::before {{content:"↓"; left:50%; top:-0.85rem;
        transform:translateX(-50%);}}
      .ext-row {{grid-template-columns:1fr 1fr; }}
      .ext-row span:first-child, .ext-row .verdict {{grid-column:1 / -1; text-align:center;}}
      .ext-row.head span:first-child, .ext-row.head span:last-child {{display:none;}}
      .spec {{border-left:none !important; border-top:1px solid var(--line) !important;}}
      .spec:first-child {{border-top:none !important;}}
      .metrics-card .m.bench {{grid-column:1 / -1; border-left:none;
        border-top:1px solid var(--line);}}
    }}

    .card {{background:var(--panel); border:1px solid var(--line); border-radius:20px;
      padding:1.25rem 1.35rem; height:100%;
      transition:border-color .2s ease, transform .2s ease;}}
    .card:hover {{border-color:var(--line-accent); transform:translateY(-2px);}}
    .card h4 {{color:var(--ink);}}
    .fund-name {{font-weight:600; font-size:1.15rem; color:var(--ink);}}
    .rule {{border:none; border-top:1px solid var(--line); margin:2rem 0;}}
    .band {{background:var(--panel); border:1px solid var(--line-accent);
      border-radius:20px; padding:1.4rem 1.7rem; color:var(--ink);}}
    .band .sep {{color:var(--muted); margin:0 0.6rem;}}
    .approp {{border:1px solid var(--line-accent); border-radius:18px;
      padding:1.1rem 1.3rem; background:var(--panel);}}
    .approp h4 {{margin:0 0 0.6rem 0; font-size:1rem;}}
    .source {{font-size:0.75rem; color:var(--muted); margin-top:0.3rem;}}
    .descr {{color:var(--muted); font-size:0.93rem; line-height:1.6;}}
    .foot {{color:var(--muted); font-size:0.78rem; border-top:1px solid var(--line);
      padding-top:0.9rem; margin-top:2rem;}}

    /* green-tick bullets */
    ul.ticks {{list-style:none; padding:0; margin:0.2rem 0 0.4rem;}}
    ul.ticks li {{position:relative; padding-left:2rem; margin:0.55rem 0;
      color:var(--ink); line-height:1.5;}}
    ul.ticks li::before {{content:""; position:absolute; left:0; top:0.1rem;
      width:1.25rem; height:1.25rem; border-radius:50%; background:var(--pos);}}
    ul.ticks li::after {{content:""; position:absolute; left:0.45rem; top:0.33rem;
      width:0.3rem; height:0.58rem; border:solid {BG}; border-width:0 2px 2px 0;
      transform:rotate(45deg);}}

    /* buttons: primary = filled indigo pill, secondary = indigo outline */
    .stButton > button {{border-radius:999px; font-weight:600; padding:0.45rem 1.1rem;
      transition:background .2s ease, border-color .2s ease, color .2s ease;}}
    .stButton > button[kind="secondary"],
    .stButton [data-testid="stBaseButton-secondary"] {{background:transparent;
      color:var(--ink); border:1px solid var(--line-accent);}}
    .stButton > button[kind="secondary"]:hover,
    .stButton [data-testid="stBaseButton-secondary"]:hover {{background:rgba(91,108,240,0.14);
      border-color:var(--accent); color:#fff;}}
    .stButton > button[kind="primary"],
    .stButton [data-testid="stBaseButton-primary"] {{background:var(--accent);
      color:#fff; border:1px solid var(--accent);}}
    .stButton > button[kind="primary"]:hover,
    .stButton [data-testid="stBaseButton-primary"]:hover {{background:var(--accent-dk);
      border-color:var(--accent-dk);}}
    div[data-testid="column"] .stButton > button {{width:100%;}}

    /* tables, tabs, inputs */
    [data-testid="stDataFrame"] {{border:1px solid var(--line); border-radius:14px;
      overflow:hidden;}}
    .stTabs [data-baseweb="tab-list"] {{gap:1.6rem; border-bottom:1px solid var(--line);}}
    .stTabs [data-baseweb="tab"] {{font-weight:600; color:var(--muted); padding:0.6rem 0.2rem;}}
    .stTabs [aria-selected="true"] {{color:var(--ink);}}
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
    # S&P 500 (SPY, dividends included), built by scripts/build_sp500_benchmark.py.
    sp500 = pd.read_csv(DATA / "sp500_returns.csv", index_col=0, parse_dates=True)["SP500"]
    return {"fr": fr, "bench": bench, "metrics": metrics, "bcomp": bcomp,
            "weights": weights, "sent": sent, "fus": fus, "sp500": sp500,
            "hero_art": _hero_art(fr["Combined_MaxSharpe"])}


def _latest_holdings(weights: pd.DataFrame, fund: str) -> pd.DataFrame:
    """Target weights at the fund's most recent rebalance, largest first."""
    wf = weights[weights.fund == fund]
    hold = (wf[wf.rebalance_date == wf.rebalance_date.max()][["ticker", "weight"]]
            .sort_values("weight", ascending=False))
    return hold[hold.weight > 0.0005].reset_index(drop=True)


def _hero_art(r: pd.Series) -> str:
    """Faint backdrop for the page heroes: the High Growth fund's weekly growth
    curve over faint gridlines, with weekly move sizes as bars. Real backtest data,
    drawn as an SVG data URI."""
    g = (1 + r.dropna()).cumprod().resample("W").last()
    w, h = 1600, 460
    xs = np.linspace(0, w, len(g))
    ys = h * 0.82 - (g - g.min()) / (g.max() - g.min()) * h * 0.6
    pts = " ".join(f"{x:.0f},{y:.0f}" for x, y in zip(xs, ys))
    moves = g.pct_change().abs().fillna(0.0)
    bw = w / len(g) * 0.55
    bars = "".join(f"<rect x='{x - bw / 2:.1f}' y='{h - m * 1400:.1f}' width='{bw:.1f}' "
                   f"height='{m * 1400:.1f}'/>" for x, m in zip(xs, moves))
    grid = "".join(f"<line x1='0' x2='{w}' y1='{y}' y2='{y}'/>" for y in range(40, h, 70))
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' "
           f"preserveAspectRatio='none'>"
           f"<g stroke='#A3A7C2' stroke-width='1' opacity='0.5'>{grid}</g>"
           f"<g fill='#5B6CF0' opacity='0.55'>{bars}</g>"
           f"<polygon points='0,{h} {pts} {w},{h}' fill='#5B6CF0' opacity='0.35'/>"
           f"<polyline points='{pts}' fill='none' stroke='#9AA5F7' stroke-width='3'/></svg>")
    return "data:image/svg+xml," + quote(svg)


def beats_sp500(d: dict, fund: str) -> bool:
    """Sharpe above the S&P 500's over the same out-of-sample days."""
    return bool(d["metrics"].loc[fund, "sharpe"] > annualise(d["sp500"])["sharpe"])


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
        font=dict(family=FONT, color=MUTED, size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(color=INK)),
        hoverlabel=dict(bgcolor=PANEL, bordercolor=ACCENT, font=dict(color=INK, family=FONT)),
        hovermode="x unified")
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=LINE)
    fig.update_yaxes(gridcolor=LINE, zeroline=False)
    return fig


def _add_benchmarks(fig: go.Figure, d: dict, index: pd.DatetimeIndex) -> None:
    """Equal-weight market and S&P 500 growth-of-$1 lines over the given dates."""
    # Solid but muted, and drawn first, so the fund's indigo line sits on top.
    for series, name, color in ((d["bench"], "Equal-weight market", BENCH_GREY),
                                (d["sp500"], "S&P 500", SP500_TINT)):
        g = (1 + series.reindex(index).fillna(0.0)).cumprod()
        fig.add_trace(go.Scatter(x=g.index, y=g, name=name,
                                 line=dict(color=color, width=1.5)))


PLOTLY_CFG = {"displayModeBar": False}


def growth_fig(fund: str, d: dict) -> go.Figure:
    r = d["fr"][fund].dropna()
    gf = (1 + r).cumprod()
    fig = go.Figure()
    _add_benchmarks(fig, d, r.index)
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
                               fillcolor="rgba(240,122,122,0.16)"))
    fig.update_yaxes(title="Decline from peak", tickformat=".0%")
    return _style(fig)


def holding_groups(fund: str, hold: pd.DataFrame, d: dict) -> tuple[pd.Series, dict]:
    """Group each holding and colour each group. Stocks group by GICS sector and
    coins as "Crypto"; a crypto-only fund has no sectors, so each coin is its own
    group, coloured by descending weight."""
    if FAMILY_OF[fund] == "Crypto":
        groups = hold.ticker
        return groups, dict(zip(groups, COIN_COLORS))
    return hold.ticker.map(GICS).fillna("Crypto"), SECTOR_COLORS


def holdings_fig(fund: str, d: dict):
    w = d["weights"]
    latest = w.loc[w.fund == fund, "rebalance_date"].max()
    hold = _latest_holdings(w, fund)
    groups, colors = holding_groups(fund, hold, d)
    top = hold.head(TOP_N).assign(group=groups.head(TOP_N)).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top.weight, y=top.ticker, orientation="h", customdata=top.group,
        marker=dict(color=[colors[g] for g in top.group], cornerradius="45%"),
        hovertemplate="<b>%{y}</b> · %{customdata}<br>%{x:.1%}<extra></extra>"))
    fig.update_layout(bargap=0.45, hovermode="closest")
    fig.update_xaxes(title="Portfolio weight", tickformat=".1~%", showgrid=True,
                     gridcolor="rgba(255,255,255,0.05)")
    fig.update_yaxes(showgrid=False)
    return _style(fig, 90 + 34 * len(top)), hold, latest


def sector_donut(fund: str, d: dict, hold: pd.DataFrame) -> go.Figure:
    """Donut of the fund's weight by sector (by coin for crypto-only funds). Names
    and shares show on hover; the bar chart below carries the holding detail."""
    groups, colors = holding_groups(fund, hold, d)
    by = hold.assign(group=groups).groupby("group").weight.sum().sort_values(ascending=False)
    by = by / by.sum()
    fig = go.Figure(go.Pie(
        labels=by.index, values=by.values, hole=0.64, sort=False, direction="clockwise",
        rotation=0, textinfo="none",
        marker=dict(colors=[colors[g] for g in by.index], line=dict(color=BG, width=2)),
        hovertemplate="<b>%{label}</b><br>%{percent:.1%}<extra></extra>"))
    fig = _style(fig, 300)
    fig.update_layout(showlegend=False, margin=dict(l=6, r=6, t=6, b=6), annotations=[dict(
        text=(f"<span style='font-size:12px;color:{MUTED}'>"
              f"{'coins' if FAMILY_OF[fund] == 'Crypto' else 'sectors'}</span><br>"
              f"<b>{len(by)}</b>"),
        showarrow=False, font=dict(size=26, color=INK, family=FONT), x=0.5, y=0.5)])
    return fig


# --- small components ---------------------------------------------------------

def stat_block(col, label: str, value: str, tone: str = "") -> None:
    col.markdown(f"<div class='stat-label'>{label}</div>"
                 f"<div class='stat-value {tone}'>{value}</div>", unsafe_allow_html=True)


def _sign(x: float) -> str:
    """CSS tone for a figure: green when positive, red when negative."""
    return "pos" if x > 0 else "neg" if x < 0 else ""


def beats_pill(beats: bool, against: str) -> str:
    return (f"<span class='pill-pos'>✓ Beats {against}</span>" if beats
            else f"<span class='pill-neg'>Trails {against}</span>")


def bench_pills(d: dict, fund: str) -> str:
    """Two pills: Sharpe vs the equal-weight market and vs the S&P 500."""
    return ("<div class='pills'>"
            + beats_pill(bool(d["bcomp"].loc[fund, "beats_benchmark"]), "equal-weight")
            + beats_pill(beats_sp500(d, fund), "S&P 500") + "</div>")


def hero(d: dict, badge: str, title: str, subtitle: str, under_back: bool = False) -> None:
    """Centred page opener: pill badge, large title, one-line subtitle, on a
    full-width navy band with the faint backtest chart behind it. ``under_back``
    pulls the band up behind a back button placed just before it."""
    cls = "hero under-back" if under_back else "hero"
    st.markdown(
        f"<div class='{cls}'><div class='art' style=\"background-image:url('{d['hero_art']}')\">"
        f"</div><span class='hero-badge'><span class='dot'></span>{badge}</span>"
        f"<h1 class='page-title'>{title}</h1><p class='subtitle'>{subtitle}</p></div>",
        unsafe_allow_html=True)


# Gauge ramp in the site's pastel palette: solid coral to 15, solid green from 85.
MOOD_STOPS = [(0, "#E07A7A"), (15, "#E07A7A"), (30, "#E9A07A"), (50, "#F7D47F"),
              (70, "#A0D97F"), (85, "#7CC47F"), (100, "#7CC47F")]


def _mood_color(v: float) -> str:
    """Colour of the ramp at score ``v`` (0-100), interpolated between stops."""
    def rgb(h):
        return [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    for (x0, c0), (x1, c1) in zip(MOOD_STOPS, MOOD_STOPS[1:]):
        if v <= x1:
            t = (v - x0) / (x1 - x0)
            a, b = rgb(c0), rgb(c1)
            return "#%02X%02X%02X" % tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))
    return MOOD_STOPS[-1][1]


def _mood_gradient(n: int = 100) -> list[dict]:
    """Gauge background as a smooth five-stop ramp: many thin opaque steps,
    overlapping slightly so no anti-aliased seams show between them."""
    return [{"range": [100 * k / n, min(100, 100 * (k + 1) / n + 0.8)],
             "color": _mood_color(100 * (k + 0.5) / n), "thickness": 1,
             "line": {"width": 0}} for k in range(n)]


def author_card(size: str = "") -> str:
    """The author card: initials avatar, name, credentials, LinkedIn and GitHub.
    Shown in the header drop-down and, larger (``size="lg"``), on About."""
    # keep each " · "-separated part whole, so lines only break between parts
    lines = "".join("<p>" + " · ".join(f"<span class='nb'>{part}</span>"
                                        for part in x.split(" · ")) + "</p>"
                    for x in AUTHOR["lines"])
    return (f"<div class='author-card {size}'><div class='author-top'>"
            f"<div class='avatar'>{AUTHOR['initials']}</div><div>"
            f"<div class='author-name'>{AUTHOR['name']}</div>{lines}</div></div>"
            f"<div class='author-actions'>"
            f"<a class='btn-in' href='{LINKEDIN_URL}' target='_blank' rel='noopener'>"
            f"{LINKEDIN_SVG}Connect on LinkedIn</a>"
            f"<a class='btn-gh' href='{REPO_URL}' target='_blank' rel='noopener'>"
            f"{GITHUB_SVG}GitHub</a></div></div>")


def section(title: str, eyebrow: str = "") -> None:
    """Centred section heading for the main blocks further down a page."""
    eb = f"<div class='eyebrow'>{eyebrow}</div>" if eyebrow else ""
    st.markdown(f"<div class='section-head'>{eb}<h2 class='section-title'>{title}</h2></div>",
                unsafe_allow_html=True)


def ticks(items) -> str:
    return "<ul class='ticks'>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def go_detail(fund: str) -> None:
    st.session_state["selected_fund"] = fund
    st.session_state["page"] = "Funds"


# --- pages --------------------------------------------------------------------

def page_home(d: dict) -> None:
    m, b = d["metrics"], d["bcomp"]
    n_beat = int(b["beats_benchmark"].sum())
    n_beat_sp = sum(beats_sp500(d, f) for f in FUNDS)
    bench_sr, sp_sr = annualise(d["bench"])["sharpe"], annualise(d["sp500"])["sharpe"]
    best = m["sharpe"].idxmax()
    w = d["weights"]
    n_rebal = w.loc[w.fund == best, "rebalance_date"].nunique()
    n_days = int(m.loc[best, "oos_days"])
    hero(d, "Quant portfolio project · Python · Streamlit",
         "Systematic stock and crypto funds, tested out of sample.",
         f"{len(FUNDS)} long-only portfolios, trained on a rolling one-year window and "
         "rebalanced monthly, then judged on three years of data the models never saw.")

    # Headline results, in the same card as the fund pages' key metrics.
    cells = [("Best Sharpe", f"{m.loc[best, 'sharpe']:.2f}", "", META[best]["short"] + " fund"),
             ("Its annual return", f"{m.loc[best, 'ann_return']:.1%}", "pos", "out of sample"),
             ("Beat the S&amp;P 500", f"{n_beat_sp} of {len(FUNDS)}", "", f"S&amp;P Sharpe {sp_sr:.2f}"),
             ("Beat equal-weight", f"{n_beat} of {len(FUNDS)}", "", f"1/N Sharpe {bench_sr:.2f}"),
             ("Live trading days", f"{n_days}", "", f"{n_rebal} monthly rebalances")]
    st.markdown("<div class='metrics-card'>" + "".join(
        f"<div class='m'><div class='stat-label'>{lab}</div>"
        f"<div class='stat-value {tone}'>{val}</div><div class='m-sub'>{sub}</div></div>"
        for lab, val, tone, sub in cells) + "</div>", unsafe_allow_html=True)

    # The backtest on one axis: what the models trained on, then what they were judged on.
    st.markdown(
        "<div class='timeline'>"
        "<div class='seg train'><b>Training</b><span>2020 · 252 trading days</span></div>"
        f"<div class='seg live'><b>Out of sample</b><span>Jan 2021 – Dec 2023 · {n_days} "
        f"trading days · {n_rebal} rebalances</span>"
        "<div class='ticks-row'>" + "<i></i>" * n_rebal + "</div></div></div>"
        "<p class='source' style='text-align:center'>Weights at each rebalance use only the "
        "252 trading days before it; the window rolls forward one month at a time.</p>",
        unsafe_allow_html=True)

    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("How it was built")
    spec = [
        ("Universe", "50 US large caps (10 sectors) + 10 cryptocurrencies"),
        ("Fund grid", "Stocks only, crypto only and combined × 3 methods, + 2 two-stage funds"),
        ("Methods", "Minimum variance, maximum Sharpe, risk parity"),
        ("Estimation", "Rolling 252-day window, re-fitted at every rebalance"),
        ("Rebalance", "First trading day of each month"),
        ("Constraints", "Long-only, fully invested; risk-free rate 0%"),
        ("Benchmarks", "Equal-weight 50-stock market and the S&amp;P 500 (SPY)"),
        ("No look-ahead", "A probe that lets the model peek one day ahead changes the "
                          "results, so the honest run is not peeking"),
    ]
    st.markdown(_spec_grid(spec), unsafe_allow_html=True)

    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("What the study found")
    sr = m["sharpe"]
    fus = d["fus"].pivot(index="fund", columns="variant", values="sharpe")
    winners = [META[f]["short"] for f in FUNDS
               if bool(b.loc[f, "beats_benchmark"]) and beats_sp500(d, f)]
    findings = (
        ("Mixing stocks and crypto paid off for two of three methods",
         f"Max-Sharpe rose from {sr['Equity_MaxSharpe']:.2f} (stocks) and "
         f"{sr['Crypto_MaxSharpe']:.2f} (crypto) to {sr['Combined_MaxSharpe']:.2f} combined; "
         f"risk parity from {sr['Equity_RiskParity']:.2f} and {sr['Crypto_RiskParity']:.2f} to "
         f"{sr['Combined_RiskParity']:.2f}. Minimum variance did not improve "
         f"({sr['Combined_MinVariance']:.2f} vs {sr['Crypto_MinVariance']:.2f})."),
        (f"{len(winners)} funds beat both benchmarks",
         f"{', '.join(winners[:-1])} and {winners[-1]} beat the equal-weight market "
         f"({bench_sr:.2f}) and the S&amp;P 500 ({sp_sr:.2f}). Every minimum-variance fund "
         "trailed both."),
        ("The news-sentiment tilt hurt, and is reported",
         "Tilting stocks toward sectors with positive headline sentiment, lagged one "
         f"trading day, cut Sharpe from {fus.loc['Combined_MaxSharpe', 'base']:.2f} to "
         f"{fus.loc['Combined_MaxSharpe', 'sentiment']:.2f} (High Growth) and from "
         f"{fus.loc['Combined_MinVariance', 'base']:.2f} to "
         f"{fus.loc['Combined_MinVariance', 'sentiment']:.2f} (Balanced)."),
    )
    # One grid, not st.columns: equal card heights, and subgrid rows keep each
    # card's number, heading and body on shared lines across the row.
    st.markdown("<div class='findings'>" + "".join(
        f"<div class='finding'><div class='stat-value'>0{i}</div><h4>{head}</h4>"
        f"<p class='descr'>{txt}</p></div>"
        for i, (head, txt) in enumerate(findings, start=1)) + "</div>",
        unsafe_allow_html=True)

    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("Our multi-asset funds")
    _fund_cards(d, COMBINED_FUNDS)
    st.markdown("<p class='descr' style='text-align:center'>Equity-only and crypto-only "
                "versions of each method are on the Funds page.</p>", unsafe_allow_html=True)


def page_funds(d: dict) -> None:
    if st.session_state.get("selected_fund"):
        page_detail(d, st.session_state["selected_fund"])
        return
    m, b = d["metrics"], d["bcomp"]
    hero(d, "The offering", "Compare the funds",
         f"{len(FUNDS)} systematic funds, each scored against the equal-weight market "
         "and the S&amp;P 500 over the same days.")
    # Fund cards first, by family; the full comparison table follows them.
    for k, family in enumerate(("Combined", "Equity", "Crypto")):
        if k:
            st.markdown("<hr class='rule'>", unsafe_allow_html=True)
        section(FAMILY_TITLE[family])
        _fund_cards(d, [f for f in FUNDS if FAMILY_OF[f] == family])

    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("All funds side by side")
    rows = [{"Fund": META[f]["name"], "Annual return": m.loc[f, "ann_return"],
             "Annual volatility": m.loc[f, "ann_vol"], "Sharpe": m.loc[f, "sharpe"],
             "Max drawdown": m.loc[f, "max_drawdown"],
             "Beats equal-weight?": "Yes" if bool(b.loc[f, "beats_benchmark"]) else "No",
             "Beats S&P 500?": "Yes" if beats_sp500(d, f) else "No"}
            for f in FUNDS]
    for name, series in (("Equal-weight market", d["bench"]), ("S&P 500 (SPY)", d["sp500"])):
        s = annualise(series)
        rows.append({"Fund": name, "Annual return": s["ann_return"],
                     "Annual volatility": s["ann_vol"], "Sharpe": s["sharpe"],
                     "Max drawdown": s["max_drawdown"],
                     "Beats equal-weight?": "-", "Beats S&P 500?": "-"})
    st.dataframe(pd.DataFrame(rows).style.format(
        {"Annual return": "{:.1%}", "Annual volatility": "{:.1%}",
         "Sharpe": "{:.2f}", "Max drawdown": "{:.1%}"}),
        hide_index=True, width="stretch", height=35 * (len(rows) + 1) + 3)
    st.markdown("<p class='source'>Source: out-of-sample backtest, Jan 2021 – Dec 2023; "
                "S&amp;P 500 via SPY with dividends. A fund beats a benchmark when its "
                "Sharpe ratio is higher over the same days.</p>",
                unsafe_allow_html=True)


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
                f"<div class='fund-name'>{meta['name']}</div></div></div>"
                f"<p class='descr fund-blurb'>{meta['blurb']}</p>"
                f"<div style='display:flex;gap:1.6rem;flex-wrap:wrap'>"
                f"<div><div class='stat-label'>Ann. return</div><div class='stat-value {_sign(m.loc[f,'ann_return'])}' style='font-size:1.15rem'>{m.loc[f,'ann_return']:.1%}</div></div>"
                f"<div><div class='stat-label'>Sharpe</div><div class='stat-value' style='font-size:1.15rem'>{m.loc[f,'sharpe']:.2f}</div></div>"
                f"<div><div class='stat-label'>Max DD</div><div class='stat-value neg' style='font-size:1.15rem'>{m.loc[f,'max_drawdown']:.1%}</div></div>"
                f"</div>{bench_pills(d, f)}</div>", unsafe_allow_html=True)
            st.button(f"View {meta['name']} →", key=f"view_{f}",
                      on_click=go_detail, args=(f,))
            st.write("")


def page_detail(d: dict, fund: str) -> None:
    m, b = d["metrics"], d["bcomp"]
    meta = META[fund]
    st.button("← Back to funds", key="back",
              on_click=lambda: st.session_state.update(selected_fund=None))
    hero(d, f"{meta['code']} · {meta['eyebrow'].title()}", meta["name"], meta["blurb"],
         under_back=True)

    # Key metrics: one card, five equal centred columns, labels and figures on
    # shared baselines; the benchmark pills stack in the last column.
    mm = m.loc[fund]
    cells = [("Annual return", f"{mm['ann_return']:.1%}", _sign(mm["ann_return"])),
             ("Annual volatility", f"{mm['ann_vol']:.1%}", ""),
             ("Sharpe", f"{mm['sharpe']:.2f}", ""),
             ("Max drawdown", f"{mm['max_drawdown']:.1%}", "neg")]
    pills = (beats_pill(bool(b.loc[fund, "beats_benchmark"]), "equal-weight")
             + beats_pill(beats_sp500(d, fund), "S&P 500"))
    st.markdown(
        "<div class='metrics-card'>"
        + "".join(f"<div class='m'><div class='stat-label'>{lab}</div>"
                  f"<div class='stat-value {tone}'>{val}</div></div>"
                  for lab, val, tone in cells)
        + "<div class='m bench'><div class='stat-label'>Vs benchmarks</div>"
        + f"<div class='pill-stack'>{pills}</div></div></div>",
        unsafe_allow_html=True)

    t_over, t_perf, t_hold = st.tabs(["Overview", "Performance", "Holdings"])
    with t_over:
        st.markdown("**Investment objective**")
        st.markdown(f"<p class='descr'>{meta['objective']}</p>", unsafe_allow_html=True)
        st.markdown(f"<div class='approp'><h4>Is this fund right for you?</h4>"
                    + ticks(meta["good"]) + "</div>", unsafe_allow_html=True)
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
        st.markdown("<p class='source'>Source: out-of-sample backtest, Jan 2021 – Dec 2023."
                    "</p>", unsafe_allow_html=True)
    with t_hold:
        fig, hold, latest = holdings_fig(fund, d)
        st.markdown(f"**Current holdings** (as at {latest:%d %b %Y}, {len(hold)} positions)")
        donut = sector_donut(fund, d, hold)
        st.markdown("<div class='stat-label' style='text-align:center'>"
                    f"{'Coin' if FAMILY_OF[fund] == 'Crypto' else 'Sector'} allocation</div>",
                    unsafe_allow_html=True)
        st.plotly_chart(donut, use_container_width=True, config=PLOTLY_CFG)
        st.markdown("<div class='stat-label' style='text-align:center;margin-top:1rem'>"
                    "Top holdings</div>", unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)
        st.markdown("<div class='stat-label' style='text-align:center;padding:1.6rem 0 1.9rem'>"
                    "Full holdings</div>", unsafe_allow_html=True)
        st.dataframe(hold.assign(weight=(hold.weight).map("{:.1%}".format))
                     .rename(columns={"ticker": "Holding", "weight": "Weight"}),
                     hide_index=True, width="stretch", height=280)
        st.markdown(f"<p class='source'>Source: target weights at the {latest:%d %b %Y} "
                    "rebalance.</p>", unsafe_allow_html=True)

    st.markdown(f"<div class='foot'>{OOS}. Figures are precomputed and traceable to "
                "source. Past performance is not a reliable indicator of future results.</div>",
                unsafe_allow_html=True)


def page_sentiment(d: dict) -> None:
    hero(d, "News signal", "Market sentiment",
         "What 2020–2023 headlines said about each sector, and whether it helped the funds.")
    sent = d["sent"]
    market = sent.mean(axis=1)
    recent = float(market.tail(21).mean())
    gauge = (recent + 1) / 2 * 100
    mood = "Fearful" if gauge < 40 else "Greedy" if gauge > 60 else "Neutral"
    as_of = market.index.max()

    g1, g2 = st.columns([1, 2])
    mood_color = _mood_color(gauge)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=round(gauge, 1),
        title={"text": f"News mood: <b><span style='color:{mood_color}'>{mood}</span></b>",
               "font": {"color": INK}},
        number={"suffix": " / 100", "font": {"color": INK}},
        gauge={"axis": {"range": [0, 100], "tickcolor": MUTED},
               # no progress arc: a slim white needle across the ramp marks the score
               "bar": {"color": "rgba(0,0,0,0)", "thickness": 0},
               "threshold": {"line": {"color": "#FFFFFF", "width": 5}, "thickness": 1,
                             "value": gauge},
               "bgcolor": PANEL, "borderwidth": 0, "steps": _mood_gradient()}))
    g1.plotly_chart(_style(fig, 300), use_container_width=True, config=PLOTLY_CFG)
    g1.markdown(f"<p class='source'>Equal-weight sentiment across 10 sectors, 21-day "
                f"average as at {as_of:%d %b %Y}. 50 = neutral.</p>", unsafe_allow_html=True)

    monthly = sent.resample("ME").mean()
    mm = monthly.mean(axis=1)
    figs = go.Figure()
    for col in monthly.columns:
        figs.add_trace(go.Scatter(x=monthly.index, y=monthly[col],
                                  line=dict(color="rgba(163,167,194,0.28)", width=1),
                                  showlegend=False, hoverinfo="skip"))
    figs.add_trace(go.Scatter(x=mm.index, y=mm, name="Market average",
                              line=dict(color=ACCENT, width=2.6)))
    figs.update_yaxes(title="VADER compound (-1 to 1)")
    g2.markdown("**Sector sentiment over time**")
    g2.plotly_chart(_style(figs, 320), use_container_width=True, config=PLOTLY_CFG)

    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("Did folding sentiment into the funds help?")
    piv = d["fus"].pivot(index="fund", columns="variant", values="sharpe")
    figb = go.Figure()
    for col, name, color in (("base", "Base fund", "#6CB4EE"),
                             ("sentiment", "With sentiment tilt", "#E9A07A")):
        figb.add_trace(go.Bar(
            x=[META[f]["short"] for f in piv.index], y=piv[col], name=name,
            marker=dict(color=color, cornerradius=8),
            text=piv[col], texttemplate="%{text:.2f}", textposition="outside",
            textfont=dict(color=INK, family=FONT, size=13), cliponaxis=False))
    figb.update_yaxes(title="Sharpe ratio", range=[0, float(piv.max().max()) * 1.18])
    figb.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08)
    st.plotly_chart(_style(figb, 320), use_container_width=True, config=PLOTLY_CFG)
    st.markdown("<p class='source'>The tilt lowered the Sharpe of both funds, a negative "
                "result reported as found. Source: out-of-sample backtest, Jan 2021 – "
                "Dec 2023.</p>", unsafe_allow_html=True)


def page_allocate(d: dict) -> None:
    hero(d, "Your portfolio", "Build an allocation",
         "Blend our three multi-asset funds into one portfolio, choose how much to "
         "invest, and see how it is deployed and what you would keep after our fixed "
         "management fee.")
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
    if st.button(f"Invest ${amount:,.0f}", key="invest_cta", type="primary"):
        st.success("Educational demo - no funds are moved and no order is placed.")
    st.markdown("<p class='source'>Weights are rescaled to 100%. Deployment is "
                "illustrative; the button places no real order.</p>", unsafe_allow_html=True)

    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("What you would have kept, net of the fixed fee")
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
    fig = go.Figure()
    _add_benchmarks(fig, d, fr.index)
    fig.add_trace(go.Scatter(x=gg.index, y=gg, name="Your blend (gross)",
                             line=dict(color="#9AA5F7", width=1.4)))
    fig.add_trace(go.Scatter(x=gn.index, y=gn, name="Your blend (net of fee)",
                             line=dict(color=ACCENT, width=2.6)))
    fig.update_yaxes(title="Value of $1", tickprefix="$")
    st.plotly_chart(_style(fig), use_container_width=True, config=PLOTLY_CFG)
    st.markdown("<p class='source'>Net line is what you would keep after the fixed "
                f"{MGMT_FEE:.2f}% fee. Source: out-of-sample backtest, Jan 2021 – "
                "Dec 2023.</p>",
                unsafe_allow_html=True)


def page_about(d: dict) -> None:
    hero(d, "About", "Methodology, in detail",
         "Everything needed to check the numbers: the data, the rules, the tests, "
         "and where the study falls short.")
    m, ext = d["metrics"], _extension_tables()
    n_days = int(m["oos_days"].iloc[0])
    w = d["weights"]
    n_rebal = w.loc[w.fund == FUNDS[0], "rebalance_date"].nunique()

    # 1. Data
    section("The data")
    st.markdown(_spec_grid([
        ("Stocks", "50 US large caps across 10 sectors, daily adjusted closes "
                   "(dividends included), 2020–2023"),
        ("Crypto", "10 coins: BTC, ETH, ADA, BCH, EOS, ETC, LTC, TRX, XLM, XRP"),
        ("News", "About 147,000 headlines on the 50 stocks after removing exact "
                 "duplicates, each aligned to its trading day"),
        ("Calendars", "Crypto trades every day, so its returns are computed on its own "
                      "calendar first, then lined up to stock trading days"),
    ]), unsafe_allow_html=True)

    # 2. Methods, each with its optimisation problem
    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("Three ways to set the weights")
    methods = (
        ("Minimum variance", "The lowest-risk mix. Ignores expected returns entirely.",
         r"\min_{w}\; w^\top \Sigma\, w"),
        ("Maximum Sharpe", "The best return per unit of risk (the tangency portfolio).",
         r"\max_{w}\; \frac{w^\top \mu - r_f}{\sqrt{w^\top \Sigma\, w}}"),
        ("Risk parity", "Every holding contributes the same share of total risk.",
         r"w_i\,(\Sigma w)_i = \tfrac{1}{n}\, w^\top \Sigma\, w \;\; \forall i"),
    )
    cols = st.columns(3)
    for i, (col, (name, blurb, eq)) in enumerate(zip(cols, methods)):
        with col.container(key=f"method_{i}"):
            st.markdown(f"<div class='stat-label'>{name}</div>"
                        f"<p class='descr method-blurb'>{blurb}</p>", unsafe_allow_html=True)
            st.latex(eq)
    st.markdown(
        "<p class='descr center-note'>All three are long-only and fully invested "
        "(w<sub>i</sub> ≥ 0, Σ w<sub>i</sub> = 1). μ and Σ are the sample mean and "
        "covariance of daily returns over the estimation window; r<sub>f</sub> = 0. "
        "Solved with SciPy (SLSQP for the first two; risk parity via its convex "
        "log-barrier form).</p>", unsafe_allow_html=True)

    # 3. Backtest design
    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("How the backtest runs")
    st.markdown(_spec_grid([
        ("Estimation window", "Rolling 252 trading days (one year), re-fitted at every "
                              "rebalance"),
        ("Rebalance rule", f"First trading day of each month, {n_rebal} times"),
        ("Between rebalances", "Weights held at their monthly targets; daily fund "
                               "return = w·r"),
        ("Live period", f"4 Jan 2021 to 29 Dec 2023, {n_days} trading days; 2020 is "
                        "training only"),
        ("Annualising", "Mean daily return × 252; volatility × √252"),
        ("Sharpe ratio", "Annualised return ÷ annualised volatility, risk-free rate 0%"),
        ("Max drawdown", "Largest fall from a running peak in the growth of $1"),
        ("Look-ahead probe", "Shifting the window one day into the future changes the "
                             "results, so the honest run uses past data only"),
    ]), unsafe_allow_html=True)

    # 4. Benchmarks
    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("What counts as beating the market")
    bench_sr, sp_sr = annualise(d["bench"])["sharpe"], annualise(d["sp500"])["sharpe"]
    st.markdown(
        "<div class='findings two'>"
        f"<div class='finding'><div class='stat-value'>{bench_sr:.2f}</div>"
        "<h4>Equal-weight market (1/N)</h4><p class='descr'>All 50 stocks at equal "
        "weight, reset on the same monthly schedule. It uses the same universe and the "
        "same days, so it is the fair test of whether optimising adds anything.</p></div>"
        f"<div class='finding'><div class='stat-value'>{sp_sr:.2f}</div>"
        "<h4>S&amp;P 500 (SPY)</h4><p class='descr'>The index a real investor would "
        "otherwise buy, with dividends included, over the same days. Shown as the "
        "everyday yardstick.</p></div></div>"
        "<p class='descr center-note'>Figures are Sharpe ratios. A fund beats a benchmark "
        f"when its Sharpe ratio is higher over the same {n_days} days. Both benchmarks "
        "hold stocks only, so part of a combined fund's edge comes from holding crypto "
        "at all.</p>", unsafe_allow_html=True)

    # 5. Sentiment pipeline
    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("From headlines to a trading signal")
    steps = [("Score", "Each headline gets a VADER compound score from −1 to +1"),
             ("Aggregate", "Daily score per stock; a day with no news scores 0"),
             ("Sector index", "Equal-weight average of the five stocks in each sector"),
             ("Lag", "Only sentiment from before the rebalance day is used, averaged "
                     "over the prior 21 trading days"),
             ("Tilt", "Each stock's weight × max(0, 1 + 0.5·z), where z is its "
                      "sector's standardised score; crypto weights unchanged")]
    st.markdown("<div class='pipeline'>" + "".join(
        f"<div class='step'><span class='n'>{k}</span><b>{t}</b><p>{x}</p></div>"
        for k, (t, x) in enumerate(steps, start=1)) + "</div>", unsafe_allow_html=True)

    # 6. Extensions, before -> after, read from the result tables
    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("Extensions tested")
    sh, ts, dc = ext["shrink"], ext["two"], ext["decay"]
    ts_params = int(ts["cross_asset_cov_params"].max()), int(ts["cross_asset_cov_params"].min())
    rows = [
        ("Ledoit-Wolf shrinkage", "Pulls the noisy sample covariance toward a simple target",
         sh.loc[("min_variance", "sample"), "sharpe"], sh.loc[("min_variance", "shrunk"), "sharpe"],
         sh.loc[("max_sharpe", "sample"), "sharpe"], sh.loc[("max_sharpe", "shrunk"), "sharpe"],
         "Helped minimum variance; max-Sharpe roughly flat"),
        ("Two-stage allocation", f"Builds stock and crypto sleeves first, then blends them: "
                                 f"{ts_params[0]:,} cross-asset covariance terms become "
                                 f"{ts_params[1]}",
         ts.loc[("min_variance", "one_stage"), "sharpe"], ts.loc[("min_variance", "two_stage"), "sharpe"],
         ts.loc[("max_sharpe", "one_stage"), "sharpe"], ts.loc[("max_sharpe", "two_stage"), "sharpe"],
         "About a tie with far fewer estimates"),
        ("Sentiment decay", "Old news fades over a 5-day half-life instead of dropping "
                            "straight to 0",
         dc.loc[("Combined_MinVariance", "sentiment_neutral0"), "sharpe"],
         dc.loc[("Combined_MinVariance", "sentiment_decay"), "sharpe"],
         dc.loc[("Combined_MaxSharpe", "sentiment_neutral0"), "sharpe"],
         dc.loc[("Combined_MaxSharpe", "sentiment_decay"), "sharpe"],
         "Softened the tilt's damage, still below no tilt"),
    ]

    def arrow(a, b):
        tone = "pos" if b > a + 0.005 else "neg" if b < a - 0.005 else ""
        return f"{a:.2f} → <span class='{tone}'>{b:.2f}</span>"

    st.markdown(
        "<div class='ext-table'><div class='ext-row head'><span>Extension</span>"
        "<span>Balanced (min-var)</span><span>High Growth (max-Sharpe)</span>"
        "<span>Verdict</span></div>" + "".join(
            f"<div class='ext-row'><span><b>{name}</b><em>{what}</em></span>"
            f"<span>{arrow(a1, b1)}</span><span>{arrow(a2, b2)}</span>"
            f"<span class='verdict'>{verdict}</span></div>"
            for name, what, a1, b1, a2, b2, verdict in rows) + "</div>"
        "<p class='descr center-note'>Sharpe ratios, before → after, on the combined "
        "funds. Each extension was chosen before seeing its result and is reported "
        "either way; the headline funds keep the plain versions.</p>",
        unsafe_allow_html=True)

    # 7. Limitations
    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("Where the study falls short")
    st.markdown("<div class='limits'>" + "".join(
        f"<div class='limit'><b>{t}</b><p>{x}</p></div>" for t, x in [
            ("No trading costs", "Monthly rebalancing is free in the backtest. Costs and "
                                 "slippage would lower every fund, the high-turnover "
                                 "ones most."),
            ("A fixed stock list", "The 50 names are fixed for the whole sample, not "
                                   "point-in-time index membership."),
            ("One short period", "Three years out of sample covers one market cycle: the "
                                 "2022 sell-off and the 2023 rebound."),
            ("Risk-free rate of 0%", "Cash yielded several percent in 2023, so every "
                                     "Sharpe ratio here is higher than it would be "
                                     "against a cash hurdle."),
            ("Noisy expected returns", "Max-Sharpe relies on one year's sample means, "
                                       "which are unstable; it is the most concentrated "
                                       "method."),
            ("Weekend crypto moves", "Aligning coins to stock trading days drops "
                                     "weekend-only moves, by design."),
        ]) + "</div>", unsafe_allow_html=True)

    # 8. Stack and reproducibility
    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("Built with")
    st.markdown(
        "<div class='chips'>" + "".join(f"<span>{t}</span>" for t in (
            "Python 3.13", "pandas", "NumPy", "SciPy", "NLTK · VADER", "Plotly",
            "Streamlit", "pytest")) + "</div>"
        "<p class='descr center-note'>One script rebuilds every table and figure from the "
        "raw data and checks its own counts. Automated tests cover the outputs and every "
        "page of this app, which only reads precomputed results.</p>"
        f"<div style='text-align:center;margin-top:1rem'><a class='gh-pill' href='{REPO_URL}' "
        "target='_blank' rel='noopener'>View the code on GitHub</a></div>",
        unsafe_allow_html=True)

    st.markdown("<hr class='rule'>", unsafe_allow_html=True)
    section("About the author")
    st.markdown(author_card("lg"), unsafe_allow_html=True)
    st.markdown("<p class='foot' style='text-align:center'>Educational project, not "
                "investment advice. Past performance is not a reliable indicator of future "
                "results.</p>", unsafe_allow_html=True)


@st.cache_data(ttl=86_400, show_spinner=False)
def _extension_tables() -> dict:
    """Before/after tables for the extensions shown on About."""
    return {
        "shrink": pd.read_csv(TABLES / "shrinkage_comparison.csv").set_index(["method", "variant"]),
        "two": pd.read_csv(TABLES / "two_stage_comparison.csv").set_index(["method", "structure"]),
        "decay": pd.read_csv(TABLES / "decay_comparison.csv").set_index(["fund", "variant"]),
    }


def _spec_grid(items) -> str:
    return ("<div class='spec-grid'>" + "".join(
        f"<div class='spec'><div class='stat-label'>{k}</div><p>{v}</p></div>"
        for k, v in items) + "</div>")


PAGES = {"Home": page_home, "Funds": page_funds, "Sentiment": page_sentiment,
         "Build portfolio": page_allocate, "About": page_about}


def top_nav() -> None:
    # One sticky row: wordmark, the five nav links, then the author drop-down. The
    # columns are sized by CSS (auto width), so the spec here only sets their count.
    with st.container(key="site_header"):
        cols = st.columns(len(PAGES) + 2, vertical_alignment="center", gap="small")
        cols[0].markdown("<span class='wordmark'>REVELATIO<span>.</span></span>",
                         unsafe_allow_html=True)
        for i, name in enumerate(PAGES, start=1):
            active = st.session_state.get("page") == name
            if cols[i].button(name, key=f"nav_{name}",
                              type="primary" if active else "secondary"):
                st.session_state["page"] = name
                st.session_state["selected_fund"] = None
                st.rerun()
        # Click (not hover) so it also works on phones; plain HTML, no rerun.
        cols[-1].markdown(f"<details class='author-menu'><summary class='gh-pill'>"
                          f"Made by {AUTHOR['name']}<span class='chev'>▾</span></summary>"
                          f"{author_card()}</details>", unsafe_allow_html=True)


def main() -> None:
    inject_css()
    st.session_state.setdefault("page", "Home")
    st.session_state.setdefault("selected_fund", None)
    d = load_all()
    top_nav()
    PAGES.get(st.session_state["page"], page_home)(d)


if __name__ == "__main__":
    main()

"""Revelatio house style - the design system every exhibit passes through.

Dark ink on a parchment ground, with a single gilded series carrying the point
and everything else muted back to the page. An illuminated manuscript gives one
colour to the thing that matters and lets the rest be text - the same discipline
a good chart needs.

VENDORED FOR PART B (carried from Part A, made self-contained). Part A's version
imported ``fintools.figures`` for the Word/A4 figure spec and the rcParams
baseline. Part B is a standalone, deployable repository, so those values are
inlined here instead: the figure dimensions (``_SPECS``) and the baseline rc
(``_BASELINE``) are the exact numbers Part A's fintools produced, so the look is
unchanged while the file depends on nothing outside this folder. Figures are a
BUILD step (scripts/run_part_b.py) - the deployed app only reads the saved PNGs,
so matplotlib is a build dependency, never a runtime one.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

# --- The palette ---------------------------------------------------------------
REVELATIO = {
    "parchment": "#FDF1E6",
    "vellum": "#F6E8D8",
    "ink": "#241C15",
    "ink_soft": "#5C5044",
    "muted": "#A2937F",
    "rule": "#DCCDB8",
    "gilt": "#B8860B",        # THE accent. One series per figure.
    "gilt_light": "#D9AE45",
    "rubric": "#8C2F1F",      # warnings, negative values
    "verdigris": "#4A6F62",   # the one cool tone, for a genuine second category
}

CYCLE = [
    REVELATIO["gilt"],
    REVELATIO["ink_soft"],
    REVELATIO["verdigris"],
    REVELATIO["rubric"],
    REVELATIO["muted"],
    REVELATIO["gilt_light"],
]

# Word/A4 figure dimensions (inches), inlined from fintools word_figure_spec.
_SPECS = {
    "full_width": (6.27, 3.75),
    "half_width": (3.05, 2.25),
    "portrait_tall": (6.27, 5.05),
    "portrait_full": (6.27, 7.35),
    "two_panel": (6.27, 4.20),
    "landscape_wide": (9.70, 5.45),
}

# rcParams baseline (the fintools word_a4/ft values that the house palette tunes).
_BASELINE = {
    "figure.constrained_layout.use": True,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.04,
    "font.family": "DejaVu Sans",
    "axes.labelsize": 11,
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": True,
    "axes.spines.bottom": True,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9,
    "lines.linewidth": 2.0,
}


def revelatio_rc() -> dict:
    """rcParams: the Word/A4 baseline tuned to the house palette."""
    rc = dict(_BASELINE)
    rc.update({
        "axes.facecolor": REVELATIO["parchment"],
        "figure.facecolor": REVELATIO["parchment"],
        "savefig.facecolor": REVELATIO["parchment"],
        "axes.edgecolor": REVELATIO["rule"],
        "axes.labelcolor": REVELATIO["ink_soft"],
        "axes.titlecolor": REVELATIO["ink"],
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.prop_cycle": plt.cycler(color=CYCLE),
        "axes.grid": True,
        "axes.grid.axis": "y",     # horizontal gridlines only; no vertical rules
        "axes.axisbelow": True,
        "grid.color": REVELATIO["rule"],
        "grid.alpha": 0.55,
        "grid.linewidth": 0.6,
        "grid.linestyle": "--",
        "xtick.color": REVELATIO["ink_soft"],
        "ytick.color": REVELATIO["ink_soft"],
        "text.color": REVELATIO["ink"],
        "legend.frameon": False,
    })
    return rc


class revelatio_style:
    """Context manager applying the house style to one plotting block."""

    def __enter__(self):
        self._ctx = plt.rc_context(revelatio_rc())
        self._ctx.__enter__()
        return self

    def __exit__(self, *exc):
        return self._ctx.__exit__(*exc)


def new_figure(spec: str = "full_width", **kwargs) -> tuple[Figure, plt.Axes]:
    """A figure sized to a Word/A4 spec so it drops into the report at true size."""
    w, h = _SPECS[spec]
    return plt.subplots(figsize=(w, h), **kwargs)


def stamp(
    fig: Figure,
    ax: plt.Axes,
    title: str,
    subtitle: str,
    *,
    sample: str = "2020-01-01 to 2023-12-31",
    units: str | None = None,
    source: str | None = None,   # kept for signature compatibility; not rendered
    wrap: int = 74,
    title_wrap: int = 48,
    source_y: float | None = None,
) -> None:
    """Stamp caption-ready furniture: title, subtitle (units), and sample period.

    The sample period sits on the FOOTER line (where a source note used to);
    provenance now lives in the Word figure caption, not on the plot. Everything
    is positioned in AXES coordinates so the furniture stays clear of the plot at
    any figure size (figure coordinates fight constrained layout).
    """
    line = subtitle
    if units:
        line = f"{line} | {units}"
    line = "\n".join(textwrap.wrap(line, wrap))
    tit = "\n".join(textwrap.wrap(title, title_wrap))
    n_sub = line.count("\n") + 1

    ax.set_title("")
    ax.annotate(line, xy=(0, 1), xycoords="axes fraction",
                xytext=(0, 8), textcoords="offset points",
                ha="left", va="bottom", color=REVELATIO["ink_soft"],
                fontsize=9, annotation_clip=False)
    ax.annotate(tit, xy=(0, 1), xycoords="axes fraction",
                xytext=(0, 8 + 11.5 * n_sub + 3), textcoords="offset points",
                ha="left", va="bottom", color=REVELATIO["ink"],
                fontsize=12, fontweight="bold", annotation_clip=False)
    if source_y is None:
        source_y = -34 if ax.get_xlabel() else -22
    ax.annotate(f"Sample: {sample}",
                xy=(0, 0), xycoords="axes fraction",
                xytext=(0, source_y), textcoords="offset points",
                ha="left", va="top", color=REVELATIO["muted"],
                fontsize=8, annotation_clip=False)


def date_axis(ax: plt.Axes, fmt: str = "%Y") -> None:
    """Year ticks with minor quarter marks, so date labels never overlap."""
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=(4, 7, 10)))
    ax.tick_params(axis="x", which="minor", length=3, color=REVELATIO["rule"])


def save(fig: Figure, path: str | Path, dpi: int = 300) -> Path:
    """Save preserving the parchment ground (respects the figure's own facecolor)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        out, dpi=dpi, bbox_inches="tight", pad_inches=0.06,
        facecolor=fig.get_facecolor(),
        metadata={"Creator": "Revelatio house style (z5736927)"},
    )
    plt.close(fig)
    return out

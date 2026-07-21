# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib"]
# ///
"""House-style matplotlib chart helpers (importable library).

Generalised from Power & Utilities `tools/chartgen.py`. Gives any project the
same deck-ready chart look: a fixed house palette, consistent fonts/ticks, and
an EXACT-inch canvas so saved PNGs drop into slide placeholders without
distortion.

Geometry contract (why charts swap into decks cleanly):
- Figures are created with layout="constrained" at the EXACT figsize (inches).
- They are saved WITHOUT bbox_inches="tight", so the PNG canvas aspect ratio
  always equals the figsize you asked for. Cropping with "tight" would change
  the aspect ratio and distort the image when scaled into a fixed placeholder.
- Attach legends with fig.legend(loc="outside ...") so constrained layout
  reserves room for them INSIDE the canvas instead of cropping around them.

Usage:
    import chartstyle as cs
    fig, ax = cs.new_fig(4.0, 2.5)        # width_in, height_in
    ax.plot(x, y, color=cs.PALETTE["NAVY"])
    cs.style_axes(ax, unit_label="EUR/MWh")
    cs.save_fig(fig, "out.png")

This module forces the non-interactive "Agg" backend on import, so it works
headless. Importing it also applies the house rcParams globally (font, sizes,
spine/grid colours), matching the original deck style.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")  # headless / deterministic PNG output
import matplotlib.pyplot as plt  # noqa: E402

# --- House palette -----------------------------------------------------------
NAVY = "#2E3E80"
TEAL = "#5FA1AD"
SAGE = "#ACBFB7"
FOREST = "#3D664A"
GOLD = "#CC9F53"
WINE = "#8A1E41"
GREY_GRID = "#E5E5E5"
GREY_LINE = "#C9D2CD"

# Ordered series colours (use for multi-series charts).
SERIES = [NAVY, TEAL, SAGE, FOREST, GOLD, WINE]

# Named-access palette (same colours; convenient for explicit picks).
PALETTE = {
    "NAVY": NAVY,
    "TEAL": TEAL,
    "SAGE": SAGE,
    "FOREST": FOREST,
    "GOLD": GOLD,
    "WINE": WINE,
    "GREY_GRID": GREY_GRID,
    "GREY_LINE": GREY_LINE,
}

# --- House rcParams (applied on import) --------------------------------------
RC_PARAMS = {
    # Arial on macOS; Liberation Sans is metrically identical and is what Linux/CI
    # has, so a CI-rendered chart is indistinguishable from a locally-rendered one.
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Liberation Sans", "Helvetica", "DejaVu Sans"],
    "font.size": 9,
    "axes.edgecolor": "#666666",
    "axes.linewidth": 0.6,
    "axes.titlesize": 9.5,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "legend.fontsize": 8.5,
    "legend.frameon": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
}
plt.rcParams.update(RC_PARAMS)


# --- Figure lifecycle --------------------------------------------------------
def new_fig(width_in: float, height_in: float):
    """Exact-canvas figure at the placeholder size (inches).

    Returns (fig, ax) from plt.subplots with constrained layout, so the saved
    PNG fills the canvas and keeps the (width_in x height_in) aspect ratio.
    """
    return plt.subplots(figsize=(width_in, height_in), layout="constrained")


def save_fig(fig, path, dpi: int = 220) -> None:
    """Save at the exact canvas size, then close the figure.

    Deliberately does NOT pass bbox_inches="tight": that would crop the canvas
    and change the aspect ratio away from the placeholder's, distorting the
    image when it is scaled into a fixed-size slide box.
    """
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


def accounting_formatter():
    """Return a matplotlib FuncFormatter for accounting-style negatives.

    -25 -> "(25)". Keeps up to 2 decimals for small magnitudes (|v| < 10),
    otherwise rounds to a thousands-separated integer.
    """

    def _fmt(v, _pos):
        if abs(v) < 10:
            s = f"{abs(v):,.2f}".rstrip("0").rstrip(".")
        else:
            s = f"{abs(v):,.0f}"
        return f"({s})" if v < 0 else s

    return plt.FuncFormatter(_fmt)


def style_axes(
    ax,
    unit_label: Optional[str] = None,
    ylim: Optional[Tuple[float, float]] = None,
    ytick_step: Optional[float] = None,
) -> None:
    """Apply the house axes style to `ax`.

    - Hide top/right spines.
    - Light horizontal gridlines behind the data.
    - Accounting-style negative y-tick labels.
    - Optional y-limits / fixed y-tick step.
    - Optional left-aligned unit label (set as a small left title so
      constrained layout reserves space for it).
    """
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=GREY_GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.margins(x=0.01)
    if ylim:
        ax.set_ylim(*ylim)
        if ytick_step:
            v = ylim[0]
            ticks = []
            # inclusive of the upper bound, robust to float steps
            while v <= ylim[1] + 1e-9:
                ticks.append(v)
                v += ytick_step
            ax.set_yticks(ticks)
    ax.yaxis.set_major_formatter(accounting_formatter())
    if unit_label:
        ax.set_title(unit_label, loc="left", fontsize=8.5, pad=5)


__all__ = [
    "PALETTE",
    "SERIES",
    "RC_PARAMS",
    "NAVY",
    "TEAL",
    "SAGE",
    "FOREST",
    "GOLD",
    "WINE",
    "GREY_GRID",
    "GREY_LINE",
    "new_fig",
    "save_fig",
    "style_axes",
    "accounting_formatter",
]

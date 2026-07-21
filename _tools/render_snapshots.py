"""
render_snapshots.py — static house-style PNGs for the two slide-31 exhibits that
don't need live data (fixed historical comparisons):
  * Spain quarterly duck curves, 2025 vs 2019  (intraday price by hour, Q1-Q4)
  * Spain July daily duck-curve spaghetti, 2025 vs 2019

Spain = ES day-ahead price (labelled Spain to match the live country-variant charts,
Fred 2026-07-18). Reads the published G2/G3 tables; writes PNGs to outputs/deck_img/.
Uses the house chart-style library.
"""
from __future__ import annotations
import os, sys
import pandas as pd
# chartstyle is VENDORED into _tools/ (see chartstyle.py) so CI can render too
import chartstyle as cs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, "published", "charts")
IMG = os.path.join(ROOT, "outputs", "deck_img")
os.makedirs(IMG, exist_ok=True)
HOURS = list(range(24))
QCOL = [cs.PALETTE["NAVY"], cs.PALETTE["TEAL"], cs.PALETTE["SAGE"], cs.PALETTE["FOREST"]]

def spain(df, suffix):
    """ES_<suffix> — Spain day-ahead price (single-market, MIBEL)."""
    es, pt = f"ES_{suffix}", f"PT_{suffix}"
    return df[es] if es in df else df.get(pt)

def quarterly(year):
    df = pd.read_csv(os.path.join(PUB, "g2_price_by_quarter.csv"))
    fig, ax = cs.new_fig(4.3, 2.6)
    for i, q in enumerate([1, 2, 3, 4]):
        ax.plot(HOURS, spain(df, f"{year}_Q{q}"), color=QCOL[i], lw=1.8, label=f"{q}Q")
    ax.set_xticks(range(0, 24, 3))
    cs.style_axes(ax, unit_label="€/MWh", ylim=(0, 150), ytick_step=25)
    fig.legend(loc="outside lower center", ncols=4)
    cs.save_fig(fig, os.path.join(IMG, f"snap_quarterly_{year}.png"))
    print("  wrote", f"snap_quarterly_{year}.png")

def july_daily(year):
    df = pd.read_csv(os.path.join(PUB, "g3_price_july_daily.csv"))
    days = [f"{d:02d}" for d in range(1, 32)]
    series = []
    for d in days:
        s = spain(df, f"{year}_D{d}")
        if s.notna().any():
            series.append(s)
    fig, ax = cs.new_fig(4.3, 2.6)
    for s in series:
        ax.plot(HOURS, s, color=cs.PALETTE["GREY_LINE"], lw=0.6, alpha=0.85)
    mean = pd.concat(series, axis=1).mean(axis=1)
    ax.plot(HOURS, mean, color=cs.PALETTE["NAVY"], lw=2.4, label="July average")
    ax.set_xticks(range(0, 24, 3))
    cs.style_axes(ax, unit_label="€/MWh", ylim=(-25, 150), ytick_step=25)
    fig.legend(loc="outside lower center", ncols=1)
    cs.save_fig(fig, os.path.join(IMG, f"snap_july_{year}.png"))
    print("  wrote", f"snap_july_{year}.png")

if __name__ == "__main__":
    print("rendering static snapshots ->", IMG)
    for y in (2025, 2019):
        quarterly(y); july_daily(y)
    print("done")

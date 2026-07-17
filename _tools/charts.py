"""
charts.py — reproduce the Redburn ENTSO-E figures in Rothschild house style.

These PNGs are REFERENCE renders: they prove the workbook data regenerates every
Redburn figure, and act as templates for the live PowerPoint charts you build
linked to outputs/PowerPriceData.xlsx. Country/year picks match the Redburn deck
(Fig 1-3,5,6 Germany; Fig 4 & 7 Iberia/Portugal) but any country is a param away.

Writes: outputs/charts/*.png
"""
from __future__ import annotations
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
sys.path.insert(0, "/Users/fredhill/.claude/skills/chart-style")
import chartstyle as cs
import config as cfg

SUM = os.path.join(cfg.PROC_DIR, "summaries")
CHARTS = os.path.join(cfg.OUTPUT_DIR, "charts")
os.makedirs(CHARTS, exist_ok=True)
DATA_YEARS = cfg.YEARS
SRC = "Source: Redburn Atlantic, ENTSO-E Transparency Platform"

def load(n): return pd.read_parquet(os.path.join(SUM, f"{n}.parquet"))

def year_colors(years):
    """older = light grey-teal, most recent = navy (Redburn convention)."""
    import matplotlib.colors as mc
    ramp = mc.LinearSegmentedColormap.from_list("yr", ["#C9D2CD", cs.TEAL, cs.NAVY])
    n = len(years)
    return {y: ramp(i / max(n - 1, 1)) for i, y in enumerate(years)}

def footer(fig, text=SRC):
    fig.text(0.01, 0.005, text, fontsize=5.5, style="italic", color="#808080")

def save(fig, name):
    p = os.path.join(CHARTS, name)
    cs.save_fig(fig, p); print("  ->", name, flush=True)

# ---------------------------------------------------------------------------
def fig1_price_sd(country="DE"):
    df = load("price_sd"); d = df[df.country == country].sort_values("year")
    fig, ax = cs.new_fig(4.6, 2.8)
    ax.plot(d.year, d.sd, color=cs.NAVY, marker="o", ms=4, lw=1.6)
    for _, r in d.iterrows():
        ax.annotate(f"{r.sd:.0f}", (r.year, r.sd), textcoords="offset points",
                    xytext=(0, 6), ha="center", fontsize=6, color=cs.NAVY)
    cs.style_axes(ax, unit_label="std dev (EUR/MWh)")
    ax.set_title(f"Fig 1 — Std-dev of power-price distribution ({cfg.COUNTRIES[country]['name']})",
                 fontsize=8, color=cs.NAVY, loc="left", weight="bold")
    footer(fig); save(fig, "fig1_price_sd.png")

def fig2_intraday(country="DE"):
    df = load("intraday_price"); d = df[df.country == country]
    yrs = sorted(d.year.unique()); cmap = year_colors(yrs)
    fig, ax = cs.new_fig(4.6, 2.8)
    for y in yrs:
        s = d[d.year == y].sort_values("hour_utc")
        ax.plot(s.hour_utc, s.indexed, color=cmap[y], lw=1.8 if y == yrs[-1] else 1.0,
                label=str(y))
    cs.style_axes(ax, unit_label="indexed (1 = annual base)")
    ax.set_xticks(range(0, 24, 3)); ax.set_xlabel("hour (UTC)", fontsize=6)
    ax.set_title(f"Fig 2 — Indexed hourly power prices ({cfg.COUNTRIES[country]['name']})",
                 fontsize=8, color=cs.NAVY, loc="left", weight="bold")
    fig.legend(loc="outside lower center", ncols=len(yrs), fontsize=5.5, frameon=False)
    footer(fig); save(fig, "fig2_intraday_price.png")

def fig3_cumneg(country="DE"):
    df = load("cum_neghours"); d = df[df.country == country]
    yrs = sorted(d.year.unique()); cmap = year_colors(yrs)
    fig, ax = cs.new_fig(4.6, 2.8)
    for y in yrs:
        s = d[d.year == y].sort_values("doy")
        ax.plot(s.doy, s.cum_near_neg, color=cmap[y], lw=1.8 if y == yrs[-1] else 1.0, label=str(y))
    cs.style_axes(ax, unit_label="# hours (cumulative)")
    ax.set_xlim(1, 366); ax.set_xlabel("day of year (UTC)", fontsize=6)
    ax.set_title(f"Fig 3 — Cumulative near-negative price hours ({cfg.COUNTRIES[country]['name']})",
                 fontsize=8, color=cs.NAVY, loc="left", weight="bold")
    fig.legend(loc="outside lower center", ncols=len(yrs), fontsize=5.5, frameon=False)
    footer(fig); save(fig, "fig3_cum_neg_hours.png")

def fig4_duration(country="PT"):
    df = load("duration_curve"); d = df[df.country == country]
    yrs = sorted(d.year.unique()); cmap = year_colors(yrs)
    fig, ax = cs.new_fig(4.6, 2.8)
    for y in yrs:
        s = d[d.year == y].sort_values("pct_of_hours")
        ax.plot(s.pct_of_hours, s.price, color=cmap[y], lw=1.8 if y == yrs[-1] else 1.0, label=str(y))
    cs.style_axes(ax, unit_label="EUR/MWh")
    ax.axhline(0, color="#B0B0B0", lw=0.6)
    ax.set_xlabel("% of hours (0 = highest-priced)", fontsize=6)
    ax.set_title(f"Fig 4 — Annual price duration curves ({cfg.COUNTRIES[country]['name']})",
                 fontsize=8, color=cs.NAVY, loc="left", weight="bold")
    fig.legend(loc="outside lower center", ncols=len(yrs), fontsize=5.5, frameon=False)
    footer(fig); save(fig, "fig4_duration_curve.png")

def fig5_capture(country="DE"):
    df = load("capture_annual"); d = df[df.country == country]
    yrs = sorted(d.year.unique()); cmap = year_colors(yrs)
    techs = [t for t in cfg.TECH_ORDER if d[d.tech == t]["capture_vs_base_pct"].notna().any()]
    fig, ax = cs.new_fig(6.6, 3.0)
    n = len(yrs); w = 0.8 / n
    x = np.arange(len(techs))
    for i, y in enumerate(yrs):
        vals = [d[(d.tech == t) & (d.year == y)]["capture_vs_base_pct"].pipe(
                lambda s: s.iloc[0] if len(s) and pd.notna(s.iloc[0]) else np.nan) for t in techs]
        ax.bar(x + i * w - 0.4 + w / 2, vals, w, color=cmap[y], label=str(y))
    ax.axhline(0, color="#606060", lw=0.7)
    cs.style_axes(ax, unit_label="% above/below base price")
    ax.set_xticks(x); ax.set_xticklabels(techs, rotation=45, ha="right", fontsize=5.5)
    ax.set_title(f"Fig 5 — Capture price by technology vs base ({cfg.COUNTRIES[country]['name']})",
                 fontsize=8, color=cs.NAVY, loc="left", weight="bold")
    fig.legend(loc="outside lower center", ncols=len(yrs), fontsize=5.5, frameon=False)
    footer(fig); save(fig, "fig5_capture_by_tech.png")

def fig6_minmax(country="DE", year=2024):
    df = load("daily_minmax"); d = df[(df.country == country) & (df.year == year)]
    fig, ax = cs.new_fig(4.4, 3.2)
    ax.scatter(d.max_price, d.min_price, s=9, color=cs.TEAL, alpha=0.6, edgecolors="none")
    ax.scatter([d.max_price.mean()], [d.min_price.mean()], s=45, color=cs.NAVY, zorder=5)
    ax.axhline(0, color="#B0B0B0", lw=0.6); ax.axvline(0, color="#B0B0B0", lw=0.6)
    cs.style_axes(ax, unit_label="min price (EUR/MWh)")
    ax.set_xlabel("max price (EUR/MWh)", fontsize=6)
    sp = (d.max_price - d.min_price).mean()
    ax.set_title(f"Fig 6 — Daily min-to-max spread ({cfg.COUNTRIES[country]['name']} {year}) · avg EUR{sp:.0f}",
                 fontsize=8, color=cs.NAVY, loc="left", weight="bold")
    footer(fig); save(fig, "fig6_daily_spread.png")

TECH_COLORS = {
    "Nuclear": "#7A2048", "Lignite": "#5C4033", "Hard coal": "#2B2B2B", "Gas": "#9E9E9E",
    "Oil & other fossil": "#6D4C41", "Biomass": "#8D6E63", "Waste": "#A1887F",
    "Geothermal": "#B08968", "Hydro run-of-river": "#4FC3D9", "Hydro reservoir": "#2E7D8A",
    "Hydro pumped (production)": "#3D664A", "Onshore wind": "#5FA1AD", "Offshore wind": "#2E3E80",
    "Solar": "#E7B84B", "Marine": "#80CBC4", "Other renewable": "#ACBFB7", "Other": "#CFCFCF",
}

def fig7_genmix(country="PT", year=2024):
    df = load("intraday_genmix"); d = df[(df.country == country) & (df.year == year)].sort_values("hour_utc")
    techs = [t for t in cfg.TECH_ORDER if f"gen_{t}" in d.columns and d[f"gen_{t}"].abs().sum() > 0]
    fig, ax = cs.new_fig(6.6, 3.4)
    hours = d.hour_utc.values
    bottom = np.zeros(len(d))
    for t in techs:
        v = d[f"gen_{t}"].values
        ax.bar(hours, v, bottom=bottom, color=TECH_COLORS.get(t, "#CCCCCC"), width=0.9, label=t)
        bottom += np.nan_to_num(v)
    # pumped consumption (negative) and net flow
    ax.bar(hours, d["pumped_consumption"].values, color="#9CCC65", width=0.9, label="Pumped (consumption)")
    ax.bar(hours, d["flow_net"].values, bottom=bottom, color="#D4A017", width=0.5, label="Net import/(export)")
    cs.style_axes(ax, unit_label="MW")
    ax2 = ax.twinx()
    ax2.plot(hours, d["price"].values, color="black", lw=1.8, label="Power price")
    ax2.set_ylabel("EUR/MWh", fontsize=6); ax2.tick_params(labelsize=6)
    ax.set_xlabel("hour (UTC)", fontsize=6); ax.set_xticks(range(0, 24, 3))
    ax.set_title(f"Fig 7 — Avg intraday generation mix & price ({cfg.COUNTRIES[country]['name']} {year})",
                 fontsize=8, color=cs.NAVY, loc="left", weight="bold")
    fig.legend(loc="outside right upper", fontsize=4.6, frameon=False)
    footer(fig, "Source: Redburn Atlantic, ENTSO-E Transparency Platform (Redburn Fig 7 uses company data)")
    save(fig, "fig7_gen_mix.png")

def fig9_capacity(country="DE"):
    df = load("capacity"); d = df[df.country == country]
    yrs = sorted(d.year.unique()); cmap = year_colors(yrs)
    techs = [t for t in cfg.TECH_ORDER if d[d.tech == t]["capacity_mw"].sum() > 0]
    fig, ax = cs.new_fig(6.6, 3.0)
    n = len(yrs); w = 0.8 / n; x = np.arange(len(techs))
    for i, y in enumerate(yrs):
        vals = [d[(d.tech == t) & (d.year == y)]["capacity_mw"].pipe(
                lambda s: s.iloc[0] if len(s) and pd.notna(s.iloc[0]) else np.nan) for t in techs]
        ax.bar(x + i * w - 0.4 + w / 2, vals, w, color=cmap[y], label=str(y))
    cs.style_axes(ax, unit_label="installed capacity (MW)")
    ax.set_xticks(x); ax.set_xticklabels(techs, rotation=45, ha="right", fontsize=5.5)
    ax.set_title(f"Fig 9 — Installed capacity by technology ({cfg.COUNTRIES[country]['name']})",
                 fontsize=8, color=cs.NAVY, loc="left", weight="bold")
    fig.legend(loc="outside lower center", ncols=len(yrs), fontsize=5.5, frameon=False)
    footer(fig, "Source: Redburn Atlantic, ENTSO-E Transparency Platform")
    save(fig, "fig9_capacity.png")

def main():
    print("rendering Rothschild-style reference charts ->", CHARTS, flush=True)
    fig1_price_sd(); fig2_intraday(); fig3_cumneg(); fig4_duration("PT")
    fig5_capture(); fig6_minmax("DE", 2024); fig7_genmix("PT", 2024); fig9_capacity("DE")
    print("charts done", flush=True)

if __name__ == "__main__":
    main()

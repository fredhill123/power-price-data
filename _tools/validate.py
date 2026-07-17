"""
validate.py — adversarial checks of the built data against known Redburn figures
and internal consistency. Run after summaries.py. Prints PASS/FAIL per check.

Redburn 'Volatility Capture' appendix reference points (2 May 2025):
  * Germany 2024: >600 hours below EUR1/MWh (Fig 3 text)
  * Germany 2024: avg daily spread ~EUR112 (min EUR33 / max EUR144) (Fig 6 text)
  * Germany capture: Solar strongly negative, Gas positive (Fig 5)
"""
from __future__ import annotations
import os, warnings; warnings.filterwarnings("ignore")
import pandas as pd, numpy as np
import config as cfg

PROC = cfg.PROC_DIR
SUM = os.path.join(PROC, "summaries")
results = []

def check(name, cond, detail):
    results.append((cond, name, detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}: {detail}", flush=True)

def main():
    m = pd.read_parquet(os.path.join(PROC, "hourly_master.parquet"))
    m["ts_utc"] = pd.to_datetime(m["ts_utc"], utc=True)
    m["year"] = m["ts_utc"].dt.year

    # coverage
    print("== coverage ==")
    for c in cfg.COUNTRY_ORDER:
        for y in cfg.YEARS:
            g = m[(m.country == c) & (m.year == y)]
            if len(g) == 0:
                print(f"  MISSING {c} {y}"); continue
            pcov = g["price"].notna().mean() * 100
            gcov = g["gen_total"].notna().mean() * 100
            flag = "" if pcov > 90 else "  <-- LOW price coverage"
            print(f"  {c} {y}: {len(g):5d}h  price {pcov:5.1f}%  gen {gcov:5.1f}%{flag}")

    # internal: gen categories sum to gen_total (DE 2024)
    print("\n== internal consistency ==")
    g = m[(m.country == "DE") & (m.year == 2024)]
    gencols = [f"gen_{t}" for t in cfg.TECH_ORDER if f"gen_{t}" in g.columns]
    catsum = g[gencols].sum().sum()
    tot = g["gen_total"].sum()
    check("DE24 categories == gen_total", abs(catsum - tot) / tot < 0.001,
          f"cats {catsum/1e6:.1f} TWh vs total {tot/1e6:.1f} TWh")

    # Redburn cross-checks (Germany 2024)
    print("\n== Redburn Fig cross-checks (DE 2024) ==")
    neg = pd.read_parquet(os.path.join(SUM, "neg_hours.parquet"))
    de24 = neg[(neg.country == "DE") & (neg.year == 2024)].iloc[0]
    check("DE24 near-neg hours > 600 (Fig 3)", de24["near_neg_hours"] > 600,
          f"near-neg = {de24['near_neg_hours']} (neg<0 = {de24['neg_hours']})")

    dmm = pd.read_parquet(os.path.join(SUM, "daily_minmax.parquet"))
    d = dmm[(dmm.country == "DE") & (dmm.year == 2024)]
    amin, amax, aspread = d["min_price"].mean(), d["max_price"].mean(), d["spread"].mean()
    check("DE24 avg daily spread ~EUR112 (Fig 6)", 95 < aspread < 130,
          f"spread {aspread:.0f} (min {amin:.0f} vs ref33, max {amax:.0f} vs ref144)")

    cap = pd.read_parquet(os.path.join(SUM, "capture_annual.parquet"))
    de = cap[(cap.country == "DE") & (cap.year == 2024)].set_index("tech")["capture_vs_base_pct"]
    check("DE24 Solar capture strongly negative (Fig 5)", de.get("Solar", 0) < -20,
          f"Solar {de.get('Solar'):.0f}%")
    check("DE24 Gas capture positive (Fig 5)", de.get("Gas", 0) > 0,
          f"Gas {de.get('Gas'):.0f}%")

    # Italy PUN proxy sanity
    print("\n== Italy PUN proxy sanity ==")
    it = m[(m.country == "IT") & (m.year == 2024)]["price"]
    if len(it):
        check("IT24 PUN proxy in sane range", 50 < it.mean() < 160,
              f"mean {it.mean():.1f} EUR/MWh, {it.notna().mean()*100:.0f}% coverage")

    npass = sum(1 for ok, _, _ in results if ok)
    print(f"\n==== {npass}/{len(results)} checks passed ====")

if __name__ == "__main__":
    main()

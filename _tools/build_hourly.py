"""
build_hourly.py — assemble the raw ENTSO-E pulls into an hourly UTC master.

Output:
  data/processed/hourly_master.parquet   one row per (country, ts_utc)
  data/processed/capacity_annual.parquet one row per (country, year, tech)
  data/processed/power.duckdb            DuckDB with both tables (fast querying)

Master columns (all MW except price):
  country, ts_utc(UTC, hourly)
  price                 EUR/MWh   (IT = load-weighted PUN proxy)
  load                  MW
  gen_total             MW        (sum of all Actual Aggregated production types)
  gen_<canonical tech>  MW        per config.TECH_ORDER category
  pumped_consumption    MW        (Hydro Pumped Storage, Actual Consumption; positive)
  flow_import           MW        (all-borders physical import)
  flow_export           MW        (all-borders physical export)
  flow_net              MW        (import - export; +ve = net importer)

Everything is resampled to hourly by MEAN of sub-hourly MW (= average power over
the hour ~ MWh delivered that hour). The canonical timeline is a gapless hourly
UTC index per year — UTC has no DST gaps/duplicates by construction.
"""
from __future__ import annotations
import os, glob, warnings; warnings.filterwarnings("ignore")
import pandas as pd
import duckdb
import config as cfg

RAW = cfg.RAW_DIR

def _read(country, series, year):
    p = os.path.join(RAW, f"{country}_{series}_{year}.parquet")
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return pd.read_parquet(p)
    return None

def _hourly_index(year):
    start = pd.Timestamp(f"{year}-01-01", tz="UTC")
    now = pd.Timestamp.now(tz="UTC").floor("h")
    end = pd.Timestamp(f"{year+1}-01-01", tz="UTC")
    if end > now:
        end = now
    return pd.date_range(start, end, freq="h", inclusive="left", tz="UTC")

def _to_hourly_mean(df):
    """Resample a tz-aware sub-hourly (or hourly) frame to hourly mean."""
    if df is None or len(df) == 0:
        return None
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df.resample("h").mean()

def build_price(country, year, hidx):
    meta = cfg.COUNTRIES[country]
    zones = meta["price_zones"]
    if len(zones) == 1:
        pr = _read(country, f"price_{zones[0]}", year)
        pr = _to_hourly_mean(pr)
        if pr is None:
            return pd.Series(index=hidx, dtype="float64")
        return pr.iloc[:, 0].reindex(hidx)
    # PUN proxy: load-weighted average across zones
    num = pd.Series(0.0, index=hidx)
    den = pd.Series(0.0, index=hidx)
    used = []
    for z in zones:
        pr = _to_hourly_mean(_read(country, f"price_{z}", year))
        ld = _to_hourly_mean(_read(country, f"load_{z}", year))
        if pr is None or ld is None:
            continue
        p = pr.iloc[:, 0].reindex(hidx)
        w = ld.iloc[:, 0].reindex(hidx)
        m = p.notna() & w.notna()
        num = num.add((p * w).where(m, 0.0), fill_value=0.0)
        den = den.add(w.where(m, 0.0), fill_value=0.0)
        used.append(z)
    pun = num / den.replace(0.0, pd.NA)
    return pun.reindex(hidx)

def build_generation(country, year, hidx):
    g = _to_hourly_mean(_read(country, "generation", year))
    cols = {}
    pumped = pd.Series(0.0, index=hidx)
    gen_total = pd.Series(0.0, index=hidx)
    have_pumped = False
    if g is not None:
        g = g.reindex(hidx)
        # canonical category buckets
        cat = {c: pd.Series(0.0, index=hidx) for c in cfg.TECH_ORDER}
        for col in g.columns:
            if "|" in col:
                psr, biz = col.split("|", 1)
            else:
                psr, biz = col, "Actual Aggregated"
            vals = g[col].fillna(0.0)
            if biz.strip() == "Actual Consumption":
                if psr.strip() == "Hydro Pumped Storage":
                    pumped = pumped.add(vals, fill_value=0.0)
                    have_pumped = True
                continue  # ignore other self-consumption
            # production
            canon = cfg.TECH_MAP.get(psr.strip(), "Other")
            cat.setdefault(canon, pd.Series(0.0, index=hidx))
            cat[canon] = cat[canon].add(vals, fill_value=0.0)
            gen_total = gen_total.add(vals, fill_value=0.0)
        for c in cfg.TECH_ORDER:
            cols[f"gen_{c}"] = cat[c]
    else:
        for c in cfg.TECH_ORDER:
            cols[f"gen_{c}"] = pd.Series(index=hidx, dtype="float64")
        gen_total = pd.Series(index=hidx, dtype="float64")
    cols["gen_total"] = gen_total if g is not None else pd.Series(index=hidx, dtype="float64")
    cols["pumped_consumption"] = pumped if have_pumped else pd.Series(index=hidx, dtype="float64")
    return cols

def build_flows(country, year, hidx):
    imp = _to_hourly_mean(_read(country, "flow_import", year))
    exp = _to_hourly_mean(_read(country, "flow_export", year))
    def _sum(df):
        if df is None:
            return pd.Series(index=hidx, dtype="float64")
        col = "sum" if "sum" in df.columns else df.columns[-1]
        return df[col].reindex(hidx)
    i = _sum(imp); e = _sum(exp)
    return i, e, (i - e)

def build_country_year(country, year):
    hidx = _hourly_index(year)
    if len(hidx) == 0:
        return None
    out = pd.DataFrame(index=hidx)
    out.index.name = "ts_utc"
    out["price"] = build_price(country, year, hidx)
    ld = _to_hourly_mean(_read(country, "load", year))
    out["load"] = ld.iloc[:, 0].reindex(hidx) if ld is not None else pd.NA
    gcols = build_generation(country, year, hidx)
    imp, exp, net = build_flows(country, year, hidx)
    out["gen_total"] = gcols.pop("gen_total")
    out["pumped_consumption"] = gcols.pop("pumped_consumption")
    for k, v in gcols.items():
        out[k] = v
    out["flow_import"] = imp
    out["flow_export"] = exp
    out["flow_net"] = net
    out.insert(0, "country", country)
    return out.reset_index()

def build_capacity(years=None):
    years = years if years is not None else cfg.YEARS
    rows = []
    for country in cfg.COUNTRY_ORDER:
        for year in years:
            cap = _read(country, "capacity", year)
            if cap is None:
                continue
            # capacity parquet: index is a single timestamp, columns are psr types
            # (query returns a 1-row frame; stored transposed sometimes). Normalise.
            df = cap.copy()
            # after _to_utc + _save, index=ts, columns=psr types, 1 row
            if df.shape[0] >= 1:
                ser = df.iloc[0]
            else:
                continue
            cat = {}
            for psr, val in ser.items():
                canon = cfg.TECH_MAP.get(str(psr).strip(), "Other")
                if pd.isna(val):
                    continue
                cat[canon] = cat.get(canon, 0.0) + float(val)
            for tech, mw in cat.items():
                rows.append({"country": country, "year": year, "tech": tech, "capacity_mw": mw})
    return pd.DataFrame(rows)

FIXED_MASTER = os.path.join(cfg.PROC_DIR, "master_fixed.parquet")
FIXED_CAP = os.path.join(cfg.PROC_DIR, "capacity_fixed.parquet")
LEAD = ["country", "ts_utc", "price", "load", "gen_total", "pumped_consumption",
        "flow_import", "flow_export", "flow_net"]

def _order_cols(df):
    gencols = [f"gen_{c}" for c in cfg.TECH_ORDER]
    return df[[c for c in LEAD if c in df.columns] + [c for c in gencols if c in df.columns]]

def _build_years(years):
    frames = []
    for country in cfg.COUNTRY_ORDER:
        for year in years:
            df = build_country_year(country, year)
            if df is not None and len(df):
                frames.append(df); print(f"  {country} {year}: {len(df)} hours", flush=True)
    return _order_cols(pd.concat(frames, ignore_index=True)) if frames else None

def main():
    import sys
    full = "--full" in sys.argv
    cur = cfg.CURRENT_YEAR

    if full:
        # bootstrap / annual re-freeze: rebuild everything from raw AND refreeze history
        print(f"FULL build (all years {cfg.YEARS[0]}-{cfg.YEARS[-1]})", flush=True)
        master = _build_years(cfg.YEARS)
        cap = build_capacity(cfg.YEARS)
        # refreeze completed years (< current) so future incremental runs are fast
        master[pd.to_datetime(master.ts_utc, utc=True).dt.year < cur].to_parquet(FIXED_MASTER, index=False)
        cap[cap.year < cur].to_parquet(FIXED_CAP, index=False)
        print(f"refroze history (<{cur}) -> master_fixed / capacity_fixed", flush=True)
    else:
        # incremental: build only the current year from raw, stitch onto frozen history
        print(f"INCREMENTAL build (current year {cur}; history from master_fixed)", flush=True)
        current = _build_years([cur])
        fixed = pd.read_parquet(FIXED_MASTER)
        fixed = fixed[pd.to_datetime(fixed.ts_utc, utc=True).dt.year != cur]  # safety: no overlap
        master = _order_cols(pd.concat([fixed, current], ignore_index=True)) if current is not None else _order_cols(fixed)
        capf = pd.read_parquet(FIXED_CAP)
        cap = pd.concat([capf[capf.year != cur], build_capacity([cur])], ignore_index=True)

    mp = os.path.join(cfg.PROC_DIR, "hourly_master.parquet")
    master.to_parquet(mp, index=False)
    print(f"master -> {mp}  shape {master.shape}", flush=True)
    cp = os.path.join(cfg.PROC_DIR, "capacity_annual.parquet")
    cap.to_parquet(cp, index=False)
    print(f"capacity -> {cp}  shape {cap.shape}", flush=True)

    dbp = os.path.join(cfg.PROC_DIR, "power.duckdb")
    if os.path.exists(dbp):
        os.remove(dbp)
    con = duckdb.connect(dbp)
    con.execute("CREATE TABLE hourly AS SELECT * FROM read_parquet(?)", [mp])
    con.execute("CREATE TABLE capacity AS SELECT * FROM read_parquet(?)", [cp])
    print("duckdb rows hourly:", con.execute("SELECT count(*) FROM hourly").fetchone()[0], flush=True)
    con.close()
    print(f"duckdb -> {dbp}", flush=True)

if __name__ == "__main__":
    main()

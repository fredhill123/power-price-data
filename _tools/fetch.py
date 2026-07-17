"""
fetch.py — pull all raw ENTSO-E series and cache to Parquet.

Series per country / year (UTC-year boundaries):
  price_<zone>   day-ahead prices (one file per price zone; IT has several)
  load           actual total load (national)
  load_<zone>    actual load per price zone  (IT only, for PUN weighting)
  generation     actual aggregated generation per production type (national)
  flow_import    physical cross-border flows INTO the country (all borders, +sum)
  flow_export    physical cross-border flows OUT of the country (all borders, +sum)
  capacity       annual installed generation capacity per type

Everything is stored with a tz-aware UTC DatetimeIndex. Resampling to the hourly
canonical timeline happens later in build_hourly.py.

Resumable: an existing, non-empty parquet for (country, series, year) is skipped
unless --force. For incremental updates, re-run with --years <latest> --force.

Usage:
  python fetch.py                       # everything, all countries, all years
  python fetch.py --country DE          # one country
  python fetch.py --country DE --years 2024   # one country-year (smoke test)
  python fetch.py --force               # re-fetch even if cached
"""
from __future__ import annotations
import argparse, os, sys, time, traceback
import warnings; warnings.filterwarnings("ignore")
import pandas as pd
from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError

import config as cfg

client = EntsoePandasClient(api_key=cfg.API_KEY, retry_count=4, retry_delay=8)

SLEEP = 0.7          # politeness pause between calls (well under 400/min limit)
LOG = []

def log(msg):
    line = f"[{pd.Timestamp.now(tz='UTC').strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.append(line)

def year_bounds(year: int):
    """UTC-year boundaries. 2026 (current) capped at 'now' floored to the hour."""
    start = pd.Timestamp(f"{year}-01-01", tz="UTC")
    now = pd.Timestamp.now(tz="UTC").floor("h")
    end = pd.Timestamp(f"{year+1}-01-01", tz="UTC")
    if end > now:
        end = now
    return start, end

def raw_path(country, series, year):
    return os.path.join(cfg.RAW_DIR, f"{country}_{series}_{year}.parquet")

def _to_utc(obj):
    """Return obj with a tz-aware UTC index; DataFrame or Series."""
    idx = obj.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    obj = obj.copy()
    obj.index = idx.tz_convert("UTC")
    obj.index.name = "ts_utc"
    return obj

def _save(obj, path):
    if obj is None or len(obj) == 0:
        return False
    if isinstance(obj, pd.Series):
        obj = obj.to_frame(name="value")
    # flatten MultiIndex columns (generation) to "a|b" strings for parquet
    if isinstance(obj.columns, pd.MultiIndex):
        obj = obj.copy()
        obj.columns = ["|".join(str(x) for x in c) for c in obj.columns]
    else:
        obj = obj.copy()
        obj.columns = [str(c) for c in obj.columns]
    obj.to_parquet(path)
    return True

def _need(path, force):
    if force:
        return True
    return not (os.path.exists(path) and os.path.getsize(path) > 0)

def _attempt(label, fn, path, force):
    if not _need(path, force):
        log(f"  skip  {label} (cached)")
        return
    try:
        obj = fn()
        if _save(_to_utc(obj) if obj is not None and len(obj) else obj, path):
            log(f"  ok    {label}  ({len(obj)} rows)")
        else:
            log(f"  EMPTY {label}")
    except NoMatchingDataError:
        log(f"  none  {label} (no data published)")
    except Exception as ex:
        log(f"  FAIL  {label}: {type(ex).__name__}: {str(ex)[:90]}")
    time.sleep(SLEEP)

def fetch_country_year(country, year, force=False):
    meta = cfg.COUNTRIES[country]
    code = meta["code"]
    s, e = year_bounds(year)
    if s >= e:
        log(f"{country} {year}: future/empty window, skip")
        return
    log(f"== {country} ({code}) {year}  [{s.date()}..{e.date()}] ==")

    # ---- prices (per zone) ----
    for zone in meta["price_zones"]:
        _attempt(f"price {zone}",
                 lambda z=zone: client.query_day_ahead_prices(z, start=s, end=e),
                 raw_path(country, f"price_{zone}", year), force)

    # ---- load (national) ----
    _attempt("load",
             lambda: client.query_load(code, start=s, end=e),
             raw_path(country, "load", year), force)

    # ---- per-zone load for IT PUN weighting ----
    if len(meta["price_zones"]) > 1:
        for zone in meta["price_zones"]:
            _attempt(f"load {zone}",
                     lambda z=zone: client.query_load(z, start=s, end=e),
                     raw_path(country, f"load_{zone}", year), force)

    # ---- generation per type (national) ----
    _attempt("generation",
             lambda: client.query_generation(code, start=s, end=e, psr_type=None),
             raw_path(country, "generation", year), force)

    # ---- cross-border physical flows (all borders) ----
    _attempt("flow_import",
             lambda: client.query_physical_crossborder_allborders(code, start=s, end=e, export=False),
             raw_path(country, "flow_import", year), force)
    _attempt("flow_export",
             lambda: client.query_physical_crossborder_allborders(code, start=s, end=e, export=True),
             raw_path(country, "flow_export", year), force)

    # ---- installed capacity (annual) ----
    cs = pd.Timestamp(f"{year}-01-01", tz="UTC")
    ce = pd.Timestamp(f"{year}-12-31", tz="UTC")
    _attempt("capacity",
             lambda: client.query_installed_generation_capacity(code, start=cs, end=ce),
             raw_path(country, "capacity", year), force)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default=None, help="DE/FR/ES/PT/IT (default all)")
    ap.add_argument("--years", default=None, help="comma list, e.g. 2024 or 2019,2020")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    countries = [a.country] if a.country else cfg.COUNTRY_ORDER
    years = [int(y) for y in a.years.split(",")] if a.years else cfg.YEARS

    t0 = time.time()
    for country in countries:
        for year in years:
            try:
                fetch_country_year(country, year, force=a.force)
            except Exception:
                log(f"UNCAUGHT {country} {year}\n{traceback.format_exc()}")
    log(f"DONE in {(time.time()-t0)/60:.1f} min")
    with open(os.path.join(cfg.META_DIR, "fetch_log.txt"), "a") as f:
        f.write("\n".join(LOG) + "\n")

if __name__ == "__main__":
    main()

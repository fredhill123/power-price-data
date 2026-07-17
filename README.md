# Power Price Data — ENTSO-E auto-updating dataset

Hourly ENTSO-E data (2019–2026) for **Germany, Spain, Portugal, France, Italy**, distilled into a
fixed-cell-reference Excel workbook that feeds auto-updating PowerPoint charts (Redburn/Rothschild style).

## What it produces
- **`output/PowerPriceData.xlsx`** — summary-only workbook, one tab per chart, every datapoint at a
  **stable cell reference** so linked PPT charts update on refresh.
- Charts covered: Redburn Figs **1** (price SD), **2** (indexed intraday price), **3** (negative-hour
  counts + cumulative), **4** (price duration curves), **5** (capture price vs base by tech), **6** (daily
  min/max spread), **7** (intraday generation mix + net flow + price), **9** (annual capacity).

## Data it holds (hourly, UTC)
Per country: day-ahead **price** (Italy = load-weighted **PUN proxy**), total **generation** + per-technology
breakdown, **pumped-storage consumption**, total **load**, cross-border **import/export/net** flow, and
annual installed **capacity** by technology.

## Architecture
```
_tools/config.py        countries, zones, technology taxonomy, paths
_tools/fetch.py         pull raw ENTSO-E series -> data/raw/*.parquet   (resumable)
_tools/build_hourly.py  resample to hourly UTC master -> data/processed/{hourly_master,capacity_annual}.parquet + power.duckdb
_tools/summaries.py     derived tables -> data/processed/summaries/*.parquet
_tools/build_excel.py   fixed-cell workbook -> output/PowerPriceData.xlsx
```
Raw hourly data lives in **Parquet + DuckDB** (fast to query/aggregate); Excel holds only chart summaries.

## Regular update (the whole point)
To refresh with the latest data (re-fetch the current + previous year, rebuild everything):
```bash
cd _tools && source .venv/bin/activate
python fetch.py --years 2025,2026 --force     # re-pull latest (older years cached)
python build_hourly.py
python summaries.py
python build_excel.py
```
Because every datapoint keeps its **exact cell reference**, the linked PowerPoint charts update
automatically — no re-linking needed. A one-shot `refresh.sh` wraps the four commands.

## Key conventions
- **UTC everywhere** — all hour/day/month buckets use UTC (DST-safe, no duplicated/missing hours).
- **2026 is year-to-date** — flagged amber in the workbook.
- **Italy price is a PUN proxy** (load-weighted zonal). See `_meta/sources.jsonl`.
- Generation/flows stored as hourly-mean MW (≈ MWh delivered that hour).

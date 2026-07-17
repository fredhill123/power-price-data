"""
export_csv.py — export the summary tables as stable-schema CSVs for hosting.

These CSVs are what the Excel workbook pulls (via Power Query 'From Web') on
your work PC. The GitHub Action runs the pipeline and publishes these to a
stable public URL; Excel is set to refresh-on-open, so a non-technical person
just opens the workbook and it pulls the latest.

Tidy/long format (one row per observation) — Power Query loads each into a
table, and the fixed-cell figure tabs look values up from those tables, so
every datapoint keeps a stable cell reference for PowerPoint links.

Writes: outputs/csv/*.csv  (one per summary table) + manifest.json
"""
from __future__ import annotations
import os, json, warnings; warnings.filterwarnings("ignore")
import pandas as pd
import config as cfg

SUM = os.path.join(cfg.PROC_DIR, "summaries")
CSV_DIR = os.path.join(cfg.OUTPUT_DIR, "csv")
os.makedirs(CSV_DIR, exist_ok=True)

TABLES = [
    "neg_hours", "cum_neghours", "intraday_price", "price_sd",
    "duration_curve", "daily_minmax", "capture_monthly", "capture_annual",
    "intraday_genmix", "capacity",
]

def main():
    manifest = {"generated_utc": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tables": {}}
    for name in TABLES:
        src = os.path.join(SUM, f"{name}.parquet")
        if not os.path.exists(src):
            print(f"  MISSING {name}"); continue
        df = pd.read_parquet(src)
        out = os.path.join(CSV_DIR, f"{name}.csv")
        df.to_csv(out, index=False, encoding="utf-8")
        manifest["tables"][name] = {"rows": len(df), "cols": list(df.columns)}
        print(f"  {name:16s} {df.shape} -> {name}.csv", flush=True)
    with open(os.path.join(CSV_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"exported {len(manifest['tables'])} CSVs -> {CSV_DIR}", flush=True)

if __name__ == "__main__":
    main()

"""
extra_summaries.py — build the three NEW chart-ready tables that the deck needs
but the existing summary tabs can't produce (they need raw hourly granularity):

  G1  g1_solar_peakhour.csv       — daily solar share of total generation in each
                                     day's PEAK SOLAR hour, per country, + a
                                     quarterly-average step column per country.
  G2a g2_price_by_quarter.csv     — intraday price profile (abs €/MWh) by hour,
                                     split by country × year × QUARTER.
  G2b g2_price_by_month.csv       — same, split by country × year × MONTH.
  G3  g3_price_july_daily.csv     — every day's hourly price profile in JULY,
                                     per country × year × day (the "daily duck
                                     curve spaghetti").

Reads the assembled master (data/processed/hourly_master.parquet); writes CSVs to
outputs/csv/charts/ AND published/charts/. Year columns pre-allocated to
DISPLAY_END_YEAR so future years fill blank columns without shifting cells.
"""
from __future__ import annotations
import os
import pandas as pd
import config as cfg

MASTER = os.path.join(cfg.PROC_DIR, "hourly_master.parquet")
OUT = os.path.join(cfg.OUTPUT_DIR, "csv", "charts")
PUB = os.path.join(cfg.ROOT, "published", "charts")
YRS = list(range(cfg.START_YEAR, cfg.DISPLAY_END_YEAR + 1))   # 2019..2030
CO = cfg.COUNTRY_ORDER                                        # DE, ES, PT, FR, IT
JULY = 7

def _load():
    df = pd.read_parquet(MASTER)
    t = pd.to_datetime(df["ts_utc"], utc=True)
    df["year"] = t.dt.year; df["quarter"] = t.dt.quarter
    df["month"] = t.dt.month; df["day"] = t.dt.day
    df["hour"] = t.dt.hour; df["date"] = t.dt.normalize()
    return df

def _save(df, name):
    for d in (OUT, PUB):
        os.makedirs(d, exist_ok=True)
        df.to_csv(os.path.join(d, name + ".csv"), index=False, encoding="utf-8")
    print(f"  wrote {name}: {df.shape[0]} rows x {df.shape[1]} cols", flush=True)

# ---------------------------------------------------------------- G1
def g1(df):
    # peak solar hour per (country, date): row where gen_Solar is maximal
    idx = df.groupby(["country", "date"])["gen_Solar"].idxmax()
    pk = df.loc[idx, ["country", "date", "gen_Solar", "gen_total"]].copy()
    pk["share"] = (pk["gen_Solar"] / pk["gen_total"] * 100).clip(lower=0)
    wide = pk.pivot(index="date", columns="country", values="share")
    full = pd.date_range("2019-01-01", f"{cfg.DISPLAY_END_YEAR}-12-31", freq="D", tz="UTC")
    wide = wide.reindex(full)
    out = pd.DataFrame({"date": wide.index.strftime("%Y-%m-%d")})
    qkey = [wide.index.year, wide.index.quarter]
    for c in CO:
        if c not in wide.columns:
            continue
        out[c] = wide[c].round(1).values
        out[c + "_qavg"] = wide[c].groupby(qkey).transform("mean").round(1).values
    _save(out, "g1_solar_peakhour")

# ---------------------------------------------------------------- G2 / G3 helper
def _intraday_pivot(df, extra_key, key_vals, label, name):
    """avg price by hour, split by country × year × <extra_key>."""
    pt = df.pivot_table(index="hour", columns=["country", "year", extra_key],
                        values="price", aggfunc="mean")
    cols = [(c, y, k) for c in CO for y in YRS for k in key_vals]
    pt = pt.reindex(index=range(24), columns=cols)
    pt.columns = [f"{c}_{y}_{label(k)}" for (c, y, k) in cols]
    out = pt.round(2).reset_index().rename(columns={"hour": "hour_utc"})
    _save(out, name)

def g2_quarter(df):
    _intraday_pivot(df, "quarter", [1, 2, 3, 4], lambda q: f"Q{q}", "g2_price_by_quarter")

def g2_month(df):
    _intraday_pivot(df, "month", list(range(1, 13)), lambda m: f"M{m:02d}", "g2_price_by_month")

def g3_july(df):
    jul = df[df["month"] == JULY]
    _intraday_pivot(jul, "day", list(range(1, 32)), lambda d: f"D{d:02d}", "g3_price_july_daily")

def main():
    print("building extra chart tables (G1/G2/G3) ->", PUB, flush=True)
    df = _load()
    g1(df); g2_quarter(df); g2_month(df); g3_july(df)
    print("done", flush=True)

if __name__ == "__main__":
    main()

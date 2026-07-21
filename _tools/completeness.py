"""
completeness.py — work out which calendar periods are FULLY complete in the data,
so period-based charts never plot a half-finished month/quarter/year.

A period counts as complete only when the data coverage reaches its final hour AND
every country has data that far (we take the earliest per-country coverage end, so
a lagging country can't make a period look complete when it isn't).

Used by render_all.py:
  * annual-stat charts  -> plot years <= last_complete_year
  * quarterly ducks      -> quarters <= last_complete_quarter
  * monthly ducks        -> months  <= last_complete_month
  * intraday PROFILES    -> keep the current partial year but LABEL it "YTD"
"""
from __future__ import annotations
import os
import pandas as pd
import config as cfg


def coverage_end(master_path: str | None = None) -> pd.Timestamp:
    """Earliest per-country last-non-null-price timestamp (tz-naive UTC)."""
    p = master_path or os.path.join(cfg.PROC_DIR, "hourly_master.parquet")
    df = pd.read_parquet(p, columns=["country", "ts_utc", "price"])
    df["ts_utc"] = pd.to_datetime(df["ts_utc"])
    last = df[df["price"].notna()].groupby("country")["ts_utc"].max().min()
    ts = pd.Timestamp(last)
    return ts.tz_localize(None) if ts.tz is not None else ts


def cutoffs(ce: pd.Timestamp | None = None, master_path: str | None = None) -> dict:
    """Return the completeness cutoffs given a coverage-end timestamp."""
    ce = pd.Timestamp(ce) if ce is not None else coverage_end(master_path)
    if ce.tz is not None:
        ce = ce.tz_localize(None)
    years = [Y for Y in range(cfg.START_YEAR, ce.year + 1)
             if ce >= pd.Timestamp(year=Y + 1, month=1, day=1)]
    last_year = max(years) if years else ce.year - 1
    pm = pd.Period(ce, freq="M"); last_m = pm if ce >= pm.end_time else pm - 1
    pq = pd.Period(ce, freq="Q"); last_q = pq if ce >= pq.end_time else pq - 1
    return {
        "coverage_end": ce,
        "last_complete_year": last_year,
        "last_complete_month": (last_m.year, last_m.month),
        "last_complete_quarter": (last_q.year, last_q.quarter),
        "last_complete_month_end": last_m.end_time,      # Timestamp
        "last_complete_quarter_end": last_q.end_time,    # Timestamp
    }


if __name__ == "__main__":
    c = cutoffs()
    print("coverage end        :", c["coverage_end"])
    print("last complete year  :", c["last_complete_year"])
    print("last complete quarter:", c["last_complete_quarter"])
    print("last complete month :", c["last_complete_month"])

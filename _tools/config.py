"""
config.py — canonical configuration for the ENTSO-E power-price data system.

Countries: Germany (DE-LU), France, Spain, Portugal, Italy.
Range:     2019-01-01 .. present (2026 is YTD).
Timebase:  everything is stored on an HOURLY UTC canonical timeline (DST-safe).

Key design decisions (locked with Fred, 2026-07-16):
  * Italy has no single national day-ahead price -> we build a load-weighted
    PUN *proxy* across the Italian bidding zones. Generation / load / flows /
    capacity for Italy are queried at national "IT" level (verified to work).
  * Intraday "hour-of-day" analytics bucket by UTC hour (Fred's choice).
  * Charts to reproduce: Redburn Figs 1-6 (ENTSO-E), + Fig 7 (intraday gen mix)
    + Fig 9 (annual capacity).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
# Key resolution (never hardcode — repo may be public):
#   1) ENTSOE_API_KEY env var (GitHub Actions injects this from encrypted Secrets)
#   2) a git-ignored local file  _tools/.entsoe_key  (for runs on Fred's machine)
import os as _os
def _load_api_key():
    k = _os.environ.get("ENTSOE_API_KEY")
    if k:
        return k.strip()
    kf = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".entsoe_key")
    if _os.path.exists(kf):
        with open(kf) as f:
            return f.read().strip()
    raise RuntimeError(
        "No ENTSO-E API key: set ENTSOE_API_KEY env var or create _tools/.entsoe_key")
API_KEY = _load_api_key()

# ---- Year handling (future-proof) -----------------------------------------
# DATA years auto-extend to the current calendar year, so next January the
# pipeline fetches 2027 with no code change. The current year is partial (YTD).
from datetime import date as _date
START_YEAR = 2019
CURRENT_YEAR = _date.today().year
YEARS = list(range(START_YEAR, CURRENT_YEAR + 1))   # years we actually fetch/have data for

# DISPLAY horizon: the Excel workbook pre-allocates a fixed cell grid out to
# DISPLAY_END_YEAR. Future years (beyond CURRENT_YEAR) are laid out as BLANK
# cells now, so a PowerPoint chart linked to the full range auto-populates them
# on a future refresh WITHOUT any cell reference moving. Bump this once if you
# ever need to see past 2035.
DISPLAY_END_YEAR = 2035
DISPLAY_YEARS = list(range(START_YEAR, DISPLAY_END_YEAR + 1))

# ---------------------------------------------------------------------------
# Countries
# ---------------------------------------------------------------------------
# For each country:
#   code        : the ENTSO-E area used for generation / load / flows / capacity
#   price_zones : zone(s) used to derive the representative day-ahead price
#                 - single-element -> used directly
#                 - multi-element  -> load-weighted PUN proxy
#   tz          : local market timezone (documentation only; storage is UTC)
COUNTRIES = {
    "DE": {
        "name": "Germany",
        "code": "DE_LU",
        "price_zones": ["DE_LU"],
        "tz": "Europe/Berlin",
    },
    "FR": {
        "name": "France",
        "code": "FR",
        "price_zones": ["FR"],
        "tz": "Europe/Paris",
    },
    "ES": {
        "name": "Spain",
        "code": "ES",
        "price_zones": ["ES"],
        "tz": "Europe/Madrid",
    },
    "PT": {
        "name": "Portugal",
        "code": "PT",
        "price_zones": ["PT"],
        "tz": "Europe/Lisbon",  # WET/WEST (UTC+0/+1) — the only non-CET market
    },
    "IT": {
        "name": "Italy",
        "code": "IT",  # national generation/load/flows/capacity work at "IT"
        # PUN proxy: load-weighted across bidding zones. CALA (Calabria) only
        # exists from 2021; zones that return no data for a year are skipped.
        "price_zones": [
            "IT_NORD", "IT_CNOR", "IT_CSUD", "IT_SUD",
            "IT_CALA", "IT_SICI", "IT_SARD",
        ],
        "tz": "Europe/Rome",
    },
}

COUNTRY_ORDER = ["DE", "ES", "PT", "FR", "IT"]  # display order (Iberia grouped)

# ---------------------------------------------------------------------------
# Technology taxonomy
# ---------------------------------------------------------------------------
# Maps raw ENTSO-E production types -> canonical categories used in every
# output (capture prices, generation mix, capacity). Pumped-storage consumption
# is tracked as its OWN category (stored positive here; rendered negative in the
# intraday-mix chart, per Redburn Fig 7).
#
# ENTSO-E returns generation columns as a MultiIndex (psr_type, business_type)
# where business_type is "Actual Aggregated" (production) or
# "Actual Consumption" (load of the unit, used for pumped storage).
TECH_MAP = {
    "Solar":                              "Solar",
    "Wind Onshore":                       "Onshore wind",
    "Wind Offshore":                      "Offshore wind",
    "Hydro Run-of-river and poundage":    "Hydro run-of-river",
    "Hydro Water Reservoir":              "Hydro reservoir",
    "Hydro Pumped Storage":               "Hydro pumped (production)",  # Actual Aggregated
    "Nuclear":                            "Nuclear",
    "Biomass":                            "Biomass",
    "Fossil Gas":                         "Gas",
    "Fossil Coal-derived gas":            "Gas",
    "Fossil Brown coal/Lignite":          "Lignite",
    "Fossil Hard coal":                   "Hard coal",
    "Fossil Oil":                         "Oil & other fossil",
    "Fossil Oil shale":                   "Oil & other fossil",
    "Fossil Peat":                        "Oil & other fossil",
    "Geothermal":                         "Geothermal",
    "Marine":                             "Marine",
    "Waste":                              "Waste",
    "Other":                              "Other",
    "Other renewable":                    "Other renewable",
}

# Special category for pumped-storage CONSUMPTION (from the "Actual Consumption"
# business type on Hydro Pumped Storage). Stored as a positive MW figure.
PUMPED_CONSUMPTION = "Hydro pumped (consumption)"

# Canonical ordered category list (production categories, stacking order for
# Fig 7 roughly bottom->top; consumption handled separately).
TECH_ORDER = [
    "Nuclear",
    "Lignite",
    "Hard coal",
    "Gas",
    "Oil & other fossil",
    "Biomass",
    "Waste",
    "Geothermal",
    "Hydro run-of-river",
    "Hydro reservoir",
    "Hydro pumped (production)",
    "Onshore wind",
    "Offshore wind",
    "Solar",
    "Marine",
    "Other renewable",
    "Other",
]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
import os
_TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_TOOLS)
RAW_DIR = os.path.join(ROOT, "data", "raw")            # per (country, series, year) parquet
PROC_DIR = os.path.join(ROOT, "data", "processed")     # master hourly parquet + duckdb
OUTPUT_DIR = os.path.join(ROOT, "outputs")             # Excel + charts (house-style dir)
META_DIR = os.path.join(ROOT, "_meta")

for _d in (RAW_DIR, PROC_DIR, OUTPUT_DIR, META_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------------
# Thresholds / analytics params
# ---------------------------------------------------------------------------
NEG_PRICE_THRESHOLD = 0.0          # "negative hours" : price < 0
NEAR_NEG_THRESHOLD = 1.0           # Redburn Fig 3 : price < 1 EUR/MWh (near-negative)
DURATION_CURVE_STEPS = 101         # 0..100% in 1% steps for price-duration curves

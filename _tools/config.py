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
    # Lazy: return None if absent so build/summary scripts (which don't fetch)
    # can import config without a key. fetch.py raises when it actually needs it.
    k = _os.environ.get("ENTSOE_API_KEY")
    if k:
        return k.strip()
    kf = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".entsoe_key")
    if _os.path.exists(kf):
        with open(kf) as f:
            return f.read().strip()
    return None
API_KEY = _load_api_key()

# ---- Year handling (future-proof) -----------------------------------------
# DATA years auto-extend to the current calendar year, so next January the
# pipeline fetches 2027 with no code change. The current year is partial (YTD).
from datetime import date as _date
START_YEAR = 2019
CURRENT_YEAR = _date.today().year
YEARS = list(range(START_YEAR, CURRENT_YEAR + 1))   # years we actually fetch/have data for

# DISPLAY horizon: the published chart CSVs pre-allocate a fixed cell grid out to
# DISPLAY_END_YEAR, so future years land in already-reserved cells without any
# reference shifting. The delivered Redburn charts CAP their plotted range at the
# last year WITH data (so no empty future years show — Fred, 2026-07-17).
#
# MUST stay 2035: the live workbook's chart column references are built for a
# 17-year block per country (DE_2019..DE_2035, then ES_..., then PT_...). Shrinking
# this horizon shifts every country block left, so e.g. the Portugal capture chart
# silently starts plotting French data. Verified 2026-07-21.
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
# Display curation — technology charts
# ---------------------------------------------------------------------------
# ENTSO-E reports 17 production types, but plotting all 17 as bar categories (or
# as stack/legend entries) makes the exhibit unreadable. Skye's volatility-capture
# note shows a CURATED set instead: Fig 5/47 (German capture vs base) uses 10
# technologies, Fig 50 (Portugal) 7, Fig 7 (Portugal intraday mix) 8 + storage
# consumption, net imports and price. We mirror that.
#
# An Excel chart series reads ONE contiguous range, so each country's set gets its
# own STACKED BLOCK of rows in the capture/capacity CSVs. That lets every chart keep
# the note's exact ordering rather than sharing one compromise order (the blocks
# repeat some technologies — deliberate; these are chart-feed tables, one per chart).
#
#   rows  2-12  Germany  — note Fig 5/47 order
#   rows 13-19  Portugal — note Fig 50 order
#   rows 20-25  technologies in neither chart, kept for reference
TECH_BLOCKS = {
    # Fig 5/47: Solar, Onshore wind, Offshore wind, Hydro pumped, Hydro,
    #           Nuclear, Biomass, Gas, Lignite, Hard coal
    "DE": [
        "Solar",
        "Onshore wind",
        "Offshore wind",
        "Hydro pumped (production)",
        "Hydro reservoir",
        "Hydro run-of-river",
        "Nuclear",
        "Biomass",
        "Gas",
        "Lignite",
        "Hard coal",
    ],
    # Fig 50: Solar, Wind, Hydro run-of-river, Hydro reservoir, Hydro pumped,
    #         Biomass, Gas
    "PT": [
        "Solar",
        "Onshore wind",
        "Hydro run-of-river",
        "Hydro reservoir",
        "Hydro pumped (production)",
        "Biomass",
        "Gas",
    ],
}

_BLOCK_SEQ = ["DE", "PT"]          # stacking order == row order in the CSVs


def tech_keep(country):
    """Curated technology list for a country's capture / capacity charts."""
    return TECH_BLOCKS.get(country, TECH_BLOCKS["DE"])


def tech_block_start(country):
    """1-based data-row offset of this country's block (row 1 = CSV header)."""
    row = 2
    for c in _BLOCK_SEQ:
        if c == country:
            return row
        row += len(TECH_BLOCKS[c])
    return row


def tech_row_order():
    """Full row order of the capture/capacity CSVs: the blocks, then the leftovers."""
    rows = []
    for c in _BLOCK_SEQ:
        rows += TECH_BLOCKS[c]
    seen = set(rows)
    rows += [t for t in TECH_ORDER if t not in seen]
    return rows


TECH_DISPLAY_ORDER = None   # superseded by TECH_BLOCKS / tech_row_order()


# Intraday generation mix (note Fig 7): the same curated set plus the "Other"
# bucket. For Portugal the 9 omitted types are 0.13% of volume (no nuclear,
# lignite, coal, oil, waste, geothermal or marine at all).
GENMIX_KEEP = TECH_BLOCKS["PT"] + ["Other"]

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

# Your remaining setup — Windows work machine

_Verified 2026-07-21 against the delivered files, and against the workbook you refreshed
and sent back (all 6 new queries loaded exactly the published data, no column shift)._

**All 18 Power Query connections are now wired into the workbook itself**, with
refresh-on-open already ticked. There is no query-building left to do.

Two steps remain.

---

## 1. Put both live files in the shared Redburn folder
The deck links to the workbook by **absolute path** — read out of the pptx, it is:
```
\\redburn.local\core\data\Oils\Oils 2.0\Power & Utilities Team Resources\Sector Presentation\
    HourlyPowerData.xlsx
    HourlyPowerData.pptx
```
(the `H:\Oils\Oils 2.0\…` mapped drive). Both must sit **together** there. If your actual
folder differs, tell Claude the real path and it'll rebuild the deck pointing there —
otherwise the links won't resolve.

## 2. Update the deck's links
Open `HourlyPowerData.pptx` ▸ **File ▸ Info ▸ Edit Links to Files ▸ Update Now**
(or set to **Automatic**).

That's it. From then on: open the workbook (it refreshes itself), open the deck (links
update). The GitHub Action refreshes the underlying data monthly.

---

## What changed, and why you don't wire queries any more
`_tools/add_power_queries.py` injects each connection directly into the workbook —
the M query into the DataMashup blob, plus the connection, queryTable, table and hidden
`ExternalData_1` name — by cloning the patterns the original 12 queries already used. It
runs inside `generate.py`, so a rebuild can never silently drop them.

The 18 tabs and their sources (base URL =
`https://raw.githubusercontent.com/fredhill123/power-price-data/main/published/charts/`):

| Tab | CSV | Tab | CSV |
|-----|-----|-----|-----|
| Fig1_PriceSD | `fig1_price_sd` | CaptureMonthly | `capture_monthly` |
| Fig2_Intraday | `fig2_intraday_indexed` | G1_SolarPeak | `g1_solar_peakhour` |
| Fig2_Intraday_avg | `fig2_intraday_avg` | G2_MonthDuck | `g2_price_by_month` |
| Fig3_NegHours | `fig3_neg_hours_annual` | A_MonthPrice | `figA_monthly_price` |
| Fig3_CumNeg | `fig3_cum_near_neg` | B_Penetration | `figB_penetration` |
| Fig4_Duration | `fig4_duration_curve` | C_CaptureErosion | `figC_capture_erosion` |
| Fig5_Capture | `fig5_capture_pct` | D_NetloadDuck | `figD_netload_duck` |
| Fig5_Capture_abs | `fig5_capture_abs` | Fig7_GenMix | `fig7_gen_mix` |
| Fig6_MinMax | `fig6_daily_minmax` | Fig9_Capacity | `fig9_capacity` |

The price-cannibalisation scatter, quarterly-duck and July-spaghetti exhibits are **static
images** — no query, nothing to set up.

## If you ever DO need to add a query by hand
**Data ▸ Get Data ▸ From Web** ▸ paste the URL ▸ **Load To… ▸ Existing worksheet ▸** that
tab's **`$A$1`**, keeping the header row (every chart reads from row 2 down). Load into
**empty** cells — anything pre-typed makes Power Query shift the columns and detach the chart.

## Known limits
- **Year-series charts don't self-extend.** The net-load duck plots `DE_2019…DE_2026` — the
  years with data today. A future calendar year needs a `generate.py` rebuild on the Mac.
- **Don't click "Recover"** if Excel ever offers to repair the file. Repair strips Power
  Query, which is the one thing that would cost you real work. Send the file to Claude instead.

## What needs NO setup
`HourlyPowerData_frozen.xlsx` and `HourlyPowerData_snapshot.pptx` are self-contained — just
open them. The monthly data refresh (GitHub Action) and the whole generate-a-fresh-deck path
are already done.

_Full system overview: `GENERATE.md`. Non-technical team refresh: `Deliverables/updating-the-deck`._

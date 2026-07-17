# Linking the workbook to auto-updating PowerPoint charts

The whole point: build each chart **once** in PowerPoint, linked to
`outputs/PowerPriceData.xlsx`, then every future refresh updates the charts with
**no re-linking** — because every datapoint keeps its exact cell reference.

## One-time setup (per chart)
1. Open `outputs/PowerPriceData.xlsx` and the target PowerPoint side by side.
2. In Excel, select the data range for the chart (see the tab guide below) and
   **Insert → Chart**, or build the chart in PowerPoint and set its data range to
   the Excel range.
3. Paste into PowerPoint with **Paste Special → Paste Link** (or Insert Chart →
   link to the workbook). This creates a *linked* chart, not an embedded copy.
4. Style it in the Rothschild look — the PNGs in `outputs/charts/` are your
   visual templates (colours, ordering, labels).

## Refreshing (every period)
```bash
cd _tools && ./refresh.sh          # re-fetch latest years, rebuild everything
```
Then in PowerPoint: **File → Info → Edit Links to Files → Update Now** (or it
prompts on open). Charts redraw with the new numbers. Keep the workbook at the
**same path** — moving it breaks the links.

## Why the references stay stable
- **Time-series tabs** (Fig1, Fig2, Fig3, Fig3_CumNegHours, Fig4, Fig5, Fig9,
  CaptureMonthly): year columns are pre-allocated out to **2035** (blank until
  data exists). Link a chart to the *full* range once and future years appear
  automatically — no cell moves.
- **Single-panel tabs** (Fig6, Fig7): blocks are ordered YEAR-then-country, so a
  new year is appended at the **bottom**; existing blocks never move.
- The current (partial) year is highlighted amber.

## Which range feeds which chart
| Tab | Chart | Range to link |
|---|---|---|
| Fig1_PriceSD | SD by year | year rows × country columns |
| Fig2_IntradayPrice | indexed price by hour | per-country block: 24 hour-rows × year-cols (INDEXED side) |
| Fig3_NegHours | neg / near-neg counts | year rows × country cols (two blocks) |
| Fig3_CumNegHours | cumulative neg hours | 366 doy-rows × country-year cols |
| Fig4_DurationCurve | price duration | 101 pct-rows × country-year cols |
| Fig5_Capture | capture vs base % | tech rows × country-year cols (% block on top) |
| Fig6_DailyMinMax | daily min/max scatter | one country-year block: Max col (x) vs Min col (y) |
| Fig7_GenMix | intraday gen mix | one country-year block: 24 hour-rows × series cols + price col |
| Fig9_Capacity | annual capacity | tech rows × country-year cols |
| CaptureMonthly | monthly capture | month rows × country-tech cols |

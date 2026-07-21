# Your workflow — Windows work machine

_Verified end-to-end on 2026-07-21 by running the full GitHub Actions workflow
(run 29823518203): data fetched, CSVs published, and all four deliverables rebuilt
and committed by CI, with `CONSISTENCY: PASS`._

**There is no setup left, and nothing you need to run.** All 18 Power Query connections
ship inside the workbook with refresh-on-open already ticked.

---

## The whole routine

1. **Open `HourlyPowerData.xlsx`** — it refreshes itself on open.
2. **Open `HourlyPowerData.pptx`** ▸ **File ▸ Info ▸ Edit Links to Files ▸ Update Now**
   (or set the links to **Automatic** once, and even this goes away).

That's it, monthly and forever.

Both files must sit **together** at the path the deck links to:
```
\\redburn.local\core\data\Oils\Oils 2.0\Power & Utilities Team Resources\Sector Presentation\
```
(the `H:\Oils\Oils 2.0\…` mapped drive). If that path ever changes, the deck's links must be
rebuilt to match — that is the one change that needs someone to rebuild the file.

## What happens without you

- **Monthly** (2nd of each month, 06:00 UTC) GitHub Actions pulls fresh ENTSO-E data,
  republishes the chart CSVs, and **rebuilds all four deliverables**, committing them to
  `deliverables/` in the repo. Your workbook picks the data up on open.
- **At the turn of the year** the same run folds the completed year into the frozen history
  and rebuilds the charts so they carry the new year. Nothing manual, no rollover to remember.

The only reason to fetch a fresh copy from `deliverables/` is if you want the *charts* to show
a newly completed year — the data in your existing file is current either way. Grab the newest
`HourlyPowerData.xlsx` / `.pptx` from the repo when the Status tab tells you to.

## The Status tab — read this if something looks off

The workbook **opens on a `Status` sheet**. It compares the published refresh record against
today's date on your machine and says one of:

- ✅ *"OK - data is current. Last refreshed …, data through …"* — nothing to do.
- ⚠️ *"STALE DATA - the monthly refresh has not run for N days"* — the GitHub job has stopped
  running. Someone needs to look at the Actions tab.
- ⚠️ *"ANNUAL ROLLOVER OVERDUE - charts were built for YYYY"* — download the latest files from
  `deliverables/`.

Both warnings are in large red text and cannot be missed. Green means genuinely fine.

## Two things not to do
- **Never click "Recover"** if Excel offers to repair the workbook. Repair strips Power Query,
  which is the one thing that would cost real work. Send the file to be fixed instead.
- **Don't hand-edit the data tabs.** They are Power Query load targets; anything typed there is
  overwritten on refresh, and pre-seeded cells can shift the columns and detach a chart.

## What needs no setup at all
`HourlyPowerData_frozen.xlsx` and `HourlyPowerData_snapshot.pptx` are fully self-contained —
open and use. They're rebuilt monthly alongside the live pair.

_System overview: `GENERATE.md`. Manual rollover fallback (only if CI is broken): `ROLLOVER.md`._

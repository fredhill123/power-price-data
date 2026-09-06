# Your workflow — Windows work machine

_Verified end-to-end on 2026-07-21 by running the full GitHub Actions workflow
(run 29823518203): data fetched, CSVs published, and all four deliverables rebuilt
and committed by CI, with `CONSISTENCY: PASS`._

**There is no setup left, and nothing you need to run.** All **19** Power Query connections
ship inside the workbook with refresh-on-open already ticked.

> ⚠️ **Ignore the `READ_ME_FIRST` tab.** It is left over from the original build and still
> walks you through adding queries by hand (`Get Data > From Web > …`). That work is done —
> all 19 are wired. Nothing on that tab needs doing. (Being fixed; see `pending-updates.md`.)

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

- **On the 2nd, 10th, 18th and 26th of every month** (07:23 UTC) GitHub Actions pulls fresh
  ENTSO-E data, republishes the chart CSVs, and **rebuilds all four deliverables**, committing
  them to `deliverables/` in the repo. Your workbook picks the data up on open.
  Four runs a month, on the same dates in every month, never more than 8 days apart. The run on
  the 2nd is the one that lands the just-closed month in the monthly exhibits; the rest keep the
  data fresh and mean a failed run is retried within 8 days rather than thirty. Every run
  re-pulls the whole year from ENTSO-E, so a stored file that has gone bad repairs itself
  without anyone acting. Nothing here needs a person.
- **At the turn of the year** the same run folds the completed year into the frozen history and
  rebuilds the charts so they carry the new year — on the repo's copy. Mechanically: the January
  run notices the frozen history still ends two years back, fetches the just-completed year as
  well as the current one, absorbs it via `build_hourly.py --absorb-prior-year`, and commits the
  extended history. It does not depend on the Mac's raw archive.

### The two halves: DATA refreshes itself, the FILE does not

This is the single thing worth understanding about how this works, because everything
else follows from it.

|  | Comes from | How you get it |
|---|---|---|
| **The numbers** | `published/` CSVs on GitHub | Automatically, on open. Never download anything. |
| **The workbook itself** — which technologies a chart plots, tab order, captions, the banner | The `.xlsx` file | Only by rebuilding the file. Not by refreshing. |

CI rebuilds **both** every run: it republishes the CSVs *and* builds a fresh
`HourlyPowerData.xlsx` / `.pptx` into `deliverables/`. Your copy on the share picks up
the first half by itself and **never** picks up the second.

Why: Power Query writes *values into cells*. A chart's category range, its series list
and its formatting live in the file's own XML. Refreshing cannot change them.

**Worked example (2026-07-30).** German nuclear was dropped from the Fig 5 capture chart
because the fleet closed in April 2023, leaving empty bars. That change moved the chart's
range from `$A$2:$A$12` to `$A$2:$A$11`. A workbook built before that change still reads
`$A$2:$A$12` after any number of refreshes — so it still draws the empty Nuclear bar. The
only way to get the fix is to take the rebuilt file.

**Rule of thumb:** if the numbers look wrong or old → refresh. If the *chart itself* is
wrong — an unwanted technology, a gap, a caption — → the file needs rebuilding. A missing
*year* is no longer on that list; see the next section.

> ⚠️ **Do not replace the share copy by downloading `deliverables/HourlyPowerData.xlsx`**
> if the deck is linked with **UpSlide**. UpSlide does not match its links by file path: it
> stamps a hidden marker into each chart, so dropping a freshly generated workbook in place
> orphans every link in the deck, whatever the new file is called or where it sits.
> `_tools/merge_into_linked.py` exists for exactly this — it ADDS a fresh build's new content
> to the linked workbook rather than replacing it. Before doing anything, ask whether a rebuild
> is even due:
> ```
> python _tools/merge_into_linked.py --dry-run --base <the share copy> --donor <a fresh build>
> ```
> It changes nothing and exits 1 if the template is genuinely behind, 0 if it is not.

### The year turn needs nothing from you (corrected 2026-09-06)

**This section used to say the opposite**, and until 2026-08-03 it was right. It told you that
once a year you MUST replace the workbook file, and to watch the Status tab for an
**ANNUAL ROLLOVER OVERDUE** banner. Both are now wrong, and the banner no longer exists:
`add_status_sheet.py` stopped raising it because "every one of the nineteen charts now advances
on an ordinary refresh, so there is no annual action to raise". Anyone following the old
instruction would have replaced a workbook that did not need replacing, which for the UpSlide
deck is the one action that breaks it (see below).

**Why it used to be true.** Each year was a separate **chart series**, and the number of series is
fixed when a workbook is built. Power Query loads data into cells; it cannot create a series. So a
2026-vintage file would have shown 2019 to 2025 for ever, however often it refreshed.

**What changed.** The charts were re-pointed at a **rolling window** instead of at fixed years.
Every chart now reads the same `w1..w7` columns for ever, the build fills them from the last seven
complete years, and each series takes its NAME from a Status-sheet cell, so the legend rolls with
the data. `roll_year_window.py` did the annual bar charts, `roll_line_windows.py` the seven line
charts and the two category charts, and `roll_single_year_charts.py` the last three, captions
included. The trade Fred accepted is that an exhibit is now "the last seven complete years", so
2019 drops off in 2027.

**So every January, do nothing.** The new complete year appears on an ordinary refresh-on-open,
with correct labels and no change in bar width.

**What still has a real deadline** is on the CI side, not yours: the January run must fold the
completed year into the frozen history, because CI only ever fetches the current year. It does
this by itself (`build_hourly.py --absorb-prior-year`). If it fails, the monthly-granularity
charts develop a visible 12-month hole and `ROLLOVER.md` is the recovery.

### For the team — who does what

Almost nobody needs to "update" anything. The three situations, in the order they come up:

| Situation | What to do | Who can |
|---|---|---|
| **Normal use** — you want current numbers | **Just open the workbook.** It pulls the latest published data on open. | Anyone |
| **You want data fresher than the last scheduled run** | Open the status page and press **Start a refresh**, then re-open the workbook. The page quotes how long the last run took. | Anyone with the link |
| **The chart itself is wrong** — an unwanted technology, a gap, a caption | Not a missing year: that fixes itself on refresh. Otherwise the file needs rebuilding, and if the deck is UpSlide-linked that means `merge_into_linked.py`, not a download. | Whoever holds the template |

**The status page is the one link to share:**
<https://power-price-data.fredhill.workers.dev>
It shows when the data was last refreshed, when the next automatic run is due, download
links for all four files, and the refresh button. No login, no GitHub account, nothing to
install — it works from a locked-down machine because it is just a web page. The link is
also in cell A6 of the workbook's `READ_ME_FIRST` tab.

**What the team does NOT need:** a GitHub account, Power Query knowledge, this Mac, or any
admin rights. Nobody should hand-edit the data tabs — they are Power Query load targets and
anything typed there is overwritten on the next refresh, and can shift columns and detach a
chart.

**The refresh button is rate-limited on purpose:** it refuses if a run is already going or
one finished in the last 30 minutes, so two people pressing it cannot start duplicate runs.

### Triggering a refresh yourself, without a terminal

You do **not** need the Mac, Claude Code, admin rights, or any local install. `workflow_dispatch`
is enabled, so the workflow has a **Run workflow** button in the browser:

> github.com/Power-Utilities-team/power-price-data → **Actions** → *Refresh ENTSO-E power-price data* →
> **Run workflow** → **Run workflow**

It takes ~20 minutes, then commits fresh CSVs and rebuilt deliverables. A browser and a GitHub
login with **write** access to the repo is the only requirement — the sandboxed Windows machine
can do this, since it is just a web page.

Note it cannot be triggered *from inside Excel*: Power Query only issues unauthenticated GETs,
while starting a run needs an authenticated POST. It is technically possible to POST from Power
Query with a personal access token in the query — **do not do this.** It would put a credential
with write access to the repo inside a workbook sitting on a shared drive.

The only reason to fetch a fresh copy from `deliverables/` is to make the *charts* show a newly
completed year — the data in your existing file is current either way. That is not optional once
a year has completed, though: see the annual-replacement section above.

## The Status tab — read this if something looks off

The workbook **opens on a `Status` sheet**. It compares the published refresh record against
today's date on your machine and says one of:

- ✅ *"OK - data is current. Last refreshed …, data through …"* — nothing to do.
- ⚠️ *"STALE DATA - the refresh has not run for N days"* — the GitHub job has stopped
  running. Someone needs to look at the Actions tab.
- ⚠️ *"ANNUAL ROLLOVER OVERDUE - charts were built for YYYY"* — download the latest files from
  `deliverables/`.

Both warnings are in large red text and cannot be missed. Green means genuinely fine.

**To answer "how fresh is this file?" — that green line is the answer, and it is always on
screen when you open the workbook.** It reads e.g. *"Last refreshed 2026-07-21, data through
2026-07-21 09:00"*: the first date is when the GitHub job last ran, the second is the last hour
of actual price data. Nothing else needs checking, and you do not need the repo to find out.

Two things the banner is deliberately not. It does not fire the instant a run is missed: the
tolerance is 10 days, set just above the 8-day maximum gap between runs, because GitHub queues
scheduled jobs on shared runners and starts them late (the one scheduled run we can measure was
2h02m behind). A tolerance equal to the cadence would cry wolf before every ordinary run. As set,
it stays silent when nothing is wrong and trips about two days after a genuinely missed run.

And it cannot tell you a run *failed* — a failed run simply does not update the record, so the day
count climbs until it trips. That is what the failure issue is for: any failed run opens (or
comments on) an issue in the repository's Issues tab that @-mentions the owner, with a link
straight to the run log. That is the faster and more specific signal; the banner is the backstop
for the case where no run happened at all.

## Two things not to do
- **Never click "Recover"** if Excel offers to repair the workbook. Repair strips Power Query,
  which is the one thing that would cost real work. Send the file to be fixed instead.
- **Don't hand-edit the data tabs.** They are Power Query load targets; anything typed there is
  overwritten on refresh, and pre-seeded cells can shift the columns and detach a chart.

## What needs no setup at all
`HourlyPowerData_frozen.xlsx` and `HourlyPowerData_snapshot.pptx` are fully self-contained —
open and use. They're rebuilt monthly alongside the live pair.

_System overview: `GENERATE.md`. Manual rollover fallback (only if CI is broken): `ROLLOVER.md`._

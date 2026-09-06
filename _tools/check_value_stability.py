#!/usr/bin/env python3
"""check_value_stability.py — a number for a CLOSED period may not quietly change.

WHAT THIS ASKS THAT NOTHING ELSE DOES. Every other guard here is structural. The Open XML
validator asks whether Excel will open the file. check_reference_stability asks whether a
column moved. check_coverage asks whether anything got shorter or blanker. check_consistency
asks whether the two decks agree. check_chart_captions asks whether a caption matches its own
data. All of them pass on a file that is the right shape and holds the wrong numbers.

That is not a hypothetical gap; it is the one this repository keeps falling into:

  * 2026-09-05  entsoe-py corrected its own typo, "Hydro Run-of-river and poundage" ->
                "pondage". config.TECH_MAP matched the old spelling exactly, so run-of-river
                silently vanished from every newly fetched month in all five ENTSO-E markets.
                capture_monthly fell from 92 populated months to 84 while every job reported
                success. Only check_coverage noticed, and only because those columns already
                had history to shrink against.
  * 2026-07-31  France and Italy lost January to June 2026 from capture_monthly entirely.
  * 2026-07-31  A cold cache published a 31-day "year" in place of 212 days, twice, fast and
                green, because a 31-day series is perfectly valid data.

WHY "CLOSED PERIODS" IS THE RIGHT UNIT. The current month and the current year move on every
run by design, so comparing them says nothing. A month that has ended should not move, and a
year that has ended should move less still. Anything that does move there is either an
upstream restatement (real, bounded, and the reason for the tolerances below) or a bug.

WHAT COUNTS AS SETTLED. A cell is compared only when the period it names had already closed
at the time of the baseline:

  * a COLUMN named for a year (DE_2024, DE_2019_M03, GB_2021_Q2) is settled when that year is
    over; within the current year, a column naming a month or quarter is settled once that
    month or quarter is over;
  * a ROW keyed by a year (fig1_price_sd) or a month (capture_monthly, figA_monthly_price) is
    settled on the same rule;
  * a cell needs one of the two to be settled and neither to be open;
  * rolling-window columns (_w1.._w7) are skipped outright. The window SHIFTS, so w3 names a
    different year after a rollover and comparing it position-to-position would fire on every
    January for a reason that is not a fault. The underlying year columns are checked anyway.

THE BASELINE IS GIT, exactly as in check_coverage: whatever the previous commit published IS
the claim being defended. That makes this work identically in CI and against a working tree.

AND "SETTLED" IS JUDGED AGAINST THE BASELINE'S COVERAGE, NOT THE CALENDAR. This was wrong in
the first version and the replay caught it. The 5 September publish appeared to move 123
settled values, all of them August 2026. August was over by the calendar, but the baseline's
data ended on 26 August, so its August figures were three quarters of a month and the new
ones were the whole of it. Nothing had moved: a partial month had finished. The as-of date
therefore comes from the BASELINE's own `status.csv` coverage_end, so a period only counts as
settled once the baseline actually covered all of it.

Exit 0 = every settled value held. Exit 1 = something moved that should not have.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLISHED = os.path.join(ROOT, "published")

# HOW FAR A SETTLED NUMBER MAY MOVE, and these are measured rather than chosen.
#
# Between the 2026-08-02 and 2026-09-05 publishes, over every period already closed on
# 2 August:
#
#   fig1_price_sd          0 values moved out of thousands
#   figA_monthly_price     1 value moved, by 0.006%
#   capture_monthly       46 values moved, 4 of them by more than 1%, the largest 3.5%
#
# The split is not arbitrary. A day-ahead price is an auction result: once the day is over
# it is a settled fact and ENTSO-E does not revise it. Anything generation-weighted is a
# different animal, because ENTSO-E restates generation for weeks afterwards and a capture
# price is a generation-weighted mean, so it moves whenever the weights do.
#
# So a price feed gets a tolerance tight enough that any real movement fires, and a
# generation-derived feed gets a band wide enough to sit above ordinary restatement and well
# below the size of a technology disappearing from the weighting.
PRICE_PCT = 0.5          # measured worst case 0.006%; two orders of magnitude of headroom
DERIVED_PCT = 8.0        # measured worst case 3.5%
ABS_FLOOR = 0.05         # ignore movement below this in absolute terms: rounding, not news

# Feeds whose values are prices or price statistics and nothing else. Everything not named
# here gets the wider band, which is the fail-SAFE direction: a new feed is never held to a
# tolerance it was not measured against, so adding one cannot turn the build red on its
# first run. The cost is that a new price-shaped feed is watched loosely until it is listed.
PRICE_FEEDS = {
    "fig1_price_sd", "fig1_price_sd_extra",
    "fig2_intraday_avg", "fig2_intraday_indexed", "fig2_intraday_indexed_extra",
    "fig3_neg_hours_annual", "fig3_neg_hours_annual_extra",
    "fig3_cum_near_neg", "fig3_cum_near_neg_extra",
    "fig4_duration_curve", "fig6_daily_minmax",
    "figA_monthly_price", "g2_price_by_month", "g2_price_by_quarter",
    "g3_price_july_daily",
}

# A settled cell that HELD A VALUE and is now empty is always a failure, whatever the
# tolerance. That is the shape the run-of-river rename made, one cell at a time, and it is
# the shape check_coverage can only see once enough cells go at once to clear its floor.
YEAR_RE = re.compile(r"_(\d{4})(?:_|$)")
MONTH_COL_RE = re.compile(r"_(\d{4})_M(\d{2})(?:_|$)")
QUARTER_COL_RE = re.compile(r"_(\d{4})_Q([1-4])(?:_|$)")
WINDOW_RE = re.compile(r"_w\d+$")
ROW_YEAR_RE = re.compile(r"^(\d{4})$")
ROW_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})(?:-\d{2})?$")


def git_show(ref: str, relpath: str) -> str | None:
    r = subprocess.run(["git", "show", f"{ref}:{relpath}"],
                       capture_output=True, text=True, cwd=ROOT)
    return r.stdout if r.returncode == 0 else None


def baseline_asof(ref: str) -> date | None:
    """The baseline's own coverage end, which is the only honest "as of" for this check.

    A period is settled for comparison when the BASELINE covered all of it, not when the
    calendar says it is over. Those differ by up to a whole slot gap, and the difference is
    exactly the size of the false positive the first version of this produced.
    """
    txt = git_show(ref, "published/charts/status.csv")
    if not txt:
        return None
    rows = list(csv.reader(io.StringIO(txt)))
    if len(rows) < 2 or "coverage_end" not in rows[0]:
        return None
    try:
        return date.fromisoformat(rows[1][rows[0].index("coverage_end")].strip()[:10])
    except Exception:
        return None


def _closed(y: int, m: int | None, today: date) -> bool:
    """Had the period (year y, optional month m) already ended before today?"""
    if m is None:
        return y < today.year
    return (y, m) < (today.year, today.month)


def column_period(name: str, today: date):
    """(settled, judged) for a column name.

    `judged` is False when the name carries no period at all, which is the ordinary case for
    a market column like `DE` — those cells are settled or not by their ROW instead.
    """
    if WINDOW_RE.search(name):
        return False, True                       # a rolling slot: never comparable by position
    m = MONTH_COL_RE.search(name)
    if m:
        return _closed(int(m.group(1)), int(m.group(2)), today), True
    q = QUARTER_COL_RE.search(name)
    if q:
        last_month_of_q = int(q.group(2)) * 3
        return _closed(int(q.group(1)), last_month_of_q, today), True
    y = YEAR_RE.search(name)
    if y:
        return _closed(int(y.group(1)), None, today), True
    return False, False


def row_period(key: str, today: date):
    """(settled, judged) for a row key: a bare year, or a month as YYYY-MM[-DD]."""
    key = (key or "").strip()
    m = ROW_MONTH_RE.match(key)
    if m:
        return _closed(int(m.group(1)), int(m.group(2)), today), True
    y = ROW_YEAR_RE.match(key)
    if y:
        return _closed(int(y.group(1)), None, today), True
    return False, False


def _num(v):
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def compare(before: str, now: str, tol_pct: float, today: date):
    """Every settled cell whose value moved beyond tolerance, or vanished."""
    rb = list(csv.reader(io.StringIO(before)))
    rn = list(csv.reader(io.StringIO(now)))
    if not rb or not rn:
        return []
    hb, hn = rb[0], rn[0]
    # Match by NAME, never by position. A column that moved sideways is check_reference_
    # stability's business; here it must not be read as a value change.
    idx_b = {c: i for i, c in enumerate(hb)}
    rows_b = {r[0]: r for r in rb[1:] if r}
    out = []
    for r in rn[1:]:
        if not r:
            continue
        key = r[0]
        prev = rows_b.get(key)
        if prev is None:
            continue                             # a new row has nothing to be compared with
        r_settled, r_judged = row_period(key, today)
        if r_judged and not r_settled:
            continue                             # the row's own period is still open
        for j, col in enumerate(hn):
            if j == 0 or col not in idx_b:
                continue
            c_settled, c_judged = column_period(col, today)
            if c_judged and not c_settled:
                continue
            if not (c_judged or r_judged):
                continue                         # nothing here names a period: cannot judge
            i = idx_b[col]
            b = prev[i].strip() if i < len(prev) else ""
            n = r[j].strip() if j < len(r) else ""
            if b == n:
                continue
            fb, fn = _num(b), _num(n)
            if fb is None:
                continue                         # was empty: gaining a value is never a fault
            if fn is None:
                out.append((key, col, b, "(empty)", "a settled value was removed"))
                continue
            delta = abs(fn - fb)
            if delta < ABS_FLOOR:
                continue
            pct = delta / max(abs(fb), 1e-9) * 100
            if pct > tol_pct:
                out.append((key, col, b, n, f"{pct:.2f}% > {tol_pct}%"))
    return out


def published_csvs(ref: str | None = None):
    if ref:
        r = subprocess.run(["git", "ls-tree", "--name-only", f"{ref}:published/charts"],
                           capture_output=True, text=True, cwd=ROOT)
        names = r.stdout.split() if r.returncode == 0 else []
        return sorted("published/charts/" + f for f in names if f.endswith(".csv"))
    d = os.path.join(PUBLISHED, "charts")
    if not os.path.isdir(d):
        return []
    return sorted("published/charts/" + f for f in os.listdir(d) if f.endswith(".csv"))


def check(ref: str, today: date, verbose: bool = True, now_ref: str | None = None):
    """`now_ref` replays a past transition instead of judging the working tree. That is how
    the tolerances above were set: run over every published transition in this repo's
    history, the guard must be silent on the ordinary ones and speak on the known-bad ones.
    A guard nobody has replayed is a guess."""
    bad = 0
    for rel in published_csvs(now_ref):
        stem = os.path.splitext(os.path.basename(rel))[0]
        before = git_show(ref, rel)
        if before is None:
            continue                             # a feed that did not exist in the baseline
        if now_ref:
            now = git_show(now_ref, rel)
            if now is None:
                continue
        else:
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                now = fh.read()
        tol = PRICE_PCT if stem in PRICE_FEEDS else DERIVED_PCT
        moved = compare(before, now, tol, today)
        if moved:
            bad += len(moved)
            if verbose:
                print(f"\n  {rel}  ({len(moved)} settled value(s) moved, tolerance {tol}%)")
                for key, col, b, n, why in moved[:12]:
                    print(f"    {key:<14} {col:<24} {b} -> {n}   ({why})")
                if len(moved) > 12:
                    print(f"    ... and {len(moved) - 12} more")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", default="HEAD",
                    help="git ref to compare against (CI uses origin/main)")
    ap.add_argument("--asof", default=None,
                    help="treat this YYYY-MM-DD as today, for replaying history")
    ap.add_argument("--now", default=None,
                    help="replay: judge this ref instead of the working tree")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    # Explicit --asof wins (that is what makes the history replay reproducible); otherwise
    # the baseline's own coverage end; only then the calendar, which is the weakest of the
    # three and is reached solely when a baseline predates status.csv.
    today = (date.fromisoformat(a.asof) if a.asof
             else baseline_asof(a.baseline) or date.today())
    print(f"value stability: settled periods only, as of {today} "
          f"(the baseline's coverage end), baseline {a.baseline}")
    bad = check(a.baseline, today, verbose=not a.quiet, now_ref=a.now)
    if bad:
        print(f"\nVALUE STABILITY: FAIL — {bad} value(s) changed on a period that had "
              f"already closed.\n"
              f"These are not supposed to move. The usual causes, in the order they occur:\n"
              f"  1. An upstream label was renamed or remapped, so a technology left the\n"
              f"     weighting. This is what run-of-river did on 2026-09-05.\n"
              f"  2. A unit, timezone or aggregation change in the build.\n"
              f"  3. A genuine ENTSO-E restatement larger than anything measured so far —\n"
              f"     possible, and the one case where widening a tolerance is the right fix.\n"
              f"Establish which before publishing. Do not widen a tolerance to make this pass.")
        return 1
    print("value stability: ok — every settled value held")
    return 0


if __name__ == "__main__":
    sys.exit(main())

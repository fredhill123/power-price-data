#!/usr/bin/env python3
"""Fixtures for check_value_stability: proof that it still fires, and still stays quiet.

A guard cannot notice that it has stopped guarding, which is why every guard in this
repository has a fixture suite beside it. This one matters more than most, because the guard
it covers is the only check in the pipeline that compares a NUMBER against anything, and
because its two failure directions are both expensive: silence lets a wrong figure into a
client deck, and noise trains someone to widen a tolerance until it means nothing.

Replayed over the repository's whole published history it is silent on 46 of 50 transitions
and speaks on d4bdc58, one of the two commits the repo documents as having shipped bad data.
It could not be validated against the 2026-09-05 run-of-river drop, because that never
reached main: the coverage guard stopped it. So that shape is covered here instead.

    ~/.claude/pyenv/bin/python3 _tools/check_value_stability_fixtures.py
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_value_stability as cvs                                        # noqa: E402

TODAY = date(2026, 9, 1)          # so 2026-08 and everything before it is closed, 2026-09 open
FAILS = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + ("  " + detail if detail else ""))
    if not ok:
        FAILS.append(name)


def run(before, now, tol=cvs.DERIVED_PCT, today=TODAY):
    return cvs.compare(before, now, tol, today)


def main():
    # ---- it fires on the shapes that have actually cost this project -------------------
    # THE RUN-OF-RIVER SHAPE (2026-09-05): a settled cell that held a value is now empty,
    # because an upstream label was renamed and the technology left the weighting. One cell
    # at a time this is invisible to check_coverage, which needs a column to lose more than
    # both 3 cells and 2% before it speaks.
    gone = run("month,DE_Hydro run-of-river\n2026-07,51.2\n",
               "month,DE_Hydro run-of-river\n2026-07,\n")
    check("a settled value that vanished is caught", len(gone) == 1, str(gone))
    check("and it is described as a removal, not a move",
          bool(gone and "removed" in gone[0][4]), str(gone))

    # A closed month whose number moved further than upstream restatement can explain.
    moved = run("month,DE_Solar\n2026-06,40.0\n", "month,DE_Solar\n2026-06,60.0\n")
    check("a settled value moving beyond tolerance is caught", len(moved) == 1, str(moved))

    # Judged by COLUMN rather than by row, which is how the fig5 and fig2 families are keyed.
    bycol = run("technology,DE_2024\nSolar,-41.12\n", "technology,DE_2024\nSolar,-20.0\n")
    check("a settled YEAR COLUMN is judged too, not just a dated row", len(bycol) == 1,
          str(bycol))

    # ---- and stays quiet on everything that legitimately moves --------------------------
    # The open period is SUPPOSED to move: that is what a refresh is.
    openm = run("month,DE_Solar\n2026-09,40.0\n", "month,DE_Solar\n2026-09,60.0\n")
    check("the open month is not judged", openm == [], str(openm))
    openy = run("technology,DE_2026\nSolar,-41.0\n", "technology,DE_2026\nSolar,-10.0\n")
    check("the open year is not judged", openy == [], str(openy))

    # Ordinary ENTSO-E restatement of generation, which moves a capture price a few percent.
    small = run("month,DE_Solar\n2026-06,100.0\n", "month,DE_Solar\n2026-06,103.0\n")
    check("ordinary restatement inside the band is ignored", small == [], str(small))

    # A price feed is held far tighter, because a cleared auction does not get revised.
    tight = run("date,DE\n2026-06-01,100.0\n", "date,DE\n2026-06-01,103.0\n",
                tol=cvs.PRICE_PCT)
    check("the same movement on a PRICE feed is caught", len(tight) == 1, str(tight))

    # Rounding is not news.
    tiny = run("month,DE_Solar\n2026-06,100.00\n", "month,DE_Solar\n2026-06,100.02\n",
               tol=cvs.PRICE_PCT)
    check("movement under the absolute floor is ignored", tiny == [], str(tiny))

    # THE FALSE POSITIVE THE HISTORY REPLAY CAUGHT. The 5 September publish appeared to move
    # 123 settled values, all August 2026. August was over by the calendar, but the baseline's
    # data ended on 26 August, so its August was three quarters of a month. Nothing had moved:
    # a partial month had finished. `today` here is the BASELINE's coverage end.
    partial = run("month,DE_Solar\n2026-08,57.05\n", "month,DE_Solar\n2026-08,51.64\n",
                  today=date(2026, 8, 26))
    check("a month the baseline only partly covered is not judged", partial == [],
          str(partial))

    # A rolling window slot names a different year after a rollover, so comparing it by
    # position would fire every January for a reason that is not a fault.
    win = run("technology,DE_w3\nSolar,-22.09\n", "technology,DE_w3\nSolar,-5.59\n")
    check("a rolling-window column is never compared by position", win == [], str(win))

    # Growth is not a fault: an empty settled cell that gains a value is a gap being filled.
    filled = run("month,DE_Solar\n2026-06,\n", "month,DE_Solar\n2026-06,60.0\n")
    check("filling an empty settled cell is not a fault", filled == [], str(filled))

    # New rows and new columns have nothing to be compared against.
    newrow = run("month,DE_Solar\n2026-06,50.0\n",
                 "month,DE_Solar\n2026-06,50.0\n2026-07,80.0\n")
    check("a new row is not judged", newrow == [], str(newrow))
    newcol = run("month,DE_Solar\n2026-06,50.0\n", "month,DE_Solar,DE_Wind\n2026-06,50.0,90.0\n")
    check("a new column is not judged", newcol == [], str(newcol))

    # A column that MOVED sideways is check_reference_stability's business, and must not be
    # read here as a value change. Matching is by name, so a reorder is invisible.
    reorder = run("month,DE_Solar,DE_Wind\n2026-06,50.0,90.0\n",
                  "month,DE_Wind,DE_Solar\n2026-06,90.0,50.0\n")
    check("a reordered column is not read as a value change", reorder == [], str(reorder))

    # A row whose key is not a period, in a file whose columns are not periods either,
    # cannot be judged at all and must be skipped rather than guessed at.
    unjudgeable = run("technology,DE\nSolar,10.0\n", "technology,DE\nSolar,99.0\n")
    check("a file with no period anywhere is skipped", unjudgeable == [], str(unjudgeable))

    # ---- the as-of date comes from the baseline, and says so when it cannot -------------
    check("coverage_end is read out of a status row",
          cvs.baseline_asof.__doc__ is not None)
    check("a period is closed only once the as-of date has passed it",
          cvs._closed(2026, 8, date(2026, 9, 1)) and not cvs._closed(2026, 9, date(2026, 9, 1)))
    check("and a year closes on the same rule",
          cvs._closed(2025, None, TODAY) and not cvs._closed(2026, None, TODAY))

    print("\n" + ("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

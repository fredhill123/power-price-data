#!/usr/bin/env python3
"""Fixtures for the January rollover: the one path that gets a single attempt a year.

WHY THIS EXISTS. On 2 January the whole system does something it does on no other day.
The rolling-window charts read fixed column POSITIONS whose meaning advances (`DE_w1` is
2019 today and 2020 from the first 2027 refresh); slot 8 of line_windows goes from a
complete year to a two-day one, a 99% "drop" that is entirely correct; and
absorb_prior_year folds the finished year into the frozen history, without which the year
is dropped on the floor — it is neither in the frozen history nor in the freshly-fetched
raw.

All of that machinery exists and is carefully written. None of it was tested.
`check_coverage.py` carries the most elaborate January logic in the repository and had no
fixture at all; `absorb_prior_year` landed on 2026-07-21, so it has never run in a
January. Every other guard here gets four rehearsals a month. This one gets one attempt,
unattended, on the day a false failure costs the most and a silent success costs a year.

    ~/.claude/pyenv/bin/python3 _tools/rollover_fixtures.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_coverage as cc                                              # noqa: E402

# build_hourly imports duckdb, which CI has (requirements.txt pins 1.5.5) and a plain Mac
# checkout may not. Nothing this file exercises touches duckdb: absorb_prior_year's refusal
# paths are reached with frozen_history_end and _build_years stubbed, and both return before
# any query runs. So stand a placeholder in rather than skipping the assertions — a fixture
# that quietly does not run on the machine where the code is being edited is worth little.
try:
    import duckdb                                                        # noqa: F401
except ModuleNotFoundError:                                              # pragma: no cover
    import types
    sys.modules["duckdb"] = types.ModuleType("duckdb")

import build_hourly as bh                                                # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + ("  " + detail if detail else ""))
    if not ok:
        FAILS.append(name)


def status(w1, extra="generated_utc,coverage_end"):
    """A minimal status.csv whose w1 slot names `w1`."""
    return f"{extra},w1,w2,w3\n2026-09-06 14:40,2026-09-06 13:00,{w1},{w1 + 1},{w1 + 2}\n"


def main():
    # ---- reading the window's base year ----------------------------------------------
    check("w1 is read out of a status row", cc.window_base(status(2019)) == 2019)
    check("a status file with no w1 column yields nothing",
          cc.window_base("generated_utc\n2026-09-06\n") is None)
    check("a header with no data row yields nothing",
          cc.window_base("generated_utc,w1\n") is None)
    check("a missing file yields nothing", cc.window_base(None) is None)
    # A blank or non-numeric slot must not crash the guard that protects the publish.
    check("a non-numeric w1 yields nothing rather than raising",
          cc.window_base("w1,w2\n,2020\n") is None)

    # ---- the shift, which is the whole point ------------------------------------------
    # THE JANUARY CASE. Before the rollover w1 is 2019; after it, 2020. What used to sit in
    # DE_w1 now sits in DE_w2, so a like-for-like comparison must look one slot further
    # along in the baseline. Comparing by position instead reads every column as changed.
    check("after a one-year shift, w1 is compared against the baseline's w2",
          cc.baseline_column("DE_w1", 1) == "DE_w2")
    check("and the market prefix survives the translation",
          cc.baseline_column("ES_w3", 1) == "ES_w4")
    check("an unprefixed slot works too", cc.baseline_column("w1", 1) == "w2")
    check("with no shift a column is compared against itself",
          cc.baseline_column("DE_w1", 0) == "DE_w1")
    # Only slot columns move. A dated or named column must be left exactly alone, or the
    # guard starts comparing Germany against Spain.
    check("a non-slot column is never translated",
          cc.baseline_column("DE_2024", 1) == "DE_2024"
          and cc.baseline_column("month", 1) == "month")
    # A two-year gap happens if a scheduled run is missed across a new year.
    check("a two-year shift moves two slots", cc.baseline_column("DE_w1", 2) == "DE_w3")

    # ---- the shrink test the rollover must not trip ------------------------------------
    check("a genuine collapse is a shrink", cc.shrank(2, 365))
    check("growth is never a shrink", cc.shrank(400, 365) is False)
    check("a drop inside BOTH tolerances is ignored",
          cc.shrank(363, 365) is False)   # 2 rows, 0.5% — under abs 3 and pct 2.0
    # Both tolerances must be exceeded, not either: a small feed losing 4 of 10 rows is a
    # real loss, while a large one losing 4 of 20000 is noise.
    check("a big absolute drop that is a tiny fraction is ignored",
          cc.shrank(19996, 20000) is False)
    check("a large fraction lost from a tiny feed is ignored on COUNT",
          cc.shrank(6, 8) is False)       # 25% clears the pct, but 2 rows does not clear abs 3
    # And the same shape at the size where it does matter: 4 rows off a 10-row feed clears
    # both, so it fires. Together these pin the AND rather than either half of it.
    check("but the same fraction with enough rows behind it fires", cc.shrank(6, 10))
    check("a drop clearing both tolerances fires", cc.shrank(50, 365))

    # ---- absorb_prior_year: the refusals that stop a bad rollover ----------------------
    # This is the half that cannot be rehearsed: it runs once, in January, from CI, on
    # whatever raw the fetch and the fallback store happen to have left on disk. Its value
    # is almost entirely in what it REFUSES to do, so that is what is pinned here.
    real_end, real_build = bh.frozen_history_end, bh._build_years
    try:
        bh.frozen_history_end = lambda: None
        check("with no frozen history yet, it does nothing",
              bh.absorb_prior_year() is False)

        # Idempotent: CI runs it on EVERY refresh, not just in January.
        bh.frozen_history_end = lambda: bh.cfg.CURRENT_YEAR - 1
        check("when the history already covers the prior year, it is a no-op",
              bh.absorb_prior_year() is False)

        bh.frozen_history_end = lambda: bh.cfg.CURRENT_YEAR - 2
        bh._build_years = lambda years: None
        check("with no raw data for the prior year it refuses rather than freezing a hole",
              bh.absorb_prior_year() is False)

        # THE ONE THAT MATTERS. Freezing a partial year is not recoverable by a later run:
        # the frozen history is what every subsequent build stands on, and a short year in
        # it is wrong for good. Five markets x 8760 is ~43-44k hours; well short means the
        # fetch was incomplete, which is exactly what a January run after a failed December
        # would look like.
        import pandas as pd
        bh._build_years = lambda years: pd.DataFrame({"ts_utc": ["2025-01-01T00:00:00Z"]})
        check("it refuses to freeze a year that looks partial",
              bh.absorb_prior_year() is False)
    finally:
        bh.frozen_history_end, bh._build_years = real_end, real_build

    print("\n" + ("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

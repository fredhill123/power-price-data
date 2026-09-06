#!/usr/bin/env python3
"""Fixtures for check_workbook_queries: proof it fires, and proof it stays quiet.

This guard is the only one in the pipeline that knows the workbook exists, so if it
silently stops guarding there is nothing behind it. Its quiet direction matters as much
as its loud one: the build legitimately produces 31 chart CSVs and the workbook queries
24, so a guard that complained about the other seven would be turned off within a week.

    ~/.claude/pyenv/bin/python3 _tools/check_workbook_queries_fixtures.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_workbook_queries as cwq                                      # noqa: E402

FAILS = []
GOOD = "year,DE\n2024,41.2\n"


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + ("  " + detail if detail else ""))
    if not ok:
        FAILS.append(name)


def man(files=("a.csv", "b.csv"), **kw):
    m = {"files": list(files), "base_urls": [cwq.EXPECT_IN_URL.join(
        ("https://raw.githubusercontent.com", ""))], "refresh_on_load": ["1"],
        "extracted": "2026-09-06"}
    m.update(kw)
    return m


def run(contents, built=None, **kw):
    """contents: {filename: text or None} on the SERVED surface. None = do not create.

    built: which of those the build actually produced this run. Defaults to all of them,
    which is the healthy case. Pass a shorter list to model a stale leftover.
    """
    d = tempfile.mkdtemp()
    b = tempfile.mkdtemp()
    try:
        for n, text in contents.items():
            if text is None:
                continue
            open(os.path.join(d, n), "w", encoding="utf-8").write(text)
            if built is None or n in built:
                open(os.path.join(b, n), "w", encoding="utf-8").write(text)
        return cwq.check(charts_dir=d, manifest=man(**kw), build_dir=b)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(b, ignore_errors=True)


def main():
    # ---- stays quiet when the contract holds ------------------------------------------
    ok = run({"a.csv": GOOD, "b.csv": GOOD})
    check("a build that serves every queried file is silent", ok == [], str(ok))

    # THE FALSE POSITIVE THAT WOULD KILL THIS GUARD. The build makes 31 chart CSVs; the
    # workbook queries 24. The seven it does not query are not faults.
    extra = run({"a.csv": GOOD, "b.csv": GOOD, "not_queried.csv": GOOD})
    check("files the workbook does not query are ignored", extra == [], str(extra))

    # Excel writes a UTF-8 BOM. Reading it as plain utf-8 makes the first header cell
    # "﻿year", which still has content — but the reader must not trip on it.
    bom = run({"a.csv": "﻿" + GOOD, "b.csv": GOOD})
    check("a BOM on the header is not read as a fault", bom == [], str(bom))

    # ---- fires on every shape that breaks the live workbook ----------------------------
    gone = run({"a.csv": GOOD, "b.csv": None})
    check("a queried file that vanished is caught", len(gone) == 1 and "MISSING" in gone[0][1],
          str(gone))

    empty = run({"a.csv": GOOD, "b.csv": ""})
    check("an empty queried file is caught", len(empty) == 1, str(empty))

    hdr_only = run({"a.csv": GOOD, "b.csv": "year,DE\n"})
    check("a header with no data rows is caught", len(hdr_only) == 1, str(hdr_only))

    blank = run({"a.csv": GOOD, "b.csv": ",,\n1,2,3\n"})
    check("a header row of blanks is caught", len(blank) == 1, str(blank))

    # A repo or branch rename breaks every copy of the workbook at once, and no amount of
    # correct data in this repository helps. Cheap to assert, catastrophic to miss.
    moved = run({"a.csv": GOOD, "b.csv": GOOD},
                base_urls=["https://raw.githubusercontent.com/someone/else/main/x/"])
    check("a workbook pointed at another repo is caught", len(moved) == 1, str(moved))

    # If refresh-on-open is ever off, the workbook shows whatever Excel last saved and
    # every other guard in this pipeline is beside the point.
    noload = run({"a.csv": GOOD, "b.csv": GOOD}, refresh_on_load=["0"])
    check("a workbook that no longer refreshes on open is caught", len(noload) == 1,
          str(noload))

    # THE HOLE THIS GUARD SHIPPED WITH, for about twenty minutes on 2026-09-06. The build
    # job starts with actions/checkout, so published/charts arrives already holding the
    # PREVIOUS run's files and the publish step copies over them rather than replacing the
    # directory. A feed that quietly stopped being generated leaves last week's file in
    # place: present, populated, and completely stale. Checking the served surface alone
    # passes it, and the stale copy gets committed again — the very failure this guard
    # exists to catch, wearing the previous run's clothes.
    stale = run({"a.csv": GOOD, "b.csv": GOOD}, built=["a.csv"])
    check("a file this build did NOT produce is caught, however healthy it looks",
          len(stale) == 1 and "STALE" in stale[0][1], str(stale))

    # Several at once must all be reported, not just the first: a person fixing this wants
    # the whole list, not one round trip per file.
    both = run({"a.csv": None, "b.csv": ""})
    check("every breakage is reported, not just the first", len(both) == 2, str(both))

    print("\n" + ("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

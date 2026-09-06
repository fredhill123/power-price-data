#!/usr/bin/env python3
"""Refuse a publish that would break the workbook people actually open.

THE LAST MILE, AND WHY NOTHING WATCHED IT UNTIL NOW. Every other guard in this pipeline
stops at the git commit: check_coverage asks whether the data got shorter,
check_reference_stability whether a column moved, check_value_stability whether a settled
number changed. None of them knows that a workbook on a share drive fetches 24 specific
CSVs from raw.githubusercontent.com every time somebody opens it. Rename or drop one of
those and every guard here stays green, while the reader gets a Power Query error on a
Monday morning — or worse, keeps the values Excel last saved, with nothing saying they
are stale.

WHAT IT CHECKS. Every file the workbook queries exists in published/charts, is non-empty,
has a header and at least one data row. It runs against published/charts rather than
outputs/csv/charts because that directory IS the surface the URLs serve; status.csv in
particular is written straight there by build_status.py.

WHERE THE LIST COMES FROM. workbook_queries.json, extracted from the workbook itself by
extract_workbook_queries.py — never typed by hand. EXCEL_SETUP.md described 18 files
where the workbook queries 24, so a list transcribed from the prose would have carried a
25% blind spot, silently, in the one check whose entire job is to notice.

    python check_workbook_queries.py            # against published/charts
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MANIFEST = os.path.join(HERE, "workbook_queries.json")
CHARTS = os.path.join(ROOT, "published", "charts")

# The repo and branch the workbook's URLs are pinned to. If either is ever renamed, every
# query in every copy of the workbook breaks at once and no amount of correct data helps.
EXPECT_IN_URL = "/Power-Utilities-team/power-price-data/main/published/charts/"


def load_manifest():
    if not os.path.exists(MANIFEST):
        raise SystemExit("workbook queries: no workbook_queries.json — run "
                         "extract_workbook_queries.py against the linked workbook")
    return json.load(open(MANIFEST))


def check(charts_dir=CHARTS, manifest=None):
    """Returns a list of (file, problem). Empty means every query would still resolve."""
    man = manifest or load_manifest()
    bad = []

    for base in man.get("base_urls", []):
        if EXPECT_IN_URL not in base:
            bad.append((base, "the workbook points somewhere this repo does not publish"))

    # refreshOnLoad is what makes this workbook self-updating for a non-technical reader.
    # Recorded at extraction time; if it was ever off, say so here rather than in a file
    # nobody opens.
    if man.get("refresh_on_load") not in (["1"], None):
        bad.append((man.get("source_workbook", "workbook"),
                    f"refreshOnLoad is {man['refresh_on_load']}, so it does not refresh on open"))

    for name in man["files"]:
        p = os.path.join(charts_dir, name)
        if not os.path.exists(p):
            bad.append((name, "MISSING — the workbook's query for it will 404"))
            continue
        if os.path.getsize(p) == 0:
            bad.append((name, "empty file"))
            continue
        with open(p, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
        if not rows or not any(c.strip() for c in rows[0]):
            bad.append((name, "no header row"))
        elif len(rows) < 2:
            bad.append((name, "header but no data rows"))
    return bad


def main():
    man = load_manifest()
    bad = check(manifest=man)
    n = len(man["files"])
    if not bad:
        print(f"workbook queries: ok — all {n} files the workbook fetches are present "
              f"and populated (manifest extracted {man.get('extracted','?')})")
        return 0
    print(f"workbook queries: {len(bad)} of {n} would break the live workbook")
    for name, why in bad:
        print(f"  FAIL  {name}: {why}")
    print("\nThe workbook on the share drive refreshes on open from these URLs. Publishing "
          "this build gives whoever opens it a query error, or silently stale numbers.\n"
          "If a rename was deliberate, re-point the workbook's query, re-export it, re-run "
          "extract_workbook_queries.py and commit the new manifest in the same change.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

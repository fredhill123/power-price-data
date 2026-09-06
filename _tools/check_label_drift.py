#!/usr/bin/env python3
"""check_label_drift.py — fail the run when entsoe-py renames a label config.py maps.

WHY THIS EXISTS. On 2026-09-05 entsoe-py 0.8.1 corrected its own typo, "Hydro Run-of-river
and poundage" -> "pondage" (their issue #540). config.TECH_MAP matched the misspelling by
exact string, so the correction silently dropped run-of-river from every newly fetched month:
capture_monthly.csv fell from 92 populated months to 84 across all five ENTSO-E markets while
every job reported success. Only the publish-time coverage guard caught it, and only because
those columns already had history to shrink against. A BRAND NEW column, or a rename in the
first month of a series, would have published silently.

So this runs BEFORE the fetch: a rename is a loud failure in the first minute rather than a
quiet hole discovered at publish, or not at all.

WHAT IT DOES NOT DO. It does not check that a label still returns DATA, only that the string
config.py maps still exists upstream. A technology ENTSO-E stops publishing is a coverage
question, which the publish guard already owns.
"""

import sys


# Deliberately retained keys that are NOT expected upstream, each with its reason. A key here
# is exempt from the drift check; anything else missing upstream fails the run.
ALLOWED_ABSENT = {
    "Hydro Run-of-river and poundage":
        "the pre-0.8.1 spelling, kept because fetch_uk.py emits it for GB and the stored "
        "history was fetched under it (see requirements.txt and _tools/config.py)",
}


def upstream_labels() -> set:
    """Every PSR-type label entsoe-py can produce, read from the installed package."""
    from entsoe import mappings
    out = set()
    for name in dir(mappings):
        if name.startswith("_"):
            continue
        obj = getattr(mappings, name)
        if isinstance(obj, dict):
            for k, v in obj.items():
                for candidate in (k, v):
                    if isinstance(candidate, str):
                        out.add(candidate)
    return out


def main() -> int:
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    import config

    labels = upstream_labels()
    if not labels:
        # Reading nothing is not the same as finding nothing wrong. Fail loudly: a silent
        # pass here would recreate exactly the blind spot this script exists to remove.
        print("LABEL DRIFT: could not read any labels from entsoe.mappings — "
              "the package layout changed. Check this script against the installed version.")
        return 1

    missing = [k for k in config.TECH_MAP if k not in labels and k not in ALLOWED_ABSENT]
    exempt = [k for k in config.TECH_MAP if k in ALLOWED_ABSENT]

    print(f"label drift: {len(config.TECH_MAP)} TECH_MAP keys checked against "
          f"{len(labels)} labels in the installed entsoe-py")
    for k in exempt:
        print(f"  allowed absent: {k!r} — {ALLOWED_ABSENT[k]}")

    if missing:
        print(f"\nLABEL DRIFT: FAIL — {len(missing)} key(s) no longer exist upstream:")
        for k in missing:
            print(f"  ✗ {k!r} -> would have silently dropped '{config.TECH_MAP[k]}'")
        print("\nentsoe-py has renamed these, so every series behind them would be dropped "
              "from newly fetched data while older stored months kept it, and every job "
              "would still report success. Add the NEW spelling to TECH_MAP alongside the "
              "old one (keep the old: stored history and fetch_uk.py rely on it). Do not "
              "delete this check to make the run pass.")
        return 1

    print("label drift: ok — every mapped label still exists upstream")
    return 0


if __name__ == "__main__":
    sys.exit(main())

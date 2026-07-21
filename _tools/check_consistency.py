"""
check_consistency.py — fail-loud guard that the LINKED deck and the STATIC deck
never drift from deck_spec.py (or each other). Run before every delivery.

Asserts, for BOTH decks:
  * slide count == 1 (title) + len(deck_spec.SLIDES)
  * each content slide's title + kicker == deck_spec
  * each content slide's navy-bar captions (in order) == deck_spec exhibit captions
And that the linked workbook holds charts 1..19.

Exit 0 = consistent; exit 1 = drift (prints the diffs).
"""
from __future__ import annotations
import os, sys, zipfile, re
from pptx import Presentation
import deck_spec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINKED = os.path.join(ROOT, "outputs", "HourlyPowerData.pptx")
STATIC = os.path.join(ROOT, "outputs", "HourlyPowerData_snapshot.pptx")
WORKBOOK = os.path.join(ROOT, "outputs", "HourlyPowerData.xlsx")


def deck_content(path):
    """Return [(title, kicker, [captions...]), ...] for content slides (skip title)."""
    prs = Presentation(path)
    out = []
    for s in list(prs.slides)[1:]:
        title = kicker = ""
        caps = []
        for ph in s.placeholders:
            idx = ph.placeholder_format.idx
            if idx == 0: title = ph.text.strip()
            elif idx == 13: kicker = ph.text.strip()
        for sh in s.shapes:
            if not sh.is_placeholder and sh.has_text_frame and sh.text_frame.text.strip():
                caps.append(sh.text_frame.text.strip())
        out.append((title, kicker, caps))
    return out


def expected():
    return [(s["title"], s["kicker"], [e["caption"] for e in s["exhibits"]]) for s in deck_spec.SLIDES]


def check_deck(name, path, exp):
    errs = []
    if not os.path.exists(path):
        return [f"{name}: file missing ({path})"]
    got = deck_content(path)
    if len(got) != len(exp):
        errs.append(f"{name}: {len(got)} content slides, expected {len(exp)}")
    for i, (e, g) in enumerate(zip(exp, got), start=1):
        if e[0] != g[0]:
            errs.append(f"{name} slide {i} title: got {g[0]!r} != spec {e[0]!r}")
        if e[1] != g[1]:
            errs.append(f"{name} slide {i} kicker: got {g[1]!r} != spec {e[1]!r}")
        if e[2] != g[2]:
            errs.append(f"{name} slide {i} captions: got {g[2]} != spec {e[2]}")
    return errs


def main():
    exp = expected()
    errs = []
    errs += check_deck("LINKED", LINKED, exp)
    errs += check_deck("STATIC", STATIC, exp)
    # workbook holds charts 1..15
    if os.path.exists(WORKBOOK):
        z = zipfile.ZipFile(WORKBOOK)
        nums = sorted(int(re.search(r"chart(\d+)", n).group(1))
                      for n in z.namelist() if re.match(r"xl/charts/chart\d+\.xml$", n))
        if nums != list(range(1, 20)):
            errs.append(f"WORKBOOK charts: {nums} != 1..19")
    else:
        errs.append(f"WORKBOOK missing ({WORKBOOK})")

    if errs:
        print("CONSISTENCY: FAIL")
        for e in errs: print("  ✗", e)
        sys.exit(1)
    print(f"CONSISTENCY: PASS — both decks match deck_spec ({len(exp)} content slides, "
          f"{sum(len(s['exhibits']) for s in deck_spec.SLIDES)} exhibits) + workbook charts 1-19.")


if __name__ == "__main__":
    main()

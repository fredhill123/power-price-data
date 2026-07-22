"""
resync_prefill.py — make every Power Query tab's PRE-FILLED data match the CSV it
will load, so the table never changes shape when Excel refreshes it.

WHY THIS EXISTS (a real bug this fixes, found 2026-07-22)
--------------------------------------------------------
Each query tab ships with a cached copy of its CSV so the charts render before the
first refresh. The 12 original tabs inherit that cache from the frozen base workbook
(archive/phase4_2026-07-17/), which was built when fig5_capture_pct.csv had 17 rows.
Curating the technology sets grew it to 24. Nothing in the pipeline resynced the
cache, so the workbook shipped with 18 rows of data and a table declared A1:CH18.

On the first refresh in Excel the table grew 18 -> 25 rows. Excel RE-ANCHORS any
chart series whose range runs to or past the old end of the data: chart12 (Portugal
capture price) was $A$13:$A$19, past row 18, so Excel stretched it to $A$13:$A$26 —
silently putting the six uncurated leftover technologies back into the chart that
curate_tech_charts.py had just taken them out of.

Charts whose ranges sit strictly INSIDE the cached data (chart6 at rows 2-12) were
untouched. That is the whole mechanism: a range at the edge of a stale cache moves.

The fix is to ship a cache that is already the right shape. check_consistency.py
then enforces both halves of the invariant on every build:
    prefill extent == CSV extent, and no chart range past the prefill extent.

WHAT IT TOUCHES
    ~ xl/worksheets/sheetN.xml   <dimension> + <sheetData> (data rows only)
    ~ xl/tables/tableN.xml       ref + autoFilter ref
    ~ xl/workbook.xml            the sheet's ExternalData_1 range
Connections, queryTables, the M queries and tableColumns are NOT touched — the 12
original queries are Fred's own wiring and must survive byte-for-byte.

Usage: python resync_prefill.py [workbook.xlsx]   (defaults to outputs/HourlyPowerData.xlsx)
"""
from __future__ import annotations
import os, re, sys, zipfile

from add_power_queries import load_csv, sheet_data_xml, col_letter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "outputs", "HourlyPowerData.xlsx")
PUB = os.path.join(ROOT, "published", "charts")


def sheet_index(wb_xml):
    """name -> (rId, 0-based document order) — localSheetId is this index."""
    hits = re.findall(r'<sheet name="([^"]+)"[^>]*?r:id="(rId\d+)"', wb_xml)
    return {nm: (rid, i) for i, (nm, rid) in enumerate(hits)}


def table_of(parts, sheet_part):
    """the table part backing a query tab, via the sheet's rels (None if not a query tab)."""
    rels_path = sheet_part.replace("worksheets/", "worksheets/_rels/") + ".rels"
    if rels_path not in parts:
        return None
    m = re.search(r'Target="\.\./tables/(table\d+\.xml)"', parts[rels_path].decode())
    return "xl/tables/" + m.group(1) if m else None


def replace_data_rows(sheet_xml, new_sheet_data):
    """Swap the data rows, keeping any hand-authored rows (the Status banner) intact.

    Data rows are rows 1..N of the incoming block; anything the sheet already has at a
    HIGHER row number (Status rows 4-10) is preserved and re-appended in order.
    """
    body = new_sheet_data[len("<sheetData>"):-len("</sheetData>")]
    keep_from = max((int(r) for r in re.findall(r'<row r="(\d+)"', body)), default=0)
    existing = re.search(r"<sheetData>(.*?)</sheetData>", sheet_xml, re.S)
    kept = ""
    if existing:
        for m in re.finditer(r'<row r="(\d+)".*?</row>', existing.group(1), re.S):
            if int(m.group(1)) > keep_from:
                kept += m.group(0)
    return re.sub(r"<sheetData\s*/>|<sheetData>.*?</sheetData>",
                  lambda _: f"<sheetData>{body}{kept}</sheetData>", sheet_xml, count=1, flags=re.S)


def main():
    zin = zipfile.ZipFile(WB)
    order = zin.namelist()
    parts = {n: zin.read(n) for n in order}
    zin.close()

    wb_xml = parts["xl/workbook.xml"].decode()
    relmap = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"',
                             parts["xl/_rels/workbook.xml.rels"].decode()))
    idx = sheet_index(wb_xml)

    changed = []
    for name, (rid, doc_i) in idx.items():
        spart = "xl/" + relmap[rid].lstrip("/")
        tpart = table_of(parts, spart)
        if not tpart or tpart not in parts:
            continue
        tbl = parts[tpart].decode()
        stem = re.search(r'\sname="([^"]+)"', tbl).group(1)
        if not os.path.exists(os.path.join(PUB, stem + ".csv")):
            print(f"  {name:20s} no CSV for '{stem}' — skipped")
            continue

        header, body, kinds = load_csv(stem)
        want = f"A1:{col_letter(len(header))}{len(body) + 1}"
        have = re.search(r'<table[^>]*\sref="([^"]+)"', tbl).group(1)
        if have == want:
            continue

        # a column-count change would invalidate tableColumns/queryTableFields, which this
        # script deliberately does not rewrite. Fail rather than ship a broken table.
        cols_have = int(re.search(r'<tableColumns count="(\d+)"', tbl).group(1))
        if cols_have != len(header):
            raise SystemExit(
                f"!! {name}: CSV '{stem}' now has {len(header)} columns but the table declares "
                f"{cols_have}. Column changes need the table rebuilt (add_power_queries.py), "
                f"not a prefill resync. Refusing to guess.")

        parts[spart] = replace_data_rows(
            re.sub(r'<dimension ref="[^"]*"/>', f'<dimension ref="{want}"/>',
                   parts[spart].decode()),
            sheet_data_xml(header, body, kinds)).encode()

        tbl = re.sub(r'(<table[^>]*\sref=")[^"]+(")', rf'\g<1>{want}\g<2>', tbl, count=1)
        tbl = re.sub(r'(<autoFilter ref=")[^"]+(")', rf'\g<1>{want}\g<2>', tbl, count=1)
        parts[tpart] = tbl.encode()

        # the hidden ExternalData_1 range for THIS sheet (scoped by 0-based doc order)
        wb_xml = re.sub(
            rf'(<definedName name="ExternalData_1" localSheetId="{doc_i}"[^>]*>)[^<]*(</definedName>)',
            rf'\g<1>{name}!${"A"}$1:${col_letter(len(header))}${len(body) + 1}\g<2>', wb_xml)

        changed.append((name, stem, have, want))
        print(f"  {name:20s} {stem:24s} {have:12s} -> {want}")

    parts["xl/workbook.xml"] = wb_xml.encode()

    if not changed:
        print("prefill already matches every CSV — nothing to do")
        return

    tmp = WB + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for n in order:
            zo.writestr(n, parts[n])
    os.replace(tmp, WB)
    print(f"resynced {len(changed)} tab(s) — the tables no longer change shape on refresh")


if __name__ == "__main__":
    print("resyncing pre-filled query data ->", os.path.basename(WB), flush=True)
    main()

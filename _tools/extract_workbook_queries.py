#!/usr/bin/env python3
"""Read the live-linked workbook and write down every URL it actually fetches.

WHY THIS EXISTS. The workbook on the share drive refreshes itself on open from
raw.githubusercontent.com, so the set of chart CSVs it queries IS the contract this
pipeline has to keep. Until 2026-09-06 that contract was written down only in prose, in
EXCEL_SETUP.md, and the prose was wrong: it listed 18 files where the workbook queries
24. The six it missed were capture_monthly_extra, fig5_capture_window,
fig9_capacity_window, hydro_window, line_windows and status — the last of which feeds the
staleness banner. A check built from that list would have waved through a build that
dropped any of the six, and anyone rebuilding the workbook by following the document
would have produced one missing six charts.

So the list is EXTRACTED, not typed. Run this whenever the workbook's queries change:

    python extract_workbook_queries.py "/path/to/linked-template.xlsx"

and commit the resulting workbook_queries.json. The workbook itself is not in this
repository (it lives in Fred's private work tree, and it is a 2.6MB binary that git
cannot merge), which is exactly why the extracted manifest is.

READ-ONLY, deliberately. It opens the .xlsx as a zip and never writes it back. Round-
tripping a real workbook through a library drops charts, queries and metadata, and Excel
then refuses the file.
"""
import base64
import io
import json
import os
import re
import sys
import zipfile
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "workbook_queries.json")


def queries_in(xlsx_path):
    """Every https URL in the workbook's Power Query (M) code, plus its refresh settings.

    Power Query lives in customXml/item1.xml as a `DataMashup` element: UTF-16 XML whose
    text is base64 of a small header followed by a zip, inside which one .m file holds the
    query source. There is no supported API for this, so it is parsed structurally.
    """
    with zipfile.ZipFile(xlsx_path) as z:
        names = z.namelist()
        # The part is UTF-16, so "DataMashup" is not present as ASCII bytes — decode
        # before looking. Testing the raw bytes silently finds nothing.
        item = None
        for n in names:
            if not re.fullmatch(r"customXml/item\d+\.xml", n):
                continue
            head = z.read(n)[:4096]
            enc = "utf-16" if head[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
            if "DataMashup" in head.decode(enc, "replace"):
                item = n
                break
        if item is None:
            raise SystemExit(f"{xlsx_path} carries no Power Query (no DataMashup part). "
                             "This is not the live-linked workbook.")
        raw = z.read(item)
        txt = raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff")
                         else "utf-8", "replace")
        conns = z.read("xl/connections.xml").decode("utf-8") if \
            "xl/connections.xml" in names else ""

    blob = base64.b64decode(re.search(r">([A-Za-z0-9+/=]{500,})<", txt).group(1))
    # 4-byte version, 4-byte length, then the package zip.
    pkg = zipfile.ZipFile(io.BytesIO(blob[8:8 + int.from_bytes(blob[4:8], "little")]))
    src = pkg.read(next(n for n in pkg.namelist()
                        if n.lower().endswith(".m"))).decode("utf-8", "replace")

    urls = sorted(set(re.findall(r'https?://[^\s"\)]+', src)))
    # refreshOnLoad is the whole reason a non-technical reader can just open the file.
    # If it is ever off, the workbook silently shows whatever it last saved.
    on_load = sorted(set(re.findall(r'refreshOnLoad="([^"]*)"', conns)))
    return urls, on_load, len(re.findall(r"<connection\b", conns))


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__.strip().split("\n\n")[-2].strip())
    wb = sys.argv[1]
    urls, on_load, n_conn = queries_in(wb)
    files = sorted({u.rsplit("/", 1)[1] for u in urls})
    bases = sorted({u.rsplit("/", 1)[0] + "/" for u in urls})

    if on_load != ["1"]:
        print(f"!! refreshOnLoad is {on_load or 'unset'}, not ['1'] — this workbook does "
              "NOT refresh on open, so a reader sees whatever it last saved.")

    out = {
        "_comment": "EXTRACTED from the live-linked workbook by extract_workbook_queries.py."
                    " Do not hand-edit: re-run the extractor instead.",
        "source_workbook": os.path.basename(wb),
        "extracted": date.today().isoformat(),
        "base_urls": bases,
        "refresh_on_load": on_load,
        "connections": n_conn,
        "files": files,
    }
    json.dump(out, open(MANIFEST, "w"), indent=1)
    open(MANIFEST, "a").write("\n")
    print(f"{len(files)} queried files from {n_conn} connections "
          f"(refreshOnLoad={on_load}) -> {os.path.relpath(MANIFEST, HERE)}")
    for f in files:
        print("   ", f)


if __name__ == "__main__":
    main()

"""
move_charts.py — move all 9 charts onto a single new 'Charts' worksheet placed
as the LEFTMOST tab, each with a navy caption above it, and remove the charts
from the individual Fig sheets. Pure zip/XML surgery: Power Query, tables,
queryTables, sharedStrings and the (already-restyled) chart parts are copied
byte-for-byte. Only the container wiring changes.

What changes:
  + add  xl/worksheets/sheet14.xml            (Charts, with rich-text captions)
  + add  xl/worksheets/_rels/sheet14.xml.rels (-> drawing10)
  + add  xl/drawings/drawing10.xml            (9 graphicFrames -> chart1..9)
  + add  xl/drawings/_rels/drawing10.xml.rels (-> chart1..9)
  ~ edit xl/workbook.xml            (Charts as first <sheet>, activeTab=0)
  ~ edit xl/_rels/workbook.xml.rels (rId20 -> sheet14)
  ~ edit [Content_Types].xml        (add sheet14+drawing10; drop drawing1..9)
  ~ edit docProps/app.xml           (13 -> 14 sheets, prepend 'Charts')
  ~ edit xl/worksheets/sheet2..10.xml       (remove <drawing>)
  ~ edit xl/worksheets/_rels/sheet*.xml.rels(remove the drawing relationship)
  - drop xl/drawings/drawing1..9.xml (+ their _rels)

Usage: python move_charts.py "<in.xlsx>" "<out.xlsx>"
"""
from __future__ import annotations
import sys, re, zipfile

# chart -> caption (Fig sheet chart order = chart1..chart9)
CAPTIONS = [
    "Fig 1 — Price volatility: annual standard deviation of hourly day-ahead price (€/MWh)",
    "Fig 2 — Intraday price shape by year, indexed to daily mean = 1 (Germany)",
    "Fig 3 — Negative-price hours per year, by country",
    "Fig 3 — Cumulative near-negative-price hours through the year (Germany)",
    "Fig 4 — Price duration curves by year (Portugal)",
    "Fig 5 — Capture price vs baseload by technology (Germany)",
    "Fig 6 — Daily minimum vs maximum price (Germany, 2024)",
    "Fig 7 — Intraday generation mix and price (Portugal, 2024)",
    "Fig 9 — Installed generation capacity by technology (Germany)",
]
NAVY = "2E3E80"
EXT_CX, EXT_CY = 6120000, 3240000     # same size as the original charts
COL_L, COL_R = 0, 11                  # two-column grid
BLOCK_ROWS = 20                       # vertical spacing between chart blocks

def col_letter(n):
    s=""
    n+=1
    while n>0:
        n,r=divmod(n-1,26); s=chr(65+r)+s
    return s

def caption_cell(ref, text):
    t=(text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))
    return (f'<c r="{ref}" t="inlineStr"><is><r>'
            f'<rPr><b/><sz val="12"/><color rgb="FF{NAVY}"/><rFont val="Arial"/></rPr>'
            f'<t xml:space="preserve">{t}</t></r></is></c>')

def build_sheet14():
    # captions grouped by row: charts 2k,2k+1 share row (block k)
    rows={}
    for k in range(9):
        block=k//2; side=k%2
        row1=block*BLOCK_ROWS+1
        col=COL_L if side==0 else COL_R
        rows.setdefault(row1,[]).append(caption_cell(f"{col_letter(col)}{row1}", CAPTIONS[k]))
    sheetData="".join(
        f'<row r="{r}">' + "".join(cells) + "</row>"
        for r,cells in sorted(rows.items())
    )
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<dimension ref="A1"/>'
            '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
            '<sheetFormatPr defaultRowHeight="15"/>'
            f'<sheetData>{sheetData}</sheetData>'
            '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>'
            '<drawing r:id="rId1"/></worksheet>')

def build_drawing10():
    XDR="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
    A="http://schemas.openxmlformats.org/drawingml/2006/main"
    C="http://schemas.openxmlformats.org/drawingml/2006/chart"
    R="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    frames=[]
    for k in range(9):
        block=k//2; side=k%2
        col=COL_L if side==0 else COL_R
        row0=block*BLOCK_ROWS+1          # 0-indexed drawing row (1 below caption)
        frames.append(
            '<xdr:oneCellAnchor>'
            f'<xdr:from><xdr:col>{col}</xdr:col><xdr:colOff>0</xdr:colOff>'
            f'<xdr:row>{row0}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>'
            f'<xdr:ext cx="{EXT_CX}" cy="{EXT_CY}"/>'
            '<xdr:graphicFrame macro="">'
            f'<xdr:nvGraphicFramePr><xdr:cNvPr id="{k+2}" name="Chart {k+1}"/>'
            '<xdr:cNvGraphicFramePr/></xdr:nvGraphicFramePr>'
            '<xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
            f'<c:chart xmlns:c="{C}" xmlns:r="{R}" r:id="rId{k+1}"/>'
            '</a:graphicData></a:graphic></xdr:graphicFrame><xdr:clientData/></xdr:oneCellAnchor>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<xdr:wsDr xmlns:xdr="{XDR}" xmlns:a="{A}">' + "".join(frames) + '</xdr:wsDr>')

def build_drawing10_rels():
    R="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart"
    rels="".join(
        f'<Relationship Id="rId{k+1}" Type="{R}" Target="../charts/chart{k+1}.xml"/>'
        for k in range(9))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{rels}</Relationships>')

def sheet14_rels():
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" '
            'Target="../drawings/drawing10.xml"/></Relationships>')

def main():
    src,dst=sys.argv[1],sys.argv[2]
    zin=zipfile.ZipFile(src,"r")
    parts={i.filename: zin.read(i.filename) for i in zin.infolist()}
    order=[i.filename for i in zin.infolist()]
    zin.close()

    # --- 1. strip <drawing> from the 9 fig sheets + their rels ---
    # map: fig sheets are sheet2..sheet10 (they each have a drawing rel)
    for s in range(2,11):
        relname=f"xl/worksheets/_rels/sheet{s}.xml.rels"
        rel=parts[relname].decode()
        m=re.search(r'<Relationship[^>]*Target="\.\./drawings/drawing\d+\.xml"[^>]*/>', rel)
        if not m: continue
        rid=re.search(r'Id="([^"]+)"', m.group(0)).group(1)
        parts[relname]=(rel[:m.start()]+rel[m.end():]).encode()
        sheetname=f"xl/worksheets/sheet{s}.xml"
        sx=parts[sheetname].decode()
        sx=re.sub(rf'<drawing r:id="{rid}"/>', "", sx)
        parts[sheetname]=sx.encode()

    # --- 2. delete drawing1..9 parts + rels ---
    for k in range(1,10):
        parts.pop(f"xl/drawings/drawing{k}.xml", None)
        parts.pop(f"xl/drawings/_rels/drawing{k}.xml.rels", None)
    order=[o for o in order if not re.match(r"xl/drawings/(_rels/)?drawing[1-9]\.xml", o)]

    # --- 2b. drop calcChain: its cell entries reference sheets by index and we
    #     inserted a sheet at position 1; a stale calcChain triggers Excel's
    #     "found a problem with content" repair. Excel rebuilds it on open. ---
    if "xl/calcChain.xml" in parts:
        parts.pop("xl/calcChain.xml", None)
        order=[o for o in order if o!="xl/calcChain.xml"]
        ct0=parts["[Content_Types].xml"].decode()
        ct0=ct0.replace(
            '<Override PartName="/xl/calcChain.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.calcChain+xml"/>', "")
        parts["[Content_Types].xml"]=ct0.encode()
        wr0=parts["xl/_rels/workbook.xml.rels"].decode()
        wr0=re.sub(r'<Relationship[^>]*Target="calcChain\.xml"[^>]*/>', "", wr0)
        parts["xl/_rels/workbook.xml.rels"]=wr0.encode()

    # --- 3. add new parts ---
    new={
        "xl/worksheets/sheet14.xml": build_sheet14().encode(),
        "xl/worksheets/_rels/sheet14.xml.rels": sheet14_rels().encode(),
        "xl/drawings/drawing10.xml": build_drawing10().encode(),
        "xl/drawings/_rels/drawing10.xml.rels": build_drawing10_rels().encode(),
    }
    parts.update(new); order.extend(new.keys())

    # --- 4. workbook.xml: Charts as first sheet, activeTab=0 ---
    #     CRITICAL: sheet-scoped defined names (Power Query's hidden ExternalData_1
    #     bindings, Excel Tables, etc.) reference their sheet by a 0-BASED index in
    #     localSheetId. Inserting Charts at position 0 shifts every existing sheet
    #     down one, so every localSheetId must be incremented by 1 — otherwise each
    #     scoped name points at the wrong sheet and Excel reports the file as corrupt
    #     and unrepairable (openpyxl / LibreOffice silently tolerate the mismatch).
    wb=parts["xl/workbook.xml"].decode()
    wb=re.sub(r'localSheetId="(\d+)"',
              lambda m: f'localSheetId="{int(m.group(1))+1}"', wb)
    wb=wb.replace('<sheets>',
        '<sheets><sheet name="Charts" sheetId="14" r:id="rId20"/>', 1)
    wb=re.sub(r'activeTab="\d+"', 'activeTab="0"', wb)
    parts["xl/workbook.xml"]=wb.encode()

    # --- 5. workbook rels: rId20 -> sheet14 ---
    wr=parts["xl/_rels/workbook.xml.rels"].decode()
    wr=wr.replace('</Relationships>',
        '<Relationship Id="rId20" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet14.xml"/></Relationships>')
    parts["xl/_rels/workbook.xml.rels"]=wr.encode()

    # --- 6. content types: add sheet14 + drawing10, drop drawing1..9 ---
    ct=parts["[Content_Types].xml"].decode()
    for k in range(1,10):
        ct=ct.replace(
            f'<Override PartName="/xl/drawings/drawing{k}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>', "")
    ct=ct.replace('</Types>',
        '<Override PartName="/xl/worksheets/sheet14.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/drawings/drawing10.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/></Types>')
    parts["[Content_Types].xml"]=ct.encode()

    # --- 7. app.xml: 13 -> 14 sheets, prepend 'Charts' ---
    ap=parts["docProps/app.xml"].decode()
    ap=ap.replace('<vt:i4>13</vt:i4>','<vt:i4>14</vt:i4>')
    ap=ap.replace('<vt:vector size="13" baseType="lpstr">',
                  '<vt:vector size="14" baseType="lpstr"><vt:lpstr>Charts</vt:lpstr>')
    parts["docProps/app.xml"]=ap.encode()

    # --- write out (preserve original order, new parts appended) ---
    zout=zipfile.ZipFile(dst,"w",zipfile.ZIP_DEFLATED)
    for name in order:
        zout.writestr(name, parts[name])
    zout.close()
    print(f"charts moved to a new leftmost 'Charts' tab -> {dst}", flush=True)

if __name__=="__main__":
    main()

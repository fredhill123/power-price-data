"""
redburn_charts.py — transform the 9 native Excel charts to the true Redburn look,
cap year ranges (mixed cutoff), clean series names and recolour — all by editing
ONLY xl/charts/chartN.xml, copying every other zip part (Power Query DataMashup,
connections, queryTables, tables, sharedStrings) byte-for-byte so the workbook's
queries and refresh-on-open are untouched.

Redburn spec (from Power & Utilities/tools/chartgen.py, the canonical source):
  * NO chart title (a slide/panel header names it; here a worksheet caption does).
  * Arial 8.5pt axis/legend/tick text.
  * Series palette NAVY #2E3E80, TEAL #5FA1AD, SAGE #ACBFB7, FOREST #3D664A,
    GOLD #CC9F53, WINE #8A1E41; multi-year charts colour latest-year = NAVY,
    older years fading through the palette then grey (most-recent-first).
  * Horizontal (value-axis) gridlines only, #E5E5E5; no vertical gridlines.
  * Legend bottom, no frame, clean human names (no "_neg"/"DE_2024_" suffixes).
  * Accounting-style negatives on the value axis:  -25 -> (25).

Year cutoff (agreed with Fred, Mixed):
  * Annual-total / annual-stat charts stop at the last COMPLETE year (2025):
    Fig1 (price SD), Fig3 (negative hours), Fig5 (capture), Fig9 (capacity).
  * Intraday / profile / duration charts keep the latest data (2026):
    Fig2 (intraday), Fig3 cumulative, Fig4 (duration).
  * Single-year charts unchanged: Fig6 (scatter 2024), Fig7 (gen mix 2024).

Usage: python redburn_charts.py "<in.xlsx>" "<out.xlsx>"
"""
from __future__ import annotations
import sys, re, zipfile
from lxml import etree

C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
def c(t): return f"{{{C}}}{t}"
def a(t): return f"{{{A}}}{t}"

# ---- house palette (chartgen.py ground truth) ----
NAVY="2E3E80"; TEAL="5FA1AD"; SAGE="ACBFB7"; FOREST="3D664A"; GOLD="CC9F53"; WINE="8A1E41"
GREY1="9AA5B1"; GREY2="C9D2CD"
GRID="E5E5E5"; AXISLN="BFBFBF"; TXT="595959"; RED="C00000"
FONT="Arial"
SERIES=[NAVY, TEAL, SAGE, FOREST, GOLD, WINE]
YEAR_FADE=[NAVY, TEAL, SAGE, FOREST, GOLD, WINE, GREY1, GREY2]  # most-recent-first

# CT_ChartSpace child order — Excel validates this strictly (LibreOffice does not)
ORDER_SPACE=["date1904","lang","roundedCorners","style","clrMapOvr","pivotSource",
             "protection","chart","spPr","txPr","externalData","printSettings",
             "userShapes","extLst"]
# CT_BarChart child order (for gapWidth placement)
ORDER_BAR=["barDir","grouping","varyColors","ser","dLbls","gapWidth","overlap",
           "serLines","axId"]

def insert_ordered(parent, child, order):
    tag=etree.QName(child).localname
    idx=order.index(tag) if tag in order else len(order)
    pos=len(parent)
    for i,ex in enumerate(parent):
        ln=etree.QName(ex).localname
        if ln in order and order.index(ln) > idx:
            pos=i; break
    parent.insert(pos, child)

TECH_COLORS = {
    "Nuclear":"8A1E41","Lignite":"7A6A53","Hard coal":"1A1A1A","Gas":"9AA5B1",
    "Oil & other fossil":"6B6B6B","Biomass":"E8C9BA","Waste":"B0A08F","Geothermal":"C97B5A",
    "Hydro run-of-river":"5FA1AD","Hydro reservoir":"3D664A","Hydro pumped (production)":"6F8F77",
    "Onshore wind":"2E3E80","Offshore wind":"5B6FB0","Solar":"CC9F53","Marine":"ACBFB7",
    "Other renewable":"8FB09A","Other":"D6D1CA",
}

# per-chart transform plan
PLAN = {
    1: dict(kind="line",   theme="country", numfmt="#,##0;(#,##0)",   cap_row=8),
    2: dict(kind="line",   theme="year",    numfmt="#,##0;(#,##0)"),
    3: dict(kind="bar",    theme="country", numfmt="#,##0;(#,##0)",   strip="_neg", cap_row=8),
    4: dict(kind="line",   theme="year",    numfmt="#,##0;(#,##0)"),
    5: dict(kind="line",   theme="year",    numfmt="#,##0;(#,##0)"),
    6: dict(kind="bar",    theme="year",    numfmt='#,##0"%";(#,##0"%")', drop_last=1),
    7: dict(kind="scatter",                 numfmt="#,##0;(#,##0)"),
    8: dict(kind="mix",                     numfmt="#,##0;(#,##0)",   strip="PT_2024_"),
    9: dict(kind="bar",    theme="year",    numfmt="#,##0;(#,##0)",   drop_last=1),
}

# ---------- small builders ----------
def solidFill(hexv):
    sf=etree.Element(a("solidFill")); etree.SubElement(sf, a("srgbClr")).set("val", hexv); return sf
def noFill():
    return etree.Element(a("noFill"))
def line(hexv, w):
    ln=etree.Element(a("ln")); ln.set("w", str(w)); ln.append(solidFill(hexv))
    etree.SubElement(ln, a("prstDash")).set("val","solid"); return ln
def line_none():
    ln=etree.Element(a("ln")); ln.append(noFill()); return ln

def txPr(sz=850, color=TXT, bold=False):
    t=etree.Element(c("txPr")); etree.SubElement(t, a("bodyPr")); etree.SubElement(t, a("lstStyle"))
    p=etree.SubElement(t, a("p")); pPr=etree.SubElement(p, a("pPr"))
    d=etree.SubElement(pPr, a("defRPr")); d.set("sz", str(sz))
    if bold: d.set("b","1")
    d.append(solidFill(color)); etree.SubElement(d, a("latin")).set("typeface", FONT)
    etree.SubElement(p, a("endParaRPr")).set("lang","en-GB")
    return t

def set_ser_name(ser, text):
    """Replace <c:tx> with a literal value so it survives a PQ refresh."""
    for old in ser.findall(c("tx")): ser.remove(old)
    tx=etree.Element(c("tx")); v=etree.SubElement(tx, c("v")); v.text=text
    # tx must sit right after <c:order>
    order=ser.find(c("order"))
    order.addnext(tx)

def set_ser_spPr(ser, spPr):
    for old in ser.findall(c("spPr")): ser.remove(old)
    ref = ser.find(c("tx"))
    if ref is None: ref = ser.find(c("order"))
    ref.addnext(spPr)

def spPr_line(hexv, w=22000):
    s=etree.Element(c("spPr")); s.append(line(hexv, w)); return s
def spPr_fill(hexv):
    s=etree.Element(c("spPr")); s.append(solidFill(hexv))
    ln=etree.SubElement(s, a("ln")); ln.append(noFill()); return s

def marker_none(ser):
    for old in ser.findall(c("marker")): ser.remove(old)
    mk=etree.Element(c("marker")); etree.SubElement(mk, c("symbol")).set("val","none")
    spPr=ser.find(c("spPr"))
    (spPr if spPr is not None else ser.find(c("tx"))).addnext(mk)

def clean_year(name):
    m=re.search(r"(\d{4})", name)
    return m.group(1) if m else name

# ---------- range capping ----------
def cap_numref(numref, end_row):
    f=numref.find(c("f"))
    f.text=re.sub(r"(\$[A-Z]+\$)\d+(\s*)$", lambda m: f"{m.group(1)}{end_row}", f.text)
    cache=numref.find(c("numCache"))
    if cache is not None:
        keep=end_row-1  # rows 2..end_row inclusive
        pc=cache.find(c("ptCount"));  pc.set("val", str(keep))
        for pt in list(cache.findall(c("pt"))):
            if int(pt.get("idx")) > keep-1:
                cache.remove(pt)

def cap_series(ser, end_row):
    for tag in ("cat","val"):
        holder=ser.find(c(tag))
        if holder is None: continue
        nr=holder.find(c("numRef"))
        if nr is not None: cap_numref(nr, end_row)

# ---------- axis / legend / title ----------
def strip_title(chart):
    t=chart.find(c("title"))
    if t is not None: chart.remove(t)
    atd=chart.find(c("autoTitleDeleted"))
    if atd is None:
        atd=etree.Element(c("autoTitleDeleted"))
        # must come right after (absent) title, before plotArea
        chart.insert(0, atd)
    atd.set("val","1")

def style_axes(root, numfmt):
    for ax in list(root.iter(c("catAx"))) + list(root.iter(c("valAx"))):
        is_val = etree.QName(ax).localname == "valAx"
        # un-hide
        d=ax.find(c("delete"));  d.set("val","0") if d is not None else None
        # gridlines: keep on value axis (light), remove on category axis
        for gl in ax.findall(c("majorGridlines")): ax.remove(gl)
        for gl in ax.findall(c("minorGridlines")): ax.remove(gl)
        if is_val:
            gl=etree.Element(c("majorGridlines")); sp=etree.SubElement(gl, c("spPr"))
            sp.append(line(GRID, 6350))
            # majorGridlines goes right after axPos
            axpos=ax.find(c("axPos")); axpos.addnext(gl)
            nf=ax.find(c("numFmt"))
            if nf is not None:
                nf.set("formatCode", numfmt); nf.set("sourceLinked","0")
        # tick marks small/out, labels nextTo
        for tm,val in (("majorTickMark","out"),("minorTickMark","none")):
            e=ax.find(c(tm))
            if e is not None: e.set("val", val)
        tlp=ax.find(c("tickLblPos"));  tlp.set("val","nextTo") if tlp is not None else None
        # axis line colour + tick font — insert spPr/txPr just before crossAx
        crossAx=ax.find(c("crossAx"))
        sp=etree.Element(c("spPr")); sp.append(line(AXISLN, 9525))
        crossAx.addprevious(sp)
        crossAx.addprevious(txPr(850, TXT))
        # small grey axis title if present
        for title in ax.iter(c("title")):
            for rpr in title.iter(a("defRPr")):
                rpr.set("sz","850"); rpr.set("b","0")
                for sf in rpr.findall(a("solidFill")): rpr.remove(sf)
                rpr.insert(0, solidFill(TXT)); etree.SubElement(rpr, a("latin")).set("typeface", FONT)
            for r in title.iter(a("rPr")):
                r.set("sz","850"); r.set("b","0")

def style_legend(chart, scatter=False):
    legend=chart.find(c("legend"))
    if scatter:
        if legend is not None: chart.remove(legend)
        return
    if legend is None:
        legend=etree.Element(c("legend"))
        pv=chart.find(c("plotVisOnly")); (pv.addprevious(legend) if pv is not None else chart.append(legend))
    for ch in list(legend): legend.remove(ch)
    etree.SubElement(legend, c("legendPos")).set("val","b")
    etree.SubElement(legend, c("overlay")).set("val","0")
    legend.append(txPr(850, TXT))

def style_chartspace(root):
    # white bg, no border, square corners, Arial default — all inserted in
    # schema order (Excel rejects a chartSpace whose children are out of order).
    rc=root.find(c("roundedCorners"))
    if rc is None:
        rc=etree.Element(c("roundedCorners")); insert_ordered(root, rc, ORDER_SPACE)
    rc.set("val","0")
    for old in root.findall(c("spPr")): root.remove(old)
    for old in root.findall(c("txPr")): root.remove(old)
    sp=etree.Element(c("spPr")); sp.append(solidFill("FFFFFF")); sp.append(line_none())
    insert_ordered(root, sp, ORDER_SPACE)
    insert_ordered(root, txPr(850, "404040"), ORDER_SPACE)

def style_plotarea(chart):
    pa=chart.find(c("plotArea"))
    sp=pa.find(c("spPr"))
    if sp is None: sp=etree.SubElement(pa, c("spPr"))
    for old in list(sp): sp.remove(old)
    sp.append(noFill()); sp.append(line_none())

# ---------- main per-chart transform ----------
def transform(xml_bytes, idx):
    plan=PLAN[idx]
    root=etree.fromstring(xml_bytes)
    chart=root.find(c("chart"))
    kind=plan["kind"]

    strip_title(chart)

    sers=list(root.iter(c("ser")))

    # drop trailing year-series (e.g. 2026) for annual charts
    if plan.get("drop_last"):
        for s in sers[-plan["drop_last"]:]:
            s.getparent().remove(s)
        sers=sers[:-plan["drop_last"]]

    # per-series: name + colour
    if kind in ("line","bar") and plan.get("theme")=="year":
        n=len(sers)
        for i,ser in enumerate(sers):
            yr=clean_year(_ser_raw_name(ser))
            set_ser_name(ser, yr)
            col=YEAR_FADE[min((n-1)-i, len(YEAR_FADE)-1)]
            set_ser_spPr(ser, spPr_line(col, 22000) if kind=="line" else spPr_fill(col))
            if kind=="line": marker_none(ser)
    elif kind in ("line","bar") and plan.get("theme")=="country":
        for i,ser in enumerate(sers):
            nm=_ser_raw_name(ser)
            if plan.get("strip"): nm=nm.replace(plan["strip"],"")
            set_ser_name(ser, nm)
            col=SERIES[i % len(SERIES)]
            set_ser_spPr(ser, spPr_line(col, 22000) if kind=="line" else spPr_fill(col))
            if kind=="line": marker_none(ser)
    elif kind=="mix":
        for ser in sers:
            nm=_ser_raw_name(ser)
            if plan.get("strip"): nm=nm.replace(plan["strip"],"")
            is_price = nm.lower()=="price"
            set_ser_name(ser, "Price" if is_price else nm)
            if is_price:
                set_ser_spPr(ser, spPr_line(RED, 28575)); marker_none(ser)
            else:
                set_ser_spPr(ser, spPr_fill(TECH_COLORS.get(nm, GREY1)))
    elif kind=="scatter":
        for ser in sers:
            set_ser_spPr(ser, _scatter_spPr())
            _scatter_marker(ser)

    # cap year ranges (row-based charts only)
    if plan.get("cap_row"):
        for ser in sers:
            cap_series(ser, plan["cap_row"])

    # bar gap width
    if kind in ("bar","mix"):
        for bc in root.iter(c("barChart")):
            gw=bc.find(c("gapWidth"))
            if gw is None:
                gw=etree.Element(c("gapWidth")); insert_ordered(bc, gw, ORDER_BAR)
            gw.set("val","60")

    style_axes(root, plan["numfmt"])
    style_legend(chart, scatter=(kind=="scatter"))
    style_plotarea(chart)
    style_chartspace(root)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

def _ser_raw_name(ser):
    tx=ser.find(c("tx"))
    if tx is None: return ""
    v=tx.find(c("v"))
    if v is not None and v.text: return v.text
    cache=tx.find(f"{c('strRef')}/{c('strCache')}")
    if cache is not None:
        pv=cache.find(f"{c('pt')}/{c('v')}")
        if pv is not None and pv.text: return pv.text
    return ""

def _scatter_spPr():
    s=etree.Element(c("spPr")); s.append(line_none()); return s
def _scatter_marker(ser):
    for old in ser.findall(c("marker")): ser.remove(old)
    mk=etree.Element(c("marker"))
    etree.SubElement(mk, c("symbol")).set("val","circle")
    etree.SubElement(mk, c("size")).set("val","4")
    sp=etree.SubElement(mk, c("spPr")); sp.append(solidFill(NAVY)); sp.append(line_none())
    ser.find(c("spPr")).addnext(mk)

def main():
    src,dst=sys.argv[1],sys.argv[2]
    zin=zipfile.ZipFile(src,"r"); zout=zipfile.ZipFile(dst,"w",zipfile.ZIP_DEFLATED)
    n=0
    for item in zin.infolist():
        data=zin.read(item.filename)
        m=re.match(r"xl/charts/chart(\d+)\.xml$", item.filename)
        if m:
            data=transform(data, int(m.group(1))); n+=1
        zout.writestr(item, data)
    zin.close(); zout.close()
    print(f"transformed {n} charts -> {dst}", flush=True)

if __name__=="__main__":
    main()

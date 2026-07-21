"""
restyle_charts.py — give the native Excel charts the Redburn/Rothschild look,
WITHOUT disturbing Power Query. Only xl/charts/chartN.xml are transformed; every
other zip part (customXml DataMashup, connections, queryTables, data) is copied
byte-for-byte, so the workbook's queries and refresh-on-open are untouched.

Usage: python restyle_charts.py "<in.xlsx>" "<out.xlsx>"
"""
from __future__ import annotations
import sys, zipfile, shutil, os
from lxml import etree

C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"c": C, "a": A}
def c(t): return f"{{{C}}}{t}"
def a(t): return f"{{{A}}}{t}"

NAVY = "1F3864"; GREY = "595959"; AXIS = "BFBFBF"; GRID = "E8E8E8"; FONT = "Calibri"

# child order for schema-correct insertion
ORDER_SPACE = ["date1904","lang","roundedCorners","AlternateContent","style","clrMapOvr",
               "pivotSource","protection","chart","spPr","txPr","externalData","printSettings",
               "userShapes","extLst"]
ORDER_CHART = ["title","autoTitleDeleted","pivotFmts","view3D","floor","sideWall","backWall",
               "plotArea","legend","plotVisOnly","dispBlanksAs","showDLblsOverMax","extLst"]
ORDER_LEGEND = ["legendPos","legendEntry","layout","overlay","spPr","txPr","extLst"]
ORDER_AXIS = ["axId","scaling","delete","axPos","majorGridlines","minorGridlines","title","numFmt",
              "majorTickMark","minorTickMark","tickLblPos","spPr","txPr","crossAx","crosses",
              "crossesAt","auto","lblAlgn","lblOffset","tickLblSkip","tickMarkSkip","noMultiLvlLbl",
              "dispUnits","majorUnit","minorUnit","extLst"]

def _localname(el): return etree.QName(el).localname

def insert_ordered(parent, child, order):
    tag = _localname(child)
    idx = order.index(tag) if tag in order else len(order)
    pos = len(parent)
    for i, existing in enumerate(parent):
        ln = _localname(existing)
        if ln in order and order.index(ln) > idx:
            pos = i; break
    parent.insert(pos, child)

def default_txpr(sz=900, color=GREY, bold=False):
    txPr = etree.Element(c("txPr"))
    etree.SubElement(txPr, a("bodyPr"))
    etree.SubElement(txPr, a("lstStyle"))
    p = etree.SubElement(txPr, a("p"))
    pPr = etree.SubElement(p, a("pPr"))
    d = etree.SubElement(pPr, a("defRPr")); d.set("sz", str(sz))
    if bold: d.set("b", "1")
    sf = etree.SubElement(d, a("solidFill")); etree.SubElement(sf, a("srgbClr")).set("val", color)
    etree.SubElement(d, a("latin")).set("typeface", FONT)
    etree.SubElement(p, a("endParaRPr")).set("lang", "en-US")
    return txPr

def line_noFill():
    ln = etree.Element(a("ln")); etree.SubElement(ln, a("noFill")); return ln

def solid_line(color, w=9525):
    ln = etree.Element(a("ln")); ln.set("w", str(w))
    sf = etree.SubElement(ln, a("solidFill")); etree.SubElement(sf, a("srgbClr")).set("val", color)
    return ln

def restyle(xml_bytes):
    root = etree.fromstring(xml_bytes)
    chart = root.find(c("chart"))

    # 1) square corners
    rc = root.find(c("roundedCorners"))
    if rc is None:
        rc = etree.Element(c("roundedCorners")); insert_ordered(root, rc, ORDER_SPACE)
    rc.set("val", "0")

    # 2) remove all gridlines
    for gl in root.iter(c("majorGridlines")):
        gl.getparent().remove(gl)
    for gl in root.iter(c("minorGridlines")):
        gl.getparent().remove(gl)

    # 3) axes: light axis line, grey small tick labels, ticks outward small.
    #    IMPORTANT: every child must be inserted in schema order — a misplaced
    #    spPr/txPr/tickMark (e.g. after crossAx) makes Excel drop axis labels.
    for ax in list(root.iter(c("catAx"))) + list(root.iter(c("valAx"))):
        # un-delete the axis (openpyxl left delete=1, which hides all labels)
        dele = ax.find(c("delete"))
        if dele is None:
            dele = etree.Element(c("delete")); insert_ordered(ax, dele, ORDER_AXIS)
        dele.set("val", "0")
        # axis line colour
        spPr = ax.find(c("spPr"))
        if spPr is None:
            spPr = etree.Element(c("spPr")); insert_ordered(ax, spPr, ORDER_AXIS)
        for old in spPr.findall(a("ln")): spPr.remove(old)
        spPr.insert(0, solid_line(AXIS, 9525))
        # tick label font
        for old in ax.findall(c("txPr")): ax.remove(old)
        insert_ordered(ax, default_txpr(900, GREY), ORDER_AXIS)
        # tick marks
        for tm in ("majorTickMark", "minorTickMark"):
            e = ax.find(c(tm))
            if e is None:
                e = etree.Element(c(tm)); insert_ordered(ax, e, ORDER_AXIS)
            e.set("val", "out" if tm == "majorTickMark" else "none")
        # ensure labels are shown next to the axis
        tlp = ax.find(c("tickLblPos"))
        if tlp is None:
            tlp = etree.Element(c("tickLblPos")); insert_ordered(ax, tlp, ORDER_AXIS)
        tlp.set("val", "nextTo")

    # 3b) scatter charts: kill per-point colouring (varyColors=1 turns 365 days
    #     into 365 legend entries) and give the cloud one house-navy marker.
    scatter = root.find(c("chart") + "/" + c("plotArea") + "/" + c("scatterChart"))
    is_scatter = scatter is not None
    if is_scatter:
        vc = scatter.find(c("varyColors"))
        if vc is None:
            vc = etree.Element(c("varyColors")); scatter.insert(0, vc)
        vc.set("val", "0")
        for ser in scatter.findall(c("ser")):
            for dp in ser.findall(c("dPt")): ser.remove(dp)  # drop per-point overrides
            mk = ser.find(c("marker"))
            if mk is not None:
                mspPr = mk.find(c("spPr"))
                if mspPr is None:
                    mspPr = etree.SubElement(mk, c("spPr"))
                for old in mspPr.findall(a("solidFill")) + mspPr.findall(a("ln")):
                    mspPr.remove(old)
                sf = etree.Element(a("solidFill")); etree.SubElement(sf, a("srgbClr")).set("val", NAVY)
                mspPr.insert(0, sf)
                mspPr.append(line_noFill())

    # 4) legend to bottom, small font, no overlay.
    #    A single-series scatter needs no legend — drop it entirely.
    legend = chart.find(c("legend"))
    if is_scatter and legend is not None:
        chart.remove(legend); legend = None
    if legend is not None:
        lp = legend.find(c("legendPos"))
        if lp is None:
            lp = etree.Element(c("legendPos")); insert_ordered(legend, lp, ORDER_LEGEND)
        lp.set("val", "b")
        ov = legend.find(c("overlay"))
        if ov is None:
            ov = etree.Element(c("overlay")); insert_ordered(legend, ov, ORDER_LEGEND)
        ov.set("val", "0")
        for old in legend.findall(c("txPr")): legend.remove(old)
        insert_ordered(legend, default_txpr(800, GREY), ORDER_LEGEND)

    # 5) title -> bold navy (style existing run props; don't touch the text)
    title = chart.find(c("title"))
    if title is not None:
        for rpr in title.iter(a("defRPr")):
            rpr.set("b", "1")
            for sf in rpr.findall(a("solidFill")): rpr.remove(sf)
            sf = etree.Element(a("solidFill")); etree.SubElement(sf, a("srgbClr")).set("val", NAVY)
            rpr.insert(0, sf)
        for rpr in title.iter(a("rPr")):
            rpr.set("b", "1")
            for sf in rpr.findall(a("solidFill")): rpr.remove(sf)
            sf = etree.Element(a("solidFill")); etree.SubElement(sf, a("srgbClr")).set("val", NAVY)
            rpr.insert(0, sf)

    # 6) plot area: no border/fill
    pa = chart.find(c("plotArea"))
    if pa is not None:
        spPr = pa.find(c("spPr"))
        if spPr is None:
            spPr = etree.SubElement(pa, c("spPr"))
        for old in spPr.findall(a("noFill")) + spPr.findall(a("solidFill")) + spPr.findall(a("ln")):
            spPr.remove(old)
        etree.SubElement(spPr, a("noFill"))
        spPr.append(line_noFill())

    # 7) chart space: white fill, no border, clean default font
    spPr = root.find(c("spPr"))
    if spPr is None:
        spPr = etree.Element(c("spPr")); insert_ordered(root, spPr, ORDER_SPACE)
    for old in spPr.findall(a("solidFill")) + spPr.findall(a("ln")) + spPr.findall(a("noFill")):
        spPr.remove(old)
    sf = etree.SubElement(spPr, a("solidFill")); etree.SubElement(sf, a("srgbClr")).set("val", "FFFFFF")
    spPr.append(line_noFill())
    for old in root.findall(c("txPr")): root.remove(old)
    insert_ordered(root, default_txpr(900, "404040"), ORDER_SPACE)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

def main():
    src, dst = sys.argv[1], sys.argv[2]
    zin = zipfile.ZipFile(src, "r")
    zout = zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED)
    n = 0
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename.startswith("xl/charts/chart") and item.filename.endswith(".xml"):
            data = restyle(data); n += 1
        zout.writestr(item, data)
    zin.close(); zout.close()
    print(f"restyled {n} charts -> {dst}", flush=True)

if __name__ == "__main__":
    main()

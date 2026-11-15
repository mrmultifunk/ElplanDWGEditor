from __future__ import annotations

"""Dependency-free Excel (.xlsx) writer for the BOM export.

The desktop build should not depend on a locally installed Excel/Office package
or an extra spreadsheet Python package just to create a material list.  This
module therefore writes the small Office Open XML package directly with the
standard library.
"""

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZIP_DEFLATED, ZipFile

import price_display


def bom_columns(price_vat_mode="excl"):
    vat_label = "inkl. moms" if str(price_vat_mode or "").casefold() == "incl" else "ekskl. moms"
    return (
    ("Artikelnummer", "article_no", "text"),
    ("Rum", "room_display", "text"),
    ("Beskrivelse", "description", "text"),
    ("Fabrikat", "manufacturer", "text"),
    ("Type/kategori", "bom_category", "text"),
    ("Monteringsprofil", "mounting_zone_label", "text"),
    ("Monteringshøjde [mm]", "mounting_height_mm", "qty"),
    ("Materialefarve", "material_color", "text"),
    ("Artikelfarve", "article_color", "text"),
    ("Indkøbsstatus", "purchase_status", "text"),
    ("Kilde / stykliste", "source_summary", "text"),
    ("EAN", "ean", "text"),
    ("EL-/LM-nr.", "el_no", "text"),
    ("Enhed", "unit", "text"),
    ("Antal", "qty", "qty"),
    ("Antal tilbage at købe", "quantity_to_buy", "qty"),
    ("Salgsenhed", "sales_unit", "text"),
    ("Antal pr. salgsenhed", "sales_package_quantity", "qty"),
    ("Indkøbsantal", "purchase_quantity", "qty"),
    ("Indkøbsantal tilbage", "purchase_quantity_to_buy", "qty"),
    ("Overskud", "surplus_quantity", "qty"),
    (f"Estimeret pris {vat_label}", "estimated_price", "price"),
    (f"Manuel pris {vat_label}", "manual_price", "price"),
    (f"Anvendt enhedspris {vat_label}", "unit_price", "price"),
    ("Pris pr.", "price_unit", "text"),
    ("Valuta", "price_currency", "text"),
    ("Prisstatus", "price_status", "text"),
    (f"Linjesum {vat_label}", "line_total", "price"),
    (f"Beløb tilbage {vat_label}", "line_total_to_buy", "price"),
    ("Priskilde", "price_source", "text"),
    ("Pris opdateret", "price_checked", "text"),
    ("Grundlag", "detail", "text"),
    ("Produktlink", "product_page", "text"),
    ("Leverandørlink", "supplier_page", "text"),
    )


BOM_COLUMNS = bom_columns()

MISSING_COLUMNS = (
    ("Type", "symbol_name", "text"),
    ("Del/specifikation", "part_label", "text"),
    ("Behov", "qty", "qty"),
    ("Enhed", "unit", "text"),
    ("Bemærkning", "detail", "text"),
)


def room_summary_columns(price_vat_mode="excl"):
    vat_label = price_display.vat_caption(price_vat_mode)
    return (
        ("Rum", "room_display", "text"),
        ("Valuta", "price_currency", "text"),
        ("Forskellige artikler", "article_count", "integer"),
        ("Linjer med pris", "priced_lines", "integer"),
        ("Linjer uden pris", "missing_price_lines", "integer"),
        (f"Delsum {vat_label}", "subtotal", "price"),
        ("Prisdækning", "coverage_note", "text"),
    )


def build_room_summary(rows):
    """Summarise already VAT-adjusted room rows per room and currency."""
    groups = {}
    for raw in rows or []:
        row = dict(raw or {})
        room = str(row.get("room_display", "") or "Uden rum").strip() or "Uden rum"
        currency = str(row.get("price_currency", "DKK") or "DKK").strip().upper() or "DKK"
        key = (room, currency)
        group = groups.setdefault(key, {
            "room_display": room,
            "price_currency": currency,
            "article_numbers": set(),
            "priced_lines": 0,
            "missing_price_lines": 0,
            "subtotal": 0.0,
        })
        article_no = str(row.get("article_no", "") or "").strip()
        if article_no:
            group["article_numbers"].add(article_no)
        line_total = _number(row.get("line_total"))
        if line_total is None:
            group["missing_price_lines"] += 1
        else:
            group["priced_lines"] += 1
            group["subtotal"] += line_total

    summary = []
    for group in groups.values():
        priced = int(group["priced_lines"])
        missing = int(group["missing_price_lines"])
        note = "Komplet prisdækning" if not missing else f"{missing} linje(r) mangler pris"
        summary.append({
            "room_display": group["room_display"],
            "price_currency": group["price_currency"],
            "article_count": len(group["article_numbers"]),
            "priced_lines": priced,
            "missing_price_lines": missing,
            "subtotal": round(float(group["subtotal"]), 6) if priced else None,
            "coverage_note": note,
        })
    summary.sort(key=lambda row: (row["room_display"].casefold(), row["price_currency"]))
    return summary


def _xml_text(value) -> str:
    text = str(value if value is not None else "")
    # XML 1.0 rejects most control characters.
    text = "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 32)
    return escape(text)


def _col_name(index: int) -> str:
    out = ""
    number = int(index) + 1
    while number:
        number, rem = divmod(number - 1, 26)
        out = chr(65 + rem) + out
    return out


def _cell_ref(row: int, col: int) -> str:
    return f"{_col_name(col)}{row}"


def _number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _inline_cell(ref: str, value, style: int = 6) -> str:
    text = _xml_text(value)
    preserve = ' xml:space="preserve"' if text.startswith(" ") or text.endswith(" ") or "\n" in text else ""
    style_attr = f' s="{style}"' if style else ""
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t{preserve}>{text}</t></is></c>'


def _number_cell(ref: str, value, style: int) -> str:
    number = _number(value)
    if number is None:
        return _inline_cell(ref, "", style)
    # repr keeps useful precision while remaining locale-neutral OOXML.
    return f'<c r="{ref}" s="{style}"><v>{number!r}</v></c>'


def _row_xml(row_number: int, values, kinds, *, header: bool = False) -> str:
    cells = []
    for col, (value, kind) in enumerate(zip(values, kinds)):
        ref = _cell_ref(row_number, col)
        if header:
            cells.append(_inline_cell(ref, value, 3))
        elif kind == "qty":
            cells.append(_number_cell(ref, value, 4))
        elif kind == "price":
            cells.append(_number_cell(ref, value, 5))
        elif kind == "integer":
            cells.append(_number_cell(ref, value, 7))
        else:
            cells.append(_inline_cell(ref, value))
    return f'<row r="{row_number}">{"".join(cells)}</row>'


def _column_widths(columns, rows, *, minimum=9.0, maximum=44.0):
    widths = []
    for title, key, _kind in columns:
        longest = len(str(title))
        for row in rows:
            value = row.get(key, "")
            if value is None:
                continue
            # Use the longest physical line for wrapped cells.
            length = max((len(part) for part in str(value).splitlines()), default=0)
            longest = max(longest, length)
        widths.append(min(maximum, max(minimum, longest * 1.08 + 2.0)))
    return widths


def _cols_xml(widths) -> str:
    parts = ["<cols>"]
    for idx, width in enumerate(widths, start=1):
        parts.append(f'<col min="{idx}" max="{idx}" width="{width:.2f}" customWidth="1"/>')
    parts.append("</cols>")
    return "".join(parts)


def _table_xml(table_id: int, display_name: str, ref: str, headers) -> str:
    columns = "".join(
        f'<tableColumn id="{idx}" name={quoteattr(str(name))}/>'
        for idx, name in enumerate(headers, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'id="{table_id}" name={quoteattr(display_name)} displayName={quoteattr(display_name)} ref={quoteattr(ref)} totalsRowShown="0">'
        f'<autoFilter ref={quoteattr(ref)}/><tableColumns count="{len(headers)}">{columns}</tableColumns>'
        '<tableStyleInfo name="TableStyleMedium2" showFirstColumn="0" showLastColumn="0" showRowStripes="1" showColumnStripes="0"/>'
        '</table>'
    )


def _worksheet_xml(columns, rows, *, title: str, subtitle: str, table_rel_id: str, table_ref: str, freeze_row: int, include_meta: bool):
    widths = _column_widths(columns, rows)
    headers = [title for title, _key, _kind in columns]
    kinds = [kind for _title, _key, kind in columns]
    out = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
        f'<dimension ref="A1:{_cell_ref(max(freeze_row + len(rows), 1), len(columns)-1)}"/>',
        '<sheetViews><sheetView workbookViewId="0">',
        f'<pane ySplit="{freeze_row}" topLeftCell="A{freeze_row + 1}" activePane="bottomLeft" state="frozen"/>',
        '<selection pane="bottomLeft" activeCell="A1" sqref="A1"/>',
        '</sheetView></sheetViews>',
        '<sheetFormatPr defaultRowHeight="15"/>',
        _cols_xml(widths),
        '<sheetData>',
    ]
    if include_meta:
        out.append(f'<row r="1" ht="25" customHeight="1">{_inline_cell("A1", title, 1)}</row>')
        out.append(f'<row r="2">{_inline_cell("A2", "Omfang", 2)}{_inline_cell("B2", subtitle)}</row>')
        header_row = freeze_row
    else:
        header_row = freeze_row
    out.append(_row_xml(header_row, headers, ["text"] * len(headers), header=True))
    start = header_row + 1
    for offset, row in enumerate(rows):
        values = [row.get(key, "") for _title, key, _kind in columns]
        out.append(_row_xml(start + offset, values, kinds))
    out.extend([
        '</sheetData>',
        f'<tableParts count="1"><tablePart r:id="{table_rel_id}"/></tableParts>',
        '</worksheet>',
    ])
    return "".join(out)


def _styles_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="2"><numFmt numFmtId="164" formatCode="0.00####"/><numFmt numFmtId="165" formatCode="#,##0.00"/></numFmts>
  <fonts count="4">
    <font><sz val="11"/><name val="Calibri"/><family val="2"/><scheme val="minor"/></font>
    <font><b/><sz val="16"/><name val="Calibri"/><family val="2"/></font>
    <font><b/><sz val="11"/><name val="Calibri"/><family val="2"/></font>
    <font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/><family val="2"/></font>
  </fonts>
  <fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="8">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>
    <xf numFmtId="0" fontId="3" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
    <xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
    <xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
    <xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
  <dxfs count="0"/><tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/>
</styleSheet>'''


def _workbook_xml(sheet_names) -> str:
    sheets = "".join(
        f'<sheet name={quoteattr(name)} sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="12000"/></bookViews>'
        f'<sheets>{sheets}</sheets><calcPr calcId="191029"/></workbook>'
    )


def _workbook_rels(sheet_count: int) -> str:
    rels = []
    for idx in range(1, sheet_count + 1):
        rels.append(
            f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>'
        )
    rels.append(
        f'<Relationship Id="rId{sheet_count + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels) + '</Relationships>'
    )


def _content_types(sheet_count: int, table_count: int) -> str:
    overrides = [
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    overrides += [
        f'<Override PartName="/xl/worksheets/sheet{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for idx in range(1, sheet_count + 1)
    ]
    overrides += [
        f'<Override PartName="/xl/tables/table{idx}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"/>'
        for idx in range(1, table_count + 1)
    ]
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + "".join(overrides) + '</Types>'
    )


def _root_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''


def _sheet_rels(table_id: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/table" Target="../tables/table{table_id}.xml"/>'
        '</Relationships>'
    )


def _core_props(title: str) -> str:
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dc:title>{_xml_text(title)}</dc:title><dc:creator>Elplan DWG Editor</dc:creator>'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{stamp}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{stamp}</dcterms:modified>'
        '</cp:coreProperties>'
    )


def _app_props(sheet_names) -> str:
    titles = "".join(f'<vt:lpstr>{_xml_text(name)}</vt:lpstr>' for name in sheet_names)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Application>Elplan DWG Editor</Application><DocSecurity>0</DocSecurity><ScaleCrop>false</ScaleCrop>'
        '<HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant><vt:lpstr>Regneark</vt:lpstr></vt:variant>'
        f'<vt:variant><vt:i4>{len(sheet_names)}</vt:i4></vt:variant></vt:vector></HeadingPairs>'
        f'<TitlesOfParts><vt:vector size="{len(sheet_names)}" baseType="lpstr">{titles}</vt:vector></TitlesOfParts>'
        '</Properties>'
    )


def write_bom_xlsx(path, rows, missing=None, *, room_scope="Alle rum", project_name="", room_rows=None, price_vat_mode="excl"):
    """Write a polished BOM workbook and return the final :class:`Path`.

    ``rows`` is the authoritative project/selected-room BOM.  When ``room_rows``
    is supplied, ``Rumoversigt`` and ``BOM pr. rum`` tables are added.  Detail
    rows must contain exactly one concrete room in ``room_display`` so Excel's
    normal table filter can select a room.  Keeping the room distribution
    separate prevents additive manual BOM-room assignments from being mistaken
    for the authoritative project total on the main sheet.

    ``price_vat_mode`` controls both conversion of price fields and their
    headings; input rows are never mutated.
    """
    target = Path(path)
    if target.suffix.casefold() != ".xlsx":
        target = target.with_suffix(".xlsx")
    target.parent.mkdir(parents=True, exist_ok=True)

    mode = price_display.normalize_vat_mode(price_vat_mode)
    bom_rows = price_display.convert_bom_rows(rows, mode)
    room_rows = price_display.convert_bom_rows(room_rows, mode)
    missing_rows = [dict(row or {}) for row in (missing or [])]
    if not bom_rows:
        raise ValueError("BOM'en indeholder ingen artikler.")

    title = "BOM"
    if str(project_name or "").strip():
        title += f" · {str(project_name).strip()}"

    columns = bom_columns(mode)
    vat_caption = price_display.vat_caption(mode)
    sheets = []
    sheets.append({
        "name":"BOM", "columns":columns, "rows":bom_rows,
        "title":title, "subtitle":f"{str(room_scope or 'Alle rum')} · priser {vat_caption}",
        "header_row":4, "include_meta":True, "table_name":"BOMTable",
    })
    if room_rows:
        summary_rows = build_room_summary(room_rows)
        summary_title = "Rumoversigt"
        if str(project_name or "").strip():
            summary_title += f" · {str(project_name).strip()}"
        sheets.append({
            "name":"Rumoversigt", "columns":room_summary_columns(mode), "rows":summary_rows,
            "title":summary_title,
            "subtitle":f"Delsummer pr. rum og valuta · priser {vat_caption} · summen af rum kan overstige projekttotalen ved ekstra BOM-rum",
            "header_row":4, "include_meta":True, "table_name":"BOMRoomSummaryTable",
        })
        room_title = "BOM pr. rum"
        if str(project_name or "").strip():
            room_title += f" · {str(project_name).strip()}"
        sheets.append({
            "name":"BOM pr. rum", "columns":columns, "rows":room_rows,
            "title":room_title,
            "subtitle":f"Én konkret rumværdi pr. række · priser {vat_caption} · filtrér i kolonnen Rum · samlet projekttotal findes på fanen BOM",
            "header_row":4, "include_meta":True, "table_name":"BOMRoomTable",
        })
    if missing_rows:
        sheets.append({
            "name":"Ikke tilknyttet", "columns":MISSING_COLUMNS, "rows":missing_rows,
            "title":"Ikke tilknyttet", "subtitle":"", "header_row":1,
            "include_meta":False, "table_name":"MissingTable",
        })

    sheet_names=[sheet["name"] for sheet in sheets]
    sheet_count=len(sheets)
    table_count=sheet_count

    with ZipFile(target, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types(sheet_count, table_count))
        zf.writestr("_rels/.rels", _root_rels())
        zf.writestr("docProps/core.xml", _core_props(title))
        zf.writestr("docProps/app.xml", _app_props(sheet_names))
        zf.writestr("xl/workbook.xml", _workbook_xml(sheet_names))
        zf.writestr("xl/_rels/workbook.xml.rels", _workbook_rels(sheet_count))
        zf.writestr("xl/styles.xml", _styles_xml())

        for index,sheet in enumerate(sheets,start=1):
            columns=sheet["columns"]; data_rows=sheet["rows"]; header_row=sheet["header_row"]
            end_row=header_row+len(data_rows)
            table_ref=f"A{header_row}:{_cell_ref(end_row, len(columns)-1)}"
            sheet_xml=_worksheet_xml(
                columns,data_rows,title=sheet["title"],subtitle=sheet["subtitle"],
                table_rel_id="rId1",table_ref=table_ref,freeze_row=header_row,
                include_meta=sheet["include_meta"],
            )
            headers=[column[0] for column in columns]
            zf.writestr(f"xl/worksheets/sheet{index}.xml",sheet_xml)
            zf.writestr(f"xl/worksheets/_rels/sheet{index}.xml.rels",_sheet_rels(index))
            zf.writestr(f"xl/tables/table{index}.xml",_table_xml(index,sheet["table_name"],table_ref,headers))

    return target

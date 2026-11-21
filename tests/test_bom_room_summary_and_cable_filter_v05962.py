from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from elplan_catalog.bom_xlsx_export import build_room_summary, write_bom_xlsx


def _row(article_no, room, line_total, currency="DKK", unit_price=10.0):
    return {
        "article_no":article_no, "room_display":room, "description":"Testartikel",
        "manufacturer":"Test", "unit":"stk", "qty":1,
        "unit_price":unit_price if line_total is not None else None,
        "price_currency":currency, "line_total":line_total,
    }


def test_room_summary_separates_currency_and_reports_price_coverage():
    rows=[
        _row("A1","R01 · Gang",10.0),
        _row("A2","R01 · Gang",None),
        _row("A3","R01 · Gang",5.0,"EUR",5.0),
        _row("A4","R02 · Køkken",20.0),
    ]
    summary=build_room_summary(rows)
    assert [(row["room_display"],row["price_currency"]) for row in summary] == [
        ("R01 · Gang","DKK"),("R01 · Gang","EUR"),("R02 · Køkken","DKK")]
    gang_dkk=summary[0]
    assert gang_dkk["article_count"] == 2
    assert gang_dkk["priced_lines"] == 1
    assert gang_dkk["missing_price_lines"] == 1
    assert gang_dkk["subtotal"] == 10.0
    assert "mangler pris" in gang_dkk["coverage_note"]


def test_excel_adds_room_summary_before_filterable_room_details():
    total=[_row("A1","Alle rum",10.0)]
    by_room=[
        _row("A1","R01 · Gang",10.0),
        _row("A2","R01 · Gang",None),
        _row("A3","R02 · Køkken",20.0),
    ]
    with TemporaryDirectory() as directory:
        path=write_bom_xlsx(
            Path(directory)/"bom.xlsx",total,[],room_scope="Alle rum",
            room_rows=by_room,price_vat_mode="incl",
        )
        with ZipFile(path) as archive:
            names=set(archive.namelist())
            for name in names:
                if name.endswith(".xml"):
                    ET.fromstring(archive.read(name))
            workbook=archive.read("xl/workbook.xml").decode("utf-8")
            summary_sheet=archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
            summary_table=archive.read("xl/tables/table2.xml").decode("utf-8")
            detail_table=archive.read("xl/tables/table3.xml").decode("utf-8")
            assert 'name="Rumoversigt"' in workbook
            assert 'name="BOM pr. rum"' in workbook
            assert 'name="BOMRoomSummaryTable"' in summary_table
            assert 'name="Delsum inkl. moms"' in summary_table
            assert 'ref="A4:G6"' in summary_table
            assert 'name="BOMRoomTable"' in detail_table
            assert "summen af rum kan overstige projekttotalen" in summary_sheet
            assert "R01 · Gang" in summary_sheet and "R02 · Køkken" in summary_sheet
            assert "<v>12.5</v>" in summary_sheet
            assert "<v>25.0</v>" in summary_sheet


def test_bom_cable_toggle_recalculates_data_sources_totals_and_export():
    source=(Path(__file__).resolve().parents[1]/"elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    assert 'self.bom_show_cables=QCheckBox("Vis kabler")' in source
    assert "def _bom_cable_inputs(self):" in source
    assert "cables,cable_bindings=self._bom_cable_inputs()" in source
    assert "cables,cable_bindings,factor,reserve" in source
    assert "self.window.project.rooms,cables,cable_bindings" in source
    assert 'cable_filter=" · kabler skjult"' in source
    assert 'export_scope+=" · kabler skjult"' in source

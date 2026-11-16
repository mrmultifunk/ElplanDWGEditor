from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import core_logic as core
from project_model import APP_VERSION
from bom_xlsx_export import write_bom_xlsx


def _row(article_no="A1", room="Alle rum", qty=1.0):
    return {
        "article_no": article_no,
        "room_display": room,
        "description": "Testartikel",
        "manufacturer": "Test",
        "ean": "",
        "el_no": "",
        "unit": "stk",
        "qty": qty,
        "unit_price": 10.0,
        "price_currency": "DKK",
        "line_total": 10.0 * qty,
        "price_kind": "",
        "price_source": "",
        "price_checked": "",
        "detail": "",
        "product_page": "",
        "supplier_page": "",
    }


def test_version_05922():
    assert APP_VERSION == core.APP_VERSION == "0.59.85"


def test_excel_all_rooms_adds_filterable_room_breakdown_without_changing_main_total():
    total=[_row(qty=1.0)]
    # Samme fysiske artikel kan med vilje tilhøre både fysisk rum og et ekstra
    # BOM-rum. Hovedfanen skal fortsat vise projekttotal 1, mens rumfanen viser
    # begge filterkontekster.
    by_room=[_row(room="R01 · Gang",qty=1.0),_row(room="R02 · Køkken",qty=1.0)]
    with TemporaryDirectory() as td:
        path=write_bom_xlsx(Path(td)/"bom.xlsx",total,[],room_scope="Alle rum",room_rows=by_room)
        with ZipFile(path) as zf:
            assert zf.testzip() is None
            names=set(zf.namelist())
            assert "xl/worksheets/sheet1.xml" in names
            assert "xl/worksheets/sheet2.xml" in names
            assert "xl/tables/table2.xml" in names
            workbook=zf.read("xl/workbook.xml").decode("utf-8")
            sheet1=zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
            summary=zf.read("xl/worksheets/sheet2.xml").decode("utf-8")
            sheet3=zf.read("xl/worksheets/sheet3.xml").decode("utf-8")
            table3=zf.read("xl/tables/table3.xml").decode("utf-8")
            for name in names:
                if name.endswith(".xml"):
                    ET.fromstring(zf.read(name))
            assert 'name="Rumoversigt"' in workbook
            assert 'name="BOM pr. rum"' in workbook
            assert 'name="BOMRoomTable"' in table3
            assert '<autoFilter ref="A4:AH6"/>' in table3
            assert 'R01 · Gang' in summary and 'R02 · Køkken' in summary
            assert 'R01 · Gang' in sheet3
            assert 'R02 · Køkken' in sheet3
            # Hovedfanen har fortsat kun én autoritativ totalrække.
            assert sheet1.count('<v>1.0</v>') >= 1
            assert 'R01 · Gang' not in sheet1 and 'R02 · Køkken' not in sheet1


def test_selected_room_export_does_not_need_extra_room_sheet():
    with TemporaryDirectory() as td:
        path=write_bom_xlsx(Path(td)/"bom.xlsx",[_row(room="R02 · Køkken")],[],room_scope="R02 · Køkken")
        with ZipFile(path) as zf:
            workbook=zf.read("xl/workbook.xml").decode("utf-8")
            assert 'name="BOM pr. rum"' not in workbook
            assert 'name="Rumoversigt"' not in workbook
            assert "xl/worksheets/sheet2.xml" not in zf.namelist()


def test_qt_excel_export_builds_concrete_room_rows_for_all_rooms():
    source=(Path(__file__).resolve().parents[1]/"qt_articles.py").read_text(encoding="utf-8")
    assert "def _bom_rows_by_room_for_export" in source
    assert 'scopes.append("__outside__")' in source
    assert "room_rows=self._bom_rows_by_room_for_export() if not selected_room else []" in source
    assert "room_rows=room_rows" in source

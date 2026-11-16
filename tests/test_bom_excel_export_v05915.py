from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import core_logic as core
from project_model import APP_VERSION
from bom_xlsx_export import write_bom_xlsx


def test_version_05915():
    assert APP_VERSION == core.APP_VERSION == "0.59.82"


def _sample_rows():
    return [{
        "article_no":"221-413",
        "room_display":"R01 · Køkken",
        "description":"WAGO 221 fjedersamlemuffe",
        "manufacturer":"WAGO",
        "ean":"4050821808442",
        "el_no":"7821100000",
        "unit":"stk",
        "qty":3,
        "unit_price":12.50,
        "price_currency":"DKK",
        "line_total":37.50,
        "price_kind":"Estimat",
        "price_source":"Test",
        "price_checked":"2026-08-26",
        "detail":"3 stk",
        "product_page":"https://example.test/product",
        "supplier_page":"https://example.test/supplier",
    }]


def test_bom_xlsx_is_valid_ooxml_table_with_filter_freeze_and_missing_sheet():
    missing=[{"symbol_name":"Stikkontakt","part_label":"Afdækning","qty":2,"unit":"stk","detail":"Mangler artikel"}]
    with TemporaryDirectory() as td:
        path=write_bom_xlsx(Path(td)/"bom.xlsx",_sample_rows(),missing,room_scope="R01 · Køkken",project_name="Demo")
        assert path.exists() and path.suffix==".xlsx"
        with ZipFile(path) as zf:
            assert zf.testzip() is None
            names=set(zf.namelist())
            for required in (
                "[Content_Types].xml","xl/workbook.xml","xl/styles.xml",
                "xl/worksheets/sheet1.xml","xl/tables/table1.xml",
                "xl/worksheets/sheet2.xml","xl/tables/table2.xml",
            ):
                assert required in names
            # Every XML part written by the exporter must be well-formed.
            for name in names:
                if name.endswith(".xml"):
                    ET.fromstring(zf.read(name))
            sheet=zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
            table=zf.read("xl/tables/table1.xml").decode("utf-8")
            styles=zf.read("xl/styles.xml").decode("utf-8")
            workbook=zf.read("xl/workbook.xml").decode("utf-8")
            assert 'ySplit="4"' in sheet and 'topLeftCell="A5"' in sheet
            assert '<tableParts count="1">' in sheet
            assert 'name="BOMTable"' in table
            assert 'ref="A4:Z5"' in table
            assert 'TableStyleMedium2' in table
            assert 'name="Type/kategori"' in table
            assert 'name="Antal"' in table and 'name="Linjesum ekskl. moms"' in table
            assert 'formatCode="0.00####"' in styles
            assert 'formatCode="#,##0.00"' in styles
            assert 'name="Ikke tilknyttet"' in workbook
            # Numeric quantity/price cells are written as numeric OOXML, not locale text.
            assert '<v>3.0</v>' in sheet
            assert '<v>12.5</v>' in sheet
            assert '<v>37.5</v>' in sheet


def test_bom_xlsx_without_missing_items_only_contains_bom_sheet():
    with TemporaryDirectory() as td:
        path=write_bom_xlsx(Path(td)/"bom",_sample_rows(),[],room_scope="Alle rum")
        assert path.name == "bom.xlsx"
        with ZipFile(path) as zf:
            names=set(zf.namelist())
            assert "xl/worksheets/sheet1.xml" in names
            assert "xl/worksheets/sheet2.xml" not in names
            assert "xl/tables/table2.xml" not in names


def test_bom_ui_keeps_csv_and_adds_excel_export():
    source=(Path(__file__).resolve().parents[1]/"qt_articles.py").read_text(encoding="utf-8")
    assert 'Eksportér Excel…' in source
    assert 'Eksportér CSV…' in source
    assert 'def _export_bom_xlsx' in source
    assert 'write_bom_xlsx' in source
    assert 'def _prepare_bom_rows_for_export' in source

from pathlib import Path

import core_logic as core
from bom_pdf_export import BOM_PRINT_COLUMN_TITLES, prepare_bom_print_data, write_bom_pdf
from project_model import APP_VERSION


ROOT=Path(__file__).resolve().parents[1]


def test_version_v05968():
    assert APP_VERSION == core.APP_VERSION == "0.59.78"


def test_bom_print_is_intentionally_limited_to_five_essential_columns():
    assert BOM_PRINT_COLUMN_TITLES == ("Varenr.","Beskrivelse","Antal","Enhedspris","Beløb")


def test_bom_print_prices_follow_global_vat_mode():
    rows=[{
        "article_no":"A1","description":"Afbryder","qty":2,"unit":"stk",
        "unit_price":100,"line_total":200,"price_currency":"DKK","price_unit":"stk",
    }]
    prepared,totals,priced=prepare_bom_print_data(rows,"incl")
    assert prepared[0]["unit_price"] == "125,00 DKK / stk"
    assert prepared[0]["line_total"] == "250,00 DKK"
    assert totals == {"DKK":250.0}
    assert priced == 1


def test_bom_pdf_writer_creates_a_pdf(tmp_path):
    target=write_bom_pdf(
        tmp_path / "bom.pdf",
        [{"article_no":"A1","description":"Afbryder","qty":2,"unit":"stk","unit_price":10,"line_total":20,"price_currency":"DKK"}],
        project_name="Testprojekt",room_scope="Køkken",price_vat_mode="excl",
        filter_caption="Alle",include_cables=False,
    )
    data=target.read_bytes()
    assert data.startswith(b"%PDF-")
    assert len(data)>1500


def test_bom_ui_always_opens_preview_before_pdf_or_print():
    source=(ROOT / "qt_articles.py").read_text(encoding="utf-8")
    assert 'QPushButton("Udskriv / PDF…")' in source
    assert "class BomPrintPreviewDialog" in source
    assert "write_bom_pdf(" in source
    assert "QPrintDialog(printer,self)" in source
    assert "shutil.copyfile(self._preview_path,path)" in source
    assert "def _current_bom_export_data" in source
    assert 'price_vat_mode=self.price_vat_mode' in source
    assert 'include_cables=data["include_cables"]' in source

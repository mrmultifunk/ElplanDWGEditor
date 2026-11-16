from pathlib import Path

import pytest

import core_logic as core
from bom_pdf_export import write_bom_pdf
from project_model import APP_VERSION


ROOT=Path(__file__).resolve().parents[1]


def _row(article_no,description,qty,price,room=""):
    return {
        "article_no":article_no,"description":description,"qty":qty,"unit":"stk",
        "unit_price":price,"line_total":qty*price,"price_currency":"DKK",
        "price_unit":"stk","room_display":room,
    }


def test_version_v05969():
    assert APP_VERSION == core.APP_VERSION == "0.59.83"


def test_pdf_contains_separate_room_boms_and_subtotals(tmp_path):
    pypdf=pytest.importorskip("pypdf")
    target=write_bom_pdf(
        tmp_path / "bom_rooms.pdf",
        [_row("A1","Afbryder",2,10)],
        project_name="Testprojekt",room_scope="Alle rum",price_vat_mode="incl",
        room_rows=[
            _row("A1","Afbryder",1,10,"R01 · Køkken"),
            _row("A2","Stikkontakt",3,20,"R02 · Gang"),
        ],
    )
    text="\n".join((page.extract_text() or "") for page in pypdf.PdfReader(str(target)).pages)
    assert "BOM pr. rum" in text
    assert "R01 · Køkken" in text
    assert "R02 · Gang" in text
    assert text.count("Delsum inkl. moms") == 2


def test_room_breakdown_is_an_explicit_preview_choice_enabled_by_default():
    source=(ROOT / "qt_articles.py").read_text(encoding="utf-8")
    assert 'QCheckBox("Medtag BOM pr. rum")' in source
    assert "self.include_room_breakdown.setChecked(True)" in source
    assert "self.include_room_breakdown.toggled.connect(self._regenerate_preview)" in source
    assert "room_rows=selected_room_rows" in source
    assert 'if not data["selected_room"]' in source

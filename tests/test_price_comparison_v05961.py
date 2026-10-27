from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import price_display
from bom_xlsx_export import write_bom_xlsx


def _observations():
    return [
        {
            "provider":"WATTOO", "provider_key":"wattoo",
            "price_incl_vat":100.0, "price_excl_vat":80.0,
            "raw_price_incl_vat":1000.0, "raw_price_excl_vat":800.0,
            "package_quantity":10, "package_label":"pakke á 10 stk.",
            "currency":"DKK", "price_unit":"stk", "url":"https://www.wattoo.dk/a",
            "matched_by":"EAN", "checked":"2026-09-03", "confidence":"Høj",
        },
        {
            "provider":"LavprisEL", "provider_key":"lavprisel",
            "price_incl_vat":112.5, "price_excl_vat":90.0,
            "currency":"DKK", "price_unit":"stk", "url":"https://www.lavprisel.dk/a",
            "matched_by":"EL-nr.", "checked":"2026-09-03", "confidence":"Høj",
        },
        {
            "provider":"Meterbutik", "provider_key":"meter",
            "price_incl_vat":25.0, "price_excl_vat":20.0,
            "currency":"DKK", "price_unit":"m", "url":"https://example.test/m",
            "matched_by":"Artikelnummer", "checked":"2026-09-03", "confidence":"Høj",
        },
    ]


def test_vat_conversion_is_reversible_and_keeps_net_storage_model():
    assert price_display.to_display_amount(80.0,"excl") == 80.0
    assert price_display.to_display_amount(80.0,"incl") == 100.0
    assert price_display.from_display_amount(100.0,"incl") == 80.0
    assert price_display.vat_caption("incl") == "inkl. moms"
    assert price_display.vat_caption("anything") == "ekskl. moms"


def test_bom_conversion_returns_copies_and_converts_every_price_field():
    source=[{"estimated_price":80.0,"manual_price":90.0,"unit_price":90.0,"line_total":180.0,"qty":2}]
    before=deepcopy(source)
    converted=price_display.convert_bom_rows(source,"incl")
    assert source == before
    assert converted[0]["estimated_price"] == 100.0
    assert converted[0]["manual_price"] == 112.5
    assert converted[0]["unit_price"] == 112.5
    assert converted[0]["line_total"] == 225.0


def test_retailer_comparison_uses_exact_mode_sorts_and_compares_per_unit_group():
    record={"price_observations":_observations()}
    excl=price_display.comparison_rows(record,"excl")
    stk=[row for row in excl if row["price_unit"]=="stk"]
    assert [row["provider"] for row in stk] == ["WATTOO","LavprisEL"]
    assert stk[0]["unit_price"] == 80.0 and stk[0]["is_cheapest"]
    assert stk[0]["package_price"] == 800.0
    assert stk[1]["difference"] == 10.0
    assert stk[1]["difference_percent"] == 12.5
    metre=next(row for row in excl if row["price_unit"]=="m")
    assert metre["is_cheapest"] and metre["difference"] == 0

    incl=price_display.comparison_rows(record,"incl")
    stk_incl=[row for row in incl if row["price_unit"]=="stk"]
    assert stk_incl[0]["unit_price"] == 100.0
    assert stk_incl[0]["package_price"] == 1000.0
    assert stk_incl[1]["difference"] == 12.5


def test_excel_including_vat_has_matching_headers_and_numeric_values():
    rows=[{
        "article_no":"A1", "room_display":"Køkken", "description":"Test", "manufacturer":"Test",
        "unit":"stk", "qty":2, "estimated_price":80.0, "unit_price":80.0,
        "price_currency":"DKK", "line_total":160.0,
    }]
    with TemporaryDirectory() as directory:
        path=write_bom_xlsx(Path(directory)/"bom.xlsx",rows,price_vat_mode="incl")
        with ZipFile(path) as archive:
            table=archive.read("xl/tables/table1.xml").decode("utf-8")
            sheet=archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
            assert 'name="Estimeret pris inkl. moms"' in table
            assert 'name="Anvendt enhedspris inkl. moms"' in table
            assert 'name="Linjesum inkl. moms"' in table
            assert "priser inkl. moms" in sheet
            assert "<v>100.0</v>" in sheet
            assert "<v>200.0</v>" in sheet


def test_price_ui_wires_comparison_persistence_and_net_storage():
    root=Path(__file__).resolve().parents[1]
    source=(root/"qt_articles.py").read_text(encoding="utf-8")
    dialog=(root/"qt_price_comparison.py").read_text(encoding="utf-8")
    portability=(root/"portability.py").read_text(encoding="utf-8")
    assert 'QPushButton("Sammenlign forhandlere…")' in source
    assert 'self.price_vat_combo.addItem("Inkl. moms",price_display.VAT_MODE_INCL)' in source
    assert "price_display.from_display_amount(self.manual_amount.value(),self._vat_mode)" in source
    assert '"price_observations"' in source
    assert "comparison_rows" in dialog and "Forskel til billigste" in dialog
    assert '"price_vat_mode"' in portability

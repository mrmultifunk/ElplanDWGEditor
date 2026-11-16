from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import core_logic as core
from bom_xlsx_export import write_bom_xlsx
from project_model import APP_VERSION


def test_version():
    assert APP_VERSION == core.APP_VERSION == "0.59.83"


def test_user_facing_bom_categories_use_role_before_broad_article_type():
    article={"article_no":"A1","description":"LK FUGA afbryder uden tangent","product_type":"Afbryder / betjening"}
    assert core.bom_article_category(article,["Indsats"],["assembly"]) == "Indsatser"
    assert core.bom_article_category(article,["Tangent"],["assembly"]) == "Tangenter"
    assert core.bom_article_category(article,["Ramme"],["assembly"]) == "Rammer"


def test_description_does_not_confuse_without_tangent_or_cover_with_the_part_itself():
    switch={"article_no":"S1","description":"1-polet afbryder uden tangent","product_type":"Afbryder / betjening"}
    socket={"article_no":"S2","description":"stikkontakt uden afdækning","product_type":"Stikkontakt / udtag"}
    cover={"article_no":"A1","description":"Afdækning til stikkontakt","product_type":"Tangent / afdækning"}
    assert core.bom_article_category(switch) == "Afbrydere og betjening"
    assert core.bom_article_category(socket) == "Stikkontakter og udtag"
    assert core.bom_article_category(cover) == "Afdækninger"


def test_boxes_cables_and_wago_have_stable_categories():
    assert core.bom_article_category({"article_no":"D","function":"Dåse"}) == "Dåser"
    assert core.bom_article_category({"article_no":"K","kind":"cable"}) == "Kabler"
    assert core.bom_article_category({"article_no":"W"},source_types=["wago"]) == "Samlemuffer og klemmer"


def test_source_breakdown_preserves_assembly_component_role():
    placement=core.Placement("socket",0,0)
    assembly={"id":"a1","name":"Test","items":[{"article_no":"I1","qty":1,"role":"Indsats"}]}
    rows=core.bom_source_breakdown(
        [placement],[{"article_no":"I1","description":"Indsats","unit":"stk"}],{},
        assemblies=[assembly],assembly_bindings={placement.uid:{"symbol":"a1"}},
    )
    assert rows[0]["component_role"] == "Indsats"


def test_excel_contains_filterable_category_column():
    row={
        "article_no":"A1","room_display":"R01","description":"Ramme","manufacturer":"LK",
        "bom_category":"Rammer","unit":"stk","qty":1,"unit_price":10,"line_total":10,
        "price_currency":"DKK",
    }
    with TemporaryDirectory() as directory:
        path=write_bom_xlsx(Path(directory)/"bom.xlsx",[row],[])
        with ZipFile(path) as archive:
            table=archive.read("xl/tables/table1.xml").decode("utf-8")
            sheet=archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
            assert 'name="Type/kategori"' in table
            assert "Rammer" in sheet


def test_bom_ui_has_dynamic_category_filter_grouping_and_sorting():
    source=Path(__file__).resolve().parents[1].joinpath("qt_articles.py").read_text(encoding="utf-8")
    assert "self.bom_category_filter" in source
    assert 'self.bom_group_by.addItem("Artikeltype","bom_category")' in source
    assert 'self.bom_sort.addItem("Artikeltype","bom_category")' in source
    assert 'row["bom_category"]=core.bom_article_category' in source
    assert '"filter_caption":self._bom_filter_caption()' in source

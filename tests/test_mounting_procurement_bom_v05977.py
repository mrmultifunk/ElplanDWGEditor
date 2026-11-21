from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import core_logic as core
from elplan_catalog.bom_xlsx_export import write_bom_xlsx
from elplan_project.project_model import APP_VERSION, ProjectDocument, placement_from_raw


def _placement(uid,zone,height,color,purchased):
    return placement_from_raw({
        "uid":uid,"symbol":"socket","x":0,"y":0,
        "mounting_zone":zone,"mounting_height_mm":height,
        "material_color":color,"already_purchased":purchased,
    })


def test_mounting_and_purchase_fields_round_trip(tmp_path):
    placement=_placement("S1","gulv",300,"Koksgrå",True)
    doc=ProjectDocument(); doc.placements=[placement]
    target=doc.save(tmp_path/"mounting.elplan.json")
    loaded=ProjectDocument.load(target)
    restored=loaded.placements[0]
    assert restored.mounting_zone=="floor"
    assert restored.mounting_height_mm==300
    assert restored.material_color=="Koksgrå"
    assert restored.already_purchased is True


def test_same_article_is_segmented_by_mounting_and_purchase_status():
    floor=_placement("S1","floor",300,"Koksgrå",True)
    switch=_placement("S2","switch",1100,"Hvid",False)
    part=core.bom_symbol_parts("socket")[0]["id"]
    bindings={
        "S1":{part:[{"article_no":"A1","qty":1}]},
        "S2":{part:[{"article_no":"A1","qty":2}]},
    }
    catalog=[{"article_no":"A1","description":"Ramme","manufacturer":"LK","unit":"stk","color":"Hvid","unit_price":10}]
    rows,missing=core.build_bom([floor,switch],catalog,bindings)
    assert not missing and len(rows)==2
    by_zone={row["mounting_zone"]:row for row in rows}
    assert by_zone["floor"]["qty"]==1
    assert by_zone["floor"]["purchase_status"]=="Allerede købt"
    assert by_zone["floor"]["quantity_to_buy"]==0
    assert by_zone["switch"]["qty"]==2
    assert by_zone["switch"]["purchase_status"]=="Mangler at købe"
    assert by_zone["switch"]["quantity_to_buy"]==2
    assert by_zone["floor"]["purchase_segment_key"]!=by_zone["switch"]["purchase_segment_key"]


def test_excel_contains_filterable_mounting_and_purchase_columns(tmp_path):
    row={
        "article_no":"A1","room_display":"Stue","description":"Ramme","manufacturer":"LK",
        "bom_category":"Rammer","mounting_zone_label":"Gulv","mounting_height_mm":300,
        "material_color":"Koksgrå","article_color":"Hvid","purchase_status":"Mangler at købe",
        "source_summary":"Stykliste","unit":"stk","qty":2,"quantity_to_buy":2,
        "purchase_quantity":2,"purchase_quantity_to_buy":2,"line_total":20,"line_total_to_buy":20,
        "price_currency":"DKK","price_unit":"stk","unit_price":10,
    }
    target=write_bom_xlsx(tmp_path/"bom.xlsx",[row])
    with ZipFile(target) as archive:
        table=archive.read("xl/tables/table1.xml").decode("utf-8")
        sheet=archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    for title in ("Monteringsprofil","Monteringshøjde [mm]","Materialefarve","Artikelfarve","Indkøbsstatus","Antal tilbage at købe"):
        assert f'name="{title}"' in table
    assert "Koksgrå" in sheet and "Mangler at købe" in sheet


def test_ui_exposes_mounting_controls_and_bom_filters():
    root=Path(__file__).resolve().parents[1]
    app=(root/"elplan_qt/qt_app.py").read_text(encoding="utf-8")
    articles=(root/"elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    assert APP_VERSION==core.APP_VERSION=="0.59.85"
    assert "prop_mounting_zone" in app and "prop_mounting_height" in app
    assert "prop_material_color" in app and "prop_already_purchased" in app
    assert "bom_mounting_filter" in articles and "bom_purchase_filter" in articles

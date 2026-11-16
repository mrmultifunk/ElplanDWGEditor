from pathlib import Path
import json

import pytest

import core_logic as core
from project_model import APP_VERSION


def _rooms():
    return [
        core.RoomPlacement(name='Køkken', code='R01', points=[(0,0),(10,0),(10,10),(0,10)], label_x=5, label_y=5),
        core.RoomPlacement(name='Gang', code='R02', points=[(10,0),(20,0),(20,10),(10,10)], label_x=15, label_y=5),
    ]


def test_build_bom_can_filter_symbol_quantities_by_room_and_outside():
    rooms=_rooms()
    a=core.Placement('socket',5,5)
    b=core.Placement('socket',15,5)
    outside=core.Placement('socket',30,5)
    placements=[a,b,outside]
    catalog=[{'article_no':'S1','description':'Stikkontakt','unit':'stk'}]
    bindings={p.uid:{'symbol':[{'article_no':'S1','qty':1}]} for p in placements}

    full,_=core.build_bom(placements,catalog,bindings,rooms=rooms)
    room_a,_=core.build_bom(placements,catalog,bindings,rooms=rooms,room_filter_uid=rooms[0].uid)
    room_b,_=core.build_bom(placements,catalog,bindings,rooms=rooms,room_filter_uid=rooms[1].uid)
    outside_rows,_=core.build_bom(placements,catalog,bindings,rooms=rooms,room_filter_uid='__outside__')

    assert full[0]['qty']==3
    assert room_a[0]['qty']==1
    assert room_b[0]['qty']==1
    assert outside_rows[0]['qty']==1


def test_room_filtered_bom_splits_cable_article_by_actual_length_in_room():
    rooms=_rooms()
    cable=core.CablePlacement(points=[(-5,5),(25,5)], cable_spec='3G1,5')
    catalog=[{'article_no':'C1','description':'3G1,5','unit':'m'}]
    cable_bindings={cable.uid:'C1'}

    full,_=core.build_bom([],catalog,{},[cable],cable_bindings,1.0,0.0,rooms=rooms)
    room_a,_=core.build_bom([],catalog,{},[cable],cable_bindings,1.0,0.0,rooms=rooms,room_filter_uid=rooms[0].uid)
    room_b,_=core.build_bom([],catalog,{},[cable],cable_bindings,1.0,0.0,rooms=rooms,room_filter_uid=rooms[1].uid)
    outside,_=core.build_bom([],catalog,{},[cable],cable_bindings,1.0,0.0,rooms=rooms,room_filter_uid='__outside__')

    assert full[0]['qty']==pytest.approx(30.0)
    assert room_a[0]['qty']==pytest.approx(10.0)
    assert room_b[0]['qty']==pytest.approx(10.0)
    assert outside[0]['qty']==pytest.approx(10.0)


def test_bom_ui_has_room_filter_in_addition_to_room_sort_and_hover_preview():
    assert APP_VERSION == core.APP_VERSION == '0.59.83'
    src=Path('qt_articles.py').read_text(encoding='utf-8')
    assert 'self.bom_room_filter.addItem("Alle rum","")' in src
    assert 'self.bom_room_filter.addItem("Uden rum","__outside__")' in src
    assert 'room_filter_uid=selected' in src
    assert 'Sortér efter' in src
    assert 'class BomArticleHoverPopup' in src


def test_wago_221_images_and_p100_2273_series_are_in_predefined_catalog():
    raw=json.loads(Path('predefined_articles.json').read_text(encoding='utf-8'))
    rows={str(r.get('article_no','')):r for r in raw.get('articles',[])}
    expected={
        '2273-202':('4050821027843','7821100331'),
        '2273-203':('4050821027850','7821100344'),
        '2273-204':('4050821027867','7821100357'),
        '2273-205':('4050821027874','7821100360'),
        '2273-208':('4050821027881','7821100373'),
    }
    for article_no,(ean,lm) in expected.items():
        row=rows[article_no]
        assert row['ean']==ean
        assert row['el_no']==lm
        assert row['series']=='2273 / P100'
        assert row['image_source']=='WAGO'
        assert row['image_url'].startswith('https://www.wago.com/medias/')
        assert row['supplier_page'].startswith('https://www.lemu.dk/')
    for article_no in ('221-412','221-413','221-415','221-420'):
        row=rows[article_no]
        assert row['image_source']=='WAGO'
        assert row['image_url'].startswith('https://www.wago.com/medias/')

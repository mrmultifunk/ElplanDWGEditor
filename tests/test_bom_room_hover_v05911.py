from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def _rooms():
    return [
        core.RoomPlacement(name='Køkken', code='R01', points=[(0,0),(10,0),(10,10),(0,10)], label_x=5, label_y=5),
        core.RoomPlacement(name='Gang', code='R02', points=[(10,0),(20,0),(20,10),(10,10)], label_x=15, label_y=5),
    ]


def test_bom_article_room_usage_tracks_symbol_and_cable_rooms_without_changing_bom():
    rooms=_rooms()
    socket=core.Placement('socket',5,5)
    outside=core.Placement('socket',30,30)
    cable=core.CablePlacement(points=[(2,5),(18,5)], cable_spec='3G1,5')
    bindings={
        socket.uid:{'symbol':[{'article_no':'S1','qty':1}]},
        outside.uid:{'symbol':[{'article_no':'S1','qty':1}]},
    }
    cable_bindings={cable.uid:'C1'}
    usage=core.bom_article_room_usage([socket,outside],bindings,rooms,[cable],cable_bindings)
    assert usage['S1']==['R01 · Køkken','Uden rum']
    assert usage['C1']==['R01 · Køkken','R02 · Gang']
    rows,_=core.build_bom([socket,outside],[{'article_no':'S1','unit':'stk'}],bindings)
    assert rows[0]['qty']==2


def test_bom_ui_has_room_sort_field_and_non_interactive_hover_image_popup():
    assert APP_VERSION == core.APP_VERSION == '0.59.76'
    src=Path('qt_articles.py').read_text(encoding='utf-8')
    assert '"Rum"' in src
    assert 'Sortér efter' in src
    assert 'bom_article_room_usage' in src
    assert 'class BomArticleHoverPopup' in src
    assert 'WA_TransparentForMouseEvents' in src
    assert 'self._bom_hover_timer.setInterval(320)' in src
    assert 'Hold musen kort over en artikelrække for at se produktbillede.' in src

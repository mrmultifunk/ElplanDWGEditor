from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def _member(uid, core_id="blue"):
    return {"cable_uid": uid, "point_index": 0, "leg": "endpoint", "core_id": core_id}


def test_version_0506():
    assert APP_VERSION == core.APP_VERSION == "0.59.82"


def test_wago_position_is_normalized_and_preserved():
    splice={
        "id":"w1","function":"n",
        "members":[_member("c1"),_member("c2")],
        "article_no":"221-413",
        "position":{"x":1.4,"y":-0.2},
    }
    got=core.normalize_pl_box_splices([splice])
    assert got[0]["position"] == {"x":1.0,"y":0.0}
    assert core.normalize_pl_splice_position({"x":0.25,"y":0.75}) == {"x":0.25,"y":0.75}
    assert core.normalize_pl_splice_position({"x":"bad","y":0.5}) is None


def test_qt_source_has_hover_context_menu_and_draggable_wago():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "QPainterPathStroker" in source
    assert "def _hover_connection_function" in source
    assert "Flyt til {label}" in source
    assert "Flyt til eksisterende Wago" in source
    assert "+ Opret ny Wago for" in source
    assert "Fjern fra Wago og frigør leder" in source
    assert "spliceMoved=Signal(str,float,float)" in source
    assert "_wago_drag_override" in source
    assert "SizeAllCursor" in source
    assert "Nulstil Wago-placering" in source
    assert 'item["position"]={"x":max(0.0,min(1.0,float(x)))' in source

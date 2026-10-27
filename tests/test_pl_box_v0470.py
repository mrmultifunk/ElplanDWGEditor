from pathlib import Path
import json

import core_logic as core
from project_model import ProjectDocument, APP_VERSION


def _lamp(uid="lamp1"):
    return core.Placement(symbol="light_connection", x=0, y=0, uid=uid)


def _cable(uid, points, connection_index, cable_id="K01", spec="3G1,5"):
    cable=core.CablePlacement(points=list(points), uid=uid, cable_id=cable_id, cable_spec=spec)
    core.set_cable_symbol_connections(cable,[{"point_index":connection_index,"symbol_uid":"lamp1","symbol_port":0}])
    return cable


def test_endpoint_uses_one_pl_entry_and_loopthrough_uses_two():
    endpoint=_cable("c1",[(0,0),(100,0)],0,"K01")
    through=_cable("c2",[(-100,0),(0,0),(100,0)],1,"K02")
    legs=core.cable_legs_at_symbol([endpoint,through],"lamp1")
    assert [(x["cable_uid"],x["leg"]) for x in legs] == [
        ("c1","endpoint"),("c2","before"),("c2","after")
    ]


def test_auto_assign_places_six_unique_legs_and_reports_overflow():
    cables=[]
    for i in range(7):
        # Alternating upwards/downwards gives the allocator both rows.
        dy=100 if i%2==0 else -100
        c=_cable(f"c{i}",[(0,0),(i*20-60,dy)],0,f"K{i+1:02d}")
        cables.append(c)
    legs=core.cable_legs_at_symbol(cables,"lamp1")
    entries=core.auto_assign_pl_box_entries(legs)
    assert len(entries)==6
    assert set(entries)=={"1","2","3","4","5","6"}
    status=core.pl_box_status(entries,legs)
    assert status["required"]==7
    assert status["used"]==6
    assert status["unplaced"]==1
    assert status["overflow"]==1


def test_reconcile_survives_changed_point_index_for_unique_cable_leg():
    old={"2":{"cable_uid":"c2","point_index":1,"leg":"before","note":"fra tavle"}}
    legs=[{"cable_uid":"c2","point_index":3,"leg":"before","vector":(-1,0)}]
    got=core.reconcile_pl_box_entries(old,legs)
    assert got["2"]["point_index"]==3
    assert got["2"]["note"]=="fra tavle"


def test_project_roundtrip_keeps_pl_entries_and_strips_dead_references(tmp_path: Path):
    lamp=_lamp()
    cable=_cable("c1",[(0,0),(100,0)],0)
    lamp.pl_box_entries={
        "1":{"cable_uid":"c1","point_index":0,"leg":"endpoint","note":"OK"},
        "2":{"cable_uid":"deleted","point_index":0,"leg":"endpoint","note":"dead"},
    }
    doc=ProjectDocument.from_cad(tmp_path/"plan.dxf")
    doc.placements=[lamp]; doc.cables=[cable]
    path=tmp_path/"p.elplan.json"; doc.save(path)
    raw=json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"]==APP_VERSION=="0.59.73"
    assert raw["placements"][0]["pl_box_entries"]=={
        "1":{"cable_uid":"c1","point_index":0,"leg":"endpoint","note":"OK"}
    }
    loaded=ProjectDocument.load(path)
    assert loaded.placements[0].pl_box_entries["1"]["cable_uid"]=="c1"


def test_clipboard_does_not_copy_pl_physical_relations():
    lamp=_lamp(); lamp.pl_box_entries={"1":{"cable_uid":"c1","point_index":0,"leg":"endpoint","note":""}}
    copied=core.placement_from_clipboard_payload(core.symbol_clipboard_payload(lamp))
    assert copied is not None
    assert copied.pl_box_entries=={}


def test_qt_source_wires_pl_dialog_and_double_click():
    app=Path("qt_pl_box.py").read_text(encoding="utf-8") + Path("qt_app.py").read_text(encoding="utf-8")
    graphics=Path("qt_graphics.py").read_text(encoding="utf-8")
    assert "class PLBoxDiagramWidget" in app
    assert "class PLBoxDialog" in app
    assert "Konfigurer PL-dåse…" in app
    assert "item.signals.doubleClicked.connect(self._symbol_double_clicked)" in app
    assert 'placement.symbol != "light_connection"' in app
    assert "legDropped = Signal(int, object)" in app
    assert "doubleClicked = Signal(object)" in graphics
    assert "self.signals.doubleClicked.emit(self)" in graphics


def test_pl_box_entry_diagram_has_visual_cable_glands_and_connectors():
    app=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "def _draw_entry_connector" in app
    assert "def _port_connector_geometry" in app
    assert "kabelindføringen fortsætter nu" in app
    docs=Path("docs/history/PL_BOX_0.50.9.md").read_text(encoding="utf-8")
    assert "gennemføringsmuffe" in docs
    assert "tomme knockout" in docs


def test_pl_box_entry_diagram_previews_3g_5g_7g_conductors_inside_box():
    app=Path("qt_pl_box.py").read_text(encoding="utf-8")
    docs=(Path(__file__).resolve().parents[1] / "docs" / "history" / "PL_BOX_0.50.10.md").read_text(encoding="utf-8")
    assert "def _draw_conductor_preview" in app
    assert 'core.cable_conductor_preset(str(leg.get("cable_spec") or ""))' in app
    assert "self._draw_conductor_preview(painter,body,port,rect,leg,selected)" in app
    assert 'str(meta.get("core_id") or "")=="pe"' in app
    assert all(token in docs for token in ("3G", "5G", "7G"))
    assert "Ukendte kabelopbygninger" in docs

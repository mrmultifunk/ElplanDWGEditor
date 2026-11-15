import json

import core_logic as core
import pl_daase_api
from project_model import APP_VERSION, ProjectDocument


def _leg(uid, spec="3G1,5", leg="endpoint", point_index=0):
    return {
        "cable_uid": uid,
        "point_index": point_index,
        "leg": leg,
        "cable_id": uid.upper(),
        "cable_display": uid.upper(),
        "cable_spec": spec,
        "leg_caption": "Ende",
    }


def _field_box():
    return {
        "id": "box-1",
        "name": "Stue",
        "ref": "døren",
        "note": "Over spisebord",
        "entries": [
            {"position": 1, "function": "Forsyning", "cable": "NOMP 3G1,5", "note": "fra tavle", "marker": {"x": .2, "y": .3}},
            {"position": 2, "function": "Tom / ikke tilsluttet", "cable": "", "note": "", "marker": None},
        ],
        "photos": [{"id": "p1", "url": "https://pl.example/api/photo/box-1/p1", "markers": [{"position": 1, "x": .2, "y": .3}]}],
    }


def test_version_05975():
    assert APP_VERSION==core.APP_VERSION=="0.59.78"


def test_field_payload_is_physical_documentation_only():
    result=pl_daase_api.normalize_export_payload({"exported":"2026-11-12T07:34:12Z","user":"martin","boxes":[_field_box()]},"https://pl.example")
    record=result["boxes"][0]
    assert record["box_id"]=="box-1"
    assert len(record["entries"])==6
    assert record["entries"][0]["cable"]=="NOMP 3G1,5"
    assert record["photos"][0]["markers"][0]["position"]==1
    assert "pl_box_wiring" not in record
    assert "pl_box_splices" not in record
    assert "terminals" not in record


def test_cable_type_match_is_only_used_when_unique():
    assert core.pl_field_cable_spec_key("NOMP 3G1,5")=="3G1,5"
    assert core.pl_field_cable_spec_key("4X10 mm2")=="4X10"
    entry={"position":1,"function":"Forsyning","cable":"NOMP 3G1,5"}
    one=_leg("c1")
    assert core.pl_field_suggested_leg(entry,[one])["cable_uid"]=="c1"
    assert core.pl_field_suggested_leg(entry,[one,_leg("c2")]) is None
    assert core.pl_field_suggested_leg(entry,[one],{("c1",0,"endpoint")}) is None


def test_project_roundtrip_keeps_field_record_independent_of_wiring(tmp_path):
    lamp=core.Placement(symbol="light_connection",x=0,y=0,uid="lamp")
    cable=core.CablePlacement(points=[(0,0),(100,0)],uid="c1",cable_id="K01",cable_spec="3G1,5")
    core.set_cable_symbol_connections(cable,[{"point_index":0,"symbol_uid":"lamp","symbol_port":0}])
    lamp.pl_box_entries={"1":{"cable_uid":"c1","point_index":0,"leg":"endpoint","note":"fra tavle"}}
    lamp.pl_box_wiring=core.reconcile_pl_box_wiring([],[_leg("c1")])
    next(row for row in lamp.pl_box_wiring if row["core_id"]=="brown")["function"]="l"
    lamp.pl_box_splices=[{"id":"w1","function":"n","members":[],"connects_to_outlet":False}]
    lamp.pl_field_record=core.normalize_pl_field_record(_field_box())

    document=ProjectDocument.from_cad(tmp_path/"plan.dxf")
    document.placements=[lamp]; document.cables=[cable]
    path=tmp_path/"field.elplan.json"; document.save(path)
    loaded=ProjectDocument.load(path).placements[0]

    assert loaded.pl_field_record["box_id"]=="box-1"
    assert loaded.pl_box_entries["1"]["cable_uid"]=="c1"
    assert next(row for row in loaded.pl_box_wiring if row["core_id"]=="brown")["function"]=="l"
    assert loaded.pl_box_splices[0]["id"]=="w1"


def test_api_client_uses_bearer_token_and_read_only_export(monkeypatch):
    seen={}

    class Response:
        headers={"Content-Type":"application/json"}
        def __enter__(self):return self
        def __exit__(self,*_args):return False
        def read(self,_limit):return json.dumps({"boxes":[_field_box()]}).encode("utf-8")

    def fake_urlopen(request,timeout):
        seen["url"]=request.full_url; seen["authorization"]=request.get_header("Authorization"); seen["timeout"]=timeout
        return Response()

    monkeypatch.setattr(pl_daase_api,"urlopen",fake_urlopen)
    result=pl_daase_api.fetch_export("https://pl.example/api/export","pl_secret",timeout=7)
    assert seen=={"url":"https://pl.example/api/export","authorization":"Bearer pl_secret","timeout":7.0}
    assert result["boxes"][0]["box_id"]=="box-1"


def test_import_surface_explicitly_keeps_conductor_work_outside_pwa():
    source=(__import__("pathlib").Path(__file__).resolve().parents[1]/"qt_pl_field.py").read_text(encoding="utf-8")
    assert "Lederfordelingen ændres ikke" in source
    assert "Den overføres ikke til lederfunktioner" in source
    assert "pl_box_wiring" not in source
    assert "pl_box_splices" not in source

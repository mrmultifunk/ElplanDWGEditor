from dataclasses import asdict
import json
from pathlib import Path

import core_logic as core
from project_model import APP_VERSION, ProjectDocument


def _legacy_chain(*, uid="old-cable", cable_id="K01", spec="3G1,5"):
    cable=core.CablePlacement(
        points=[(0,0),(100,0),(200,0)],
        uid=uid,cable_id=cable_id,cable_spec=spec,circuit_id="G05",
        symbol_connections=[
            {"point_index":0,"symbol_uid":"board","symbol_port":0},
            {"point_index":1,"symbol_uid":"pl1","symbol_port":0},
            {"point_index":2,"symbol_uid":"pl2","symbol_port":0},
        ],
    )
    core.set_cable_symbol_connections(cable,cable.symbol_connections)
    return cable


def _legacy_file(path: Path, cable, *, placements=None, bindings=None, extra_cables=None):
    payload={
        "version":"0.54.3","source_file":"",
        "placements":[asdict(p) for p in (placements or [])],
        "cables":[asdict(cable)]+[asdict(c) for c in (extra_cables or [])],
        "texts":[],"layer_visibility":{},
        "cable_instance_articles":dict(bindings or {}),
    }
    path.write_text(json.dumps(payload),encoding="utf-8")


def test_split_chain_creates_one_real_cable_per_connection_span():
    cable=_legacy_chain()
    segments=core.split_cable_into_physical_segments(cable)
    assert len(segments)==2
    assert all(core.cable_is_physical_segment(c) for c in segments)
    assert [[x["symbol_uid"] for x in core.cable_symbol_connections(c)] for c in segments] == [
        ["board","pl1"],["pl1","pl2"]
    ]
    assert len({c.uid for c in segments})==2
    assert len({c.route_chain_uid for c in segments})==1
    assert {c.circuit_id for c in segments}=={"G05"}
    assert [c.cable_spec for c in segments]==["3G1,5","3G1,5"]


def test_legacy_section_settings_become_individual_cable_properties():
    cable=_legacy_chain()
    first,second=core.cable_connection_sections(cable)
    core.set_cable_route_section_mode(cable,first["a"],first["b"],"orthogonal")
    core.set_cable_spec_for_section(cable,second["a"],second["b"],"5G1,5")
    segments=core.split_cable_into_physical_segments(cable)
    assert [c.orthogonal for c in segments]==[True,False]
    assert [c.cable_spec for c in segments]==["3G1,5","5G1,5"]
    assert all(c.route_section_modes==[] and c.spec_section_overrides==[] for c in segments)


def test_legacy_project_migration_avoids_existing_cable_ids_and_copies_uniform_article(tmp_path):
    cable=_legacy_chain(uid="c1",cable_id="K01")
    existing=core.CablePlacement(points=[(0,10),(50,10)],uid="c2",cable_id="K02",cable_spec="3G1,5")
    path=tmp_path/"legacy.elplan.json"
    _legacy_file(path,cable,bindings={"c1":"662425"},extra_cables=[existing])
    doc=ProjectDocument.load(path)
    assert doc.raw["version"]==APP_VERSION=="0.59.83"
    assert [c.cable_id for c in doc.cables]==["K01","K03","K02"]
    migrated=doc.cables[:2]
    assert {doc.raw["cable_instance_articles"].get(c.uid) for c in migrated}=={"662425"}
    assert doc.dirty is True
    doc.save(path)
    saved=json.loads(path.read_text(encoding="utf-8"))
    assert saved["version"]=="0.59.83"
    assert all(core.cable_is_physical_segment(core.CablePlacement(**row)) for row in saved["cables"])


def test_mixed_legacy_article_binding_is_not_guessed_during_split(tmp_path):
    cable=_legacy_chain(uid="c1")
    second=core.cable_connection_sections(cable)[1]
    core.set_cable_spec_for_section(cable,second["a"],second["b"],"5G1,5")
    path=tmp_path/"mixed.elplan.json"
    _legacy_file(path,cable,bindings={"c1":"662425"})
    doc=ProjectDocument.load(path)
    assert [c.cable_spec for c in doc.cables]==["3G1,5","5G1,5"]
    assert doc.raw["cable_instance_articles"]=={}


def test_pl_box_references_follow_each_new_physical_cable(tmp_path):
    cable=_legacy_chain(uid="c1")
    pl=core.Placement(symbol="light_connection",x=100,y=0,uid="pl1")
    pl.pl_box_entries={
        "1":{"cable_uid":"c1","point_index":1,"leg":"before","note":"fra tavle"},
        "2":{"cable_uid":"c1","point_index":1,"leg":"after","note":"videre"},
    }
    pl.pl_box_wiring=[
        {"cable_uid":"c1","point_index":1,"leg":"before","core_id":"brown","function":"l","note":"in"},
        {"cable_uid":"c1","point_index":1,"leg":"after","core_id":"brown","function":"l","note":"out"},
    ]
    pl.pl_box_splices=[{
        "id":"w1","function":"l","connects_to_outlet":False,
        "members":[
            {"cable_uid":"c1","point_index":1,"leg":"before","core_id":"brown"},
            {"cable_uid":"c1","point_index":1,"leg":"after","core_id":"brown"},
        ],
    }]
    path=tmp_path/"pl_legacy.elplan.json"
    _legacy_file(path,cable,placements=[pl])
    doc=ProjectDocument.load(path)
    assert len(doc.cables)==2
    first,second=doc.cables
    migrated=doc.placements[0]
    entries=migrated.pl_box_entries
    assert entries["1"]=={"cable_uid":first.uid,"point_index":1,"leg":"endpoint","note":"fra tavle"}
    assert entries["2"]=={"cable_uid":second.uid,"point_index":0,"leg":"endpoint","note":"videre"}
    wiring={(r["cable_uid"],r["point_index"],r["leg"],r["core_id"],r["note"]) for r in migrated.pl_box_wiring}
    assert (first.uid,1,"endpoint","brown","in") in wiring
    assert (second.uid,0,"endpoint","brown","out") in wiring
    members={(m["cable_uid"],m["point_index"],m["leg"],m["core_id"]) for m in migrated.pl_box_splices[0]["members"]}
    assert members=={(first.uid,1,"endpoint","brown"),(second.uid,0,"endpoint","brown")}
    legs=core.cable_legs_at_symbol(doc.cables,"pl1")
    assert {(x["cable_uid"],x["leg"]) for x in legs}=={(first.uid,"endpoint"),(second.uid,"endpoint")}


def test_circuit_is_inferred_once_for_whole_migrated_string(tmp_path):
    cable=_legacy_chain(uid="c1")
    cable.circuit_id=""
    board=core.Placement(symbol="distribution_board",x=0,y=0,uid="board",group="G11")
    pl1=core.Placement(symbol="light_connection",x=100,y=0,uid="pl1")
    pl2=core.Placement(symbol="light_connection",x=200,y=0,uid="pl2")
    path=tmp_path/"infer.elplan.json"
    _legacy_file(path,cable,placements=[board,pl1,pl2])
    doc=ProjectDocument.load(path)
    assert len(doc.cables)==2
    assert {c.circuit_id for c in doc.cables}=={"G11"}


def test_pl_display_includes_physical_id_and_group():
    cable=core.CablePlacement(points=[(0,0),(10,0)],cable_id="K07",circuit_id="G05",label="Køkken")
    assert core.cable_pl_display(cable)=="K07 · G05 · Køkken"


def test_project_save_rejects_nonphysical_current_model(tmp_path):
    doc=ProjectDocument.from_cad(tmp_path/"plan.dxf")
    doc.cables=[_legacy_chain()]
    try:
        doc.save(tmp_path/"invalid.elplan.json")
    except ValueError as exc:
        assert "ét fysisk kabel pr. objekt" in str(exc)
    else:
        raise AssertionError("0.57.1 må ikke gemme en flerstop-kabelmodel")

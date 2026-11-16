from pathlib import Path
import json

from project_model import ProjectDocument


def test_load_and_roundtrip(tmp_path: Path):
    source = tmp_path / "floor.dxf"
    source.write_text("dummy", encoding="utf-8")
    path = tmp_path / "x.elplan.json"
    path.write_text(json.dumps({
        "version":"0.24.1",
        "source_file":str(source),
        "placements":[{"symbol":"socket","x":10,"y":20,"size":200,"label":"S01","group":"G01"}],
        "cables":[],"texts":[],"layer_visibility":{"Walls":True}
    }), encoding="utf-8")
    project = ProjectDocument.load(path)
    assert len(project.placements) == 1
    assert project.placements[0].label == "S01"
    out = tmp_path / "out.elplan.json"
    project.save(out)
    raw = json.loads(out.read_text(encoding="utf-8"))
    assert raw["version"] == "0.59.84"
    assert raw["placements"][0]["group"] == "G01"


def test_cable_length_helpers():
    import core_logic as core
    cable = core.CablePlacement(points=[(0, 0), (3000, 0), (3000, 4000)], cable_spec="3G1,5")
    assert abs(core.cable_route_length(cable) - 7000.0) < 1e-9
    assert abs(core.cable_length_metres(cable, 0.001) - 7.0) < 1e-9
    assert abs(core.cable_estimated_length_metres(cable, 0.001, 10.0) - 7.7) < 1e-9
    assert core.cable_length_metres(cable, None) is None


def test_cable_length_settings_roundtrip(tmp_path: Path):
    source = tmp_path / "floor.dxf"
    source.write_text("dummy", encoding="utf-8")
    project = ProjectDocument.from_cad(source)
    project.raw["cable_length_unit_mode"] = "calibrated"
    project.raw["cable_length_m_per_unit"] = 0.002
    project.raw["cable_length_reserve_percent"] = 12.5
    out = tmp_path / "lengths.elplan.json"
    project.save(out)
    loaded = ProjectDocument.load(out)
    assert loaded.raw["cable_length_unit_mode"] == "calibrated"
    assert loaded.raw["cable_length_m_per_unit"] == 0.002
    assert loaded.raw["cable_length_reserve_percent"] == 12.5

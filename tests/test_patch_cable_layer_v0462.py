from __future__ import annotations

import json
from pathlib import Path

import ezdxf

import core_logic as core
from project_model import ProjectDocument, cable_from_raw, APP_VERSION


def test_patch_cable_has_dedicated_layer_and_type():
    assert core.PATCH_CABLE_LAYER == "EL-PATCHKABLER"
    assert core.CABLE_TYPES["Patchkabel"] == core.PATCH_CABLE_LAYER
    assert core.cable_type_display(core.PATCH_CABLE_LAYER) == "Patchkabel"
    assert core.PATCH_CABLE_LAYER in core.GENERATED_LAYER_COLORS


def test_patch_cable_layer_roundtrip(tmp_path: Path):
    cable = cable_from_raw({
        "points": [[0, 0], [100, 20]],
        "layer": core.PATCH_CABLE_LAYER,
        "cable_spec": "CAT7 S/FTP",
        "cable_id": "P01",
        "uid": "patch-layer-roundtrip",
    })
    assert cable.layer == core.PATCH_CABLE_LAYER

    doc = ProjectDocument()
    doc.raw = {"version": APP_VERSION, "source_file": "", "cable_type": "Patchkabel"}
    doc.cables = [cable]
    path = tmp_path / "patch.elplan.json"
    doc.path = path
    doc.save()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == "0.59.84"
    assert raw["cables"][0]["layer"] == "EL-PATCHKABLER"

    loaded = ProjectDocument.load(path)
    assert loaded.cables[0].layer == core.PATCH_CABLE_LAYER


def test_patch_cable_dxf_keeps_dedicated_layer():
    doc = ezdxf.new()
    core.ensure_layers(doc)
    msp = doc.modelspace()
    cable = core.CablePlacement(
        points=[(0, 0), (10, 10)],
        layer=core.PATCH_CABLE_LAYER,
        cable_spec="CAT7 S/FTP",
        cable_id="P01",
    )
    core.add_cable_to_dxf(msp, cable)
    poly = next(e for e in msp if e.dxftype() == "LWPOLYLINE")
    assert poly.dxf.layer == core.cable_effective_layer(cable)
    assert poly.dxf.layer.startswith(core.PATCH_CABLE_LAYER)
    assert core.PATCH_CABLE_LAYER in doc.layers


def test_qt_source_has_separate_patch_cable_quick_filter():
    source = Path("qt_app.py").read_text(encoding="utf-8") + Path("qt_cable_panel.py").read_text(encoding="utf-8")
    assert 'QAction("Patchkabler", self, checkable=True)' in source
    assert '"patch_cables": bool(self.app_settings.get("quick_show_patch_cables", True))' in source
    assert 'def _quick_cable_visible(self, cable: core.CablePlacement)' in source
    assert '== core.PATCH_CABLE_LAYER' in source
    assert '["Kabel", "Patchkabel", "Ledning"]' in source
    assert 'core.PATCH_CABLE_LAYER if _typ=="Patchkabel"' in source
    assert 'core.PATCH_CABLE_LAYER if self.cable_type_combo.currentText()=="Patchkabel"' in source

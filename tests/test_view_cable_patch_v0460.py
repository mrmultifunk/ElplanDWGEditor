from __future__ import annotations

import json
from pathlib import Path

import ezdxf

import core_logic as core
from elplan_project.project_model import ProjectDocument, cable_from_raw, APP_VERSION


def test_patch_panel_is_data_symbol_with_twelve_ports():
    assert core.SYMBOLS["Patchpanel / datacentral (12 porte)"] == "patch_panel"
    assert core.symbol_layer("patch_panel") == core.DATA_LAYER
    ports = core.symbol_connection_points("patch_panel", 200.0)
    assert len(ports) == 12
    assert len(set(ports)) == 12
    assert core.symbol_mount_points("patch_panel", 200.0) == [(0.0, 0.0)]
    vectors = core.symbol_primitives("patch_panel", 200.0)
    assert vectors
    # Panel outline + twelve small port boxes must produce many vector segments.
    assert sum(1 for row in vectors if row[0] == "line") >= 52


def test_cable_colour_and_line_style_roundtrip(tmp_path: Path):
    raw = {
        "points": [[0, 0], [100, 50]],
        "layer": core.CABLE_LAYER,
        "line_width": 0.42,
        "color": "#2468ac",
        "line_style": "dash",
        "cable_spec": "CAT6A F/UTP",
        "cable_id": "ETH01",
        "uid": "cable-style-test",
    }
    cable = cable_from_raw(raw)
    assert cable.color == "#2468ac"
    assert cable.line_style == "dash"

    doc = ProjectDocument()
    doc.raw = {"version": APP_VERSION, "source_file": ""}
    doc.cables = [cable]
    target = tmp_path / "styled.elplan.json"
    doc.path = target
    doc.save()
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["cables"][0]["color"] == "#2468ac"
    assert saved["cables"][0]["line_style"] == "dash"

    loaded = ProjectDocument.load(target)
    assert loaded.cables[0].color == "#2468ac"
    assert loaded.cables[0].line_style == "dash"


def test_old_cables_get_safe_visual_defaults():
    cable = cable_from_raw({
        "points": [[0, 0], [1, 1]],
        "line_width": 0.35,
        "uid": "legacy-cable-style",
    })
    assert cable.color == core.DEFAULT_CABLE_COLOR
    assert cable.line_style == core.DEFAULT_CABLE_LINE_STYLE


def test_cable_style_aliases_and_dxf_output():
    assert core.normalize_cable_line_style("Stiplet") == "dash"
    assert core.normalize_cable_line_style("prikket") == "dot"
    assert core.normalize_cable_line_style("streg-prik") == "dashdot"
    doc = ezdxf.new()
    msp = doc.modelspace()
    cable = core.CablePlacement(points=[(0, 0), (10, 5)], color="#123456", line_style="dashdot")
    core.add_cable_to_dxf(msp, cable)
    entity = list(msp)[0]
    assert entity.dxf.linetype == "DASHDOT"
    assert tuple(entity.rgb) == (18, 52, 86)


def test_qt_source_exposes_fast_view_and_cable_visual_controls():
    app = Path("elplan_qt/qt_app.py").read_text(encoding="utf-8") + Path("elplan_qt/qt_cable_panel.py").read_text(encoding="utf-8")
    graphics = Path("elplan_qt/qt_graphics.py").read_text(encoding="utf-8")
    for token in ("act_quick_cad", "act_quick_symbols", "act_quick_cables", "act_quick_text", "_apply_quick_visibility"):
        assert token in app
    assert 'advanced_form.addRow("Farve", self.cable_color)' in app
    assert 'advanced_form.addRow("Linjetype", self.cable_line_style)' in app
    assert "_qt_cable_pen_style" in graphics
    assert 'getattr(self.cable,"line_style"' in graphics

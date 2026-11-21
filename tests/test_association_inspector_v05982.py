from pathlib import Path

import core_logic as core
from elplan_project.project_model import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_version_and_progressive_inspector_source():
    assert APP_VERSION == core.APP_VERSION == "0.59.85"
    source = (ROOT / "elplan_qt/qt_app.py").read_text(encoding="utf-8")
    assert 'QPushButton("Tilføj / fjern lys…")' in source
    assert 'self.assoc_button.setText("Tilknyt til afbryder…")' in source
    assert 'outer.addWidget(self.assoc_group)' in source
    assert 'self.assoc_group.setVisible(key=="connect"' in source
    assert 'DisclosureSection("Montage og indkøb"' in source
    assert 'DisclosureSection("Kombi-mærkning"' in source
    assert 'DisclosureSection("Artikler / BOM"' in source


def test_locked_placement_does_not_block_logical_light_workflow():
    source = (ROOT / "elplan_qt/qt_app.py").read_text(encoding="utf-8")
    picker = source[source.index("    def _refresh_association_source_picker"):source.index("    def _association_anchor")]
    activate = source[source.index("    def _activate_association_source"):source.index("    def start_association_mode")]
    start = source[source.index("    def start_association_mode"):source.index("    def _finish_active_association")]
    same_switch = source[source.index("    def group_selected_lights_same_switch"):source.index("    # ---------- Free text")]
    assert "p.locked" not in picker
    assert "p.locked" not in activate
    assert "placement.locked" not in start
    assert 'getattr(switch,"locked"' not in same_switch
    assert 'self.assoc_button.setEnabled(role in ("switch","light"))' in source
    assert "self.clear_assoc_button.setEnabled(has_assoc)" in source


def test_context_action_describes_the_selected_side_of_relation():
    source = (ROOT / "elplan_qt/qt_workspace.py").read_text(encoding="utf-8")
    assert '"Redigér tændinger…" if role=="switch" else "Tilknyt afbryder…"' in source
    assert "self.act_ctx_associate.setEnabled(role in (\"switch\",\"light\"))" in source

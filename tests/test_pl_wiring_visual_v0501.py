from pathlib import Path


def test_version_0504():
    import core_logic as core
    from project_model import APP_VERSION
    assert core.APP_VERSION == APP_VERSION == "0.59.81"


def test_visual_editor_supports_manual_wago_splices_and_loose_ends():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "terminal=QRectF(body.right()+terminal_gap" in source
    assert "def _wago_layout" in source
    assert "def _draw_wago_blocks" in source
    assert "def _wago_layout" in source and "core.normalize_pl_box_splices(splices)" in source
    assert "marker={\"reserve\":\"R\",\"unused\":\"X\",\"\":\"?\"}" in source
    assert "wago_map=self._wago_layout(body,terminal_items,wiring,conductor_meta,self._splices)" in source
    assert 'QPushButton("Frigør valgt leder")' in source
    assert 'add_btn=box.addButton(f"Opret Wago {label} og forbind"' in source


def test_manual_wago_state_is_persisted():
    source=Path("project_model.py").read_text(encoding="utf-8")
    assert '"pl_box_entries": {}' in source
    assert '"pl_box_wiring": []' in source
    assert '"pl_box_splices": []' in source
    assert 'core.reconcile_pl_box_splices' in source


def test_brown_conductor_color_is_lighter_for_readability():
    source=Path("core_logic.py").read_text(encoding="utf-8")
    assert "#a87943" in source

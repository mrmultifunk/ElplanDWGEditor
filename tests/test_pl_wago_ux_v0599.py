from pathlib import Path


def test_version_0599():
    import core_logic as core
    from project_model import APP_VERSION
    assert APP_VERSION == core.APP_VERSION == "0.59.73"


def test_wago_workflow_is_function_based_in_primary_ui():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "def _show_function_context_menu" in source
    assert "def _show_drop_function_menu" in source
    assert 'Forbind valgt leder direkte til' in source
    assert 'Via eksisterende Wago' in source
    assert '+ Opret ny Wago for' in source
    assert 'functionAction=Signal(str,str)' in source


def test_old_wago_combo_is_hidden_but_kept_for_compatibility():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert 'self.wago_combo=QComboBox()' in source
    assert 'self.wago_combo.hide()' in source
    assert 'self.wago_summary_label=QLabel' in source
    assert 'QPushButton("+ Wago → udtag")' in source
    assert 'QPushButton("Administrér Wago…")' in source


def test_visual_wago_block_shows_physical_capacity_and_mode():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert 'article_capacity=core.pl_wago_article_capacity(article_no)' in source
    assert 'needed_ports=max(1,core.pl_wago_required_ports(len(members),connects))' in source
    assert 'f"WAGO · {info[\'label\']}"' in source
    assert 'f"{needed}/{cap} pladser"' in source
    assert 'f"{member_count} ledere + 1 bro"' in source


def test_clicking_wago_without_selected_conductor_opens_editor():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert 'self.spliceAction.emit(sid,"edit")' in source


def test_capacity_help_requires_explicit_user_action():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert 'box.addButton(f"Opret Wago {label} og forbind"' in source
    assert 'if box.clickedButton()!=add_btn:return False' in source

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bom_manager_refreshes_only_visible_top_level_workflow():
    source = (ROOT / "elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    assert 'self._tab_dirty=set(self._tab_keys.values())' in source
    assert 'self._refresh_current_tab(force=True)' in source
    assert 'self._refresh_library_filters()\n        self._refresh_assemblies();' not in source
    assert 'self.tabs.currentChanged.connect(self._top_level_tab_changed)' in source


def test_bom_manager_remembers_last_workflow_and_collapses_help():
    source = (ROOT / "elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    assert 'bom_manager_last_tab' in source
    assert 'DisclosureSection("Sådan fungerer Artikler og BOM"' in source
    assert 'self.tabs.setDocumentMode(True)' in source


def test_cable_disclosures_do_not_repeat_groupbox_frames():
    source = (ROOT / "elplan_qt/qt_cable_panel.py").read_text(encoding="utf-8")
    assert 'drawing_group = QWidget()' in source
    assert 'advanced_group = QWidget()' in source
    assert 'visual_group = QWidget()' in source
    assert 'DisclosureSection("Avancerede kabeldata"' in source
    assert 'DisclosureSection("Parallel visning"' in source

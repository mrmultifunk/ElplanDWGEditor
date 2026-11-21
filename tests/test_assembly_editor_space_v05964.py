from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


def _editor_source():
    source=(ROOT/"elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    start=source.index("class AssemblyEditDialog")
    end=source.index("class BomManagerDialog",start)
    return source[start:end]


def test_secondary_assembly_fields_are_collapsible_and_table_stays_primary():
    source=_editor_source()
    assert 'DisclosureSection(\n            "Klassifikation og navneparametre"' in source
    assert 'DisclosureSection(\n            "Beskrivelse og note"' in source
    assert 'DisclosureSection(\n            "Tilføj eller opdatér komponent"' in source
    assert 'get("assembly_editor_classification_expanded",False)' in source
    assert 'get("assembly_editor_description_expanded",False)' in source
    assert 'get("assembly_editor_component_form_expanded",True)' in source
    assert "root.addWidget(self.table,1)" in source
    assert "self.table.setMinimumHeight(140)" in source


def test_maximise_table_collapses_every_secondary_section_and_focuses_table():
    source=_editor_source()
    block=source[source.index("def _maximize_component_table"):source.index("def _persist_editor_sections")]
    assert "self.classification_disclosure.setExpanded(False)" in block
    assert "self.description_disclosure.setExpanded(False)" in block
    assert "self._set_component_panel_visible(False)" in block
    assert "self.table.setFocus()" in block
    assert 'QPushButton("Maksimér tabel")' in source


def test_disclosure_state_is_remembered_without_changing_assembly_data():
    source=_editor_source()
    assert '"assembly_editor_classification_expanded":self.classification_disclosure.isExpanded()' in source
    assert '"assembly_editor_description_expanded":self.description_disclosure.isExpanded()' in source
    assert '"assembly_editor_component_form_expanded":self.component_disclosure.isExpanded()' in source
    for field in ("description", "category", "variant", "tags", "notes", "naming"):
        assert f'"{field}"' in source

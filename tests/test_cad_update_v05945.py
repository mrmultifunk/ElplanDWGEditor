from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_version_and_update_action_are_present():
    project=(ROOT/'project_model.py').read_text(encoding='utf-8')
    app=(ROOT/'qt_app.py').read_text(encoding='utf-8')
    workflow=(ROOT/'qt_project_open.py').read_text(encoding='utf-8')
    assert 'APP_VERSION = "0.59.80"' in project
    assert 'Opdatér plantegning…' in app
    assert 'self.act_update_cad.triggered.connect(self.update_cad)' in app
    assert 'def update_cad(self)' in workflow


def test_update_parses_before_replacing_active_document():
    source=(ROOT/'qt_project_open.py').read_text(encoding='utf-8')
    parse_pos=source.index('new_doc=core.load_document(str(source))')
    extract_pos=source.index('new_primitives,_counts=core.extract_cad_primitives(new_doc)')
    replace_pos=source.index('self.doc=new_doc')
    assert parse_pos < extract_pos < replace_pos


def test_update_preserves_project_objects_and_only_changes_source_and_cad():
    source=(ROOT/'qt_project_open.py').read_text(encoding='utf-8')
    section=source[source.index('def _replace_project_cad_background'):source.index('def update_cad')]
    assert 'self.project.source_file=self._project_source_reference(source)' in section
    assert 'self.project.placements=' not in section
    assert 'self.project.cables=' not in section
    assert 'self.project.rooms=' not in section
    assert 'self.project.texts=' not in section
    assert 'self._rebuild_scene()' in section

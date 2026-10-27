from pathlib import Path


def test_article_database_double_click_assigns_instead_of_editing():
    source=Path('qt_articles.py').read_text(encoding='utf-8')
    assert 'self.library_table.doubleClicked.connect(self._assign_selected_library_article)' in source
    assert 'self.library_table.doubleClicked.connect(self._edit_article)' not in source
    assert 'def _assign_article_to_current_part' in source
    assert 'def _open_library_for_assignment' in source
    assert 'Find i Artikeldatabase…' in source
    assert 'Tilknyt valgt artikel' in source
    assert 'Tilknytter til:' in source
    assert 'Redigér artikel…' in source


def test_article_assignment_has_explicit_target_and_keeps_quick_picker_secondary():
    source=Path('qt_articles.py').read_text(encoding='utf-8')
    assert 'self.assignment_target_title' in source
    assert 'self.library_target_title' in source
    assert 'self.library_assignment_status' in source
    assert 'Hurtigvalg' in source
    assert 'Dobbeltklik en artikel' in source
    assert 'Denne post er en kabelartikel. Tilknyt den under fanen Kabler.' in source


def test_pl_hover_title_contains_group_and_marking():
    source=Path('qt_app.py').read_text(encoding='utf-8')
    start=source.index('def _pl_entry_hover_payload')
    end=source.index('def _symbol_hover_payload',start)
    block=source[start:end]
    assert 'group=str(getattr(placement,"group","")' in block
    assert 'label=str(getattr(placement,"label","")' in block
    assert 'ident=" · ".join(x for x in (group,label) if x)' in block
    assert '"title":f"PL-dåse · {ident}"' in block

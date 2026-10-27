from pathlib import Path


def test_article_tables_are_user_resizable_and_persistent():
    source = Path('qt_articles.py').read_text(encoding='utf-8')
    helpers = Path('qt_table_utils.py').read_text(encoding='utf-8')
    assert 'QHeaderView.ResizeMode.Interactive' in helpers
    assert 'article_tables/{key}/header' in helpers
    assert 'header.restoreState(state)' in helpers
    assert 'saveState()' in helpers
    assert 'Tilpas kolonner' in source
    assert 'Nulstil bredder' in source


def test_article_picker_full_text_fallback_and_geometry_memory():
    source = Path('qt_articles.py').read_text(encoding='utf-8')
    helpers = Path('qt_table_utils.py').read_text(encoding='utf-8')
    assert 'item.setToolTip(value)' in helpers
    assert '_restore_dialog_geometry(self,"article_picker")' in source
    assert '_restore_dialog_geometry(self,"bom_manager")' in source
    assert 'setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)' in helpers


def test_article_management_tables_use_persistent_layouts():
    source = Path('qt_articles.py').read_text(encoding='utf-8')
    for key in (
        'article_picker', 'assembly_editor', 'bom_assignment', 'bom_assemblies',
        'bom_result_v05923', 'bom_missing',
    ):
        assert f'"{key}"' in source
    # 0.59.31 changes the article browser layout, so the database table gets
    # a new key rather than applying old widths to the favorite/facet columns.
    assert '"bom_standard_library_v05923"' in source
    assert '"bom_article_database_v05929"' in source

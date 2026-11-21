from pathlib import Path


def test_picker_and_standard_library_use_model_based_tables():
    source = Path("elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    table_utils = Path("elplan_qt/qt_table_utils.py").read_text(encoding="utf-8")
    assert "class ArticleTableModel(QAbstractTableModel)" in table_utils
    picker = source[source.index("class ArticlePickerDialog"):source.index("class AssemblyEditDialog")]
    assert "self.table=QTableView()" in picker
    assert "self.table_model=ArticleTableModel" in picker
    assert "self.table.setModel(self.table_model)" in picker
    assert "self.table.setItem(" not in picker
    standard = source[source.index("def _build_predefined_tab"):source.index("def _build_library_tab")]
    assert "self.std_table=QTableView()" in standard
    assert "self.std_table_model=ArticleTableModel" in standard
    assert "self.std_table.setModel(self.std_table_model)" in standard


def test_dynamic_article_refreshes_do_not_rebuild_widget_cells():
    source = Path("elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    picker = source[source.index("class ArticlePickerDialog"):source.index("class AssemblyEditDialog")]
    assert "self.table_model.set_rows(visible)" in picker
    assert "_populate_visible_chunk" not in picker
    refresh_start = source.index("    def _refresh_predefined(self,*_):", source.index("class BomManagerDialog"))
    refresh_end = source.index("    def _predefined_selection_changed", refresh_start)
    standard_refresh = source[refresh_start:refresh_end]
    assert "self.std_table_model.set_rows(visible,local)" in standard_refresh
    assert "clearContents()" not in standard_refresh
    assert "setRowCount(" not in standard_refresh


def test_article_preview_debounces_and_cancels_old_requests():
    source = Path("elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    preview = source[source.index("class ArticleVisualPreview"):source.index("class ArticlePickerDialog")]
    assert "self._load_timer.setInterval(300)" in preview
    assert "if not reply.isFinished(): reply.abort()" in preview
    assert "self._load_timer.start()" in preview

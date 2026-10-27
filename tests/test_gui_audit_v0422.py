from pathlib import Path


def test_forms_and_dialog_buttons_share_common_polish():
    source = Path("qt_app.py").read_text(encoding="utf-8") + Path("qt_theme.py").read_text(encoding="utf-8") + Path("qt_widgets.py").read_text(encoding="utf-8") + Path("qt_articles.py").read_text(encoding="utf-8")
    assert "class QFormLayout(_QtQFormLayout)" in source
    assert "self.setHorizontalSpacing(12)" in source
    assert "self.setVerticalSpacing(8)" in source
    assert "class QDialogButtonBox(_QtQDialogButtonBox)" in source
    assert 'button.setObjectName("primaryButton")' in source
    assert 'button.setObjectName("dangerButton")' in source
    assert '"Annuller"' in source


def test_theme_has_complete_control_states_and_visual_roles():
    source = Path("qt_app.py").read_text(encoding="utf-8") + Path("qt_theme.py").read_text(encoding="utf-8") + Path("qt_widgets.py").read_text(encoding="utf-8") + Path("qt_articles.py").read_text(encoding="utf-8")
    for token in (
        "QMainWindow, QDialog, QMessageBox",
        "QDockWidget::close-button",
        "QLineEdit:hover",
        "QComboBox QAbstractItemView",
        "QPushButton#dangerButton",
        "QFrame#detailPanel",
        "QLabel#infoBanner",
        "QTableView:focus",
        "QScrollBar:horizontal",
    ):
        assert token in source


def test_common_tables_receive_same_row_header_and_scroll_polish():
    source = Path("qt_table_utils.py").read_text(encoding="utf-8")
    assert "table.setAlternatingRowColors(True)" in source
    assert "vertical.setVisible(False)" in source
    assert "vertical.setDefaultSectionSize(28)" in source
    assert "header.setDefaultAlignment" in source


def test_article_picker_and_standard_library_have_bounded_detail_panels():
    source = Path("qt_app.py").read_text(encoding="utf-8") + Path("qt_theme.py").read_text(encoding="utf-8") + Path("qt_widgets.py").read_text(encoding="utf-8") + Path("qt_articles.py").read_text(encoding="utf-8")
    assert 'filter_box=QGroupBox("Filtre")' in source
    assert 'right_panel.setObjectName("detailPanel")' in source
    assert 'detail.setObjectName("detailPanel")' in source
    assert "self.std_search.setClearButtonEnabled(True)" in source


def test_colour_buttons_show_actual_selected_colour():
    source = Path("qt_app.py").read_text(encoding="utf-8") + Path("qt_theme.py").read_text(encoding="utf-8") + Path("qt_widgets.py").read_text(encoding="utf-8") + Path("qt_articles.py").read_text(encoding="utf-8")
    assert "def _set_color_button" in source
    assert "_set_color_button(self.prop_color" in source
    assert "_set_color_button(color,item.color)" in source


def test_combo_boxes_use_deterministic_visible_chevron():
    source = Path("qt_app.py").read_text(encoding="utf-8") + Path("qt_theme.py").read_text(encoding="utf-8") + Path("qt_widgets.py").read_text(encoding="utf-8") + Path("qt_articles.py").read_text(encoding="utf-8")
    assert "QComboBox as _QtQComboBox" in source
    assert "class QComboBox(_QtQComboBox)" in source
    assert "def paintEvent(self, event)" in source
    assert 'self.setProperty("elplanChevron", True)' in source
    assert 'QComboBox[elplanChevron="true"]::down-arrow { image: none' in source


def test_primary_secondary_and_destructive_actions_are_visually_distinct():
    source = Path("qt_app.py").read_text(encoding="utf-8") + Path("qt_theme.py").read_text(encoding="utf-8") + Path("qt_widgets.py").read_text(encoding="utf-8") + Path("qt_articles.py").read_text(encoding="utf-8")
    assert '_set_role(QPushButton("Gem"), "primaryButton")' in source
    assert '_set_role(QPushButton("Brug stykliste"), "primaryButton")' in source
    assert '_set_role(QPushButton("Fjern tilknytning"), "dangerButton")' in source
    assert '_set_role(QPushButton("Gendan alle viste"), "quietButton")' in source

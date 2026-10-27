from __future__ import annotations

"""Shared Qt table models and persistent table/dialog UI state."""

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSettings
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidgetItem, QMenu

import price_display

_TABLE_SETTINGS_ORG = "ElplanDWGEditor"
_TABLE_SETTINGS_APP = "ElplanDWGEditor"


def _ui_settings():
    return QSettings(_TABLE_SETTINGS_ORG, _TABLE_SETTINGS_APP)


def _save_table_header_state(table):
    key = str(getattr(table, "_elplan_table_key", "") or "")
    if not key:
        return
    _ui_settings().setValue(f"article_tables/{key}/header", table.horizontalHeader().saveState())


def _table_column_count(table):
    """Kolonneantal for både item-baserede og model-baserede Qt-tabeller."""
    if hasattr(table, "columnCount"):
        return table.columnCount()
    model = table.model() if hasattr(table, "model") else None
    return model.columnCount() if model is not None else 0


def _show_table_header_menu(table, pos):
    menu = QMenu(table)
    fit = menu.addAction("Tilpas kolonner til indhold")
    reset = menu.addAction("Nulstil kolonnebredder")
    chosen = menu.exec(table.horizontalHeader().mapToGlobal(pos))
    if chosen is fit:
        _fit_table_columns(table)
    elif chosen is reset:
        _reset_table_columns(table)


def _configure_resizable_table(table, key, default_widths):
    """Gør en tabel brugerjusterbar og husk kolonnebredder på tværs af projekter."""
    table._elplan_table_key = str(key)
    table._elplan_default_widths = tuple(int(x) for x in default_widths)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setStretchLastSection(False)
    header.setSectionsMovable(True)
    header.setHighlightSections(False)
    header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    if not bool(getattr(table, "_elplan_header_menu_connected", False)):
        header.customContextMenuRequested.connect(lambda pos, t=table: _show_table_header_menu(t, pos))
        header.sectionDoubleClicked.connect(lambda col, t=table: (t.resizeColumnToContents(col), _save_table_header_state(t)))
        table._elplan_header_menu_connected = True
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setAlternatingRowColors(True)
    table.setShowGrid(True)
    table.setCornerButtonEnabled(False)
    vertical = table.verticalHeader() if hasattr(table, "verticalHeader") else None
    if vertical is not None:
        vertical.setVisible(False)
        vertical.setDefaultSectionSize(28)
        vertical.setMinimumSectionSize(24)
    header.setMinimumSectionSize(45)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    for col, width in enumerate(table._elplan_default_widths):
        if col < _table_column_count(table):
            table.setColumnWidth(col, max(45, width))
    state = _ui_settings().value(f"article_tables/{key}/header")
    if state is not None:
        try:
            header.restoreState(state)
        except (TypeError, ValueError):
            pass
    header.sectionResized.connect(lambda *_args, t=table: _save_table_header_state(t))
    header.sectionMoved.connect(lambda *_args, t=table: _save_table_header_state(t))


def _fit_table_columns(table):
    """Auto-fit efter det aktuelle indhold og behold derefter manuel resize."""
    table.resizeColumnsToContents()
    header = table.horizontalHeader()
    for col in range(_table_column_count(table)):
        table.setColumnWidth(col, max(table.columnWidth(col), header.sectionSizeHint(col) + 8, 55))
    _save_table_header_state(table)


def _reset_table_columns(table):
    defaults = tuple(getattr(table, "_elplan_default_widths", ()) or ())
    key = str(getattr(table, "_elplan_table_key", "") or "")
    if key:
        _ui_settings().remove(f"article_tables/{key}/header")
    for col, width in enumerate(defaults):
        if col < _table_column_count(table):
            table.setColumnWidth(col, max(45, int(width)))
    _save_table_header_state(table)


def _table_item(text, user_data=None):
    """Tabelcelle med fuld tekst i tooltip, selv når kolonnen er smal."""
    value = str(text or "")
    item = QTableWidgetItem(value)
    if value:
        item.setToolTip(value)
    if user_data is not None:
        item.setData(Qt.ItemDataRole.UserRole, user_data)
    return item


class ArticleTableModel(QAbstractTableModel):
    """Letvægtsmodel til artikelvisninger uden tusindvis af QTableWidgetItem-objekter."""

    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self._columns = tuple(columns)
        self._rows = []
        self._sort_column = -1
        self._sort_order = Qt.SortOrder.AscendingOrder
        self._marked_article_nos = set()
        self._price_vat_mode = price_display.VAT_MODE_EXCL

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal and 0 <= section < len(self._columns):
            if self._columns[section][1] == "__price__":
                return f"Pris {price_display.vat_caption(self._price_vat_mode)}"
            return self._columns[section][0]
        return None

    def _price_text(self, article):
        value = price_display.to_display_amount(article.get("unit_price"), self._price_vat_mode)
        if value is None or str(value).strip() == "":
            return "—"
        try:
            number = f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except (TypeError, ValueError):
            return "—"
        prefix="~ " if str(article.get("price_status","") or "").casefold().startswith("est") else ""
        return f"{prefix}{number} {str(article.get('price_currency', 'DKK') or 'DKK').upper()}"

    def set_price_vat_mode(self, vat_mode):
        mode = price_display.normalize_vat_mode(vat_mode)
        if mode == self._price_vat_mode:
            return
        self._price_vat_mode = mode
        price_columns = [i for i, (_title, key) in enumerate(self._columns) if key == "__price__"]
        for column in price_columns:
            self.headerDataChanged.emit(Qt.Orientation.Horizontal, column, column)
            if self._rows:
                self.dataChanged.emit(
                    self.index(0, column), self.index(len(self._rows) - 1, column),
                    [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole],
                )

    def _display_value(self, article, column):
        key = self._columns[column][1]
        value = self._price_text(article) if key == "__price__" else str(article.get(key, "") or "")
        if column == 0 and str(article.get("article_no", "") or "") in self._marked_article_nos:
            value += "  ✓"
        return value

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)) or not (0 <= index.column() < len(self._columns)):
            return None
        article = self._rows[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            value = self._display_value(article, index.column())
            return value if value else None
        if role == Qt.ItemDataRole.UserRole:
            return str(article.get("article_no", "") or "")
        return None

    def set_rows(self, rows, marked_article_nos=None):
        self.beginResetModel()
        self._rows = list(rows)
        if marked_article_nos is not None:
            self._marked_article_nos = set(marked_article_nos)
        if self._sort_column >= 0:
            self._rows.sort(key=lambda a: self._sort_key(a, self._sort_column), reverse=self._sort_order == Qt.SortOrder.DescendingOrder)
        self.endResetModel()

    def clear_sort(self):
        """Return to the caller-provided row order until the user sorts a column."""
        self._sort_column = -1

    def set_marked_article_nos(self, article_nos):
        new_marks = set(article_nos or ())
        if new_marks == self._marked_article_nos:
            return
        self._marked_article_nos = new_marks
        if self._rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._rows) - 1, 0), [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole])

    def _sort_key(self, article, column):
        key = self._columns[column][1]
        if key == "__price__":
            try:
                return (1, float(article.get("unit_price")))
            except (TypeError, ValueError):
                return (0, 0.0)
        return str(article.get(key, "") or "").casefold()

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        if not (0 <= column < len(self._columns)):
            return
        persistent=list(self.persistentIndexList())
        identities=[(self.article_no_at(index.row()),index.column()) for index in persistent]
        self.layoutAboutToBeChanged.emit()
        self._sort_column = column
        self._sort_order = order
        self._rows.sort(key=lambda a: self._sort_key(a, column), reverse=order == Qt.SortOrder.DescendingOrder)
        if persistent:
            remapped=[]
            for article_no,col in identities:
                row=self.row_for_article_no(article_no)
                remapped.append(self.index(row,col) if row>=0 else QModelIndex())
            self.changePersistentIndexList(persistent,remapped)
        self.layoutChanged.emit()

    def article_at(self, row):
        return self._rows[row] if 0 <= row < len(self._rows) else {}

    def article_no_at(self, row):
        return str(self.article_at(row).get("article_no", "") or "")

    def row_for_article_no(self, article_no):
        wanted = str(article_no or "")
        for row, article in enumerate(self._rows):
            if str(article.get("article_no", "") or "") == wanted:
                return row
        return -1


def _restore_dialog_geometry(dialog, key):
    settings = _ui_settings()
    geometry = settings.value(f"article_dialogs/{key}/geometry")
    if geometry is not None:
        try:
            dialog.restoreGeometry(geometry)
        except (TypeError, ValueError):
            pass
    dialog.finished.connect(lambda _result, d=dialog, k=key: _ui_settings().setValue(f"article_dialogs/{k}/geometry", d.saveGeometry()))


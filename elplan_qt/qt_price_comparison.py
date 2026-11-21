from __future__ import annotations

"""Retailer price comparison dialog."""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from elplan_catalog import price_display
from elplan_qt.qt_ui import configure_modern_dialog, make_dialog_header
from elplan_qt.qt_widgets import QComboBox, _set_role


def _money(value, currency="DKK"):
    if value is None:
        return "—"
    number = f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{number} {str(currency or 'DKK').upper()}"


class PriceComparisonDialog(QDialog):
    def __init__(self, parent, article, price_record=None, vat_mode="excl"):
        super().__init__(parent)
        self.article = dict(article or {})
        self.price_record = dict(price_record or {})
        if not self.price_record.get("price_observations"):
            self.price_record["price_observations"] = list(self.article.get("price_observations", []) or [])
        configure_modern_dialog(self, title="Sammenlign forhandlerpriser", size=(1040, 600), minimum_size=(780, 470))

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        root.addWidget(make_dialog_header(
            "Prissammenligning",
            f"{self.article.get('article_no', '')} · {self.article.get('description', '')}",
            eyebrow="FORHANDLERE",
        ))

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Prisvisning"))
        self.vat_mode_combo = QComboBox()
        self.vat_mode_combo.addItem("Ekskl. moms", price_display.VAT_MODE_EXCL)
        self.vat_mode_combo.addItem("Inkl. moms", price_display.VAT_MODE_INCL)
        index = self.vat_mode_combo.findData(price_display.normalize_vat_mode(vat_mode))
        self.vat_mode_combo.setCurrentIndex(max(0, index))
        self.vat_mode_combo.currentIndexChanged.connect(self._refresh)
        controls.addWidget(self.vat_mode_combo)
        controls.addStretch(1)
        self.summary = QLabel("")
        self.summary.setObjectName("accentText")
        controls.addWidget(self.summary)
        root.addLayout(controls)

        self.table = QTableWidget(0, 8, self)
        self.table.setHorizontalHeaderLabels((
            "Forhandler", "Enhedspris", "Pris pr.", "Pakkepris",
            "Forskel til billigste", "Kontrolleret", "Match", "Link",
        ))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(lambda *_: self._open_selected())
        root.addWidget(self.table, 1)

        note = QLabel(
            "Enhedspriser er normaliseret til samme pris pr. enhed. Pakkeprisen vises separat. "
            "Priser i forskellige valutaer eller enheder vurderes i hver sin gruppe."
        )
        note.setWordWrap(True)
        note.setObjectName("sectionHint")
        root.addWidget(note)

        footer = QHBoxLayout()
        self.open_button = _set_role(QPushButton("Åbn valgt hos forhandler"), "quietButton")
        self.open_button.clicked.connect(self._open_selected)
        footer.addWidget(self.open_button)
        footer.addStretch(1)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        footer.addWidget(close)
        root.addLayout(footer)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self._refresh()

    def selected_vat_mode(self):
        return price_display.normalize_vat_mode(self.vat_mode_combo.currentData())

    def _refresh(self, *_):
        rows = price_display.comparison_rows(self.price_record, self.selected_vat_mode())
        self._rows = rows
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            difference = "Billigst"
            if not row["is_cheapest"]:
                percent=f"{row['difference_percent']:.1f}".replace(".",",")
                difference = f"+{_money(row['difference'], row['currency'])} · {percent} %"
            package = _money(row["package_price"], row["currency"]) if row["package_price"] is not None else "—"
            if package != "—" and row["package_label"]:
                package += f" · {row['package_label']}"
            match = row["matched_by"]
            if row["confidence"]:
                match += f" · {row['confidence']}"
            values = (
                row["provider"], _money(row["unit_price"], row["currency"]), row["price_unit"],
                package, difference, row["checked"], match, "Åbn produktside" if row["url"] else "—",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row["url"])
                if row["is_cheapest"]:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(QBrush(QColor("#16794a")))
                self.table.setItem(row_index, column, item)
        self.table.resizeColumnsToContents()
        if rows:
            best = [row for row in rows if row["is_cheapest"]]
            self.summary.setText("Billigst: " + " · ".join(
                f"{row['provider']} {_money(row['unit_price'], row['currency'])}/{row['price_unit']}" for row in best
            ))
            self.table.selectRow(0)
        else:
            self.summary.setText("Ingen webshoppriser endnu")
        self._selection_changed()

    def _selection_changed(self):
        row = self.table.currentRow()
        has_url = 0 <= row < len(getattr(self, "_rows", [])) and bool(self._rows[row].get("url"))
        self.open_button.setEnabled(has_url)

    def _open_selected(self):
        row = self.table.currentRow()
        if not (0 <= row < len(getattr(self, "_rows", []))):
            return
        url = str(self._rows[row].get("url", "") or "")
        if url.startswith(("http://", "https://")):
            QDesktopServices.openUrl(QUrl(url))

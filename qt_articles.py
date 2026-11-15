from __future__ import annotations

"""Article library, picker and BOM dialogs.

Kept outside ``qt_app`` so the main window does not parse/import the relatively
large article UI until one of these workflows is actually opened.
"""

import csv
import json
import shutil
import tempfile
import uuid
from collections import defaultdict
from copy import deepcopy
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QSignalBlocker, QPointF, QRectF, QSize, QTimer, QUrl, QStandardPaths, Signal, QThread, QEvent
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QFont, QPainter, QPageLayout, QPageSize, QPalette, QPen, QPixmap, QGuiApplication
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QProgressDialog, QPushButton, QSplitter, QTabWidget, QTableView,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QStackedWidget, QVBoxLayout, QWidget,
)

import article_exchange
import article_intelligence
import assembly_naming
import article_quality
import bom_quality
import core_logic as core
import lk_catalog_sync
import price_display
import retail_price_sync
import user_library
from bom_xlsx_export import write_bom_xlsx
from article_index import build_article_search_index, article_search_score, facet_value_counts, normalize_search_text
from project_model import APP_VERSION
from qt_table_utils import (
    ArticleTableModel, _configure_resizable_table, _fit_table_columns,
    _reset_table_columns, _restore_dialog_geometry, _table_item,
)
from qt_ui import configure_modern_dialog, make_dialog_header, DisclosureSection
from qt_widgets import QComboBox, QDialogButtonBox, QDoubleSpinBox, QFormLayout, _resize_dialog, _set_role
from qt_price_comparison import PriceComparisonDialog
from bom_pdf_export import write_bom_pdf


def _price_text(value,currency="DKK"):
    if value is None or str(value).strip()=="": return "—"
    try: number=float(value)
    except (TypeError,ValueError): return "—"
    return f"{number:,.2f}".replace(",","X").replace(".",",").replace("X",".")+f" {str(currency or 'DKK').upper()}"

def _article_price_meta_lines(article, vat_mode="excl"):
    """Korte, gennemskuelige prislinjer til artikelpreview."""
    art=dict(article or {})
    cur=str(art.get("price_currency","DKK") or "DKK")
    unit=str(art.get("price_unit","") or art.get("unit","stk") or "stk")
    caption=price_display.vat_caption(vat_mode)
    lines=[]
    if art.get("estimated_price") is not None:
        amount=price_display.to_display_amount(art.get("estimated_price"),vat_mode)
        text=f"Estimat {caption}: {_price_text(amount,cur)} pr. {unit}"
        src=str(art.get("estimated_price_source","") or "").strip(); checked=str(art.get("estimated_price_checked","") or "").strip()
        confidence=str(art.get("estimated_price_confidence","") or "").strip()
        sources=art.get("estimated_price_sources")
        if src:text+=f" · {src}"
        if confidence:text+=f" · sikkerhed {confidence.lower()}"
        if sources:text+=f" · {sources} kilder"
        if checked:text+=f" · {checked}"
        lines.append(text)
    if art.get("manual_price") is not None:
        amount=price_display.to_display_amount(art.get("manual_price"),vat_mode)
        text=f"Manuel pris {caption}: {_price_text(amount,cur)} pr. {unit}"
        src=str(art.get("manual_price_source","") or "").strip(); checked=str(art.get("manual_price_checked","") or "").strip()
        if src:text+=f" · {src}"
        if checked:text+=f" · {checked}"
        lines.append(text)
    if art.get("unit_price") is not None and not lines:
        amount=price_display.to_display_amount(art.get("unit_price"),vat_mode)
        text=f"Pris {caption}: {_price_text(amount,cur)} pr. {unit}"
        status=str(art.get("price_status",art.get("price_kind","")) or "").strip()
        if status:text+=f" · {status}"
        lines.append(text)
    return lines


def _article_packaging_meta_line(article):
    pack=core.article_packaging(article)
    if pack["sales_package_quantity"] <= 1.0000001 and pack["minimum_order_quantity"] <= 1.0000001:
        return f"Enhed: {pack['consumption_unit']}"
    text=(pack["package_label"] or
          f"{pack['sales_unit']} á {pack['sales_package_quantity']:g} {pack['consumption_unit']}")
    if pack["minimum_order_quantity"] > 1.0000001:
        text+=f" · mindst {pack['minimum_order_quantity']:g} {pack['sales_unit']}"
    return "Pakning: "+text

class _LkCatalogSyncThread(QThread):
    progress = Signal(str, int, int)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None, *, existing_articles=None, cache_path=None, force_refresh=False):
        super().__init__(parent)
        self._cancelled = False
        self._existing_articles = deepcopy(list(existing_articles or []))
        self._cache_path = Path(cache_path) if cache_path else None
        self._force_refresh = bool(force_refresh)

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            snapshot = lk_catalog_sync.collect_catalog(
                progress=lambda text, value, total: self.progress.emit(str(text), int(value), int(total)),
                cancel=lambda: self._cancelled,
                workers=1,
                timeout=12.0,
                product_timeout=8.0,
                retry_count=1,
                cache_path=self._cache_path,
                cache_max_age_hours=24.0 * 14.0,
                index_cache_hours=24.0,
                request_delay_min=0.8,
                request_delay_max=1.5,
                backoff_seconds=(5.0, 15.0, 45.0, 120.0),
                force_refresh=self._force_refresh,
                existing_articles=self._existing_articles,
            )
            self.succeeded.emit(snapshot)
        except Exception as exc:
            self.failed.emit(str(exc))

class _RetailPriceScopeDialog(QDialog):
    """Responsive scope selector for webshop price updates.

    QMessageBox puts all custom buttons on one horizontal row.  On Windows
    with larger UI/font scaling that can clip button labels, so this dialog
    deliberately uses a 2x2 grid and keeps Cancel on its own row.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        configure_modern_dialog(
            self,
            title="Opdatér webshoppriser",
            size=(700, 410),
            minimum_size=(560, 350),
        )
        self.mode = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        root.addWidget(make_dialog_header(
            "Hvilke artikler skal prisopdateres?",
            "Vælg et afgrænset udsnit for at holde opslagene skånsomme og hurtige.",
            eyebrow="WEBSHOPPRISER",
        ))

        info = QLabel(
            "Programmet søger skånsomt hos WATTOO, LavprisEL og Greenline. "
            "Kun priser med sikkert match på EAN, EL-nr. eller producentnummer accepteres. "
            "Offentlige priser omregnes fra inkl. moms til ekskl. moms, før estimatet gemmes. "
            "Manuelle priser ændres aldrig.",
            self,
        )
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(info)

        cache_note = QLabel(
            "Resultater caches i 24 timer. Der bruges kun én forbindelse ad gangen, og 403/429 giver automatisk backoff.",
            self,
        )
        cache_note.setWordWrap(True)
        cache_note.setObjectName("dialogSubtitle")
        root.addWidget(cache_note)

        choices = QGridLayout()
        choices.setHorizontalSpacing(10)
        choices.setVerticalSpacing(10)

        def add_choice(text, mode, row, col, primary=False):
            button = QPushButton(text, self)
            if primary:
                _set_role(button, "primaryButton")
            button.setMinimumHeight(38)
            # Two columns leave ample room for translated/DPI-scaled labels.
            button.setMinimumWidth(230)
            button.clicked.connect(lambda _checked=False, value=mode: self._choose(value))
            choices.addWidget(button, row, col)
            return button

        self.bom_button = add_choice("Kun artikler i BOM", "bom", 0, 0, True)
        add_choice("Kun uden pris", "missing", 0, 1)
        add_choice("Forældede > 7 dage", "stale", 1, 0)
        add_choice("Alle artikler", "all", 1, 1)
        choices.setColumnStretch(0, 1)
        choices.setColumnStretch(1, 1)
        root.addLayout(choices)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.bom_button.setDefault(True)
        self.bom_button.setFocus()

    def _choose(self, mode):
        self.mode = str(mode or "")
        self.accept()


class _RetailPriceSyncThread(QThread):
    progress = Signal(str, int, int)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None, *, articles=None, cache_path=None):
        super().__init__(parent)
        self._cancelled=False
        self._articles=deepcopy(list(articles or []))
        self._cache_path=Path(cache_path) if cache_path else user_library.user_data_dir()/"retail_price_cache.json"

    def cancel(self):
        self._cancelled=True

    def run(self):
        try:
            collector=retail_price_sync.RetailPriceCollector(
                cache_path=self._cache_path, request_delay_min=1.0, request_delay_max=1.8,
                cache_max_age_hours=24.0, timeout=10.0, backoff_seconds=(5.0,15.0,45.0),
            )
            result=collector.collect(
                self._articles,
                progress=lambda text,value,total:self.progress.emit(str(text),int(value),int(total)),
                cancel=lambda:self._cancelled,
            )
            self.succeeded.emit(result)
        except retail_price_sync.PriceSyncCancelled as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))


class ArticleImportGuideDialog(QDialog):
    """In-app guide generated from the same schema used by JSON/CSV import."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guide til artikelimport")
        _resize_dialog(self,980,720)
        self.setMinimumSize(780,560)
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(10)

        intro=QLabel(
            "Artikelbiblioteker kan importeres som JSON eller CSV. <b>Artikelnummer</b> er det eneste "
            "obligatoriske felt; beskrivelse og fabrikat anbefales. JSON er det mest komplette format, "
            "mens CSV er praktisk til Excel og leverandørlister. Brug templates nedenfor for at få de "
            "korrekte feltnavne."
        )
        intro.setWordWrap(True); intro.setTextFormat(Qt.TextFormat.RichText); root.addWidget(intro)

        tabs=QTabWidget(); root.addWidget(tabs,1)

        overview=QWidget(); ov=QVBoxLayout(overview); ov.setContentsMargins(10,10,10,10); ov.setSpacing(8)
        info=QLabel(
            "<b>Importregler</b><br>"
            "• Én række/ét objekt = én artikel.<br>"
            "• <b>article_no / Artikelnummer</b> er den stabile nøgle og skal være unik.<br>"
            "• Manglende enhed bliver automatisk <b>stk</b>.<br>"
            "• <b>Flet sikkert</b> tilføjer nye artikler og udfylder kun tomme felter.<br>"
            "• <b>Opdatér eksisterende</b> må erstatte eksisterende metadata med ikke-tomme importværdier.<br>"
            "• Tomme importfelter sletter aldrig eksisterende værdier.<br>"
            "• EAN og EL-nr. bør behandles som tekst i Excel, så foranstillede nuller ikke forsvinder.<br>"
            "• Produktbilleder vises automatisk, hvis <b>image_url / Billede</b> peger på et direkte billede.<br><br>"
            "<b>JSON</b>: brug de tekniske feltnavne fra tabellen. Filen kan enten være en ren liste af "
            "artikelobjekter eller Elplan-formatet med en <code>articles</code>-liste.<br><br>"
            "<b>CSV</b>: semikolon, komma og tabulator accepteres. Den medfølgende template bruger "
            "semikolon og danske kolonneoverskrifter."
        )
        info.setWordWrap(True); info.setTextFormat(Qt.TextFormat.RichText); ov.addWidget(info); ov.addStretch(1)
        tabs.addTab(overview,"Sådan gør du")

        fields=QWidget(); fl=QVBoxLayout(fields); fl.setContentsMargins(4,4,4,4)
        table=QTableWidget(len(article_exchange.ARTICLE_FIELD_GUIDE),5)
        table.setHorizontalHeaderLabels(["JSON-felt","CSV-kolonne","Krav","Beskrivelse","Eksempel"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True); table.verticalHeader().setVisible(False)
        for row,(key,label,level,description,example) in enumerate(article_exchange.ARTICLE_FIELD_GUIDE):
            for col,value in enumerate((key,label,level,description,example)):
                table.setItem(row,col,QTableWidgetItem(str(value)))
        table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(4,QHeaderView.ResizeMode.ResizeToContents)
        fl.addWidget(table); tabs.addTab(fields,"Felter")

        json_tab=QWidget(); jl=QVBoxLayout(json_tab); jl.setContentsMargins(8,8,8,8)
        json_hint=QLabel("Anbefalet format. Bevarer alle metadata og er bedst til backup/udveksling mellem systemer.")
        json_hint.setWordWrap(True); jl.addWidget(json_hint)
        json_example=QPlainTextEdit(); json_example.setReadOnly(True)
        payload={"format":article_exchange.FORMAT_NAME,"format_version":article_exchange.FORMAT_VERSION,
                 "application_version":APP_VERSION,"articles":[article_exchange.article_template_record(include_examples=True)]}
        json_example.setPlainText(json.dumps(payload,ensure_ascii=False,indent=2)); jl.addWidget(json_example,1)
        tabs.addTab(json_tab,"JSON-eksempel")

        csv_tab=QWidget(); cl=QVBoxLayout(csv_tab); cl.setContentsMargins(8,8,8,8)
        csv_hint=QLabel("CSV-template er beregnet til Excel. Behold kolonneoverskrifterne; slet blot kolonner du ikke har brug for.")
        csv_hint.setWordWrap(True); cl.addWidget(csv_hint)
        csv_example=QPlainTextEdit(); csv_example.setReadOnly(True)
        headers=[label for label,_key in article_exchange.CSV_TEMPLATE_COLUMNS]
        example=article_exchange.article_template_record(include_examples=True)
        csv_example.setPlainText(";".join(headers)+"\n"+";".join(str(example.get(key,"")) for _label,key in article_exchange.CSV_TEMPLATE_COLUMNS))
        cl.addWidget(csv_example,1); tabs.addTab(csv_tab,"CSV-eksempel")

        bottom=QHBoxLayout()
        save_json=QPushButton("Gem JSON-template…"); save_json.clicked.connect(self._save_json_template); bottom.addWidget(save_json)
        save_csv=QPushButton("Gem CSV-template…"); save_csv.clicked.connect(self._save_csv_template); bottom.addWidget(save_csv)
        bottom.addStretch(1)
        close=_set_role(QPushButton("Luk"),"primaryButton"); close.clicked.connect(self.accept); bottom.addWidget(close)
        root.addLayout(bottom)

    def _save_json_template(self):
        path,_=QFileDialog.getSaveFileName(self,"Gem JSON-template","article_library_template.json","JSON (*.json)")
        if not path:return
        target=Path(path)
        if target.suffix.casefold()!=".json":target=target.with_suffix(".json")
        try:
            article_exchange.save_article_template_json(target,app_version=APP_VERSION)
        except Exception as exc:
            QMessageBox.critical(self,"Artikel-template",f"Template kunne ikke gemmes:\n\n{exc}")
            return
        QMessageBox.information(self,"Artikel-template",f"JSON-template gemt:\n\n{target}")

    def _save_csv_template(self):
        path,_=QFileDialog.getSaveFileName(self,"Gem CSV-template","article_library_template.csv","CSV (*.csv)")
        if not path:return
        target=Path(path)
        if target.suffix.casefold()!=".csv":target=target.with_suffix(".csv")
        try:
            article_exchange.save_article_template_csv(target)
        except Exception as exc:
            QMessageBox.critical(self,"Artikel-template",f"Template kunne ikke gemmes:\n\n{exc}")
            return
        QMessageBox.information(self,"Artikel-template",f"CSV-template gemt:\n\n{target}")

class ArticleTechnicalSpecsDialog(QDialog):
    """Small generic editor for verified technical properties."""
    def __init__(self,parent=None,specs:dict|None=None):
        super().__init__(parent)
        configure_modern_dialog(self,title="Tekniske egenskaber",minimum_size=(620,430))
        _resize_dialog(self,720,520)
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(9)
        info=QLabel("Tilføj kun egenskaber, der kan verificeres. Automatisk udledte egenskaber vises i artikelpreviewet, mens værdier her gemmes som manuelle overrides.")
        info.setWordWrap(True); info.setObjectName("subtleText"); root.addWidget(info)
        self.table=QTableWidget(0,2); self.table.setHorizontalHeaderLabels(["Egenskab","Værdi"])
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False); root.addWidget(self.table,1)
        for key,value in dict(specs or {}).items(): self._append(str(key),str(value))
        tools=QHBoxLayout()
        add=_set_role(QPushButton("Tilføj"),"quietButton"); add.clicked.connect(lambda:self._append("","")); tools.addWidget(add)
        remove=_set_role(QPushButton("Fjern"),"dangerButton"); remove.clicked.connect(self._remove_selected); tools.addWidget(remove)
        tools.addStretch(1); root.addLayout(tools)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _append(self,key,value):
        row=self.table.rowCount(); self.table.insertRow(row)
        self.table.setItem(row,0,QTableWidgetItem(key)); self.table.setItem(row,1,QTableWidgetItem(value))

    def _remove_selected(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()},reverse=True): self.table.removeRow(row)

    def specs(self):
        out={}
        for row in range(self.table.rowCount()):
            key=str(self.table.item(row,0).text() if self.table.item(row,0) else "").strip()
            value=str(self.table.item(row,1).text() if self.table.item(row,1) else "").strip()
            if key and value: out[key]=value
        return out


class ArticleEditDialog(QDialog):
    def __init__(self,parent=None,record:dict|None=None):
        super().__init__(parent)
        self.setWindowTitle("Artikel")
        _resize_dialog(self,860,760)
        self.setMinimumWidth(680)
        self.original=deepcopy(dict(record or {}))
        rec=self.original
        facets=core.article_filter_facets(rec)

        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(10)
        intro=QLabel("Redigér kernedatabasens artikeldata. Felter kan stå tomme, bortset fra artikelnummer.")
        intro.setWordWrap(True); intro.setObjectName("subtleText"); root.addWidget(intro)

        self.article_no=QLineEdit(str(rec.get("article_no","") or ""))
        self.description=QLineEdit(str(rec.get("description","") or ""))
        self.manufacturer=QLineEdit(str(rec.get("manufacturer","") or ""))
        self.brand=QLineEdit(str(rec.get("brand","") or ""))
        self.series=QLineEdit(str(rec.get("series","") or ""))
        self.category=QLineEdit(str(rec.get("category","") or ""))
        self.category_normalized=QComboBox(); self.category_normalized.setEditable(True)
        self.category_normalized.addItems(article_intelligence.CATEGORY_PATHS)
        current_category=str(rec.get("category_normalized","") or article_intelligence.derive_category(rec))
        idx=self.category_normalized.findText(current_category); self.category_normalized.setCurrentIndex(idx if idx>=0 else 0)
        self.product_type=QLineEdit(str(rec.get("product_type",facets.get("product_type","")) or ""))
        self.function=QLineEdit(str(rec.get("function","") or article_intelligence.derive_function(rec)))
        semantics=article_intelligence.derive_product_semantics(rec)
        self._semantic_family_default=str(semantics.get("product_family","") or "")
        self._semantic_variant_default=str(semantics.get("product_variant","") or "")
        self.product_family=QLineEdit(str(rec.get("product_family_manual","") or self._semantic_family_default))
        self.product_variant=QLineEdit(str(rec.get("product_variant_manual","") or self._semantic_variant_default))
        self.design_family=QLineEdit(str(rec.get("design_family_raw",rec.get("design_family",facets.get("design_family",""))) or ""))
        self.module_size=QLineEdit(str(rec.get("module_size",facets.get("module_size","")) or ""))
        self.color=QLineEdit(str(rec.get("color",facets.get("color","")) or ""))
        self.el_no=QLineEdit(str(rec.get("el_no","") or ""))
        self.ean=QLineEdit(str(rec.get("ean","") or ""))
        self.unit=QLineEdit(str(rec.get("unit","stk") or "stk"))
        packaging=core.article_packaging(rec)
        self.consumption_unit=QComboBox(); self.consumption_unit.setEditable(True); self.consumption_unit.addItems(["stk","m","sæt"]); self.consumption_unit.setCurrentText(packaging["consumption_unit"])
        self.sales_unit=QComboBox(); self.sales_unit.setEditable(True); self.sales_unit.addItems(["stk","pakke","rulle","sæt"]); self.sales_unit.setCurrentText(packaging["sales_unit"])
        self.sales_package_quantity=QDoubleSpinBox(); self.sales_package_quantity.setRange(.01,999999999); self.sales_package_quantity.setDecimals(2); self.sales_package_quantity.setValue(packaging["sales_package_quantity"])
        self.minimum_order_quantity=QDoubleSpinBox(); self.minimum_order_quantity.setRange(.01,999999); self.minimum_order_quantity.setDecimals(2); self.minimum_order_quantity.setValue(packaging["minimum_order_quantity"])
        self.package_label=QLineEdit(packaging["package_label"]); self.package_label.setPlaceholderText("Fx pakke á 50 stk. (udledes automatisk hvis tom)")
        self.status=QLineEdit(str(rec.get("status","") or ""))
        self.product_page=QLineEdit(str(rec.get("product_page","") or ""))
        self.supplier_page=QLineEdit(str(rec.get("supplier_page","") or ""))
        self.datasheet_url=QLineEdit(str(rec.get("datasheet_url","") or ""))
        self.image_url=QLineEdit(str(rec.get("image_url","") or ""))
        self.source=QLineEdit(str(rec.get("source","") or ""))
        self.note=QLineEdit(str(rec.get("note","") or ""))
        self.variant_group_manual=QLineEdit(str(rec.get("variant_group_manual","") or ""))
        self._technical_specs_manual=deepcopy(rec.get("technical_specs_manual",{})) if isinstance(rec.get("technical_specs_manual"),dict) else {}

        columns=QHBoxLayout(); columns.setSpacing(10); root.addLayout(columns)
        base_box=QGroupBox("Grunddata"); base=QFormLayout(base_box)
        base.addRow("Artikelnummer *",self.article_no); base.addRow("Beskrivelse",self.description)
        base.addRow("Fabrikat",self.manufacturer); base.addRow("Brand",self.brand); base.addRow("Serie",self.series)
        base.addRow("Kategori",self.category); base.addRow("Status",self.status)
        columns.addWidget(base_box,1)

        class_box=QGroupBox("Klassifikation"); classification=QFormLayout(class_box)
        classification.addRow("Standardkategori",self.category_normalized)
        classification.addRow("Produkttype",self.product_type); classification.addRow("Funktion",self.function)
        classification.addRow("Produktfamilie",self.product_family); classification.addRow("Produktvariant",self.product_variant)
        self.design_family.setToolTip("Legacy-/råt designfelt. Brug Produktfamilie + Produktvariant som produktets identitet; kompatible designserier vises separat.")
        classification.addRow("Legacy design (rå)",self.design_family)
        classification.addRow("Modul",self.module_size); classification.addRow("Farve",self.color)
        classification.addRow("Variantgruppe (manuel)",self.variant_group_manual)
        classification.addRow("EL-nr.",self.el_no)
        classification.addRow("EAN",self.ean)
        columns.addWidget(class_box,1)

        package_box=QGroupBox("Enheder og pakning"); package_grid=QGridLayout(package_box)
        package_grid.addWidget(QLabel("Forbrugsenhed"),0,0); package_grid.addWidget(self.consumption_unit,0,1)
        package_grid.addWidget(QLabel("Salgsenhed"),0,2); package_grid.addWidget(self.sales_unit,0,3)
        package_grid.addWidget(QLabel("Antal pr. salgsenhed"),1,0); package_grid.addWidget(self.sales_package_quantity,1,1)
        package_grid.addWidget(QLabel("Mindste bestilling"),1,2); package_grid.addWidget(self.minimum_order_quantity,1,3)
        package_grid.addWidget(QLabel("Pakningsbeskrivelse"),2,0); package_grid.addWidget(self.package_label,2,1,1,3)
        package_hint=QLabel("BOM opgør behovet i forbrugsenheden og afrunder indkøb til hele salgsenheder. En pris pr. pakke/rulle beregnes derfor anderledes end en pris pr. stk./meter.")
        package_hint.setWordWrap(True); package_hint.setObjectName("sectionHint"); package_grid.addWidget(package_hint,3,0,1,4)
        root.addWidget(package_box)

        links_box=QGroupBox("Links og note"); links=QFormLayout(links_box)
        links.addRow("Produktlink",self.product_page); links.addRow("Leverandørlink",self.supplier_page)
        links.addRow("Datablad",self.datasheet_url); links.addRow("Billede-URL",self.image_url)
        links.addRow("Kilde",self.source); links.addRow("Note",self.note)
        root.addWidget(links_box)

        compat_text=article_intelligence.compatibility_text(semantics)
        self.compatibility_summary=QLabel("Kompatibilitet: "+(compat_text or "Ingen struktureret kompatibilitet registreret")); self.compatibility_summary.setWordWrap(True); self.compatibility_summary.setObjectName("sectionHint"); root.addWidget(self.compatibility_summary)
        specs_row=QHBoxLayout(); self.specs_summary=QLabel(); self.specs_summary.setWordWrap(True); self.specs_summary.setObjectName("sectionHint"); specs_row.addWidget(self.specs_summary,1)
        specs_btn=_set_role(QPushButton("Tekniske egenskaber…"),"quietButton"); specs_btn.clicked.connect(self._edit_technical_specs); specs_row.addWidget(specs_btn); root.addLayout(specs_row)
        self._refresh_specs_summary()

        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_checked); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept_checked(self):
        if not self.article_no.text().strip():
            QMessageBox.warning(self,"Artikel","Artikelnummer skal udfyldes.")
            return
        self.accept()

    def _refresh_specs_summary(self):
        if self._technical_specs_manual:
            text=" · ".join(f"{article_intelligence.spec_label(k)}: {v}" for k,v in list(self._technical_specs_manual.items())[:6])
            if len(self._technical_specs_manual)>6:text+=" · …"
            self.specs_summary.setText("Manuelt verificeret: "+text)
        else:self.specs_summary.setText("Ingen manuelle egenskaber. Programmet udleder stadig sikre egenskaber fra kildedata.")

    def _edit_technical_specs(self):
        dlg=ArticleTechnicalSpecsDialog(self,self._technical_specs_manual)
        if dlg.exec()==QDialog.DialogCode.Accepted:
            self._technical_specs_manual=dlg.specs(); self._refresh_specs_summary()

    def record(self):
        # Bevar skjulte standardmetadata såsom kabelspecifikation, kildelink og
        # pakkelængde når en indbygget artikel redigeres lokalt i projektet.
        rec=deepcopy(self.original)
        rec.update({
            "article_no":self.article_no.text().strip(),
            "description":self.description.text().strip(),
            "manufacturer":self.manufacturer.text().strip(),
            "brand":self.brand.text().strip(),
            "series":self.series.text().strip(),
            "category":self.category.text().strip(),
            "category_normalized":self.category_normalized.currentText().strip(),
            "product_type":self.product_type.text().strip(),
            "function":self.function.text().strip(),
            "design_family_raw":self.design_family.text().strip(),
            "module_size":self.module_size.text().strip(),
            "color":self.color.text().strip(),
            "el_no":self.el_no.text().strip(),
            "ean":self.ean.text().strip(),
            "unit":((self.unit.text().strip() or "rulle")
                    if str(self.original.get("kind","") or "").casefold()=="cable" and core.article_packaging(self.original)["sales_unit"]=="rulle"
                    else self.consumption_unit.currentText().strip() or "stk"),
            "consumption_unit":self.consumption_unit.currentText().strip() or "stk",
            "sales_unit":self.sales_unit.currentText().strip() or self.consumption_unit.currentText().strip() or "stk",
            "sales_package_quantity":float(self.sales_package_quantity.value()),
            "minimum_order_quantity":float(self.minimum_order_quantity.value()),
            "package_label":self.package_label.text().strip(),
            "status":self.status.text().strip(),
            "product_page":self.product_page.text().strip(),
            "supplier_page":self.supplier_page.text().strip(),
            "datasheet_url":self.datasheet_url.text().strip(),
            "image_url":self.image_url.text().strip(),
            "source":self.source.text().strip(),
            "note":self.note.text().strip(),
            "variant_group_manual":self.variant_group_manual.text().strip(),
            "technical_specs_manual":deepcopy(self._technical_specs_manual),
        })
        family=self.product_family.text().strip(); variant=self.product_variant.text().strip()
        if family and (family != self._semantic_family_default or self.original.get("product_family_manual")):
            rec["product_family_manual"]=family
        else:
            rec.pop("product_family_manual",None)
        if variant and (variant != self._semantic_variant_default or self.original.get("product_variant_manual")):
            rec["product_variant_manual"]=variant
        else:
            rec.pop("product_variant_manual",None)
        # The old field is retained only as raw provenance. Do not save it back
        # as controlled product identity.
        rec.pop("design_family",None)
        return rec

class ArticlePriceDialog(QDialog):
    """Redigér estimat og manuel pris uden at blande de to datakilder."""
    def __init__(self,parent,article:dict,price_record:dict|None=None,vat_mode="excl"):
        super().__init__(parent)
        self.article=deepcopy(dict(article or {}))
        self._vat_mode=price_display.normalize_vat_mode(vat_mode)
        no=str(self.article.get("article_no","") or "")
        # Prisbog og katalogestimat holdes adskilt. Et automatisk estimat fra
        # artikelmetadata vises i dialogen, men kopieres kun ind i prisbogen,
        # hvis brugeren faktisk ændrer det.
        self.original=deepcopy(user_library.normalize_article_prices({no:dict(price_record or {})}).get(no,{}))
        self.catalog_price=deepcopy(user_library.normalize_article_prices({no:self.article}).get(no,{}))
        self._remove=False
        self.setWindowTitle("Pris / prisestimat")
        self.setMinimumWidth(610)
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(10)
        title=QLabel(f"{self.article.get('article_no','')} · {self.article.get('description','')}")
        title.setWordWrap(True); title.setObjectName("sectionTitle"); root.addWidget(title)
        self.price_hint=QLabel(
            "Estimat og manuel pris gemmes separat. En manuel pris har altid prioritet i BOM og eksport, "
            "men estimatet bevares og kan senere opdateres uden at overskrive din pris."
        )
        self.price_hint.setWordWrap(True); self.price_hint.setObjectName("subtleText"); root.addWidget(self.price_hint)

        common=QGroupBox("Prisgrundlag")
        common_form=QFormLayout(common)
        price_basis=self.original if self.original else self.catalog_price
        self.currency=QComboBox(); self.currency.setEditable(True); self.currency.addItems(["DKK","EUR","SEK","NOK"]); self.currency.setCurrentText(str(price_basis.get('price_currency','DKK') or 'DKK'))
        self.price_unit=QComboBox(); self.price_unit.setEditable(True); self.price_unit.addItems(["stk","m","rulle","pakke","sæt"])
        default_unit=str(price_basis.get('price_unit','') or core.article_packaging(self.article)["consumption_unit"] or 'stk')
        self.price_unit.setCurrentText(default_unit)
        self.vat_mode_combo=QComboBox(); self.vat_mode_combo.addItem("Ekskl. moms",price_display.VAT_MODE_EXCL); self.vat_mode_combo.addItem("Inkl. moms",price_display.VAT_MODE_INCL)
        vat_index=self.vat_mode_combo.findData(self._vat_mode); self.vat_mode_combo.setCurrentIndex(max(0,vat_index))
        self.note=QLineEdit(str(self.original.get('price_note','') or ''))
        common_form.addRow("Valuta",self.currency); common_form.addRow("Pris pr.",self.price_unit); common_form.addRow("Beløb vises som",self.vat_mode_combo); common_form.addRow("Note",self.note)
        package_hint=QLabel(_article_packaging_meta_line(self.article)+". Vælg ‘pakke’/‘rulle’, hvis beløbet gælder hele salgsenheden.")
        package_hint.setWordWrap(True); package_hint.setObjectName("sectionHint"); common_form.addRow("",package_hint)
        root.addWidget(common)

        estimate_box=QGroupBox("Estimeret pris")
        estimate_form=QFormLayout(estimate_box)
        self.has_estimate=QCheckBox("Gem estimeret pris")
        self.estimated_amount=QDoubleSpinBox(); self.estimated_amount.setRange(0,999999999.99); self.estimated_amount.setDecimals(2); self.estimated_amount.setSingleStep(1.0)
        estimate=self.original if self.original.get('estimated_price') is not None else self.catalog_price
        if estimate.get('estimated_price') is not None:
            self.has_estimate.setChecked(True); self.estimated_amount.setValue(float(price_display.to_display_amount(estimate.get('estimated_price'),self._vat_mode) or 0))
        self.estimated_source=QLineEdit(str(estimate.get('estimated_price_source','') or '')); self.estimated_source.setPlaceholderText("Fx prisestimat, producent, grossist eller URL")
        estimate_checked=str(estimate.get('estimated_price_checked','') or '')
        if not estimate_checked and self.original.get('estimated_price') is not None: estimate_checked=date.today().isoformat()
        self.estimated_checked=QLineEdit(estimate_checked); self.estimated_checked.setPlaceholderText("ÅÅÅÅ-MM-DD")
        self._catalog_estimate_snapshot=(
            float(self.catalog_price.get('estimated_price')) if self.catalog_price.get('estimated_price') is not None else None,
            str(self.catalog_price.get('estimated_price_source','') or ''),
            str(self.catalog_price.get('estimated_price_checked','') or ''),
        )
        estimate_form.addRow(self.has_estimate); estimate_form.addRow("Estimat",self.estimated_amount); estimate_form.addRow("Kilde",self.estimated_source); estimate_form.addRow("Opdateret",self.estimated_checked)
        root.addWidget(estimate_box)

        manual_box=QGroupBox("Manuel prisoverride")
        manual_form=QFormLayout(manual_box)
        self.has_manual=QCheckBox("Brug manuel pris (har prioritet)")
        self.manual_amount=QDoubleSpinBox(); self.manual_amount.setRange(0,999999999.99); self.manual_amount.setDecimals(2); self.manual_amount.setSingleStep(1.0)
        if self.original.get('manual_price') is not None:
            self.has_manual.setChecked(True); self.manual_amount.setValue(float(price_display.to_display_amount(self.original.get('manual_price'),self._vat_mode) or 0))
        self.manual_source=QLineEdit(str(self.original.get('manual_price_source','') or '')); self.manual_source.setPlaceholderText("Fx egen nettopris, tilbud eller grossist")
        self.manual_checked=QLineEdit(str(self.original.get('manual_price_checked','') or (date.today().isoformat() if self.has_manual.isChecked() else ''))); self.manual_checked.setPlaceholderText("ÅÅÅÅ-MM-DD")
        manual_form.addRow(self.has_manual); manual_form.addRow("Manuel pris",self.manual_amount); manual_form.addRow("Kilde",self.manual_source); manual_form.addRow("Opdateret",self.manual_checked)
        root.addWidget(manual_box)

        observations=list((self.original or self.catalog_price).get("price_observations",[]) or [])
        if observations:
            obs_box=QGroupBox("Webshop-observationer")
            obs_layout=QVBoxLayout(obs_box)
            obs_lines=[]
            for obs in observations:
                if not isinstance(obs,dict): continue
                try: incl=_price_text(obs.get("price_incl_vat"),obs.get("currency","DKK")); excl=_price_text(obs.get("price_excl_vat"),obs.get("currency","DKK"))
                except Exception: continue
                package_qty=float(obs.get("package_quantity",1) or 1)
                raw_incl=obs.get("raw_price_incl_vat")
                unit=str(obs.get("price_unit","stk") or "stk")
                package_note=""
                if package_qty > 1.0001 and raw_incl not in (None,""):
                    package_note=f" · {obs.get('package_label') or f'pakke á {package_qty:g} stk.'}: {_price_text(raw_incl,obs.get('currency','DKK'))} inkl. moms"
                obs_lines.append(f"{obs.get('provider','Webshop')}: {incl}/{unit} inkl. moms · {excl}/{unit} ekskl. moms{package_note} · {obs.get('matched_by','match')} · {obs.get('checked','')}")
            obs_label=QLabel("<br>".join(obs_lines)); obs_label.setWordWrap(True); obs_label.setTextFormat(Qt.TextFormat.RichText); obs_label.setObjectName("subtleText")
            obs_layout.addWidget(obs_label); root.addWidget(obs_box)

        self.effective_label=QLabel(); self.effective_label.setObjectName("accentText"); root.addWidget(self.effective_label)
        for widget in (self.has_estimate,self.has_manual): widget.toggled.connect(self._update_price_state)
        for widget in (self.estimated_amount,self.manual_amount): widget.valueChanged.connect(self._update_price_state)
        self.currency.currentTextChanged.connect(self._update_price_state); self.price_unit.currentTextChanged.connect(self._update_price_state)
        self.vat_mode_combo.currentIndexChanged.connect(self._vat_mode_changed)
        self._update_price_state()

        row=QHBoxLayout(); remove=_set_role(QPushButton("Fjern alle prisdata"), "dangerButton"); remove.clicked.connect(self._remove_price); row.addWidget(remove); row.addStretch(1)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); row.addWidget(buttons); root.addLayout(row)

    def _update_price_state(self,*_):
        estimate_on=self.has_estimate.isChecked(); manual_on=self.has_manual.isChecked()
        for widget in (self.estimated_amount,self.estimated_source,self.estimated_checked): widget.setEnabled(estimate_on)
        for widget in (self.manual_amount,self.manual_source,self.manual_checked): widget.setEnabled(manual_on)
        caption=price_display.vat_caption(self._vat_mode)
        self.price_hint.setText(
            "Estimat og manuel pris gemmes separat. En manuel pris har altid prioritet i BOM og eksport, "
            f"men estimatet bevares. Du indtaster nu beløb {caption}; de gemmes altid ekskl. moms."
        )
        if manual_on:
            amount=self.manual_amount.value(); status="Manuel pris"
        elif estimate_on:
            amount=self.estimated_amount.value(); status="Estimat"
        else:
            self.effective_label.setText("Anvendt pris: —"); return
        self.effective_label.setText(f"Anvendt pris {caption}: {_price_text(amount,self.currency.currentText())} pr. {self.price_unit.currentText().strip() or 'stk'} · {status}")

    def _vat_mode_changed(self,*_):
        new_mode=price_display.normalize_vat_mode(self.vat_mode_combo.currentData())
        if new_mode==self._vat_mode:return
        for widget in (self.estimated_amount,self.manual_amount):
            net=price_display.from_display_amount(widget.value(),self._vat_mode)
            blocker=QSignalBlocker(widget); widget.setValue(float(price_display.to_display_amount(net,new_mode) or 0)); del blocker
        self._vat_mode=new_mode
        self._update_price_state()

    def selected_vat_mode(self):
        return self._vat_mode

    def _remove_price(self):
        self._remove=True; self.accept()

    def price_record(self):
        if self._remove:return None
        rec={
            "price_currency":self.currency.currentText().strip().upper() or "DKK",
            "price_unit":self.price_unit.currentText().strip() or str(self.article.get('unit','stk') or 'stk'),
            "price_note":self.note.text().strip(),
        }
        provenance=self.original if self.original else self.catalog_price
        if "price_observations" in provenance:rec["price_observations"]=deepcopy(provenance["price_observations"])
        if self.has_estimate.isChecked():
            estimate_value=round(float(price_display.from_display_amount(self.estimated_amount.value(),self._vat_mode) or 0),4)
            estimate_tuple=(estimate_value,self.estimated_source.text().strip(),self.estimated_checked.text().strip())
            # Et uændret katalogestimat behøver ikke blive et lokalt override.
            catalog_same=(
                self._catalog_estimate_snapshot[0] is not None and
                abs(estimate_tuple[0]-self._catalog_estimate_snapshot[0])<0.011 and
                estimate_tuple[1:]==self._catalog_estimate_snapshot[1:]
            )
            if self.original.get('estimated_price') is not None or not catalog_same:
                rec.update({
                    "estimated_price":estimate_tuple[0],
                    "estimated_price_source":estimate_tuple[1],
                    "estimated_price_checked":estimate_tuple[2] or date.today().isoformat(),
                })
                original_same=(
                    self.original.get('estimated_price') is not None and
                    abs(estimate_tuple[0]-float(self.original.get('estimated_price') or 0))<0.011 and
                    estimate_tuple[1]==str(self.original.get('estimated_price_source','') or '') and
                    estimate_tuple[2]==str(self.original.get('estimated_price_checked','') or '')
                )
                if original_same:
                    for key in ("estimated_price_confidence","estimated_price_method","estimated_price_sources","estimated_price_min","estimated_price_max"):
                        if key in self.original:rec[key]=deepcopy(self.original[key])
        if self.has_manual.isChecked():
            rec.update({
                "manual_price":round(float(price_display.from_display_amount(self.manual_amount.value(),self._vat_mode) or 0),4),
                "manual_price_source":self.manual_source.text().strip(),
                "manual_price_checked":self.manual_checked.text().strip() or date.today().isoformat(),
            })
        if not self.has_estimate.isChecked() and not self.has_manual.isChecked():
            return None
        return rec

class ArticleVisualPreview(QWidget):
    """Produktpreview med onlinefoto/cache og skematisk offline-fallback.

    Onlinebilledet er kun en visuel hjælp. Projekt-/BOM-data er uafhængige af
    netadgang, og den skematiske vektorillustration bruges, hvis billedkilden
    ikke kan hentes eller ikke længere findes.
    """
    def __init__(self,parent=None):
        super().__init__(parent)
        self._article={}
        self._pixmap=QPixmap()
        self._image_status=""
        self._load_token=0
        self._fallback_page_requested=False
        self._network=QNetworkAccessManager(self)
        self._active_replies=set()
        self._load_timer=QTimer(self); self._load_timer.setSingleShot(True); self._load_timer.setInterval(300)
        self._load_timer.timeout.connect(self._load_current_article_image)
        cache_root=QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
        if not cache_root:
            cache_root=str(Path.home()/".elplan_cache")
        self._cache_dir=Path(cache_root)/"article_images"
        try:self._cache_dir.mkdir(parents=True,exist_ok=True)
        except Exception:pass
        self.setMinimumSize(250,220)

    def set_article(self,article):
        self._load_timer.stop()
        self._article=deepcopy(dict(article or {}))
        self._pixmap=QPixmap()
        self._image_status=""
        self._fallback_page_requested=False
        self._load_token+=1
        for reply in tuple(self._active_replies):
            if not reply.isFinished(): reply.abort()
        self.update()
        if self._article:
            # Vent kort før netværksopslag. Hurtig navigation/søgning starter dermed
            # ikke requests for artikler, som brugeren allerede har forladt.
            self._load_timer.start()

    def _load_current_article_image(self):
        if self._article:
            self._load_online_image(self._load_token)

    def reload_image(self):
        if not self._article:return
        self._load_timer.stop()
        self._pixmap=QPixmap(); self._image_status=""
        self._fallback_page_requested=False
        self._load_token+=1
        for reply in tuple(self._active_replies):
            if not reply.isFinished(): reply.abort()
        article_no=str(self._article.get("article_no","") or "").strip()
        if article_no:
            for path in self._cache_dir.glob(article_no.replace("/","_")+".*"):
                try:path.unlink()
                except Exception:pass
        self._load_online_image(self._load_token,force=True)

    def _cache_candidates(self):
        article_no=str(self._article.get("article_no","") or "").strip().replace("/","_")
        if not article_no:return []
        return [self._cache_dir/(article_no+ext) for ext in (".png",".jpg",".jpeg",".webp",".bin")]

    def _resolve_local_image_path(self, value):
        text=str(value or "").strip()
        if not text:
            return None
        path=Path(text)
        if not path.is_absolute():
            path=(Path(__file__).resolve().parent/path).resolve()
        return path

    def _load_local_image(self, value, status):
        path=self._resolve_local_image_path(value)
        if path is None or not path.exists() or not path.is_file():
            return False
        pm=QPixmap(str(path))
        if pm.isNull():
            return False
        self._pixmap=pm; self._image_status=status; self.update(); return True

    def _load_online_image(self,token,force=False):
        if token!=self._load_token:return
        if not force:
            for path in self._cache_candidates():
                if path.exists() and path.stat().st_size>100:
                    pm=QPixmap(str(path))
                    if not pm.isNull():
                        self._pixmap=pm; self._image_status="Cached produktfoto"; self.update(); return
        local_image=str(self._article.get("image_local_path","") or "").strip()
        if self._load_local_image(local_image, "Indbygget produktbillede"):
            return
        image_url=str(self._article.get("image_url","") or "").strip()
        page_url=str(self._article.get("product_page","") or self._article.get("source","") or "").strip()
        if self._load_local_image(image_url, "Indbygget produktbillede"):
            return
        if image_url.startswith(("http://","https://")):
            self._request_image(image_url,token); return
        if page_url.startswith(("http://","https://")) and not page_url.lower().endswith(".pdf"):
            self._image_status="Henter produktfoto…"; self.update()
            req=QNetworkRequest(QUrl(page_url)); req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader,f"Mozilla/5.0 ElplanDWGEditor/{APP_VERSION}")
            reply=self._network.get(req); self._active_replies.add(reply)
            reply.finished.connect(lambda r=reply:self._active_replies.discard(r))
            reply.finished.connect(lambda r=reply,t=token,u=page_url:self._page_received(r,t,u))

    def _page_received(self,reply,token,base_url):
        try:
            if token!=self._load_token:return
            if reply.error()!=QNetworkReply.NetworkError.NoError:
                self._image_status="Onlinefoto ikke tilgængeligt"; self.update(); return
            html=bytes(reply.readAll()).decode("utf-8","ignore")
            import re, html as htmlmod
            patterns=(
                r'(https://assets\.cdnlemu\.dk/product/image/[A-Za-z0-9_-]+)',
                r'["\']((?:https?:)?//nordtronic\.dk/images/(?!design/)[^"\']+\.(?:jpg|jpeg|png|webp))["\']',
                r'(?:src|href)=["\']([^"\']*/images/(?!design/)[^"\']+\.(?:jpg|jpeg|png|webp))["\']',
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                r'<img[^>]+(?:class=["\'][^"\']*(?:product|image)[^"\']*["\'][^>]+)?src=["\']([^"\']+)["\']',
            )
            found=""
            for pat in patterns:
                m=re.search(pat,html,re.I|re.S)
                if m:
                    found=htmlmod.unescape(m.group(1)); break
            if not found:
                self._image_status="Ingen produktfoto fundet"; self.update(); return
            resolved=QUrl(base_url).resolved(QUrl(found)).toString()
            self._request_image(resolved,token)
        finally:
            reply.deleteLater()

    def _request_image(self,url,token):
        if token!=self._load_token:return
        self._image_status="Henter produktfoto…"; self.update()
        req=QNetworkRequest(QUrl(url)); req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader,f"Mozilla/5.0 ElplanDWGEditor/{APP_VERSION}")
        reply=self._network.get(req); self._active_replies.add(reply)
        reply.finished.connect(lambda r=reply:self._active_replies.discard(r))
        reply.finished.connect(lambda r=reply,t=token,u=url:self._image_received(r,t,u))

    def _image_received(self,reply,token,url):
        try:
            if token!=self._load_token:return
            if reply.error()!=QNetworkReply.NetworkError.NoError:
                page_url=str(self._article.get("product_page","") or self._article.get("source","") or "").strip()
                if (not self._fallback_page_requested and page_url.startswith(("http://","https://"))
                        and not page_url.lower().endswith(".pdf") and page_url != url):
                    self._fallback_page_requested=True
                    self._image_status="Direkte foto mangler · prøver produktside…"; self.update()
                    req=QNetworkRequest(QUrl(page_url)); req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader,f"Mozilla/5.0 ElplanDWGEditor/{APP_VERSION}")
                    nxt=self._network.get(req); self._active_replies.add(nxt)
                    nxt.finished.connect(lambda r=nxt:self._active_replies.discard(r))
                    nxt.finished.connect(lambda r=nxt,t=token,u=page_url:self._page_received(r,t,u))
                    return
                self._image_status="Onlinefoto ikke tilgængeligt"; self.update(); return
            data=bytes(reply.readAll())
            pm=QPixmap(); ok=pm.loadFromData(data)
            if not ok:
                self._image_status="Produktfoto kunne ikke læses"; self.update(); return
            self._pixmap=pm; self._image_status="Online produktfoto"
            article_no=str(self._article.get("article_no","") or "").strip().replace("/","_")
            if article_no:
                ext=Path(QUrl(url).path()).suffix.lower()
                if ext not in (".png",".jpg",".jpeg",".webp"):ext=".png"
                path=self._cache_dir/(article_no+ext)
                try:
                    if ext==".png":pm.save(str(path),"PNG")
                    elif ext in (".jpg",".jpeg"):pm.save(str(path),"JPG",90)
                    else:pm.save(str(path))
                except Exception:pass
            self.update()
        finally:
            reply.deleteLater()

    @staticmethod
    def _module_geometry(module):
        m=str(module or '').replace('×','x').replace('½','.5').replace(',','.')
        import re
        mm=re.match(r'\s*(\d+)x(\d+(?:\.5)?)M\s*$',m,re.I)
        if mm:
            cols=max(1,int(mm.group(1))); rows=max(.5,float(mm.group(2)))
            return cols,rows
        mm=re.match(r'\s*(\d+(?:\.5)?)M\s*$',m,re.I)
        if mm: return 1,max(.5,float(mm.group(1)))
        return 1,1

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        bg=self.palette().color(QPalette.ColorRole.Base)
        fg=self.palette().color(QPalette.ColorRole.Text)
        muted=self.palette().color(QPalette.ColorRole.Mid)
        p.fillRect(self.rect(),bg)
        art=self._article
        if not art:
            p.setPen(muted); p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'Vælg en artikel\nfor illustration')
            return
        if not self._pixmap.isNull():
            area=QRectF(16,12,max(40,self.width()-32),max(60,self.height()-48))
            scaled=self._pixmap.scaled(int(area.width()),int(area.height()),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
            x=area.center().x()-scaled.width()/2; y=area.center().y()-scaled.height()/2
            p.drawPixmap(QPointF(x,y),scaled)
            p.setPen(muted); p.setFont(QFont('',8))
            p.drawText(QRectF(8,self.height()-28,self.width()-16,18),Qt.AlignmentFlag.AlignCenter,self._image_status or 'Produktfoto')
            return
        facets=core.article_filter_facets(art)
        typ=facets.get('product_type',''); design=facets.get('design_family',''); module=facets.get('module_size','')
        color_name=facets.get('color','')
        colors={'Hvid':'#f7f7f5','Koksgrå':'#52565c','Stål':'#b9bdc3','Lysegrå':'#d8dadd','Sort':'#25272a','Rød':'#b84d4d','Petroleum':'#4a7777'}
        face=QColor(colors.get(color_name,'#edf0f2'))
        outline=QColor('#49515a')
        x0,y0,w,h=28,24,max(80,self.width()-56),max(90,self.height()-70)
        # Kabel: tre ledere og en lille kabelrulle.
        if typ=='Kabel':
            p.setPen(QPen(outline,4));
            cy=y0+h*.46
            p.drawLine(x0+20,int(cy),x0+w-28,int(cy))
            p.setPen(QPen(QColor('#7a7f86'),2))
            p.drawEllipse(QRectF(x0+w-82,cy-32,64,64)); p.drawEllipse(QRectF(x0+w-68,cy-18,36,36))
            p.setPen(fg); p.setFont(QFont('',11,QFont.Weight.DemiBold)); p.drawText(QRectF(x0,y0+h-28,w,24),Qt.AlignmentFlag.AlignCenter,str(art.get('cable_spec','') or module or 'Kabel'))
            return
        cols,rows=self._module_geometry(module)
        aspect=max(.6,min(2.8,cols/max(.5,rows)))
        maxw=w*.70; maxh=h*.68
        dw=min(maxw,maxh*aspect); dh=dw/aspect
        if dh>maxh: dh=maxh; dw=dh*aspect
        cx=x0+w/2; cy=y0+h*.42
        r=QRectF(cx-dw/2,cy-dh/2,dw,dh)
        # Dåser.
        if 'dåse' in typ.casefold():
            p.setPen(QPen(outline,2)); p.setBrush(QBrush(QColor('#dce5ef'))); p.drawRoundedRect(r,10,10)
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor('#8190a0'),2))
            p.drawEllipse(QRectF(r.left()+10,r.center().y()-7,14,14)); p.drawEllipse(QRectF(r.right()-24,r.center().y()-7,14,14))
            for i in range(max(1,int(round(rows)))):
                yy=r.top()+(i+.5)*r.height()/max(1,int(round(rows)))
                p.drawEllipse(QRectF(r.center().x()-8,yy-8,16,16))
        # Rammer.
        elif 'ramme' in typ.casefold():
            technical='teknisk' in typ.casefold()
            thick=3 if design=='SLIM' else (7 if '63' in design else 5)
            p.setPen(QPen(outline,2)); p.setBrush(QBrush(QColor('#c9cdd1') if technical else face)); p.drawRoundedRect(r,8,8)
            inner=r.adjusted(thick+5,thick+5,-thick-5,-thick-5)
            p.setBrush(QBrush(bg)); p.setPen(QPen(QColor('#717983'),1.5)); p.drawRoundedRect(inner,4,4)
            if technical:
                for xx,yy in ((r.left()+10,r.top()+10),(r.right()-10,r.top()+10),(r.left()+10,r.bottom()-10),(r.right()-10,r.bottom()-10)):
                    p.setBrush(QBrush(bg)); p.drawEllipse(QPointF(xx,yy),3.5,3.5)
            else:
                # Vis modulopdeling diskret ved kombinationsrammer.
                if cols>1:
                    for i in range(1,int(cols)):
                        xx=inner.left()+i*inner.width()/cols; p.drawLine(QPointF(xx,inner.top()+4),QPointF(xx,inner.bottom()-4))
        elif 'stikkontakt' in typ.casefold() or 'udtag' in typ.casefold():
            p.setPen(QPen(outline,2)); p.setBrush(QBrush(face)); p.drawRoundedRect(r,10,10)
            rr=min(r.width(),r.height())*.15
            p.setBrush(QBrush(bg));
            p.drawEllipse(QPointF(r.center().x()-rr,r.center().y()),rr*.55,rr*.55); p.drawEllipse(QPointF(r.center().x()+rr,r.center().y()),rr*.55,rr*.55)
            p.drawLine(QPointF(r.center().x(),r.center().y()+rr*.6),QPointF(r.center().x(),r.center().y()+rr*1.5))
        else:
            p.setPen(QPen(outline,2)); p.setBrush(QBrush(face)); p.drawRoundedRect(r,9,9)
            # rocker / Wiser-markering
            inset=r.adjusted(12,12,-12,-12); p.setBrush(QBrush(bg)); p.drawRoundedRect(inset,5,5)
            if design=='Wiser' or 'wiser' in str(art.get('description','')).casefold():
                p.setPen(QPen(QColor('#58758f'),2))
                c=inset.center(); p.drawArc(QRectF(c.x()-20,c.y()-20,40,40),35*16,110*16); p.drawArc(QRectF(c.x()-13,c.y()-13,26,26),35*16,110*16)
        # lille specifikationslinje i selve illustrationen
        p.setPen(fg); p.setFont(QFont('',10,QFont.Weight.DemiBold))
        label=' · '.join(x for x in (design,module,color_name) if x)
        p.drawText(QRectF(x0,y0+h-28,w,24),Qt.AlignmentFlag.AlignCenter,label or typ)

class BomArticleHoverPopup(QFrame):
    """Let produktfoto-popup til BOM-rækker. Tager hverken fokus eller museklik."""
    def __init__(self,parent=None):
        super().__init__(parent,Qt.WindowType.ToolTip|Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating,True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True)
        self.setObjectName("bomArticleHoverPopup")
        self.setStyleSheet("QFrame#bomArticleHoverPopup{border:1px solid palette(mid);border-radius:10px;background:palette(base);}")
        root=QVBoxLayout(self); root.setContentsMargins(8,8,8,8); root.setSpacing(5)
        self.title=QLabel(); self.title.setWordWrap(True); self.title.setTextFormat(Qt.TextFormat.RichText); root.addWidget(self.title)
        self.preview=ArticleVisualPreview(self); self.preview.setMinimumSize(280,210); self.preview.setMaximumSize(330,250); root.addWidget(self.preview)
        self.setFixedSize(350,305)

    def show_article(self,article,global_pos):
        art=dict(article or {})
        if not art:self.hide(); return
        no=str(art.get("article_no","") or "")
        desc=str(art.get("description","") or "")
        import html as _html
        self.title.setText(f"<b>{_html.escape(no)}</b>"+(f"<br><span style='color:#64748b'>{_html.escape(desc)}</span>" if desc else ""))
        self.preview.set_article(art)
        pos=global_pos
        x=int(pos.x()+18); y=int(pos.y()+18)
        screen=QGuiApplication.screenAt(pos)
        if screen is not None:
            g=screen.availableGeometry()
            if x+self.width()>g.right():x=int(pos.x()-self.width()-18)
            if y+self.height()>g.bottom():y=int(pos.y()-self.height()-18)
            x=max(g.left(),min(x,g.right()-self.width()+1)); y=max(g.top(),min(y,g.bottom()-self.height()+1))
        self.move(x,y); self.show(); self.raise_()


class ArticlePickerDialog(QDialog):
    """Filtrerbar artikelvælger til styklister og andre kompakte workflows."""
    def __init__(self,parent,catalog,title="Vælg artikel",initial_article_no="",kind_filter=""):
        super().__init__(parent)
        configure_modern_dialog(self,title=title,minimum_size=(760,520))
        _resize_dialog(self,1180,700)
        normalized=deepcopy(core.normalize_article_catalog(catalog))
        self.kind_filter=str(kind_filter or "").strip().casefold()
        if self.kind_filter:
            normalized=[a for a in normalized if str(a.get("kind","") or "").strip().casefold()==self.kind_filter]
        self.catalog=normalized
        self._catalog_by_no={str(a.get("article_no","") or ""):a for a in self.catalog}
        self._visible=[]
        self._selected_no=str(initial_article_no or "")
        usage_settings=core.load_app_settings()
        self.price_vat_mode=price_display.normalize_vat_mode(usage_settings.get("price_vat_mode"))
        self._favorite_article_nos=[str(x) for x in usage_settings.get("favorite_articles",[]) if str(x).strip()]
        self._recent_article_nos=[str(x) for x in usage_settings.get("recent_articles",[]) if str(x).strip()][:24]
        try:self._project_article_nos=set(parent._project_article_nos()) if hasattr(parent,"_project_article_nos") else set()
        except Exception:self._project_article_nos=set()
        # Facetter og søgetekst beregnes én gang og genbruges under filtrering.
        # Kabelvælgeren bruger samme hurtige model, men med kabelartikler inkluderet.
        self._enriched_catalog=build_article_search_index(self.catalog,include_cables=True)
        self._search_timer=QTimer(self); self._search_timer.setSingleShot(True); self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self._refresh)

        root=QVBoxLayout(self)
        root.setContentsMargins(14,14,14,14); root.setSpacing(10)
        root.addWidget(make_dialog_header(title,"Søg, filtrér og vælg en konkret artikel. Dobbeltklik kan bruges som hurtig genvej.",eyebrow="ARTIKELVÆLGER"))
        filter_box=QGroupBox("Filtre")
        filters=QGridLayout(filter_box); filters.setHorizontalSpacing(8); filters.setVerticalSpacing(6)
        self.search=QLineEdit(); self.search.setPlaceholderText("Søg på artikelnummer, navn, EAN, EL-nr., serie, specifikation…"); self.search.setClearButtonEnabled(True)
        filters.addWidget(QLabel("Søg"),0,0); filters.addWidget(self.search,0,1,1,7)
        self.manufacturer=QComboBox(); self.category=QComboBox(); self.product_type=QComboBox(); self.design=QComboBox(); self.variant=QComboBox(); self.module=QComboBox(); self.color=QComboBox(); self.status=QComboBox()
        if self.kind_filter=="cable":
            controls=(("Fabrikat",self.manufacturer,"manufacturer","Alle fabrikater"),("Serie",self.product_type,"series","Alle serier"),("Kabeltype",self.design,"cable_spec","Alle kabeltyper"),("Enhed",self.module,"unit","Alle enheder"),("Rulle [m]",self.color,"package_length_m","Alle pakninger"),("Status",self.status,"status","Alle statusser"))
        else:
            controls=(("Fabrikat",self.manufacturer,"manufacturer","Alle fabrikater"),("Kategori",self.category,"category_normalized","Alle kategorier"),("Type",self.product_type,"product_type","Alle typer"),("Produktfamilie",self.design,"product_family","Alle familier"),("Variant",self.variant,"product_variant","Alle varianter"),("Modul",self.module,"module_group","Alle moduler"),("Farve",self.color,"color","Alle farver"),("Status",self.status,"status","Alle statusser"))
        self._filter_specs=controls
        for i,(label,combo,key,all_label) in enumerate(controls):
            filters.addWidget(QLabel(label),1,i)
            filters.addWidget(combo,2,i)
            combo.setMinimumContentsLength(11)
            combo.currentIndexChanged.connect(self._refresh)
        self.scope=QComboBox(); self.scope.addItem("Alle",""); self.scope.addItem("★ Favoritter","favorites"); self.scope.addItem("Senest anvendte","recent")
        if self._project_article_nos:self.scope.addItem("Brugt i projekt","project")
        self.scope.currentIndexChanged.connect(self._refresh); filters.addWidget(QLabel("Vis"),3,0); filters.addWidget(self.scope,3,1)
        self.only_ean=QCheckBox("Kun med EAN")
        self.only_ean.toggled.connect(self._refresh)
        filters.addWidget(self.only_ean,3,2,1,2)
        self.only_price=QCheckBox("Kun med pris")
        self.only_price.toggled.connect(self._refresh); filters.addWidget(self.only_price,3,4,1,2)
        clear=_set_role(QPushButton("Nulstil filtre"), "quietButton"); clear.clicked.connect(self._clear_filters); filters.addWidget(clear,3,6)
        root.addWidget(filter_box)

        body=QHBoxLayout(); body.setSpacing(12); root.addLayout(body,1)
        left=QVBoxLayout(); body.addLayout(left,3)
        self.table=QTableView()
        if self.kind_filter=="cable":
            columns=(
                ("Artikelnummer","article_no"),("Beskrivelse","description"),("Serie","series"),("Kabeltype","cable_spec"),
                ("Enhed","unit"),("Pakning [m]","package_length_m"),("Pris ekskl. moms","__price__"),("Fabrikat","manufacturer"),
            )
            widths=(135,420,145,120,80,100,125,180)
            table_key="cable_article_picker"
        else:
            columns=(
                ("Artikelnummer","article_no"),("Beskrivelse","description"),("Kategori","category_normalized"),("Type","product_type"),("Funktion","function"),("Produktfamilie","product_family"),("Variant","product_variant"),
                ("Modul","module_size"),("Farve","color"),("Pris ekskl. moms","__price__"),("EAN","ean"),("EL-/LM-nr.","el_no"),("Fabrikat","manufacturer"),
            )
            widths=(125,390,220,150,140,165,105,80,90,120,140,120,175)
            table_key="article_picker_v05923"
        self.table_model=ArticleTableModel(columns,self.table)
        self.table_model.set_price_vat_mode(self.price_vat_mode)
        self.table.setModel(self.table_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True); self.table.verticalHeader().setVisible(False); self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setSortingEnabled(True); self.table_model.clear_sort()
        _configure_resizable_table(self.table,table_key,widths)
        self.table.selectionModel().selectionChanged.connect(lambda *_:self._selection_changed())
        self.table.doubleClicked.connect(self._accept_selection)
        left.addWidget(self.table,1)
        table_footer=QHBoxLayout()
        self.count=QLabel(); self.count.setObjectName("sectionHint"); table_footer.addWidget(self.count)
        table_footer.addStretch(1)
        fit_cols=_set_role(QPushButton("Tilpas kolonner"), "quietButton"); fit_cols.setToolTip("Tilpas kolonnebredder til det viste indhold. Du kan også trække direkte i kolonnekanterne.")
        fit_cols.clicked.connect(lambda:_fit_table_columns(self.table)); table_footer.addWidget(fit_cols)
        reset_cols=_set_role(QPushButton("Nulstil bredder"), "quietButton"); reset_cols.clicked.connect(lambda:_reset_table_columns(self.table)); table_footer.addWidget(reset_cols)
        left.addLayout(table_footer)

        right_panel=QFrame(); right_panel.setObjectName("detailPanel"); right_panel.setMinimumWidth(330)
        right=QVBoxLayout(right_panel); right.setContentsMargins(12,12,12,12); right.setSpacing(8); body.addWidget(right_panel,2)
        self.preview_title=QLabel("Vælg en artikel"); self.preview_title.setWordWrap(True); self.preview_title.setObjectName("sectionTitle"); right.addWidget(self.preview_title)
        self.preview=ArticleVisualPreview(right_panel); self.preview.setMinimumHeight(270); right.addWidget(self.preview,1)
        self.preview_specs=QLabel(); self.preview_specs.setWordWrap(True); right.addWidget(self.preview_specs)
        self.preview_meta=QLabel(); self.preview_meta.setWordWrap(True); self.preview_meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); self.preview_meta.setObjectName("subtleText"); right.addWidget(self.preview_meta)
        links=QHBoxLayout()
        self.open_product=_set_role(QPushButton("Producent"), "quietButton"); self.open_product.setToolTip("Åbn producentens produktside")
        self.open_product.clicked.connect(self._open_product); links.addWidget(self.open_product)
        self.open_supplier=_set_role(QPushButton("Leverandør"), "quietButton"); self.open_supplier.setToolTip("Åbn grossist-/leverandørside, hvis den findes")
        self.open_supplier.clicked.connect(self._open_supplier); links.addWidget(self.open_supplier)
        self.favorite_button=_set_role(QPushButton("☆ Favorit"),"quietButton"); self.favorite_button.clicked.connect(self._toggle_favorite); links.addWidget(self.favorite_button)
        links.addStretch(1); right.addLayout(links)

        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Vælg artikel")
        buttons.accepted.connect(self._accept_selection); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.ok_button=buttons.button(QDialogButtonBox.StandardButton.Ok)

        self.search.textChanged.connect(self._schedule_refresh)
        _restore_dialog_geometry(self,"article_picker")
        self._populate_filters(); self._refresh()

    def _schedule_refresh(self,*_):
        # Debounce gør hurtig indtastning flydende; kun den seneste søgning køres.
        self._search_timer.start()

    def _enriched(self):
        return self._enriched_catalog

    def _populate_filters(self):
        enriched=self._enriched()
        module_order={"1M":1,"1½M":2,"2M":3,"2½M":4,"3M":5,"3½M":6,"4M":7}
        for _caption,combo,key,label in self._filter_specs:
            combo.blockSignals(True); combo.clear(); combo.addItem(label,"")
            vals={str(a.get(key,"") or "") for a in enriched if str(a.get(key,"") or "")}
            if key=="package_length_m":
                def package_key(x):
                    try:return (float(x),x)
                    except Exception:return (999999.0,x)
                names=sorted(vals,key=package_key)
            else:
                names=sorted(vals,key=(lambda x:(module_order.get(x,99),x.casefold())) if key=="module_group" else str.casefold)
            for name in names:
                display=("Afmålt" if key=="package_length_m" and float(name or 0)<=0 else (f"{float(name):g}" if key=="package_length_m" else name))
                combo.addItem(display,name)
            combo.blockSignals(False)

    def _clear_filters(self):
        self._search_timer.stop()
        filter_combos=[combo for _caption,combo,_key,_label in self._filter_specs]
        controls=(self.search,self.scope,*filter_combos,self.only_ean,self.only_price)
        blockers=[QSignalBlocker(control) for control in controls]
        self.search.clear(); self.scope.setCurrentIndex(0)
        for combo in filter_combos: combo.setCurrentIndex(0)
        self.only_ean.setChecked(False); self.only_price.setChecked(False)
        del blockers
        self._refresh()

    def _refresh(self,*_):
        self._search_timer.stop()
        query=self.search.text().strip()
        wanted={key:str(combo.currentData() or "") for _caption,combo,key,_label in self._filter_specs}
        scope=str(self.scope.currentData() or "") if hasattr(self,"scope") else ""
        favorite=set(self._favorite_article_nos); recent_rank={no:i for i,no in enumerate(self._recent_article_nos)}
        visible=[]
        for art in self._enriched_catalog:
            no=str(art.get("article_no","") or "")
            if scope=="favorites" and no not in favorite:continue
            if scope=="recent" and no not in recent_rank:continue
            if scope=="project" and no not in self._project_article_nos:continue
            if any(v and str(art.get(k,"") or "")!=v for k,v in wanted.items()): continue
            if self.only_ean.isChecked() and not str(art.get("ean","") or "").strip(): continue
            if self.only_price.isChecked() and str(art.get("unit_price","")).strip()=="": continue
            score=article_search_score(art,query,favorite=no in favorite,recent_rank=recent_rank.get(no),project=no in self._project_article_nos)
            if score is None:continue
            row=dict(art); row["_search_score"]=score; visible.append(row)
        visible.sort(key=lambda a:(-float(a.get("_search_score",0) or 0),str(a.get("manufacturer","") or "").casefold(),str(a.get("article_no","") or "").casefold()))
        self._visible=visible
        selected_no=self._selected_no
        current=self._selected_article()
        if current: selected_no=str(current.get("article_no","") or selected_no)
        self.table_model.set_rows(visible)
        restore=self.table_model.row_for_article_no(selected_no)
        if self.table_model.rowCount():
            self.table.selectRow(restore if restore>=0 else 0)
        else:
            self.table.clearSelection(); self._selection_changed()
        self.count.setText(f"{len(visible)} artikler")

    def _selected_article(self):
        rows=sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:return {}
        no=self.table_model.article_no_at(rows[0])
        return self._catalog_by_no.get(no,{})

    def _selection_changed(self):
        art=self._selected_article(); self.ok_button.setEnabled(bool(art))
        self.open_product.setEnabled(bool(art and str(art.get("product_page","") or art.get("source","")).startswith(("http://","https://"))))
        self.open_supplier.setEnabled(bool(art and str(art.get("supplier_page","") or "").startswith(("http://","https://"))))
        if hasattr(self,"favorite_button"):
            no=str(art.get("article_no","") or "") if art else ""
            self.favorite_button.setEnabled(bool(art)); self.favorite_button.setText("★ Favorit" if no in self._favorite_article_nos else "☆ Favorit")
        self.preview.set_article(art)
        if not art:
            self.preview_title.setText("Vælg en artikel"); self.preview_specs.clear(); self.preview_meta.clear(); return
        facets=core.article_filter_facets(art)
        self.preview_title.setText(f"{art.get('article_no','')} · {art.get('description','')}")
        if self.kind_filter=="cable":
            package=float(art.get("package_length_m",0) or 0)
            package_text="afmålt" if package<=0 else f"{package:g} m rulle"
            tags=[str(art.get("series","") or ""),str(art.get("cable_spec","") or ""),package_text,str(art.get("unit","") or "")]
        else:
            tags=[str(art.get("category_normalized","") or ""),facets.get("product_type",""),str(art.get("function","") or ""),str(art.get("product_family","") or facets.get("product_family","")),str(art.get("product_variant","") or facets.get("product_variant","")),facets.get("module_size",""),facets.get("color","")]
        self.preview_specs.setText(" · ".join(x for x in tags if x))
        meta=[]
        meta.extend(_article_price_meta_lines(art,self.price_vat_mode))
        meta.append(_article_packaging_meta_line(art))
        if art.get("ean"):meta.append(f"EAN: {art['ean']}")
        if art.get("el_no"):meta.append(f"EL-/LM-nr.: {art['el_no']}")
        if art.get("manufacturer"):meta.append(str(art['manufacturer']))
        if art.get("status"):meta.append(f"Status: {art['status']}")
        if int(art.get("variant_count",1) or 1)>1:meta.append(f"Variantgruppe: {int(art.get('variant_count',1))} artikler")
        compat=article_intelligence.compatibility_text(art)
        if compat:meta.append("Kompatibilitet: "+compat)
        spec_lines=article_intelligence.technical_specs_text(art,limit=5)
        if spec_lines:meta.append("Egenskaber: "+" · ".join(spec_lines))
        self.preview_meta.setText("\n".join(meta))

    def _toggle_favorite(self,*_):
        art=self._selected_article(); no=str(art.get("article_no","") or "").strip()
        if not no:return
        if no in self._favorite_article_nos:self._favorite_article_nos=[x for x in self._favorite_article_nos if x!=no]
        else:self._favorite_article_nos.insert(0,no)
        data=core.load_app_settings(); data["favorite_articles"]=list(dict.fromkeys(self._favorite_article_nos))[:200]; core.save_app_settings(data)
        self._refresh(); self._selection_changed()

    def _open_product(self):
        art=self._selected_article(); url=str(art.get("product_page","") or art.get("source","") or "")
        if url.startswith(("http://","https://")): QDesktopServices.openUrl(QUrl(url))

    def _open_supplier(self):
        art=self._selected_article(); url=str(art.get("supplier_page","") or "")
        if url.startswith(("http://","https://")): QDesktopServices.openUrl(QUrl(url))

    def _accept_selection(self,*_):
        art=self._selected_article()
        if not art:return
        self._selected_no=str(art.get("article_no","") or "")
        self._recent_article_nos=[x for x in self._recent_article_nos if x!=self._selected_no]; self._recent_article_nos.insert(0,self._selected_no); self._recent_article_nos=self._recent_article_nos[:24]
        data=core.load_app_settings(); data["recent_articles"]=list(self._recent_article_nos); core.save_app_settings(data)
        self.accept()

    def selected_article_no(self):
        return self._selected_no


class ArticleRelationsDialog(QDialog):
    """Review variants, confirmed relations and non-destructive suggestions."""
    def __init__(self,parent,article:dict,catalog):
        super().__init__(parent)
        configure_modern_dialog(self,title="Relationer og varianter",minimum_size=(820,560))
        _resize_dialog(self,1040,680)
        self.article=deepcopy(dict(article or {}))
        self.catalog=deepcopy(core.normalize_article_catalog(catalog))
        self._relations=article_intelligence.normalize_relations(self.article.get("relations",[]),article_no=self.article.get("article_no",""))
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(9)
        title=QLabel(f"{self.article.get('article_no','')} · {self.article.get('description','')}"); title.setWordWrap(True); title.setObjectName("sectionTitle"); root.addWidget(title)
        info=QLabel("Varianter grupperes automatisk ud fra samme grundprodukt. Bekræftede relationer gemmes i databasen. Forslag er kun kandidater og bliver aldrig automatisk gjort til kompatibilitetsrelationer.")
        info.setWordWrap(True); info.setObjectName("subtleText"); root.addWidget(info)
        self.tabs=QTabWidget(); root.addWidget(self.tabs,1)

        self.variant_table=self._make_table(("Artikelnummer","Beskrivelse","Fabrikat","Variant"),"article_variants",(130,420,190,300))
        vtab=QWidget(); vl=QVBoxLayout(vtab); vl.setContentsMargins(6,6,6,6); vl.addWidget(self.variant_table); self.tabs.addTab(vtab,"Varianter")

        rtab=QWidget(); rl=QVBoxLayout(rtab); rl.setContentsMargins(6,6,6,6)
        self.relation_table=self._make_table(("Relation","Artikelnummer","Beskrivelse","Kilde","Note"),"article_relations",(150,130,400,130,280)); rl.addWidget(self.relation_table,1)
        tools=QHBoxLayout(); add=_set_role(QPushButton("Tilføj relation…"),"primaryButton"); add.clicked.connect(self._add_relation); tools.addWidget(add)
        remove=_set_role(QPushButton("Fjern relation"),"dangerButton"); remove.clicked.connect(self._remove_relation); tools.addWidget(remove); tools.addStretch(1); rl.addLayout(tools)
        self.tabs.addTab(rtab,"Bekræftede relationer")

        stab=QWidget(); sl=QVBoxLayout(stab); sl.setContentsMargins(6,6,6,6)
        self.suggestion_table=self._make_table(("Artikelnummer","Beskrivelse","Fabrikat","Match","Begrundelse"),"article_relation_suggestions",(130,400,180,90,420)); sl.addWidget(self.suggestion_table,1)
        st=QHBoxLayout(); accept=_set_role(QPushButton("Bekræft valgt forslag"),"primaryButton"); accept.clicked.connect(self._accept_suggestion); st.addWidget(accept); st.addStretch(1); sl.addLayout(st)
        hint=QLabel("Et forslag betyder kun, at metadata ligner en relevant kombination. Mekanisk/elektrisk kompatibilitet skal bekræftes før relationen gemmes."); hint.setWordWrap(True); hint.setObjectName("sectionHint"); sl.addWidget(hint)
        self.tabs.addTab(stab,"Forslag")

        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Gem relationer")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self._refresh()

    def _make_table(self,headers,key,widths):
        table=QTableWidget(0,len(headers)); table.setHorizontalHeaderLabels(list(headers)); table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); _configure_resizable_table(table,key,widths); return table

    @staticmethod
    def _set_rows(table,rows):
        table.setRowCount(len(rows))
        for r,vals in enumerate(rows):
            for c,val in enumerate(vals): table.setItem(r,c,_table_item(val))

    def _context(self):
        article=deepcopy(self.article); article["relations"]=deepcopy(self._relations)
        normalized=core.normalize_article_catalog([article]+[r for r in self.catalog if str(r.get("article_no",""))!=str(article.get("article_no",""))])
        current=next((r for r in normalized if str(r.get("article_no",""))==str(article.get("article_no",""))),article)
        return article_intelligence.relation_context(current,normalized)

    def _refresh(self):
        ctx=self._context(); self._last_context=ctx
        self._set_rows(self.variant_table,[(r.get("article_no",""),r.get("description",""),r.get("manufacturer",""),r.get("variant","")) for r in ctx.get("variants",[])])
        self._set_rows(self.relation_table,[(r.get("type_label",""),r.get("target_article_no",""),r.get("description",""),r.get("source",""),r.get("note","")) for r in ctx.get("confirmed",[])])
        self._set_rows(self.suggestion_table,[(r.get("article_no",""),r.get("description",""),r.get("manufacturer",""),f"{r.get('confidence',0)} %",r.get("reason","")) for r in ctx.get("suggestions",[])])
        self.tabs.setTabText(0,f"Varianter ({len(ctx.get('variants',[]))})")
        self.tabs.setTabText(1,f"Bekræftede relationer ({len(ctx.get('confirmed',[]))})")
        self.tabs.setTabText(2,f"Forslag ({len(ctx.get('suggestions',[]))})")

    def _add_relation(self):
        dlg=ArticlePickerDialog(self,self.catalog,"Vælg relateret artikel")
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        target=dlg.selected_article_no()
        if not target or target.casefold()==str(self.article.get("article_no","")).casefold():return
        labels=[article_intelligence.RELATION_TYPES[k] for k in article_intelligence.RELATION_TYPES]
        label,ok=QInputDialog.getItem(self,"Relationstype","Type",labels,0,False)
        if not ok:return
        rel_type=next((k for k,v in article_intelligence.RELATION_TYPES.items() if v==label),"compatible")
        note,ok=QInputDialog.getText(self,"Relation","Note (valgfri)")
        if not ok:return
        self._relations.append({"type":rel_type,"target_article_no":target,"source":"manual","note":str(note or "").strip()})
        self._relations=article_intelligence.normalize_relations(self._relations,article_no=self.article.get("article_no","")); self._refresh()

    def _remove_relation(self):
        row=self.relation_table.currentRow()
        confirmed=list(getattr(self,"_last_context",{}).get("confirmed",[]))
        if not (0<=row<len(confirmed)):return
        target=str(confirmed[row].get("target_article_no","") or "").casefold(); typ=str(confirmed[row].get("type","") or "")
        self._relations=[r for r in self._relations if not (str(r.get("target_article_no","") or "").casefold()==target and str(r.get("type","") or "")==typ)]; self._refresh()

    def _accept_suggestion(self):
        row=self.suggestion_table.currentRow(); suggestions=list(getattr(self,"_last_context",{}).get("suggestions",[]))
        if not (0<=row<len(suggestions)):return
        item=suggestions[row]; self._relations.append({"type":str(item.get("suggested_type","compatible") or "compatible"),"target_article_no":str(item.get("article_no","") or ""),"source":"confirmed suggestion","note":"Metadataforslag bekræftet manuelt"})
        self._relations=article_intelligence.normalize_relations(self._relations,article_no=self.article.get("article_no","")); self._refresh(); self.tabs.setCurrentIndex(1)

    def relations(self):
        return deepcopy(self._relations)

class AssemblyNameAssistantDialog(QDialog):
    """Hjælp til et ensartet stykliste-navn med strukturerede filterfelter."""

    def __init__(self,parent,record=None,catalog=None):
        super().__init__(parent)
        configure_modern_dialog(self,title="Navneassistent",size=(690,520),minimum_size=(590,470))
        self.record=deepcopy(dict(record or {}))
        self.catalog=deepcopy(list(catalog or []))
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(10)
        root.addWidget(make_dialog_header(
            "Hjælp til stykliste-navn",
            "Guidet udfyldning af de samme navneparametre, som findes i styklistevinduet. System/serie er en kontrolleret liste med verificerede LK/Schneider-betegnelser. Selve navnet kan altid redigeres manuelt bagefter.",
            eyebrow="STYKLISTENAVN"))

        form=QGridLayout(); form.setHorizontalSpacing(12); form.setVerticalSpacing(8)
        self.product_type=self._editable_combo(assembly_naming.TYPE_OPTIONS)
        self.configuration=self._editable_combo(assembly_naming.CONFIGURATION_OPTIONS)
        self.function=self._editable_combo(assembly_naming.FUNCTION_OPTIONS)
        self.system=self._system_combo()
        self.mounting=self._editable_combo(assembly_naming.MOUNTING_OPTIONS)
        self.color=self._editable_combo(assembly_naming.COLOR_OPTIONS)
        self.extra=QLineEdit(); self.extra.setPlaceholderText("Fx dobbelt, køkken, med ekstra udtag …")
        form.addWidget(QLabel("Type"),0,0); form.addWidget(self.product_type,0,1)
        form.addWidget(QLabel("Opbygning"),0,2); form.addWidget(self.configuration,0,3)
        form.addWidget(QLabel("Funktion / udførelse"),1,0); form.addWidget(self.function,1,1)
        form.addWidget(QLabel("System / serie"),1,2); form.addWidget(self.system,1,3)
        form.addWidget(QLabel("Montering"),2,0); form.addWidget(self.mounting,2,1)
        form.addWidget(QLabel("Farve"),2,2); form.addWidget(self.color,2,3)
        form.addWidget(QLabel("Ekstra tekst"),3,0); form.addWidget(self.extra,3,1,1,3)
        root.addLayout(form)

        self.system_info=QLabel("System/serie kan ikke fritekstes her. Vælg kun en verificeret betegnelse; brug et helt manuelt stykliste-navn, hvis du har et specialtilfælde.")
        self.system_info.setWordWrap(True); self.system_info.setObjectName("sectionHint"); root.addWidget(self.system_info)

        preview_box=QGroupBox("Navneforslag")
        preview_layout=QVBoxLayout(preview_box)
        self.preview=QLineEdit(); self.preview.setReadOnly(True); self.preview.setObjectName("accentText")
        self.preview.setPlaceholderText("Vælg mindst ét felt")
        preview_layout.addWidget(self.preview); root.addWidget(preview_box)

        tools=QHBoxLayout()
        infer=_set_role(QPushButton("Udfyld fra stykliste"),"quietButton"); infer.setToolTip("Genfortolk navn og komponenter og udfyld parametrene på ny."); infer.clicked.connect(self._infer_from_content); tools.addWidget(infer)
        tools.addStretch(1); root.addLayout(tools)

        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Brug navn og parametre")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuller")
        buttons.accepted.connect(self._accept_checked); buttons.rejected.connect(self.reject); root.addWidget(buttons)

        for widget in (self.product_type,self.configuration,self.function,self.mounting,self.color):
            widget.currentTextChanged.connect(self._update_preview)
        self.system.currentIndexChanged.connect(self._update_preview)
        self.extra.textChanged.connect(self._update_preview)
        self._infer()

    @staticmethod
    def _editable_combo(values):
        combo=QComboBox(); combo.setEditable(True); combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert); combo.addItems(list(values)); combo.setMinimumContentsLength(18)
        return combo

    @staticmethod
    def _system_combo():
        combo=QComboBox(); combo.setEditable(False); combo.setMinimumContentsLength(24)
        for row in assembly_naming.SYSTEM_SERIES:
            combo.addItem(str(row.get("label",row.get("value",""))),str(row.get("value","") or ""))
        return combo

    @staticmethod
    def _set_combo_text(combo,text):
        combo.setCurrentText(str(text or ""))

    def _set_system(self,value):
        value=str(value or "")
        idx=self.system.findData(value); self.system.setCurrentIndex(idx if idx>=0 else 0)

    def _current_record(self):
        return deepcopy(self.record)

    def _infer(self):
        values=assembly_naming.infer_assembly_name_fields(self._current_record(),self.catalog)
        blockers=[QSignalBlocker(w) for w in (self.product_type,self.configuration,self.function,self.system,self.mounting,self.color,self.extra)]
        self._set_combo_text(self.product_type,values.get("product_type",""))
        self._set_combo_text(self.configuration,values.get("configuration",""))
        self._set_combo_text(self.function,values.get("function",""))
        self._set_system(values.get("system_series",""))
        self._set_combo_text(self.mounting,values.get("mounting",""))
        self._set_combo_text(self.color,values.get("color",""))
        self.extra.setText(values.get("extra",""))
        del blockers
        self._update_preview()

    def _infer_from_content(self):
        # Tving en frisk udledning fra navn/kategori/variant/komponenter i stedet
        # for blot at genindlæse de allerede gemte navneparametre.
        record=deepcopy(self._current_record())
        record["naming"]={}
        values=assembly_naming.infer_assembly_name_fields(record,self.catalog)
        blockers=[QSignalBlocker(w) for w in (self.product_type,self.configuration,self.function,self.system,self.mounting,self.color,self.extra)]
        self._set_combo_text(self.product_type,values.get("product_type",""))
        self._set_combo_text(self.configuration,values.get("configuration",""))
        self._set_combo_text(self.function,values.get("function",""))
        self._set_system(values.get("system_series",""))
        self._set_combo_text(self.mounting,values.get("mounting",""))
        self._set_combo_text(self.color,values.get("color",""))
        self.extra.setText(values.get("extra",""))
        del blockers
        self._update_preview()

    def naming_fields(self):
        return assembly_naming.normalize_naming_fields({
            "product_type":self.product_type.currentText(),
            "configuration":self.configuration.currentText(),
            "function":self.function.currentText(),
            "system_series":str(self.system.currentData() or ""),
            "mounting":self.mounting.currentText(),
            "color":self.color.currentText(),
            "extra":self.extra.text(),
        })

    def _update_preview(self,*_args):
        self.preview.setText(assembly_naming.build_assembly_name(**self.naming_fields()))
        system=str(self.system.currentData() or "")
        kind=assembly_naming.SYSTEM_KINDS.get(system,"")
        if system:
            self.system_info.setText(f"{system}: {kind}. Betegnelsen er fra den kuraterede, verificerede system-/serieliste.")
        else:
            self.system_info.setText("System/serie er valgfrit. Listen er kontrolleret; ukendte fritekstværdier gemmes ikke som system-/seriefilter.")

    def _accept_checked(self):
        if not self.generated_name():
            QMessageBox.information(self,"Navneassistent","Vælg eller skriv mindst én del af navnet."); return
        self.accept()

    def generated_name(self):
        return self.preview.text().strip()


class AssemblyEditDialog(QDialog):
    """Editor for en genbrugelig global BOM-stykliste."""
    def __init__(self,parent,catalog,record=None,vat_mode="excl"):
        super().__init__(parent)
        self.price_vat_mode=price_display.normalize_vat_mode(vat_mode)
        self.setWindowTitle("Stykliste")
        _resize_dialog(self,1180,800)
        self.catalog=deepcopy(core.normalize_article_catalog(catalog))
        self.original=deepcopy(dict(record or {}))
        self.naming_fields=assembly_naming.effective_naming_fields(self.original,self.catalog)
        self.items=deepcopy(self.original.get("items",[]) or [])
        self._picked_article_no=""
        self._usage_count=0
        if self.original.get("id") and hasattr(parent,"_assembly_usage_count"):
            try:self._usage_count=int(parent._assembly_usage_count(str(self.original.get("id") or "")) or 0)
            except Exception:self._usage_count=0
        self._layout_settings=core.load_app_settings()

        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(9)
        root.addWidget(make_dialog_header(
            "Stykliste",
            "Beskriv en komplet stykliste én gang og genbrug den på tværs af projektet. Faste komponenter er altid aktive; valgfrie komponenter kan slås til/fra uden at oprette en ny stykliste.",
            eyebrow="STYKLISTEBIBLIOTEK"))

        name_row=QGridLayout(); name_row.setHorizontalSpacing(10); name_row.setVerticalSpacing(7)
        self.name=QLineEdit(str(self.original.get("name","") or "")); self.name.setPlaceholderText("Fx 2×1M FUGA SLIM Stikkontakt Koksgrå")
        self.name_assistant=_set_role(QPushButton("Navneassistent…"),"quietButton"); self.name_assistant.setToolTip("Dan et navneforslag ud fra strukturerede parametre. System/serie vælges fra en verificeret liste. Navnefeltet kan altid redigeres manuelt."); self.name_assistant.clicked.connect(self._open_name_assistant)
        name_row.addWidget(QLabel("Navn *"),0,0); name_row.addWidget(self.name,0,1); name_row.addWidget(self.name_assistant,0,2)
        name_row.setColumnStretch(1,1); root.addLayout(name_row)

        classification_body=QWidget()
        classification_root=QVBoxLayout(classification_body); classification_root.setContentsMargins(8,3,8,7); classification_root.setSpacing(7)
        meta=QGridLayout(); meta.setHorizontalSpacing(10); meta.setVerticalSpacing(7)
        self.category=QLineEdit(str(self.original.get("category","") or "")); self.category.setPlaceholderText("Valgfri overordnet gruppe, fx Boliginstallation")
        self.category.setToolTip("Valgfri fri bibliotekskategori. Brug Type under Navneparametre til fx Stikkontakt/Afbryder/Lampeudtag.")
        self.variant=QLineEdit(str(self.original.get("variant","") or "")); self.variant.setPlaceholderText("Valgfri undertype, hvis navneparametrene ikke dækker den")
        self.variant.setToolTip("Valgfrit frit felt. System/serie, opbygning og farve bør angives under Navneparametre i stedet for at gentages her.")
        self.tags=QLineEdit(", ".join(str(x) for x in (self.original.get("tags",[]) or []))); self.tags.setPlaceholderText("Fx fuga, air, bolig")
        meta.addWidget(QLabel("Kategori"),0,0); meta.addWidget(self.category,0,1)
        meta.addWidget(QLabel("Variant"),0,2); meta.addWidget(self.variant,0,3)
        meta.addWidget(QLabel("Tags"),1,0); meta.addWidget(self.tags,1,1,1,3)
        classification_root.addLayout(meta)
        # De strukturerede navneparametre er fortsat direkte redigerbare i
        # styklisteeditoren, men ligger i en disclosure så komponenttabellen er
        # det primære arbejdsområde. Navnet forbliver altid synligt og frit.
        naming_box=QGroupBox("Navneparametre")
        naming_root=QVBoxLayout(naming_box); naming_root.setSpacing(7)
        naming_grid=QGridLayout(); naming_grid.setHorizontalSpacing(10); naming_grid.setVerticalSpacing(7)
        self.naming_type=AssemblyNameAssistantDialog._editable_combo(assembly_naming.TYPE_OPTIONS)
        self.naming_configuration=AssemblyNameAssistantDialog._editable_combo(assembly_naming.CONFIGURATION_OPTIONS)
        self.naming_function=AssemblyNameAssistantDialog._editable_combo(assembly_naming.FUNCTION_OPTIONS)
        self.naming_system=AssemblyNameAssistantDialog._system_combo()
        self.naming_mounting=AssemblyNameAssistantDialog._editable_combo(assembly_naming.MOUNTING_OPTIONS)
        self.naming_color=AssemblyNameAssistantDialog._editable_combo(assembly_naming.COLOR_OPTIONS)
        self.naming_extra=QLineEdit(); self.naming_extra.setPlaceholderText("Ekstra tekst i navnet (valgfri)")
        naming_grid.addWidget(QLabel("Type"),0,0); naming_grid.addWidget(self.naming_type,0,1)
        naming_grid.addWidget(QLabel("Opbygning"),0,2); naming_grid.addWidget(self.naming_configuration,0,3)
        naming_grid.addWidget(QLabel("Funktion / udførelse"),1,0); naming_grid.addWidget(self.naming_function,1,1)
        naming_grid.addWidget(QLabel("System / serie"),1,2); naming_grid.addWidget(self.naming_system,1,3)
        naming_grid.addWidget(QLabel("Montering"),2,0); naming_grid.addWidget(self.naming_mounting,2,1)
        naming_grid.addWidget(QLabel("Farve"),2,2); naming_grid.addWidget(self.naming_color,2,3)
        naming_grid.addWidget(QLabel("Ekstra tekst"),3,0); naming_grid.addWidget(self.naming_extra,3,1,1,3)
        naming_root.addLayout(naming_grid)

        naming_actions=QHBoxLayout(); naming_actions.setSpacing(7)
        self.naming_preview=QLabel(); self.naming_preview.setObjectName("sectionHint"); self.naming_preview.setWordWrap(True); naming_actions.addWidget(self.naming_preview,1)
        infer_naming=_set_role(QPushButton("Udfyld fra stykliste"),"quietButton"); infer_naming.setToolTip("Forsøg at udfylde parametrene ud fra det nuværende navn og styklistekomponenterne."); infer_naming.clicked.connect(self._infer_naming_fields); naming_actions.addWidget(infer_naming)
        apply_naming=_set_role(QPushButton("Dan navn"),"primaryButton"); apply_naming.setToolTip("Erstat navnefeltet med navnet bygget af de viste parametre. Navnet kan stadig redigeres manuelt bagefter."); apply_naming.clicked.connect(self._apply_naming_name); naming_actions.addWidget(apply_naming)
        clear_naming=_set_role(QPushButton("Ryd navneparametre"),"quietButton"); clear_naming.setToolTip("Behold navnet, men ryd de strukturerede parametre der bruges til sortering og filtrering."); clear_naming.clicked.connect(self._clear_naming_fields); naming_actions.addWidget(clear_naming)
        naming_root.addLayout(naming_actions)
        classification_root.addWidget(naming_box)
        self.classification_disclosure=DisclosureSection(
            "Klassifikation og navneparametre",classification_body,
            expanded=bool(self._layout_settings.get("assembly_editor_classification_expanded",False)))
        self.classification_disclosure.button.setToolTip("Vis kategori, variant, tags og strukturerede navneparametre.")
        root.addWidget(self.classification_disclosure)

        self._load_naming_controls(self.naming_fields)
        for widget in (self.naming_type,self.naming_configuration,self.naming_function,self.naming_mounting,self.naming_color):
            widget.currentTextChanged.connect(self._naming_controls_changed)
        self.naming_system.currentIndexChanged.connect(self._naming_controls_changed)
        self.naming_extra.textChanged.connect(self._naming_controls_changed)
        self.name.textChanged.connect(self._refresh_naming_preview)

        desc_body=QWidget(); desc_row=QHBoxLayout(desc_body); desc_row.setContentsMargins(8,3,8,7); desc_row.setSpacing(8)
        desc_box=QGroupBox("Beskrivelse")
        desc_l=QVBoxLayout(desc_box); self.description=QPlainTextEdit(str(self.original.get("description","") or "")); self.description.setMaximumHeight(76); self.description.setPlaceholderText("Hvad bruges styklisten til?"); desc_l.addWidget(self.description)
        note_box=QGroupBox("Styklistenote")
        note_l=QVBoxLayout(note_box); self.notes=QPlainTextEdit(str(self.original.get("notes","") or "")); self.notes.setMaximumHeight(76); self.notes.setPlaceholderText("Valgfri intern note, fx forudsætninger eller særlige valg."); note_l.addWidget(self.notes)
        desc_row.addWidget(desc_box,1); desc_row.addWidget(note_box,1)
        self.description_disclosure=DisclosureSection(
            "Beskrivelse og note",desc_body,
            expanded=bool(self._layout_settings.get("assembly_editor_description_expanded",False)))
        self.description_disclosure.button.setToolTip("Vis de valgfrie tekstfelter Beskrivelse og Styklistenote.")
        root.addWidget(self.description_disclosure)

        self.usage_label=QLabel()
        self.usage_label.setObjectName("sectionHint"); root.addWidget(self.usage_label)

        self.work_splitter=QSplitter(Qt.Orientation.Horizontal)
        table_panel=QWidget(); table_root=QVBoxLayout(table_panel); table_root.setContentsMargins(0,0,0,0); table_root.setSpacing(7)
        items_head=QHBoxLayout(); items_head.setSpacing(8)
        items_title=QLabel("Komponenter i styklisten"); items_title.setObjectName("sectionTitle"); items_head.addWidget(items_title)
        items_head.addStretch(1)
        self.component_panel_toggle=_set_role(QPushButton("Vis komponentpanel"),"quietButton")
        self.component_panel_toggle.setCheckable(True)
        self.component_panel_toggle.setToolTip("Vis eller skjul redigeringen ved siden af tabellen. Dobbeltklik på en tabelrække åbner panelet.")
        items_head.addWidget(self.component_panel_toggle)
        maximize_table=_set_role(QPushButton("Maksimér tabel"),"quietButton")
        maximize_table.setToolTip("Skjul alle sekundære felter og giv komponenttabellen mest mulig plads.")
        maximize_table.clicked.connect(self._maximize_component_table); items_head.addWidget(maximize_table)
        table_root.addLayout(items_head)
        self.table=QTableWidget(0,8)
        price_caption=price_display.vat_caption(self.price_vat_mode)
        self.table.setHorizontalHeaderLabels(["Artikelnummer","Beskrivelse","Rolle","Type","Med","Antal",f"Enhedspris {price_caption}",f"Sum {price_caption}"])
        # Legacy layout key: "assembly_editor"
        _configure_resizable_table(self.table,"assembly_editor_v05930",(125,300,150,100,70,75,115,115))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._item_selected)
        self.table.itemDoubleClicked.connect(lambda _item:self._set_component_panel_visible(True))
        self.table.setMinimumHeight(140)
        table_root.addWidget(self.table,1)

        table_tools=QHBoxLayout()
        self.preview_label=QLabel(); self.preview_label.setObjectName("accentText"); self.preview_label.setWordWrap(True); table_tools.addWidget(self.preview_label,1)
        fit_cols=_set_role(QPushButton("Tilpas kolonner"), "quietButton"); fit_cols.clicked.connect(lambda:_fit_table_columns(self.table)); table_tools.addWidget(fit_cols)
        reset_cols=_set_role(QPushButton("Nulstil bredder"), "quietButton"); reset_cols.clicked.connect(lambda:_reset_table_columns(self.table)); table_tools.addWidget(reset_cols)
        table_root.addLayout(table_tools)
        self.total_label=QLabel("Styklistepris: —"); self.total_label.setObjectName("accentText"); table_root.addWidget(self.total_label)

        add_box=QWidget()
        add_root=QVBoxLayout(add_box); add_root.setContentsMargins(8,3,8,7); add_root.setSpacing(6)
        row=QVBoxLayout(); row.setSpacing(7)
        self.picked_label=QLabel("Ingen artikel valgt"); self.picked_label.setWordWrap(True); self.picked_label.setObjectName("subtleText")
        choose=_set_role(QPushButton("Find artikel…"), "quietButton"); choose.clicked.connect(self._choose_article)
        self.role=QLineEdit(); self.role.setPlaceholderText("Rolle, fx indsats / ramme / dåse")
        self.qty=QDoubleSpinBox(); self.qty.setRange(.01,9999); self.qty.setDecimals(2); self.qty.setValue(1); self.qty.setPrefix("× "); self.qty.setMinimumWidth(92)
        pick_row=QHBoxLayout(); pick_row.addWidget(choose); pick_row.addWidget(self.picked_label,1); row.addLayout(pick_row)
        edit_form=QFormLayout(); edit_form.addRow("Rolle",self.role); edit_form.addRow("Antal",self.qty); row.addLayout(edit_form); add_root.addLayout(row)
        flags=QVBoxLayout(); flags.setSpacing(7)
        self.optional=QCheckBox("Valgfri komponent")
        self.optional.setToolTip("Valgfrie komponenter kan gemmes i styklisten og slås til/fra uden at oprette en ny stykliste.")
        self.included=QCheckBox("Medtag i BOM"); self.included.setChecked(True); self.included.setEnabled(False)
        self.optional.toggled.connect(self._optional_changed)
        add=_set_role(QPushButton("Tilføj / opdatér"), "primaryButton"); add.clicked.connect(self._add)
        remove=_set_role(QPushButton("Fjern"), "dangerButton"); remove.clicked.connect(self._remove)
        flags.addWidget(self.optional); flags.addWidget(self.included)
        action_row=QHBoxLayout(); action_row.addWidget(add); action_row.addWidget(remove); action_row.addStretch(1); flags.addLayout(action_row); add_root.addLayout(flags)

        hint=QLabel("Faste komponenter er altid med i BOM. En valgfri komponent kan stå i styklisten som fx alternativt tilbehør og aktiveres senere. Styklister er globale; ændringer slår igennem på alle symboldele, der bruger den samme stykliste.")
        hint.setWordWrap(True); hint.setObjectName("sectionHint"); add_root.addWidget(hint)
        self.component_disclosure=DisclosureSection(
            "Tilføj eller opdatér komponent",add_box,
            expanded=bool(self._layout_settings.get("assembly_editor_component_form_expanded",True)))
        self.component_disclosure.button.setToolTip("Skjul formularen efter redigering for at give tabellen ekstra højde.")
        self.component_panel=QWidget(); component_root=QVBoxLayout(self.component_panel); component_root.setContentsMargins(8,0,0,0)
        component_root.addWidget(self.component_disclosure); component_root.addStretch(1)
        self.component_panel.setMinimumWidth(330); self.component_panel.setMaximumWidth(430)
        self.work_splitter.addWidget(table_panel); self.work_splitter.addWidget(self.component_panel)
        self.work_splitter.setStretchFactor(0,1); self.work_splitter.setStretchFactor(1,0); self.work_splitter.setCollapsible(0,False)
        root.addWidget(self.work_splitter,1)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_checked); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.classification_disclosure.button.toggled.connect(self._persist_editor_sections)
        self.description_disclosure.button.toggled.connect(self._persist_editor_sections)
        self.component_disclosure.button.toggled.connect(self._persist_editor_sections)
        self.component_panel_toggle.toggled.connect(self._set_component_panel_visible)
        self._set_component_panel_visible(bool(self._layout_settings.get("assembly_editor_component_panel_visible",False)),persist=False)
        self._refresh()

    def _maximize_component_table(self):
        self.classification_disclosure.setExpanded(False)
        self.description_disclosure.setExpanded(False)
        self._set_component_panel_visible(False)
        self.table.setFocus()

    def _set_component_panel_visible(self,visible,persist=True):
        visible=bool(visible)
        self.component_panel.setVisible(visible)
        blocker=QSignalBlocker(self.component_panel_toggle); self.component_panel_toggle.setChecked(visible); del blocker
        self.component_panel_toggle.setText("Skjul komponentpanel" if visible else "Vis komponentpanel")
        if visible:self.component_disclosure.setExpanded(True)
        if persist:self._persist_editor_sections()

    def _persist_editor_sections(self,*_args):
        values={
            "assembly_editor_classification_expanded":self.classification_disclosure.isExpanded(),
            "assembly_editor_description_expanded":self.description_disclosure.isExpanded(),
            "assembly_editor_component_form_expanded":self.component_disclosure.isExpanded(),
            "assembly_editor_component_panel_visible":self.component_panel.isVisible(),
        }
        settings=core.load_app_settings()
        if all(settings.get(key)==value for key,value in values.items()):return
        settings.update(values); core.save_app_settings(settings)

    def _naming_control_widgets(self):
        return (self.naming_type,self.naming_configuration,self.naming_function,self.naming_system,self.naming_mounting,self.naming_color,self.naming_extra)

    def _collect_naming_controls(self):
        return assembly_naming.normalize_naming_fields({
            "product_type":self.naming_type.currentText(),
            "configuration":self.naming_configuration.currentText(),
            "function":self.naming_function.currentText(),
            "system_series":str(self.naming_system.currentData() or ""),
            "mounting":self.naming_mounting.currentText(),
            "color":self.naming_color.currentText(),
            "extra":self.naming_extra.text(),
        })

    def _load_naming_controls(self,fields):
        values=assembly_naming.normalize_naming_fields(fields)
        blockers=[QSignalBlocker(w) for w in self._naming_control_widgets()]
        self.naming_type.setCurrentText(values.get("product_type",""))
        self.naming_configuration.setCurrentText(values.get("configuration",""))
        self.naming_function.setCurrentText(values.get("function",""))
        idx=self.naming_system.findData(values.get("system_series","")); self.naming_system.setCurrentIndex(idx if idx>=0 else 0)
        self.naming_mounting.setCurrentText(values.get("mounting",""))
        self.naming_color.setCurrentText(values.get("color",""))
        self.naming_extra.setText(values.get("extra",""))
        del blockers
        self.naming_fields=values
        self._refresh_naming_preview()

    def _naming_controls_changed(self,*_args):
        self.naming_fields=self._collect_naming_controls()
        self._refresh_naming_preview()

    def _generated_name_from_controls(self):
        return assembly_naming.build_assembly_name(**self._collect_naming_controls())

    def _refresh_naming_preview(self,*_args):
        if not hasattr(self,"naming_preview"):return
        generated=self._generated_name_from_controls()
        current=self.name.text().strip() if hasattr(self,"name") else ""
        if not generated:
            self.naming_preview.setText("Ingen navneparametre valgt · navnet er helt manuelt.")
        elif current and current.casefold()==generated.casefold():
            self.naming_preview.setText(f"Navn matcher parametrene: {generated}")
        elif current:
            self.naming_preview.setText(f"Navneforslag: {generated} · aktuelt navn er manuelt")
        else:
            self.naming_preview.setText(f"Navneforslag: {generated}")

    def _apply_naming_name(self):
        generated=self._generated_name_from_controls()
        if not generated:
            QMessageBox.information(self,"Stykliste-navn","Vælg mindst ét navneparameter først."); return
        self.naming_fields=self._collect_naming_controls()
        self.name.setText(generated)
        self.name.setFocus(); self.name.selectAll()

    def _infer_naming_fields(self):
        # Her udledes fra styklisteindhold/navn på ny. Eksisterende strukturerede
        # værdier skjules med vilje for at knappen faktisk kan genlæse ændringer.
        record={
            "name":self.name.text().strip(),
            "category":self.category.text().strip(),
            "variant":self.variant.text().strip(),
            "naming":{},
            "items":deepcopy(self.items),
        }
        inferred=assembly_naming.infer_assembly_name_fields(record,self.catalog)
        self._load_naming_controls(inferred)

    def _clear_naming_fields(self):
        self._load_naming_controls({})

    def _open_name_assistant(self):
        # Assistenten starter altid med de værdier, der er synlige i hovedvinduet.
        self.naming_fields=self._collect_naming_controls()
        record={
            "name":self.name.text().strip(),
            "category":self.category.text().strip(),
            "variant":self.variant.text().strip(),
            "naming":deepcopy(self.naming_fields),
            "items":deepcopy(self.items),
        }
        dlg=AssemblyNameAssistantDialog(self,record,self.catalog)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        generated=dlg.generated_name()
        self._load_naming_controls(dlg.naming_fields())
        if generated:
            self.name.setText(generated)
            self.name.setFocus()
            self.name.selectAll()

    def _lookup(self):
        return {a["article_no"]:a for a in self.catalog}

    def _selected_article_no(self):
        return self._picked_article_no if self._picked_article_no in self._lookup() else ""

    def _choose_article(self):
        dlg=ArticlePickerDialog(self,self.catalog,"Vælg artikel til stykliste",self._picked_article_no)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        self._picked_article_no=dlg.selected_article_no()
        art=self._lookup().get(self._picked_article_no,{})
        self.picked_label.setText(f"{self._picked_article_no} · {art.get('description','')}")

    def _optional_changed(self,checked):
        self.included.setEnabled(bool(checked))
        if not checked:self.included.setChecked(True)

    def _item_selected(self):
        row=self.table.currentRow()
        if not (0<=row<len(self.items)):return
        item=self.items[row]; self._picked_article_no=str(item.get("article_no","") or "")
        art=self._lookup().get(self._picked_article_no,{})
        self.picked_label.setText(f"{self._picked_article_no} · {art.get('description','')}")
        self.role.setText(str(item.get("role","") or "")); self.qty.setValue(float(item.get("qty",1) or 1))
        optional=bool(item.get("optional",False)); self.optional.setChecked(optional)
        self.included.setChecked(bool(item.get("included",True)) if optional else True)

    def _refresh(self):
        if self.items:
            wrapper=core.normalize_bom_assemblies([{"id":"x","name":"x","items":self.items}])
            self.items=wrapper[0]["items"] if wrapper else []
        else:self.items=[]
        lookup=self._lookup(); selected_no=self._picked_article_no
        self.table.setRowCount(len(self.items)); totals=defaultdict(float); priced=0; active=0
        for r,row in enumerate(self.items):
            art=lookup.get(row["article_no"],{}); qty=float(row.get("qty",1) or 1)
            optional=bool(row.get("optional",False)); included=bool(row.get("included",True)) if optional else True
            if included:active+=1
            unit_price=art.get("unit_price"); currency=str(art.get("price_currency","DKK") or "DKK").upper(); line_total=None
            if included and str(unit_price if unit_price is not None else "").strip()!="":
                try:line_total=float(unit_price)*core.article_price_basis_quantity(art,qty); totals[currency]+=line_total; priced+=1
                except (TypeError,ValueError):line_total=None
            kind="Valgfri" if optional else "Fast"
            vals=(row["article_no"],art.get("description",""),row.get("role",""),kind,"Ja" if included else "Nej",BomManagerDialog._fmt_qty(qty),self._format_price(unit_price,currency),self._format_price(line_total,currency) if included else "—")
            for c,val in enumerate(vals):
                cell=_table_item(val,r if c==0 else None)
                if optional and not included:cell.setForeground(QBrush(QColor("#7c8799")))
                self.table.setItem(r,c,cell)
        if selected_no:
            for r,item in enumerate(self.items):
                if str(item.get("article_no","") or "")==selected_no:self.table.selectRow(r); break
        counts=core.bom_assembly_item_counts({"items":self.items})
        total_text=" · ".join(self._format_price(v,k) for k,v in sorted(totals.items())) if totals else "—"
        impact=""
        if self._usage_count:
            impact=" · aktuelt projekt: "+str(self._usage_count)+" anvendelse(r)"
            if len(totals)==1:
                cur,val=next(iter(totals.items())); impact+=f" ≈ {self._format_price(val*self._usage_count,cur)}"
        self.total_label.setText(f"Styklistepris {price_display.vat_caption(self.price_vat_mode)} pr. anvendelse: {total_text} · pris på {priced}/{active} aktive komponenter{impact}")
        self.usage_label.setText(f"Brugt {self._usage_count} gang(e) i aktuelt projekt" if self._usage_count else "Ikke brugt i aktuelt projekt endnu")
        optional_text=f" · {counts['included_optional']}/{counts['optional']} valgfrie aktive" if counts["optional"] else ""
        self.preview_label.setText(f"Styklistepreview: {counts['required']} faste · {counts['active']} aktive i alt{optional_text}")

    def _format_price(self,value,currency="DKK"):
        return BomManagerDialog._fmt_price(price_display.to_display_amount(value,self.price_vat_mode),currency)

    def _add(self):
        article_no=self._selected_article_no()
        if not article_no:return
        qty=float(self.qty.value()); role=self.role.text().strip(); optional=bool(self.optional.isChecked()); included=bool(self.included.isChecked()) if optional else True
        row_index=self.table.currentRow()
        existing=None
        if 0<=row_index<len(self.items) and str(self.items[row_index].get("article_no","") or "")==article_no:existing=self.items[row_index]
        if existing is None:
            existing=next((r for r in self.items if r.get("article_no")==article_no and str(r.get("role","") or "")==role),None)
        data={"article_no":article_no,"qty":qty}
        if role:data["role"]=role
        if optional:data.update({"optional":True,"included":included})
        if existing is not None:
            existing.clear(); existing.update(data)
        else:self.items.append(data)
        self._refresh()

    def _remove(self):
        rows=sorted({i.row() for i in self.table.selectedIndexes()},reverse=True)
        for r in rows:
            if 0<=r<len(self.items):self.items.pop(r)
        self._picked_article_no=""; self.picked_label.setText("Ingen artikel valgt"); self._refresh()

    def _accept_checked(self):
        if not self.name.text().strip():
            QMessageBox.warning(self,"Stykliste","Styklisten skal have et navn."); return
        if not self.items:
            QMessageBox.warning(self,"Stykliste","Tilføj mindst én artikel til styklisten."); return
        if not core.bom_assembly_effective_items({"items":self.items}):
            QMessageBox.warning(self,"Stykliste","Styklisten skal have mindst én aktiv komponent, som medtages i BOM."); return
        self.accept()

    def record(self):
        tags=[]
        for tag in self.tags.text().replace(";",",").split(","):
            text=tag.strip()
            if text and text.casefold() not in {x.casefold() for x in tags}:tags.append(text)
        return {
            "id":str(self.original.get("id","") or uuid.uuid4().hex),
            "name":self.name.text().strip(),
            "description":self.description.toPlainText().strip(),
            "category":self.category.text().strip(),
            "variant":self.variant.text().strip(),
            "tags":tags,
            "notes":self.notes.toPlainText().strip(),
            "naming":deepcopy(self._collect_naming_controls()),
            "items":deepcopy(self.items),
        }


class BomSourceDialog(QDialog):
    """Sporbarhed for én samlet BOM-linje."""
    def __init__(self,parent,window,article_no,sources):
        super().__init__(parent)
        self.window=window; self.article_no=str(article_no or ""); self.sources=list(sources or [])
        configure_modern_dialog(self,title=f"BOM-kilder · {self.article_no}",size=(980,600),minimum_size=(760,460))
        root=QVBoxLayout(self); root.setContentsMargins(12,12,12,12); root.setSpacing(8)
        root.addWidget(make_dialog_header(
            f"Hvor kommer {self.article_no} fra?",
            "Hver række er et konkret bidrag fra en stykliste, direkte artikeltilknytning, Wago-samling eller kabelstræk.",
            eyebrow="BOM-SPORBARHED"))
        self.table=QTableWidget(0,8)
        self.table.setHorizontalHeaderLabels(["Rum","Kildetype","Stykliste / kilde","Symbol / kabel","Del","Bidrag","Enhed","Detalje"])
        _configure_resizable_table(self.table,"bom_source_dialog_v05928",(170,110,240,180,190,90,85,360))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        root.addWidget(self.table,1)
        buttons=QHBoxLayout()
        show=_set_role(QPushButton("Vis valgt på plan"),"primaryButton"); show.clicked.connect(self._show_selected); buttons.addWidget(show)
        buttons.addStretch(1)
        close=QPushButton("Luk"); close.clicked.connect(self.accept); buttons.addWidget(close); root.addLayout(buttons)
        self._refresh()
        self.table.itemDoubleClicked.connect(lambda _item:self._show_selected())

    @staticmethod
    def _source_type_label(kind):
        return {"assembly":"Stykliste","manual":"Direkte","wago":"Wago","cable":"Kabel"}.get(str(kind or ""),str(kind or ""))

    def _refresh(self):
        self.table.setRowCount(len(self.sources))
        for r,row in enumerate(self.sources):
            vals=(row.get("room_display",""),self._source_type_label(row.get("source_type")),row.get("source_label",""),
                  row.get("object_label",row.get("symbol_name","")),row.get("part_label",""),
                  BomManagerDialog._fmt_qty(row.get("qty",0)),row.get("unit",""),row.get("detail",""))
            for c,val in enumerate(vals):self.table.setItem(r,c,_table_item(val,r if c==0 else None))

    def _show_selected(self):
        row=self.table.currentRow()
        if not (0<=row<len(self.sources)):return
        src=self.sources[row]
        puid=str(src.get("placement_uid","") or ""); cuid=str(src.get("cable_uid","") or "")
        if hasattr(self.window,"_select_scene_objects"):
            self.window._select_scene_objects([puid] if puid else [],[cuid] if cuid else [],True)
            if hasattr(self.window,"_notify"):
                self.window._notify(f"{self.article_no}: valgt BOM-kilde vist på plantegningen.",kind="info")


class ArticleUsageDialog(QDialog):
    """Vis både aktuelle projektforekomster og globale styklister for en artikel."""
    def __init__(self,parent,window,article,sources,memberships):
        super().__init__(parent)
        self.window=window; self.article=dict(article or {}); self.sources=list(sources or []); self.memberships=list(memberships or [])
        no=str(self.article.get("article_no","") or "")
        configure_modern_dialog(self,title=f"Hvor bruges {no}?",size=(980,610),minimum_size=(760,460))
        root=QVBoxLayout(self); root.setContentsMargins(12,12,12,12); root.setSpacing(8)
        root.addWidget(make_dialog_header(
            f"{no} · {self.article.get('description','')}",
            f"{len(self.sources)} konkrete bidrag i projektet · {len(self.memberships)} globale styklister.",
            eyebrow="ARTIKELANVENDELSE"))
        tabs=QTabWidget(); root.addWidget(tabs,1)

        project_page=QWidget(); project_layout=QVBoxLayout(project_page); project_layout.setContentsMargins(0,0,0,0)
        self.project_table=QTableWidget(0,7)
        self.project_table.setHorizontalHeaderLabels(["Rum","Kildetype","Stykliste / kilde","Symbol / kabel","Del","Bidrag","Detalje"])
        _configure_resizable_table(self.project_table,"article_usage_project_v05972",(170,105,235,190,180,95,330))
        self.project_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.project_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        project_layout.addWidget(self.project_table,1)
        show=_set_role(QPushButton("Vis valgt på plan"),"primaryButton"); show.clicked.connect(self._show_selected); project_layout.addWidget(show,0,Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(project_page,f"I projektet ({len(self.sources)})")

        assembly_page=QWidget(); assembly_layout=QVBoxLayout(assembly_page); assembly_layout.setContentsMargins(0,0,0,0)
        self.assembly_table=QTableWidget(0,6)
        self.assembly_table.setHorizontalHeaderLabels(["Stykliste","Rolle","Antal","Type","Med i BOM","Brugt i projekt"])
        _configure_resizable_table(self.assembly_table,"article_usage_assemblies_v05972",(330,190,80,95,100,115))
        self.assembly_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.assembly_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        assembly_layout.addWidget(self.assembly_table,1); tabs.addTab(assembly_page,f"I styklister ({len(self.memberships)})")
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); close.rejected.connect(self.reject); close.accepted.connect(self.accept); root.addWidget(close)
        self._refresh(); self.project_table.itemDoubleClicked.connect(lambda _item:self._show_selected())

    def _refresh(self):
        self.project_table.setRowCount(len(self.sources))
        for r,row in enumerate(self.sources):
            vals=(row.get("room_display",""),BomSourceDialog._source_type_label(row.get("source_type")),row.get("source_label",""),row.get("object_label",row.get("symbol_name","")),row.get("part_label",""),f"{BomManagerDialog._fmt_qty(row.get('qty',0))} {row.get('unit','')}",row.get("detail",""))
            for c,val in enumerate(vals):self.project_table.setItem(r,c,_table_item(val,r if c==0 else None))
        self.assembly_table.setRowCount(len(self.memberships))
        for r,row in enumerate(self.memberships):
            vals=(row.get("assembly_name",""),row.get("role",""),BomManagerDialog._fmt_qty(row.get("qty",0)),"Valgfri" if row.get("optional") else "Fast","Ja" if row.get("included",True) else "Nej",str(row.get("uses",0)))
            for c,val in enumerate(vals):self.assembly_table.setItem(r,c,_table_item(val))

    def _show_selected(self):
        row=self.project_table.currentRow()
        if not (0<=row<len(self.sources)):return
        src=self.sources[row]; puid=str(src.get("placement_uid","") or ""); cuid=str(src.get("cable_uid","") or "")
        if hasattr(self.window,"_select_scene_objects"):
            self.window._select_scene_objects([puid] if puid else [],[cuid] if cuid else [],True)
            if hasattr(self.window,"_notify"):self.window._notify("Artikelanvendelse vist på plantegningen.",kind="info")


class BomPrintPreviewDialog(QDialog):
    """Preview af den færdige BOM-PDF før gem eller direkte udskrift."""
    def __init__(self,parent,rows,missing,*,project_name,room_scope,price_vat_mode,
                 filter_caption,include_cables,suggested_path,room_rows=None):
        super().__init__(parent)
        configure_modern_dialog(self,title="BOM - udskriftsforhåndsvisning",minimum_size=(760,560))
        _resize_dialog(self,900,720)
        self.suggested_path=str(suggested_path or "BOM.pdf")
        self.project_name=str(project_name or "Elplan-projekt")
        self.rows=list(rows or []); self.missing=list(missing or []); self.room_rows=list(room_rows or [])
        self.room_scope=str(room_scope or "Alle rum")
        self.price_vat_mode=price_display.normalize_vat_mode(price_vat_mode)
        self.filter_caption=str(filter_caption or "Alle")
        self.include_cables=bool(include_cables)
        self._temp_dir=tempfile.TemporaryDirectory(prefix="elplan_bom_preview_")
        self._preview_path=Path(self._temp_dir.name)/"BOM_preview.pdf"

        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(9)
        root.addWidget(make_dialog_header(
            "BOM til udskrift",
            f"{self.room_scope} · priser {price_display.vat_caption(self.price_vat_mode)} · "
            + ("kabler medtaget" if self.include_cables else "kabler skjult"),
            eyebrow="FORHÅNDSVISNING",
        ))
        if self.room_rows:
            options=QHBoxLayout()
            self.include_room_breakdown=QCheckBox("Medtag BOM pr. rum")
            self.include_room_breakdown.setChecked(True)
            self.include_room_breakdown.setToolTip("Tilføj en enkel artikeloversigt og delsum for hvert rum efter den samlede BOM.")
            options.addWidget(self.include_room_breakdown); options.addStretch(1); root.addLayout(options)
        self.document=QPdfDocument(self)
        self.view=QPdfView(self); self.view.setDocument(self.document)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        root.addWidget(self.view,1)

        status=QHBoxLayout()
        self.page_label=QLabel(f"{max(1,self.document.pageCount())} side(r) · A4")
        self.page_label.setObjectName("sectionHint"); status.addWidget(self.page_label)
        self.document.statusChanged.connect(self._document_status_changed)
        status.addStretch(1)
        fit_page=_set_role(QPushButton("Tilpas side"),"quietButton")
        fit_page.clicked.connect(lambda:self.view.setZoomMode(QPdfView.ZoomMode.FitInView)); status.addWidget(fit_page)
        fit_width=_set_role(QPushButton("Tilpas bredde"),"quietButton")
        fit_width.clicked.connect(lambda:self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)); status.addWidget(fit_width)
        root.addLayout(status)

        buttons=QHBoxLayout(); buttons.addStretch(1)
        save=QPushButton("Gem som PDF…"); save.clicked.connect(self._save_pdf); buttons.addWidget(save)
        print_button=_set_role(QPushButton("Udskriv…"),"primaryButton"); print_button.clicked.connect(self._print_pdf); buttons.addWidget(print_button)
        close=QPushButton("Luk"); close.clicked.connect(self.accept); buttons.addWidget(close)
        root.addLayout(buttons)
        self.finished.connect(self._cleanup)
        if self.room_rows:self.include_room_breakdown.toggled.connect(self._regenerate_preview)
        self._regenerate_preview()

    def _regenerate_preview(self,*_):
        try:
            self.document.close()
            selected_room_rows=self.room_rows if self.room_rows and self.include_room_breakdown.isChecked() else []
            write_bom_pdf(
                self._preview_path,self.rows,self.missing,project_name=self.project_name,
                room_scope=self.room_scope,price_vat_mode=self.price_vat_mode,
                filter_caption=self.filter_caption,include_cables=self.include_cables,
                room_rows=selected_room_rows,
            )
            self.page_label.setText("Indlæser preview…")
            error=self.document.load(str(self._preview_path))
            if error!=QPdfDocument.Error.None_:raise RuntimeError(f"BOM-preview kunne ikke indlæses ({error}).")
        except Exception as exc:
            self.page_label.setText("PDF-preview kunne ikke oprettes")
            QMessageBox.critical(self,"BOM-preview",str(exc))

    def _document_status_changed(self,status):
        if status==QPdfDocument.Status.Ready:
            self.page_label.setText(f"{self.document.pageCount()} side(r) · A4")
        elif status==QPdfDocument.Status.Error:
            self.page_label.setText("PDF-preview kunne ikke indlæses")

    def _save_pdf(self):
        path,_=QFileDialog.getSaveFileName(self,"Gem BOM som PDF",self.suggested_path,"PDF (*.pdf)")
        if not path:return
        if not path.lower().endswith(".pdf"):path+=".pdf"
        try:shutil.copyfile(self._preview_path,path)
        except Exception as exc:
            QMessageBox.critical(self,"BOM PDF",f"PDF-filen kunne ikke gemmes:\n{exc}"); return
        QMessageBox.information(self,"BOM PDF",f"BOM gemt som PDF:\n{path}")

    def _print_pdf(self):
        if self.document.pageCount()<1:
            QMessageBox.warning(self,"Udskriv BOM","Forhåndsvisningen indeholder ingen sider."); return
        printer=QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setDocName(f"BOM - {self.project_name}")
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        dialog=QPrintDialog(printer,self); dialog.setWindowTitle("Udskriv BOM")
        dialog.setMinMax(1,self.document.pageCount()); dialog.setFromTo(1,self.document.pageCount())
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        first=max(1,int(printer.fromPage() or 1)); last=int(printer.toPage() or self.document.pageCount())
        first=min(first,self.document.pageCount()); last=max(first,min(last,self.document.pageCount()))
        painter=QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(self,"Udskriv BOM","Printeren kunne ikke startes."); return
        try:
            for page_index in range(first-1,last):
                if page_index>first-1 and not printer.newPage():
                    raise RuntimeError("Printeren kunne ikke oprette næste side.")
                page_rect=printer.pageRect(QPrinter.Unit.DevicePixel)
                page_size=self.document.pagePointSize(page_index)
                scale=min(page_rect.width()/max(page_size.width(),1.0),page_rect.height()/max(page_size.height(),1.0))
                draw_width=page_size.width()*scale; draw_height=page_size.height()*scale
                # 324 dpi er skarpt til tekst og holder samtidig hukommelsesforbruget
                # stabilt på printerdrivere, som annoncerer 600-1200 dpi.
                render_scale=min(scale,4.5)
                width=max(1,int(round(page_size.width()*render_scale))); height=max(1,int(round(page_size.height()*render_scale)))
                image=self.document.render(page_index,QSize(width,height))
                if image.isNull():raise RuntimeError(f"Side {page_index+1} kunne ikke gengives.")
                target=QRectF(
                    page_rect.x()+(page_rect.width()-draw_width)/2.0,
                    page_rect.y()+(page_rect.height()-draw_height)/2.0,
                    draw_width,draw_height,
                )
                painter.drawImage(target,image)
        except Exception as exc:
            QMessageBox.critical(self,"Udskriv BOM",f"BOM kunne ikke udskrives:\n{exc}")
        finally:painter.end()

    def _cleanup(self,*_):
        try:self.document.close()
        except Exception:pass
        try:self._temp_dir.cleanup()
        except Exception:pass

class BomManagerDialog(QDialog):
    """Global artikelbase/styklister, projektets tilknytninger og BOM."""
    def __init__(self,window,focus_uid:str="",initial_room_uid:str=""):
        super().__init__(window)
        self.window=window
        configure_modern_dialog(self,title="Artikler og BOM",minimum_size=(820,580))
        _resize_dialog(self,1180,780)
        self.price_book=user_library.load_article_prices()
        self.catalog=user_library.load_core_article_catalog()
        self.predefined=user_library.apply_article_prices(core.load_predefined_article_catalog(),self.price_book,assume_normalized=True,prices_normalized=True)
        self._predefined_enriched=build_article_search_index(self.predefined)
        self._catalog_cache=None
        self._catalog_lookup_cache=None
        self._quality_profile_by_no={}
        self._quality_audit_ready=False
        usage_settings=core.load_app_settings()
        self.price_vat_mode=price_display.normalize_vat_mode(usage_settings.get("price_vat_mode"))
        self._favorite_article_nos=[str(x) for x in usage_settings.get("favorite_articles",[]) if str(x).strip()]
        self._recent_article_nos=[str(x) for x in usage_settings.get("recent_articles",[]) if str(x).strip()][:24]
        self._project_article_cache=None
        self._library_search_timer=QTimer(self); self._library_search_timer.setSingleShot(True); self._library_search_timer.setInterval(180)
        self._library_search_timer.timeout.connect(self._library_search_refresh)
        self._bom_hover_timer=QTimer(self); self._bom_hover_timer.setSingleShot(True); self._bom_hover_timer.setInterval(320)
        self._bom_hover_timer.timeout.connect(self._show_bom_hover_popup)
        self._bom_hover_row=-1; self._bom_hover_global_pos=None; self._bom_hover_popup=None
        # Styklister er globale for brugeren og ikke længere bundet til projektet.
        # Gamle projektafhængige styklister migreres automatisk ved åbning.
        legacy_assemblies=core.normalize_bom_assemblies(window.project.raw.get("bom_assemblies",[]))
        self._legacy_project_assemblies=deepcopy(legacy_assemblies)
        self._global_assembly_error=""
        try:
            merged,_=user_library.merge_global_bom_assemblies(legacy_assemblies,self.predefined+self.catalog)
            self.assemblies=deepcopy(merged)
            self.global_assembly_articles=deepcopy(user_library.load_global_bom_articles())
        except Exception as exc:
            self._global_assembly_error=str(exc)
            global_rows=user_library.load_global_bom_assemblies()
            self.global_assembly_articles=deepcopy(user_library.load_global_bom_articles())
            by_id={a["id"]:deepcopy(a) for a in global_rows}
            for a in legacy_assemblies: by_id.setdefault(a["id"],deepcopy(a))
            self.assemblies=core.normalize_bom_assemblies(by_id.values())
        # Artikeldatabasen er den eneste autoritative artikelkilde i UI og BOM.
        # Ældre stykliste-snapshots kan indeholde brugerartikler; flyt kun manglende
        # poster ind i kernedatabasen, så styklister aldrig kræver en skjult nr. 2 database.
        if self.global_assembly_articles:
            try:
                self.catalog,_added=user_library.merge_core_article_catalog(self.global_assembly_articles)
            except Exception:
                pass
        # Fra 0.42.3 er alle BOM-tilknytninger eksplicitte pr. fysisk instans.
        # De gamle typebaserede felter læses ikke ind her, da de ellers ville
        # tildele samme artikel/stykliste til alle forekomster af typen.
        self.bindings=deepcopy(core.normalize_symbol_article_bindings(window.project.raw.get("placement_articles",{})))
        self.assembly_bindings=deepcopy(core.normalize_symbol_assembly_bindings(window.project.raw.get("placement_assemblies",{})))
        self.cable_bindings=deepcopy(core.normalize_cable_article_bindings(window.project.raw.get("cable_instance_articles",{})))
        self.focus_uid=str(focus_uid or ""); self.initial_room_uid=str(initial_room_uid or "")
        self._legacy_type_bindings_present=bool(
            core.normalize_symbol_article_bindings(window.project.raw.get("symbol_articles",{})) or
            core.normalize_symbol_assembly_bindings(window.project.raw.get("symbol_assemblies",{})) or
            core.normalize_cable_article_bindings(window.project.raw.get("cable_articles",{}))
        )
        self._predefined_visible=[]
        self._cable_keys=[]

        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(10)
        root.addWidget(make_dialog_header("Artikler og BOM","Projektets konkrete artikelbindinger, globale styklister og samlet materialeliste ét sted.",eyebrow="MATERIALE"))
        price_display_row=QHBoxLayout(); price_display_row.addWidget(QLabel("Prisvisning"))
        self.price_vat_combo=QComboBox(); self.price_vat_combo.addItem("Ekskl. moms",price_display.VAT_MODE_EXCL); self.price_vat_combo.addItem("Inkl. moms",price_display.VAT_MODE_INCL)
        price_index=self.price_vat_combo.findData(self.price_vat_mode); self.price_vat_combo.setCurrentIndex(max(0,price_index))
        self.price_vat_combo.setToolTip("Skifter visning og eksport. De autoritative priser og BOM-beregninger gemmes fortsat ekskl. moms.")
        self.price_vat_combo.currentIndexChanged.connect(self._price_vat_mode_changed); price_display_row.addWidget(self.price_vat_combo)
        price_display_hint=QLabel("Gælder artikler, styklister, BOM og eksport · priser gemmes altid ekskl. moms")
        price_display_hint.setObjectName("sectionHint"); price_display_row.addWidget(price_display_hint); price_display_row.addStretch(1)
        root.addLayout(price_display_row)
        help_body=QWidget()
        help_layout=QVBoxLayout(help_body); help_layout.setContentsMargins(8,4,8,7); help_layout.setSpacing(4)
        intro=QLabel(
            "Tilknyt artikler eller styklister til konkrete symboler og kabelstræk. Tilknytninger gælder kun den valgte fysiske forekomst. "
            "Artikelbasen og styklisterne er globale kernedata; projektet gemmer kun de konkrete tilknytninger."
        )
        intro.setWordWrap(True); intro.setObjectName("subtleText")
        help_layout.addWidget(intro)
        self.help_disclosure=DisclosureSection("Sådan fungerer Artikler og BOM",help_body,expanded=False)
        root.addWidget(self.help_disclosure)
        self.tabs=QTabWidget(); self.tabs.setDocumentMode(True); root.addWidget(self.tabs,1)
        self._build_assignment_tab()
        self._build_assemblies_tab()
        self._build_cable_tab()
        self._build_library_tab()
        self._build_data_quality_tab()
        self._build_bom_tab()
        self._tab_keys={
            self.assignment_tab:"assignment",
            self.assemblies_tab:"assemblies",
            self.cable_tab:"cables",
            self.library_tab:"articles",
            self.data_quality_tab:"quality",
            self.bom_tab:"bom",
        }
        self._tab_dirty=set(self._tab_keys.values())
        # Tooltips make the six top-level workflows easier to scan without adding visible text.
        tab_hints={
            "assignment":"Tilknyt artikler eller styklister til konkrete symboldele.",
            "assemblies":"Administrér det globale styklistebibliotek.",
            "cables":"Tilknyt kabelartikler til konkrete kabelstræk.",
            "articles":"Søg og vedligehold artikeldatabasen.",
            "quality":"Kontrollér datakvalitet efter behov.",
            "bom":"Se projektets samlede BOM, styklister, kilder og priser.",
        }
        for i in range(self.tabs.count()):
            key=self._tab_keys.get(self.tabs.widget(i),"")
            if key:self.tabs.setTabToolTip(i,tab_hints.get(key,""))
        self._restore_last_tab()
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Gem og luk")
        buttons.accepted.connect(self._save_and_close); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        _restore_dialog_geometry(self,"bom_manager")
        self.finished.connect(lambda *_:self._persist_ui_state())
        if self.initial_room_uid and hasattr(self,"bom_room_filter"):
            self.tabs.setCurrentWidget(self.bom_tab)
            idx=self.bom_room_filter.findData(self.initial_room_uid)
            if idx>=0:
                blocker=QSignalBlocker(self.bom_room_filter); self.bom_room_filter.setCurrentIndex(idx); del blocker
        elif self.focus_uid:
            self.tabs.setCurrentWidget(self.assignment_tab)
        # Connect after the first refresh so restoring contextual/last-used tab
        # cannot accidentally trigger the same expensive refresh twice.
        self._refresh_all(normalize_state=False)
        self.tabs.currentChanged.connect(self._top_level_tab_changed)

    # ---- faner ---------------------------------------------------------
    def _build_assignment_tab(self):
        tab=QWidget(); self.assignment_tab=tab
        root=QVBoxLayout(tab); root.setContentsMargins(10,10,10,10); root.setSpacing(8)
        target=QFrame(); target.setObjectName("detailPanel")
        tl=QVBoxLayout(target); tl.setContentsMargins(10,8,10,8); tl.setSpacing(3)
        self.assignment_target_title=QLabel("Vælg symbol og fysisk del")
        self.assignment_target_title.setObjectName("sectionTitle"); tl.addWidget(self.assignment_target_title)
        self.assignment_target_hint=QLabel("Artikler tilknyttes kun den valgte fysiske forekomst.")
        self.assignment_target_hint.setWordWrap(True); self.assignment_target_hint.setObjectName("sectionHint"); tl.addWidget(self.assignment_target_hint)
        root.addWidget(target)
        row=QHBoxLayout(); row.addWidget(QLabel("Symbol i projektet"))
        self.symbol_combo=QComboBox(); self.symbol_combo.currentIndexChanged.connect(self._symbol_changed)
        row.addWidget(self.symbol_combo,1); root.addLayout(row)
        split=QHBoxLayout(); root.addLayout(split,1)
        left=QVBoxLayout(); part_heading=QLabel("Fysisk del"); part_heading.setObjectName("sectionTitle"); left.addWidget(part_heading)
        self.part_list=QListWidget(); self.part_list.currentRowChanged.connect(self._part_changed); left.addWidget(self.part_list,1)
        split.addLayout(left,1)
        right=QVBoxLayout()
        source_box=QGroupBox("Konfiguration af valgt del")
        source_layout=QVBoxLayout(source_box)
        self.assignment_source=QLabel("Manuel konfiguration")
        self.assignment_source.setObjectName("accentText"); source_layout.addWidget(self.assignment_source)
        sr=QHBoxLayout()
        self.assembly_picker=QComboBox(); self.assembly_picker.setEditable(True); self.assembly_picker.setInsertPolicy(QComboBox.InsertPolicy.NoInsert); self.assembly_picker.setMinimumContentsLength(34)
        if self.assembly_picker.completer(): self.assembly_picker.completer().setFilterMode(Qt.MatchFlag.MatchContains); self.assembly_picker.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.assembly_apply=_set_role(QPushButton("Brug stykliste"), "primaryButton"); self.assembly_apply.clicked.connect(self._apply_assembly)
        self.assembly_manual=_set_role(QPushButton("Brug manuel"), "quietButton"); self.assembly_manual.clicked.connect(self._use_manual_binding)
        sr.addWidget(self.assembly_picker,1); sr.addWidget(self.assembly_apply); sr.addWidget(self.assembly_manual); source_layout.addLayout(sr)
        sr2=QHBoxLayout(); sr2.addStretch(1)
        self.assembly_from_manual=_set_role(QPushButton("Gem manuel som stykliste…"), "quietButton"); self.assembly_from_manual.clicked.connect(self._create_assembly_from_manual); sr2.addWidget(self.assembly_from_manual); source_layout.addLayout(sr2)
        self.assembly_note=QLabel("En valgt stykliste erstatter den manuelle konfiguration i BOM'en, men de manuelle rækker gemmes, så du kan skifte tilbage.")
        self.assembly_note.setWordWrap(True); self.assembly_note.setObjectName("sectionHint"); source_layout.addWidget(self.assembly_note)
        right.addWidget(source_box)
        effective_heading=QLabel("Effektive artikler"); effective_heading.setObjectName("sectionTitle"); right.addWidget(effective_heading)
        self.assignment_table=QTableWidget(0,3)
        self.assignment_table.setHorizontalHeaderLabels(["Artikelnummer","Beskrivelse","Antal pr. del"])
        _configure_resizable_table(self.assignment_table,"bom_assignment",(130,420,100))
        self.assignment_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.assignment_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        right.addWidget(self.assignment_table,1)
        add=QHBoxLayout()
        self.assignment_find_article=_set_role(QPushButton("Find i Artikeldatabase…"), "primaryButton")
        self.assignment_find_article.setToolTip("Åbn den fulde søgbare Artikeldatabase. Dobbeltklik på en artikel for at tilknytte den til den valgte del.")
        self.assignment_find_article.clicked.connect(self._open_library_for_assignment); add.addWidget(self.assignment_find_article,1)
        self.assignment_qty=QDoubleSpinBox(); self.assignment_qty.setRange(0.01,9999); self.assignment_qty.setDecimals(2); self.assignment_qty.setValue(1); self.assignment_qty.setPrefix("× "); self.assignment_qty.setMinimumWidth(90); add.addWidget(self.assignment_qty)
        right.addLayout(add)
        # Kompakt hurtigvalg bevares som sekundær mulighed, men er ikke længere
        # den primære arbejdsgang for artikeltilknytning.
        quick=QHBoxLayout(); quick.addWidget(QLabel("Hurtigvalg"))
        self.article_picker=QComboBox(); self.article_picker.setMinimumContentsLength(24); self.article_picker.setEditable(True); self.article_picker.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        if self.article_picker.completer(): self.article_picker.completer().setFilterMode(Qt.MatchFlag.MatchContains); self.article_picker.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        quick.addWidget(self.article_picker,1)
        self.assign_add=_set_role(QPushButton("Tilknyt"), "quietButton"); self.assign_add.clicked.connect(self._add_binding); quick.addWidget(self.assign_add)
        right.addLayout(quick)
        ar=QHBoxLayout()
        self.assignment_new=_set_role(QPushButton("Ny artikel…"), "quietButton"); self.assignment_new.clicked.connect(self._new_article_from_assignment)
        self.assignment_remove=_set_role(QPushButton("Fjern tilknytning"), "dangerButton"); self.assignment_remove.clicked.connect(self._remove_binding)
        ar.addWidget(self.assignment_new); ar.addStretch(1); ar.addWidget(self.assignment_remove); right.addLayout(ar)
        self.part_note=QLabel(""); self.part_note.setWordWrap(True); self.part_note.setObjectName("sectionHint"); right.addWidget(self.part_note)
        split.addLayout(right,2)
        self.tabs.addTab(tab,"Tilknytning")

    def _build_assemblies_tab(self):
        tab=QWidget(); self.assemblies_tab=tab; root=QVBoxLayout(tab); root.setContentsMargins(10,10,10,10); root.setSpacing(8)
        info=QLabel("Globale styklister · filtrér på Type, Opbygning, Funktion, System/serie, Montering og Farve.")
        info.setWordWrap(True); info.setObjectName("subtleText")
        info.setToolTip(f"Globalt styklistebibliotek: {user_library.bom_assemblies_path()}")
        root.addWidget(info)
        if self._global_assembly_error:
            warn=QLabel("Advarsel: Det globale styklistebibliotek kunne ikke migreres/indlæses korrekt: "+self._global_assembly_error)
            warn.setWordWrap(True); warn.setObjectName("warningText"); root.addWidget(warn)

        filter_box=QGroupBox("Filtre"); filter_root=QVBoxLayout(filter_box); filter_root.setSpacing(6)
        row1=QHBoxLayout(); row1.addWidget(QLabel("Søg"))
        self.assembly_search=QLineEdit(); self.assembly_search.setPlaceholderText("Navn, navneparametre, kategori, tag eller artikelnummer…"); self.assembly_search.setClearButtonEnabled(True); self.assembly_search.textChanged.connect(self._refresh_assemblies); row1.addWidget(self.assembly_search,1)
        row1.addWidget(QLabel("Kategori")); self.assembly_category_filter=QComboBox(); self.assembly_category_filter.setMinimumWidth(145); self.assembly_category_filter.currentIndexChanged.connect(self._refresh_assemblies); row1.addWidget(self.assembly_category_filter)
        self.assembly_used_only=QCheckBox("Kun brugt i projekt"); self.assembly_used_only.toggled.connect(self._refresh_assemblies); row1.addWidget(self.assembly_used_only)
        clear=_set_role(QPushButton("Nulstil filtre"),"quietButton"); clear.clicked.connect(self._clear_assembly_filters); row1.addWidget(clear)
        filter_root.addLayout(row1)

        row2=QHBoxLayout()
        self.assembly_type_filter=self._assembly_filter_combo("Alle typer",row2,"Type")
        self.assembly_configuration_filter=self._assembly_filter_combo("Alle opbygninger",row2,"Opbygning")
        self.assembly_function_filter=self._assembly_filter_combo("Alle funktioner",row2,"Funktion")
        self.assembly_system_filter=self._assembly_filter_combo("Alle systemer/serier",row2,"System / serie")
        self.assembly_mounting_filter=self._assembly_filter_combo("Alle monteringer",row2,"Montering")
        self.assembly_color_filter=self._assembly_filter_combo("Alle farver",row2,"Farve")
        filter_root.addLayout(row2); root.addWidget(filter_box)

        self.assembly_table=QTableWidget(0,12)
        self.assembly_table.setHorizontalHeaderLabels(["Navn","Type","Opbygning","Funktion","System / serie","Montering","Farve","Kategori","Komponenter","Brugt på","Styklistepris","Beskrivelse"])
        _configure_resizable_table(self.assembly_table,"bom_assemblies_v05932",(255,125,105,150,185,120,100,140,110,85,125,320))
        self.assembly_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.assembly_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.assembly_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.assembly_table.setSortingEnabled(True)
        self.assembly_table.doubleClicked.connect(self._edit_assembly)
        self.assembly_table.itemSelectionChanged.connect(self._assembly_selection_changed)
        root.addWidget(self.assembly_table,1)

        self.assembly_summary=QLabel("Vælg en stykliste for at se anvendelser og indhold."); self.assembly_summary.setWordWrap(True); self.assembly_summary.setObjectName("sectionHint"); root.addWidget(self.assembly_summary)
        row=QHBoxLayout()
        new=_set_role(QPushButton("Ny stykliste…"), "primaryButton"); new.clicked.connect(self._new_assembly)
        edit=QPushButton("Redigér…"); edit.clicked.connect(self._edit_assembly)
        duplicate=QPushButton("Duplikér"); duplicate.clicked.connect(self._duplicate_assembly)
        show=_set_role(QPushButton("Vis anvendelser på plan"),"quietButton"); show.clicked.connect(self._show_selected_assembly_on_plan)
        delete=_set_role(QPushButton("Slet"), "dangerButton"); delete.clicked.connect(self._delete_assembly)
        row.addWidget(new); row.addWidget(edit); row.addWidget(duplicate); row.addWidget(show); row.addStretch(1); row.addWidget(delete); root.addLayout(row)
        self.tabs.addTab(tab,"Styklister")

    def _assembly_filter_combo(self,all_label,row,label):
        row.addWidget(QLabel(label)); combo=QComboBox(); combo.setMinimumWidth(115); combo.addItem(all_label,""); combo.currentIndexChanged.connect(self._refresh_assemblies); row.addWidget(combo,1); return combo

    def _clear_assembly_filters(self):
        blockers=[]
        if hasattr(self,"assembly_search"): blockers.append(QSignalBlocker(self.assembly_search)); self.assembly_search.clear()
        for name in ("assembly_category_filter","assembly_type_filter","assembly_configuration_filter","assembly_function_filter","assembly_system_filter","assembly_mounting_filter","assembly_color_filter"):
            combo=getattr(self,name,None)
            if combo is not None:
                blockers.append(QSignalBlocker(combo)); combo.setCurrentIndex(0)
        if hasattr(self,"assembly_used_only"):
            blockers.append(QSignalBlocker(self.assembly_used_only)); self.assembly_used_only.setChecked(False)
        del blockers
        self._refresh_assemblies()

    def _build_cable_tab(self):
        tab=QWidget(); self.cable_tab=tab; root=QVBoxLayout(tab); root.setContentsMargins(10,10,10,10); root.setSpacing(8)
        info=QLabel("Tilknyt en konkret kabelvare til det valgte kabelstræk · afmålt beregnes i meter, ruller afrundes til hele ruller.")
        info.setWordWrap(True); info.setObjectName("subtleText"); root.addWidget(info)
        split=QHBoxLayout(); root.addLayout(split,1)
        left=QVBoxLayout(); cable_heading=QLabel("Kabelstræk i projektet"); cable_heading.setObjectName("sectionTitle"); left.addWidget(cable_heading)
        self.cable_type_list=QListWidget(); self.cable_type_list.currentRowChanged.connect(self._cable_type_changed); left.addWidget(self.cable_type_list,1)
        split.addLayout(left,1)
        right=QVBoxLayout(); selected_heading=QLabel("Valgt kabelstræk"); selected_heading.setObjectName("sectionTitle"); right.addWidget(selected_heading)
        self.cable_summary=QLabel("–"); self.cable_summary.setWordWrap(True); self.cable_summary.setObjectName("sectionTitle"); right.addWidget(self.cable_summary)
        self.cable_current_article=QLabel("Ingen kabelartikel tilknyttet"); self.cable_current_article.setWordWrap(True); self.cable_current_article.setObjectName("subtleText"); right.addWidget(self.cable_current_article)
        right.addSpacing(10); right.addWidget(QLabel("Waskönig+Walter / artikelbase"))
        self.cable_article_picker=QComboBox(); self.cable_article_picker.setMinimumContentsLength(42); self.cable_article_picker.setEditable(True); self.cable_article_picker.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        if self.cable_article_picker.completer(): self.cable_article_picker.completer().setFilterMode(Qt.MatchFlag.MatchContains); self.cable_article_picker.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        right.addWidget(self.cable_article_picker)
        cr=QHBoxLayout(); self.cable_assign=_set_role(QPushButton("Tilknyt kabelartikel"), "primaryButton"); self.cable_assign.clicked.connect(self._assign_cable_article)
        self.cable_clear=_set_role(QPushButton("Ryd"), "dangerButton"); self.cable_clear.clicked.connect(self._clear_cable_article)
        cr.addWidget(self.cable_assign); cr.addWidget(self.cable_clear); cr.addStretch(1); right.addLayout(cr)
        hint=QLabel("Tip: varer med ‘afmålt’ giver meter i BOM. Vælger du fx en 100 m rulle, viser BOM antal hele ruller og det beregnede meterbehov som grundlag.")
        hint.setWordWrap(True); hint.setObjectName("sectionHint"); right.addWidget(hint); right.addStretch(1)
        split.addLayout(right,2)
        self.tabs.addTab(tab,"Kabler")

    def _build_predefined_tab(self):
        tab=QWidget(); root=QVBoxLayout(tab); root.setContentsMargins(10,10,10,10); root.setSpacing(8)
        filter_box=QGroupBox("Filtre"); filter_root=QVBoxLayout(filter_box); filter_root.setSpacing(6)
        row1=QHBoxLayout(); row1.addWidget(QLabel("Søg"))
        self.std_search=QLineEdit(); self.std_search.setPlaceholderText("Artikel, beskrivelse, EL-nr., EAN, serie, specifikation…"); self.std_search.setClearButtonEnabled(True); self.std_search.textChanged.connect(self._schedule_predefined_refresh); row1.addWidget(self.std_search,3)
        row1.addWidget(QLabel("Fabrikat")); self.std_manufacturer=QComboBox(); self.std_manufacturer.currentIndexChanged.connect(self._refresh_predefined); row1.addWidget(self.std_manufacturer,1)
        filter_root.addLayout(row1)
        row2=QHBoxLayout()
        row2.addWidget(QLabel("Type")); self.std_type=QComboBox(); self.std_type.currentIndexChanged.connect(self._refresh_predefined); row2.addWidget(self.std_type,1)
        row2.addWidget(QLabel("Familie")); self.std_design=QComboBox(); self.std_design.currentIndexChanged.connect(self._refresh_predefined); row2.addWidget(self.std_design,1)
        row2.addWidget(QLabel("Variant")); self.std_variant=QComboBox(); self.std_variant.currentIndexChanged.connect(self._refresh_predefined); row2.addWidget(self.std_variant,1)
        row2.addWidget(QLabel("Modul")); self.std_module=QComboBox(); self.std_module.currentIndexChanged.connect(self._refresh_predefined); row2.addWidget(self.std_module,1)
        row2.addWidget(QLabel("Farve")); self.std_color=QComboBox(); self.std_color.currentIndexChanged.connect(self._refresh_predefined); row2.addWidget(self.std_color,1)
        clear=_set_role(QPushButton("Nulstil filtre"), "quietButton"); clear.clicked.connect(self._clear_standard_filters); row2.addWidget(clear)
        filter_root.addLayout(row2)
        row3=QHBoxLayout()
        row3.addWidget(QLabel("Diameter")); self.std_diameter=QComboBox(); self.std_diameter.currentIndexChanged.connect(self._refresh_predefined); row3.addWidget(self.std_diameter,1)
        row3.addWidget(QLabel("CCT")); self.std_cct=QComboBox(); self.std_cct.currentIndexChanged.connect(self._refresh_predefined); row3.addWidget(self.std_cct,1)
        row3.addWidget(QLabel("IP")); self.std_ip=QComboBox(); self.std_ip.currentIndexChanged.connect(self._refresh_predefined); row3.addWidget(self.std_ip,1)
        self.std_only_price=QCheckBox("Kun med pris"); self.std_only_price.toggled.connect(self._refresh_predefined); row3.addWidget(self.std_only_price)
        row3.addStretch(2)
        filter_root.addLayout(row3)
        root.addWidget(filter_box)

        body=QHBoxLayout(); body.setSpacing(10); root.addLayout(body,1)
        self.std_table=QTableView()
        self.std_table_model=ArticleTableModel((
            ("Artikelnummer","article_no"),("Beskrivelse","description"),("Produktfamilie","product_family"),("Variant","product_variant"),("Type","product_type"),
            ("Modul","module_size"),("Farve","color"),("Pris ekskl. moms","__price__"),("Prisstatus","price_status"),("Priskilde","price_source"),("Pris opdateret","price_checked"),("EAN","ean"),("EL-nr.","el_no"),("Status","status"),
        ),self.std_table)
        self.std_table_model.set_price_vat_mode(self.price_vat_mode)
        self.std_table.setModel(self.std_table_model)
        _configure_resizable_table(self.std_table,"bom_standard_library_v05923",(130,390,170,105,155,80,90,125,95,155,110,140,120,105))
        self.std_table.setSortingEnabled(True)
        self.std_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.std_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.std_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.std_table.setAlternatingRowColors(True); self.std_table.verticalHeader().setVisible(False); self.std_table.verticalHeader().setDefaultSectionSize(28)
        self.std_table.doubleClicked.connect(self._import_selected_standard)
        self.std_table.selectionModel().selectionChanged.connect(lambda *_:self._predefined_selection_changed())
        body.addWidget(self.std_table,3)

        detail=QFrame(); detail.setObjectName("detailPanel"); detail.setFrameShape(QFrame.Shape.StyledPanel); detail.setMinimumWidth(300); dl=QVBoxLayout(detail); dl.setContentsMargins(10,10,10,10); dl.setSpacing(7)
        self.std_preview=ArticleVisualPreview(detail); dl.addWidget(self.std_preview)
        self.std_preview_title=QLabel("Vælg en artikel"); self.std_preview_title.setWordWrap(True); self.std_preview_title.setObjectName("sectionTitle"); dl.addWidget(self.std_preview_title)
        self.std_preview_specs=QLabel(""); self.std_preview_specs.setWordWrap(True); self.std_preview_specs.setTextFormat(Qt.TextFormat.RichText); dl.addWidget(self.std_preview_specs)
        self.std_preview_meta=QLabel(""); self.std_preview_meta.setWordWrap(True); self.std_preview_meta.setObjectName("sectionHint"); dl.addWidget(self.std_preview_meta)
        pr=QHBoxLayout()
        self.std_open_source=_set_role(QPushButton("Producent"), "quietButton"); self.std_open_source.setToolTip("Åbn producentens produktside"); self.std_open_source.clicked.connect(self._open_standard_source); pr.addWidget(self.std_open_source)
        self.std_open_supplier=_set_role(QPushButton("Leverandør"), "quietButton"); self.std_open_supplier.setToolTip("Åbn grossist-/leverandørside, hvis den findes"); self.std_open_supplier.clicked.connect(self._open_standard_supplier); pr.addWidget(self.std_open_supplier)
        self.std_open_datasheet=_set_role(QPushButton("Datablad"), "quietButton"); self.std_open_datasheet.clicked.connect(self._open_standard_datasheet); pr.addWidget(self.std_open_datasheet)
        self.std_reload_image=_set_role(QPushButton("Opdatér foto"), "quietButton"); self.std_reload_image.clicked.connect(self.std_preview.reload_image); pr.addWidget(self.std_reload_image)
        self.std_edit_price=_set_role(QPushButton("Pris…"), "quietButton"); self.std_edit_price.setToolTip("Angiv global pris/prisestimat for artiklen"); self.std_edit_price.clicked.connect(self._edit_standard_price); pr.addWidget(self.std_edit_price)
        dl.addLayout(pr)
        dl.addStretch(1); body.addWidget(detail,1)

        row=QHBoxLayout(); self.std_count=QLabel(""); self.std_count.setObjectName("sectionHint"); row.addWidget(self.std_count); row.addStretch(1)
        fit_cols=_set_role(QPushButton("Tilpas kolonner"), "quietButton"); fit_cols.setToolTip("Auto-tilpas til det viste indhold; bredder kan derefter trækkes manuelt."); fit_cols.clicked.connect(lambda:_fit_table_columns(self.std_table)); row.addWidget(fit_cols)
        reset_cols=_set_role(QPushButton("Nulstil bredder"), "quietButton"); reset_cols.clicked.connect(lambda:_reset_table_columns(self.std_table)); row.addWidget(reset_cols)
        add_sel=_set_role(QPushButton("Gendan valgte i artikelbase"), "primaryButton"); add_sel.setToolTip("Erstat den valgte artikelpost i kernedata med den medfølgende standardpost."); add_sel.clicked.connect(self._import_selected_standard); row.addWidget(add_sel)
        add_all=_set_role(QPushButton("Gendan alle viste"), "quietButton"); add_all.setToolTip("Gendan de viste standardposter i kernedatabasens artikelbase."); add_all.clicked.connect(self._import_all_visible_standard); row.addWidget(add_all)
        root.addLayout(row)
        self.tabs.addTab(tab,"Standardbibliotek")

    def _build_library_tab(self):
        tab=QWidget(); self.library_tab=tab
        root=QVBoxLayout(tab); root.setContentsMargins(10,10,10,10); root.setSpacing(8)
        info=QLabel("Global artikeldatabase · importerede, synkroniserede og manuelle artikler deles af alle projekter på denne PC.")
        info.setWordWrap(True); info.setObjectName("subtleText"); root.addWidget(info)

        self.library_target_card=QFrame(); self.library_target_card.setObjectName("detailPanel")
        ltc=QHBoxLayout(self.library_target_card); ltc.setContentsMargins(10,8,10,8); ltc.setSpacing(10)
        lt_text=QVBoxLayout(); lt_text.setSpacing(2)
        self.library_target_title=QLabel("Ingen tilknytningsdestination valgt")
        self.library_target_title.setObjectName("sectionTitle"); lt_text.addWidget(self.library_target_title)
        self.library_target_hint=QLabel("Vælg symbol og fysisk del under Tilknytning.")
        self.library_target_hint.setWordWrap(True); self.library_target_hint.setObjectName("sectionHint"); lt_text.addWidget(self.library_target_hint)
        ltc.addLayout(lt_text,1)
        self.library_assignment_qty=QDoubleSpinBox(); self.library_assignment_qty.setRange(0.01,9999); self.library_assignment_qty.setDecimals(2); self.library_assignment_qty.setValue(1); self.library_assignment_qty.setPrefix("× "); self.library_assignment_qty.setMinimumWidth(90); ltc.addWidget(self.library_assignment_qty)
        self.library_assign_button=_set_role(QPushButton("Tilknyt valgt artikel"), "primaryButton")
        self.library_assign_button.setToolTip("Tilknyt den markerede artikel til den viste fysiske del. Dobbeltklik på en artikel gør det samme.")
        self.library_assign_button.clicked.connect(self._assign_selected_library_article); ltc.addWidget(self.library_assign_button)
        self.library_back_assignment=_set_role(QPushButton("Tilknytning"), "quietButton")
        self.library_back_assignment.clicked.connect(lambda:self.tabs.setCurrentWidget(self.assignment_tab)); ltc.addWidget(self.library_back_assignment)
        root.addWidget(self.library_target_card)
        self.library_assignment_status=QLabel(""); self.library_assignment_status.setWordWrap(True); self.library_assignment_status.setObjectName("sectionHint"); root.addWidget(self.library_assignment_status)

        filter_box=QGroupBox("Filtre"); filter_root=QVBoxLayout(filter_box); filter_root.setSpacing(6)
        scope_row=QHBoxLayout(); scope_row.addWidget(QLabel("Vis"))
        self.lib_scope=QComboBox()
        self.lib_scope.addItem("Alle artikler","")
        self.lib_scope.addItem("★ Favoritter","favorites")
        self.lib_scope.addItem("Senest anvendte","recent")
        self.lib_scope.addItem("Brugt i projekt","project")
        self.lib_scope.addItem("Kræver datakontrol","quality")
        self.lib_scope.currentIndexChanged.connect(self._library_filter_changed); scope_row.addWidget(self.lib_scope)
        self.library_scope_hint=QLabel(""); self.library_scope_hint.setObjectName("sectionHint"); scope_row.addWidget(self.library_scope_hint,1)
        filter_root.addLayout(scope_row)
        row1=QHBoxLayout(); row1.addWidget(QLabel("Søg"))
        self.library_search=QLineEdit(); self.library_search.setPlaceholderText("Artikel, beskrivelse, EL-nr., EAN, familie, variant, specifikation…")
        self.library_search.setClearButtonEnabled(True); self.library_search.textChanged.connect(self._schedule_library_refresh); row1.addWidget(self.library_search,3)
        row1.addWidget(QLabel("Fabrikat")); self.lib_manufacturer=QComboBox(); self.lib_manufacturer.currentIndexChanged.connect(self._library_filter_changed); row1.addWidget(self.lib_manufacturer,1)
        filter_root.addLayout(row1)
        row2=QHBoxLayout()
        row2.addWidget(QLabel("Kategori")); self.lib_category=QComboBox(); self.lib_category.currentIndexChanged.connect(self._library_filter_changed); row2.addWidget(self.lib_category,1)
        row2.addWidget(QLabel("Type")); self.lib_type=QComboBox(); self.lib_type.currentIndexChanged.connect(self._library_filter_changed); row2.addWidget(self.lib_type,1)
        row2.addWidget(QLabel("Produktfamilie")); self.lib_design=QComboBox(); self.lib_design.currentIndexChanged.connect(self._library_filter_changed); row2.addWidget(self.lib_design,1)
        row2.addWidget(QLabel("Variant")); self.lib_variant=QComboBox(); self.lib_variant.currentIndexChanged.connect(self._library_filter_changed); row2.addWidget(self.lib_variant,1)
        row2.addWidget(QLabel("Modul")); self.lib_module=QComboBox(); self.lib_module.currentIndexChanged.connect(self._library_filter_changed); row2.addWidget(self.lib_module,1)
        row2.addWidget(QLabel("Farve")); self.lib_color=QComboBox(); self.lib_color.currentIndexChanged.connect(self._library_filter_changed); row2.addWidget(self.lib_color,1)
        clear=_set_role(QPushButton("Nulstil filtre"), "quietButton"); clear.clicked.connect(self._clear_library_filters); row2.addWidget(clear)
        filter_root.addLayout(row2)
        row3=QHBoxLayout()
        row3.addWidget(QLabel("Diameter")); self.lib_diameter=QComboBox(); self.lib_diameter.currentIndexChanged.connect(self._library_filter_changed); row3.addWidget(self.lib_diameter,1)
        row3.addWidget(QLabel("CCT")); self.lib_cct=QComboBox(); self.lib_cct.currentIndexChanged.connect(self._library_filter_changed); row3.addWidget(self.lib_cct,1)
        row3.addWidget(QLabel("IP")); self.lib_ip=QComboBox(); self.lib_ip.currentIndexChanged.connect(self._library_filter_changed); row3.addWidget(self.lib_ip,1)
        self.lib_only_price=QCheckBox("Kun med pris"); self.lib_only_price.toggled.connect(self._library_filter_changed); row3.addWidget(self.lib_only_price)
        self.lib_only_complete=QCheckBox("Kun komplette data"); self.lib_only_complete.setToolTip("Skjul artikler med fejl/advarsler i Datakvalitet."); self.lib_only_complete.toggled.connect(self._library_filter_changed); row3.addWidget(self.lib_only_complete)
        row3.addStretch(2); filter_root.addLayout(row3)
        root.addWidget(filter_box)

        body=QHBoxLayout(); body.setSpacing(10); root.addLayout(body,1)
        self.library_table=QTableView()
        self.library_table_model=ArticleTableModel((
            ("★","_favorite_mark"),("Artikelnummer","article_no"),("Beskrivelse","description"),("Fabrikat","manufacturer"),("Serie (kilde)","series"),
            ("Produktfamilie","product_family"),("Variant","product_variant"),("Kategori","category_normalized"),("Type","product_type"),("Funktion","function"),("Modul","module_size"),("Farve","color"),
            ("Pris ekskl. moms","__price__"),("Prisstatus","price_status"),("Priskilde","price_source"),("Pris opdateret","price_checked"),("EAN","ean"),("EL-nr.","el_no"),("Status","status"),
        ),self.library_table)
        self.library_table_model.set_price_vat_mode(self.price_vat_mode)
        self.library_table.setModel(self.library_table_model); self.library_table.setSortingEnabled(True); self.library_table_model.clear_sort()
        _configure_resizable_table(self.library_table,"bom_article_database_v05929",(38,130,390,185,155,170,105,225,155,140,80,90,125,95,155,110,140,120,110))
        self.library_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.library_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.library_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.library_table.setAlternatingRowColors(True); self.library_table.verticalHeader().setVisible(False); self.library_table.verticalHeader().setDefaultSectionSize(28)
        self.library_table.doubleClicked.connect(self._assign_selected_library_article)
        self.library_table.setToolTip("Dobbeltklik på en artikel for at tilknytte den til den valgte symbol-del. Brug Redigér… til at ændre artikeldata.")
        self.library_table.selectionModel().selectionChanged.connect(lambda *_:self._library_selection_changed())
        body.addWidget(self.library_table,3)

        detail=QFrame(); detail.setObjectName("detailPanel"); detail.setFrameShape(QFrame.Shape.StyledPanel); detail.setMinimumWidth(310)
        dl=QVBoxLayout(detail); dl.setContentsMargins(10,10,10,10); dl.setSpacing(7)
        self.library_preview=ArticleVisualPreview(detail); dl.addWidget(self.library_preview)
        self.library_preview_title=QLabel("Vælg en artikel"); self.library_preview_title.setWordWrap(True); self.library_preview_title.setObjectName("sectionTitle"); dl.addWidget(self.library_preview_title)
        self.library_preview_specs=QLabel(""); self.library_preview_specs.setWordWrap(True); self.library_preview_specs.setTextFormat(Qt.TextFormat.RichText); dl.addWidget(self.library_preview_specs)
        self.library_preview_meta=QLabel(""); self.library_preview_meta.setWordWrap(True); self.library_preview_meta.setObjectName("sectionHint"); dl.addWidget(self.library_preview_meta)
        pr=QHBoxLayout()
        self.library_open_source=_set_role(QPushButton("Producent"), "quietButton"); self.library_open_source.clicked.connect(self._open_library_source); pr.addWidget(self.library_open_source)
        self.library_open_supplier=_set_role(QPushButton("Leverandør"), "quietButton"); self.library_open_supplier.clicked.connect(self._open_library_supplier); pr.addWidget(self.library_open_supplier)
        self.library_open_datasheet=_set_role(QPushButton("Datablad"), "quietButton"); self.library_open_datasheet.clicked.connect(self._open_library_datasheet); pr.addWidget(self.library_open_datasheet)
        self.library_reload_image=_set_role(QPushButton("Opdatér foto"), "quietButton"); self.library_reload_image.clicked.connect(self.library_preview.reload_image); pr.addWidget(self.library_reload_image)
        dl.addLayout(pr)
        pr2=QHBoxLayout()
        self.library_edit_button=QPushButton("Redigér artikel…"); self.library_edit_button.setToolTip("Redigér artikeldata. Dobbeltklik i tabellen bruges til tilknytning."); self.library_edit_button.clicked.connect(self._edit_article); pr2.addWidget(self.library_edit_button)
        self.library_price_button=_set_role(QPushButton("Pris…"), "quietButton"); self.library_price_button.clicked.connect(self._edit_library_price); pr2.addWidget(self.library_price_button)
        self.library_relations_button=_set_role(QPushButton("Relationer…"), "quietButton"); self.library_relations_button.setToolTip("Se varianter, bekræftede relationer og kompatibilitetsforslag."); self.library_relations_button.clicked.connect(self._edit_article_relations); pr2.addWidget(self.library_relations_button)
        pr2.addStretch(1); dl.addLayout(pr2)
        compare_row=QHBoxLayout()
        self.library_usage_button=_set_role(QPushButton("Hvor bruges?"),"quietButton")
        self.library_usage_button.setToolTip("Vis alle forekomster i det aktuelle projekt og alle globale styklister, der indeholder artiklen.")
        self.library_usage_button.clicked.connect(self._show_selected_article_usage); compare_row.addWidget(self.library_usage_button)
        self.library_compare_button=_set_role(QPushButton("Sammenlign forhandlere…"),"quietButton")
        self.library_compare_button.setToolTip("Sammenlign de senest hentede priser fra WATTOO, LavprisEL og Greenline pr. normaliseret enhed.")
        self.library_compare_button.clicked.connect(self._compare_library_prices); compare_row.addWidget(self.library_compare_button); compare_row.addStretch(1); dl.addLayout(compare_row)
        quick=QHBoxLayout()
        self.library_favorite_button=_set_role(QPushButton("☆ Favorit"),"quietButton"); self.library_favorite_button.setToolTip("Gem artiklen som favorit på tværs af projekter."); self.library_favorite_button.clicked.connect(self._toggle_library_favorite); quick.addWidget(self.library_favorite_button)
        self.library_prev_variant=_set_role(QPushButton("← Variant"),"quietButton"); self.library_prev_variant.setToolTip("Vælg forrige artikel i samme variantgruppe."); self.library_prev_variant.clicked.connect(lambda:self._select_adjacent_variant(-1)); quick.addWidget(self.library_prev_variant)
        self.library_next_variant=_set_role(QPushButton("Variant →"),"quietButton"); self.library_next_variant.setToolTip("Vælg næste artikel i samme variantgruppe."); self.library_next_variant.clicked.connect(lambda:self._select_adjacent_variant(1)); quick.addWidget(self.library_next_variant)
        quick.addStretch(1); dl.addLayout(quick)
        self.library_variant_hint=QLabel(""); self.library_variant_hint.setWordWrap(True); self.library_variant_hint.setObjectName("sectionHint"); dl.addWidget(self.library_variant_hint)
        dl.addStretch(1); body.addWidget(detail,1)

        row=QHBoxLayout(); self.library_count=QLabel(""); self.library_count.setObjectName("sectionHint"); row.addWidget(self.library_count); row.addStretch(1)
        new=_set_role(QPushButton("Ny artikel…"), "primaryButton"); new.clicked.connect(self._new_article); row.addWidget(new)
        guide=_set_role(QPushButton("Importguide…"), "quietButton"); guide.setToolTip("Se felter, eksempler og gem JSON/CSV-templates."); guide.clicked.connect(self._show_article_import_guide); row.addWidget(guide)
        imp=QPushButton("Importér bibliotek…"); imp.clicked.connect(self._import_article_library); row.addWidget(imp)
        exp=QPushButton("Eksportér bibliotek…"); exp.clicked.connect(self._export_article_library); row.addWidget(exp)
        delete=_set_role(QPushButton("Slet"), "dangerButton"); delete.clicked.connect(self._delete_article); row.addWidget(delete)
        row.addSpacing(8)
        sync_lk=_set_role(QPushButton("Synkronisér LK.dk…"), "quietButton"); sync_lk.setToolTip("Hent LK/Schneider-onlinekataloget og opdatér artikeldatabasen."); sync_lk.clicked.connect(self._sync_lk_catalog); row.addWidget(sync_lk)
        sync_prices=_set_role(QPushButton("Opdatér priser…"), "quietButton"); sync_prices.setToolTip("Hent offentlige webshoppriser fra WATTOO, LavprisEL og Greenline med sikker artikelmatch."); sync_prices.clicked.connect(self._sync_retail_prices); row.addWidget(sync_prices)
        row.addSpacing(8)
        fit_cols=_set_role(QPushButton("Tilpas kolonner"), "quietButton"); fit_cols.clicked.connect(lambda:_fit_table_columns(self.library_table)); row.addWidget(fit_cols)
        reset_cols=_set_role(QPushButton("Nulstil bredder"), "quietButton"); reset_cols.clicked.connect(lambda:_reset_table_columns(self.library_table)); row.addWidget(reset_cols)
        root.addLayout(row)
        self.tabs.addTab(tab,"Artikeldatabase")

    def _retail_price_targets(self, mode):
        priced=list(self._available_catalog())
        if mode=="bom":
            rows,_missing=self._bom_data("")
            wanted={str(r.get("article_no","") or "") for r in rows}
            return [a for a in priced if str(a.get("article_no","") or "") in wanted]
        if mode=="missing":
            return [a for a in priced if a.get("unit_price") is None]
        if mode=="stale":
            today=date.today(); out=[]
            for art in priced:
                checked=str(art.get("estimated_price_checked","") or "").strip()
                if not checked: continue
                try: age=(today-date.fromisoformat(checked[:10])).days
                except Exception: age=9999
                if age>=7: out.append(art)
            return out
        return priced

    def _sync_retail_prices(self):
        if getattr(self,"_price_sync_thread",None) is not None:
            QMessageBox.information(self,"Webshoppriser","En prisopdatering kører allerede."); return
        scope_dialog=_RetailPriceScopeDialog(self)
        if scope_dialog.exec()!=QDialog.DialogCode.Accepted:
            return
        mode=scope_dialog.mode
        if not mode:
            return
        targets=self._retail_price_targets(mode)
        if not targets:
            QMessageBox.information(self,"Webshoppriser","Der er ingen artikler i det valgte udsnit, som skal kontrolleres."); return
        if mode=="all":
            answer=QMessageBox.warning(
                self,"Webshoppriser · hele databasen",
                f"Du er ved at kontrollere {len(targets)} artikler hos op til tre webshops. Det giver mange netværkskald.\n\n"
                "Programmet kører langsomt og skånsomt, men det anbefales normalt at opdatere BOM eller manglende priser i stedet. Fortsæt?",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
            if answer!=QMessageBox.StandardButton.Yes:return
        progress=QProgressDialog("Forbereder webshopopslag…","Annuller",0,max(1,len(targets)*3),self)
        progress.setWindowTitle("Opdaterer priser"); progress.setWindowModality(Qt.WindowModality.WindowModal); progress.setMinimumDuration(0); progress.setAutoClose(False); progress.setAutoReset(False); progress.setValue(0)
        thread=_RetailPriceSyncThread(self,articles=targets,cache_path=user_library.user_data_dir()/"retail_price_cache.json")
        self._price_sync_thread=thread; self._price_sync_progress=progress
        progress.canceled.connect(thread.cancel); thread.progress.connect(self._price_sync_progress_update); thread.succeeded.connect(self._price_sync_done); thread.failed.connect(self._price_sync_failed); thread.finished.connect(self._price_sync_thread_finished)
        progress.show(); thread.start()

    def _price_sync_progress_update(self,text,value,total):
        progress=getattr(self,"_price_sync_progress",None)
        if progress is None:return
        progress.setLabelText(str(text)); progress.setMaximum(max(1,int(total or 1))); progress.setValue(max(0,min(progress.maximum(),int(value or 0))))

    def _price_sync_done(self,result):
        progress=getattr(self,"_price_sync_progress",None)
        if progress is not None: progress.setLabelText("Gemmer prisestimater…"); progress.setMaximum(0); progress.setValue(0)
        try:
            self.price_book=user_library.merge_price_estimates(self.price_book,result.records)
            user_library.save_article_prices(self.price_book)
            self._rebuild_predefined_price_view(); self._invalidate_catalog_cache(); self._refresh_all()
            if progress is not None:progress.close()
            st=result.stats
            QMessageBox.information(
                self,"Webshoppriser opdateret",
                f"Prisopdateringen er færdig.\n\nKontrollerede artikler: {st.articles_total}\n"
                f"Artikler med sikre webshopfund: {st.articles_with_observations}\nOpdaterede estimater: {st.estimates_updated}\n"
                f"Cachefund: {st.cache_hits}\nNetværkskald: {st.network_requests}\n"
                f"Rate-limit hændelser: {st.rate_limit_events}\nBackoff i alt: {st.backoff_wait_seconds:.0f} sek.\n\n"
                f"Manuelle priser er bevaret uændret. Estimater vises {price_display.vat_caption(self.price_vat_mode)}; "
                "de enkelte webshopobservationer gemmes med både inkl. og ekskl. moms."
            )
        except Exception as exc:
            if progress is not None:progress.close()
            QMessageBox.critical(self,"Webshoppriser",f"Prisdataene blev hentet, men kunne ikke gemmes:\n\n{exc}")

    def _price_sync_failed(self,message):
        progress=getattr(self,"_price_sync_progress",None)
        if progress is not None:progress.close()
        if "annulleret" in str(message).casefold():QMessageBox.information(self,"Webshoppriser","Prisopdateringen blev annulleret. Allerede hentede observationer ligger fortsat i cache.")
        else:QMessageBox.warning(self,"Webshoppriser","Prisopdateringen kunne ikke gennemføres.\n\n"+str(message))

    def _price_sync_thread_finished(self):
        thread=getattr(self,"_price_sync_thread",None); self._price_sync_thread=None; self._price_sync_progress=None
        if thread is not None:thread.deleteLater()

    def _sync_lk_catalog(self):
        if getattr(self, "_lk_sync_thread", None) is not None:
            QMessageBox.information(self, "LK-katalog", "En LK-synkronisering kører allerede.")
            return

        box=QMessageBox(self)
        box.setWindowTitle("Synkronisér LK.dk")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("Opdatér LK/Schneider-artikler i kernedatabasen?")
        box.setInformativeText(
            "Skånsom synkronisering bruger kun én forbindelse til LK.dk og holder ca. 0,8–1,5 sek. "
            "pause mellem alle netværkskald. Katalogindeks caches i 24 timer, og nyligt kontrollerede "
            "produktsider genbruges i op til 14 dage.\n\n"
            "Hvis LK.dk svarer med HTTP 403/429 eller gentagne serverfejl, sættes synkroniseringen "
            "automatisk på pause med stigende backoff. Hvis begrænsningen fortsætter, stoppes den for "
            "at beskytte din adgang. Fremskridtet gemmes, så en afbrudt fuld genhentning kan fortsættes senere.\n\n"
            "Fuld genhentning ignorerer den normale produktcachealder, men kan stadig genbruge et friskt katalogindeks og bruger stadig én forbindelse, pauser "
            "og rate-limit-beskyttelse. Egne grossistlinks, noter og prisbog bevares, og artikelbasen "
            "sikkerhedskopieres før gemning."
        )
        fast_btn=box.addButton("Skånsom synkronisering", QMessageBox.ButtonRole.AcceptRole)
        full_btn=box.addButton("Fuld genhentning (skånsom)", QMessageBox.ButtonRole.ActionRole)
        cancel_btn=box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(fast_btn)
        box.exec()
        clicked=box.clickedButton()
        if clicked is cancel_btn or clicked not in (fast_btn, full_btn):
            return
        force_refresh = clicked is full_btn

        progress=QProgressDialog("Forbinder til LK-kataloget…", "Annuller", 0, 100, self)
        progress.setWindowTitle("Synkroniserer LK-katalog")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False); progress.setAutoReset(False)
        progress.setValue(0)
        cache_path=user_library.user_data_dir()/"lk_catalog_cache.json"
        thread=_LkCatalogSyncThread(
            self,
            existing_articles=self.catalog,
            cache_path=cache_path,
            force_refresh=force_refresh,
        )
        self._lk_sync_thread=thread; self._lk_sync_progress=progress
        progress.canceled.connect(thread.cancel)
        thread.progress.connect(self._lk_sync_progress_update)
        thread.succeeded.connect(self._lk_sync_done)
        thread.failed.connect(self._lk_sync_failed)
        thread.finished.connect(self._lk_sync_thread_finished)
        progress.show(); thread.start()

    def _lk_sync_progress_update(self, text:str, value:int, total:int):
        progress=getattr(self,"_lk_sync_progress",None)
        if progress is None:return
        progress.setLabelText(text)
        total=max(1,int(total or 1)); value=max(0,min(total,int(value or 0)))
        progress.setMaximum(total); progress.setValue(value)

    def _lk_sync_done(self, snapshot):
        progress=getattr(self,"_lk_sync_progress",None)
        if progress is not None:
            progress.setLabelText("Gemmer LK-artikler i kernedatabasen…")
            progress.setMaximum(0); progress.setValue(0)
        try:
            backup=user_library.backup_core_article_catalog("before_lk_sync")
            merged,stats=lk_catalog_sync.merge_lk_articles(self.catalog, snapshot.articles)
            merged=core.normalize_article_catalog(merged)
            user_library.save_core_article_catalog(merged)
            self.catalog=deepcopy(merged)
            self._invalidate_catalog_cache()
            self._refresh_all()
            settings=core.load_app_settings(); settings["lk_catalog_last_sync"]=date.today().isoformat(); settings["lk_catalog_last_count"]=len(snapshot.articles); core.save_app_settings(settings)
            if progress is not None:progress.close()
            webstats=snapshot.stats
            warning=""
            if webstats.errors:
                warning=f"\n\n{len(webstats.errors)} sider kunne ikke hentes efter genforsøg. De øvrige artikler er importeret."
            reused=int(getattr(webstats,"cached_products",0) or 0)+int(getattr(webstats,"database_reused_products",0) or 0)
            QMessageBox.information(
                self,"LK-katalog synkroniseret",
                f"LK-kataloget er opdateret.\n\n"
                f"Fundet: {len(snapshot.articles)} LK-artikler\n"
                f"Nye: {stats['added']}\n"
                f"Opdaterede: {stats['updated']}\n"
                f"Uændrede: {stats['unchanged']}\n"
                f"Rensede eksisterende LK-poster: {stats.get('cleanup_changed',0)}\n"
                f"Fjernede web-/billedartefakter: {stats.get('cleanup_removed',0)}\n\n"
                f"Hentet fra LK: {getattr(webstats,'network_products',0)}\n"
                f"Genbrugt fra cache/database: {reused}\n"
                f"Genforsøgte sider: {getattr(webstats,'retried_products',0)}\n"
                f"Forbindelser til LK ad gangen: {getattr(webstats,'workers',1)}\n"
                f"Pause mellem kald: {getattr(webstats,'request_delay_min',0.8):.1f}–{getattr(webstats,'request_delay_max',1.5):.1f} sek.\n"
                f"Rate-limit hændelser: {getattr(webstats,'rate_limit_events',0)}\n"
                f"Backoff i alt: {getattr(webstats,'backoff_wait_seconds',0.0):.0f} sek.\n"
                f"Genbrugt fra checkpoint: {getattr(webstats,'checkpoint_reused_products',0)}\n\n"
                f"Backup: {backup}{warning}"
            )
        except Exception as exc:
            if progress is not None:progress.close()
            QMessageBox.critical(self,"LK-katalog",f"Artiklerne blev hentet, men kunne ikke gemmes:\n\n{exc}")

    def _lk_sync_failed(self, message:str):
        progress=getattr(self,"_lk_sync_progress",None)
        if progress is not None:progress.close()
        if "annulleret" in str(message).casefold():
            QMessageBox.information(self,"LK-katalog","Synkroniseringen blev annulleret. Artikelbasen er ikke ændret.")
        else:
            limited = "begrænser" in str(message).casefold() or "http 403" in str(message).casefold() or "http 429" in str(message).casefold()
            extra = (
                "\n\nProgrammet sender ikke flere forespørgsler nu. Cache/checkpoint er bevaret; prøv igen senere, "
                "så synkroniseringen kan fortsætte uden at starte de allerede hentede produktsider forfra."
                if limited else ""
            )
            QMessageBox.warning(
                self,"LK-katalog",
                "LK-kataloget kunne ikke synkroniseres, og artikelbasen er ikke ændret.\n\n"+str(message)+extra
            )

    def _lk_sync_thread_finished(self):
        thread=getattr(self,"_lk_sync_thread",None)
        self._lk_sync_thread=None
        self._lk_sync_progress=None
        if thread is not None:thread.deleteLater()

    def _build_data_quality_tab(self):
        tab=QWidget(); self.data_quality_tab=tab
        root=QVBoxLayout(tab); root.setContentsMargins(10,10,10,10); root.setSpacing(8)
        info=QLabel(
            "Auditten ændrer <b>ingen</b> artikeldata. Den validerer identiteter, kilder, standardkategorier, "
            "tekniske egenskaber, variantgrupper og bekræftede relationer. Producentens originale betegnelser bevares."
        )
        info.setWordWrap(True); info.setTextFormat(Qt.TextFormat.RichText); info.setObjectName("subtleText"); root.addWidget(info)

        top=QHBoxLayout(); top.addWidget(QLabel("Datakilde"))
        self.quality_source=QComboBox(); self.quality_source.addItem("Aktiv artikeldatabase","active"); self.quality_source.addItem("Medfølgende grunddata","predefined")
        self.quality_source.currentIndexChanged.connect(self._run_article_quality_audit); top.addWidget(self.quality_source)
        run=_set_role(QPushButton("Kør audit"),"primaryButton"); run.clicked.connect(self._run_article_quality_audit); top.addWidget(run)
        top.addStretch(1)
        export=_set_role(QPushButton("Eksportér audit CSV…"),"quietButton"); export.clicked.connect(self._export_article_quality_csv); top.addWidget(export)
        root.addLayout(top)

        cards=QHBoxLayout(); cards.setSpacing(8)
        self.quality_total=QLabel("0 artikler"); self.quality_total.setObjectName("sectionTitle")
        self.quality_errors=QLabel("0 fejl"); self.quality_errors.setObjectName("sectionTitle")
        self.quality_warnings=QLabel("0 advarsler"); self.quality_warnings.setObjectName("sectionTitle")
        self.quality_score=QLabel("100 / 100"); self.quality_score.setObjectName("sectionTitle")
        self.quality_clean=QLabel("0 % uden fejl/advarsler"); self.quality_clean.setObjectName("sectionTitle")
        for label in (self.quality_total,self.quality_errors,self.quality_warnings,self.quality_score,self.quality_clean):
            frame=QFrame(); frame.setObjectName("detailPanel"); fl=QVBoxLayout(frame); fl.setContentsMargins(10,7,10,7); fl.addWidget(label); cards.addWidget(frame,1)
        root.addLayout(cards)

        filters=QHBoxLayout(); filters.addWidget(QLabel("Vis"))
        self.quality_severity=QComboBox(); self.quality_severity.addItem("Alle niveauer","")
        for name in ("Fejl","Advarsel","Info"): self.quality_severity.addItem(name,name)
        self.quality_severity.currentIndexChanged.connect(self._refresh_article_quality_table); filters.addWidget(self.quality_severity)
        filters.addWidget(QLabel("Område")); self.quality_category=QComboBox(); self.quality_category.addItem("Alle områder",""); self.quality_category.currentIndexChanged.connect(self._refresh_article_quality_table); filters.addWidget(self.quality_category)
        self.quality_search=QLineEdit(); self.quality_search.setPlaceholderText("Søg artikel, felt, værdi eller problem…"); self.quality_search.setClearButtonEnabled(True); self.quality_search.textChanged.connect(self._refresh_article_quality_table); filters.addWidget(self.quality_search,1)
        root.addLayout(filters)

        self.quality_table=QTableView()
        self.quality_table_model=ArticleTableModel((
            ("Niveau","severity"),("Område","category"),("Artikel","article_no"),("Score","quality_score"),("Fabrikat","manufacturer"),
            ("Felt","field"),("Aktuel værdi","value"),("Problem","message"),("Forslag","suggestion"),("Berørte","count"),
        ),self.quality_table)
        self.quality_table.setModel(self.quality_table_model); self.quality_table.setSortingEnabled(True)
        _configure_resizable_table(self.quality_table,"article_quality_v05919",(90,110,120,70,180,110,210,360,390,80))
        self.quality_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.quality_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.quality_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.quality_table.doubleClicked.connect(self._open_article_quality_issue)
        root.addWidget(self.quality_table,1)
        hint=QLabel("Dobbeltklik på en artikelrelateret linje for at åbne artiklen i Artikeldatabasen. Gruppefund uden artikelnummer er katalog-/taksonomiproblemer.")
        hint.setWordWrap(True); hint.setObjectName("sectionHint"); root.addWidget(hint)
        self._article_quality_result={"summary":{},"issues":[]}
        self.tabs.addTab(tab,"Datakvalitet")

    def _run_article_quality_audit(self,*_,_refresh_library=True):
        source=str(self.quality_source.currentData() or "active") if hasattr(self,"quality_source") else "active"
        records=self.catalog if source=="active" else self.predefined
        self._article_quality_result=article_quality.audit_article_catalog(records)
        summary=self._article_quality_result.get("summary",{})
        self.quality_total.setText(f"{int(summary.get('articles',0))} artikler")
        self.quality_errors.setText(f"{int(summary.get('errors',0))} fejl")
        self.quality_warnings.setText(f"{int(summary.get('warnings',0))} advarsler")
        self.quality_score.setText(f"{float(summary.get('quality_score',100.0)):.0f} / 100")
        self.quality_clean.setText(f"{float(summary.get('clean_percent',100.0)):.0f} % uden fejl/advarsler")
        if source=="active":
            self._quality_profile_by_no=dict(self._article_quality_result.get("profiles",{}) or {})
            self._quality_audit_ready=True
            if _refresh_library and hasattr(self,"library_preview"):
                self._refresh_library_filters(); self._refresh_library(); self._library_selection_changed()
        current=str(self.quality_category.currentData() or "") if self.quality_category.count() else ""
        blocker=QSignalBlocker(self.quality_category); self.quality_category.clear(); self.quality_category.addItem("Alle områder","")
        categories=sorted({str(x.get("category","") or "") for x in self._article_quality_result.get("issues",[]) if x.get("category")},key=str.casefold)
        for name in categories:self.quality_category.addItem(name,name)
        pos=self.quality_category.findData(current); self.quality_category.setCurrentIndex(pos if pos>=0 else 0); del blocker
        self._refresh_article_quality_table()

    def _restore_last_tab(self):
        """Restore the user's last material workflow unless context requests another tab."""
        if self.focus_uid or self.initial_room_uid:
            return
        settings=core.load_app_settings()
        wanted=str(settings.get("bom_manager_last_tab","assignment") or "assignment")
        self._last_tab_key=wanted
        for widget,key in self._tab_keys.items():
            if key==wanted:
                self.tabs.setCurrentWidget(widget)
                break

    def _remember_current_tab(self):
        widget=self.tabs.currentWidget() if hasattr(self,"tabs") else None
        key=self._tab_keys.get(widget,"") if hasattr(self,"_tab_keys") else ""
        if key:self._last_tab_key=key

    def _persist_ui_state(self):
        key=str(getattr(self,"_last_tab_key","") or "")
        if not key:return
        settings=core.load_app_settings()
        if settings.get("bom_manager_last_tab")==key:return
        settings["bom_manager_last_tab"]=key
        core.save_app_settings(settings)
        if hasattr(self.window,"app_settings"):self.window.app_settings=settings

    def _price_vat_mode_changed(self,*_):
        mode=price_display.normalize_vat_mode(self.price_vat_combo.currentData())
        self.price_vat_mode=mode
        settings=core.load_app_settings()
        if settings.get("price_vat_mode")!=mode:
            settings["price_vat_mode"]=mode; core.save_app_settings(settings)
            if hasattr(self.window,"app_settings"):self.window.app_settings=settings
        if hasattr(self.window,"_hover_bom_cache"):self.window._hover_bom_cache.clear()
        for model_name in ("std_table_model","library_table_model"):
            model=getattr(self,model_name,None)
            if model is not None:model.set_price_vat_mode(mode)
        self._update_bom_price_headers()
        relevant={"assemblies","articles","bom"}
        if hasattr(self,"_tab_dirty"):self._tab_dirty.update(relevant)
        widget=self.tabs.currentWidget() if hasattr(self,"tabs") else None
        key=self._tab_keys.get(widget,"") if hasattr(self,"_tab_keys") else ""
        if key in relevant:self._refresh_current_tab(force=True)

    def _select_price_vat_mode(self,mode):
        mode=price_display.normalize_vat_mode(mode)
        index=self.price_vat_combo.findData(mode) if hasattr(self,"price_vat_combo") else -1
        if index>=0 and self.price_vat_combo.currentIndex()!=index:self.price_vat_combo.setCurrentIndex(index)

    def _update_bom_price_headers(self):
        caption=price_display.vat_caption(getattr(self,"price_vat_mode","excl"))
        if hasattr(self,"bom_table"):
            self.bom_table.horizontalHeaderItem(12).setText(f"Enhedspris {caption}")
            self.bom_table.horizontalHeaderItem(15).setText(f"Sum {caption}")
        if hasattr(self,"bom_group_tree"):
            self.bom_group_tree.headerItem().setText(12,f"Enhedspris {caption}")
            self.bom_group_tree.headerItem().setText(15,f"Sum {caption}")
        if hasattr(self,"bom_assembly_tree"):
            self.bom_assembly_tree.headerItem().setText(7,f"Enhedspris {caption}")
            self.bom_assembly_tree.headerItem().setText(8,f"Sum {caption}")

    def _refresh_current_tab(self, *, force=False):
        widget=self.tabs.currentWidget() if hasattr(self,"tabs") else None
        key=self._tab_keys.get(widget,"") if hasattr(self,"_tab_keys") else ""
        if not key or (not force and key not in getattr(self,"_tab_dirty",set())):
            return
        if key=="assignment":
            self._refresh_symbol_combo(); self._refresh_article_picker(); self._refresh_assembly_picker()
        elif key=="assemblies":
            self._refresh_assemblies()
        elif key=="cables":
            self._refresh_cable_types()
        elif key=="articles":
            self._refresh_library_filters(); self._refresh_library()
        elif key=="bom":
            self._refresh_bom()
        elif key=="quality":
            if not getattr(self,"_quality_audit_ready",False):
                self._run_article_quality_audit(_refresh_library=False)
        self._tab_dirty.discard(key)

    def _top_level_tab_changed(self,*_):
        """Refresh only the workflow the user actually opened."""
        self._remember_current_tab()
        self._refresh_current_tab()

    def _ensure_library_quality_profile(self):
        scope=str(self.lib_scope.currentData() or "") if hasattr(self,"lib_scope") else ""
        complete=bool(getattr(self,"lib_only_complete",None) is not None and self.lib_only_complete.isChecked())
        if (scope=="quality" or complete) and not getattr(self,"_quality_audit_ready",False):
            # The library explicitly asked for quality metadata, so calculate it
            # now but let the caller perform the single intended table refresh.
            self._run_article_quality_audit(_refresh_library=False)

    def _refresh_article_quality_table(self,*_):
        if not hasattr(self,"quality_table_model"): return
        rows=list(self._article_quality_result.get("issues",[]) if getattr(self,"_article_quality_result",None) else [])
        severity=str(self.quality_severity.currentData() or "") if self.quality_severity.count() else ""
        category=str(self.quality_category.currentData() or "") if self.quality_category.count() else ""
        needle=self.quality_search.text().strip().casefold() if hasattr(self,"quality_search") else ""
        if severity: rows=[r for r in rows if str(r.get("severity","") or "")==severity]
        if category: rows=[r for r in rows if str(r.get("category","") or "")==category]
        if needle:
            fields=("severity","category","article_no","quality_score","manufacturer","field","value","message","suggestion","code")
            rows=[r for r in rows if needle in " ".join(str(r.get(k,"") or "") for k in fields).casefold()]
        self.quality_table_model.set_rows(rows)

    def _open_article_quality_issue(self,*_):
        rows=sorted({i.row() for i in self.quality_table.selectedIndexes()}) if hasattr(self,"quality_table") else []
        issue=self.quality_table_model.article_at(rows[0]) if rows else {}
        article_no=str(issue.get("article_no","") or "")
        if not article_no:
            listed=[str(x) for x in issue.get("articles",[]) if str(x)]
            if listed: article_no=listed[0]
        if not article_no:return
        # Gå til den samme artikel i den aktive database. Hvis auditten køres på
        # grunddata og artiklen ikke findes aktivt, bliver fanen stadig åbnet og
        # søgefeltet udfyldt, så brugeren kan se relationen.
        self.tabs.setCurrentWidget(self.library_tab)
        self.library_search.setText(article_no); self._refresh_library()
        row=self.library_table_model.row_for_article_no(article_no)
        if row>=0:
            self.library_table.selectRow(row); self.library_table.scrollTo(self.library_table_model.index(row,0),QAbstractItemView.ScrollHint.PositionAtCenter)

    def _export_article_quality_csv(self):
        if not getattr(self,"_article_quality_result",None): self._run_article_quality_audit()
        target,_=QFileDialog.getSaveFileName(self,"Eksportér artikeldata-audit","artikeldata_audit.csv","CSV (*.csv)")
        if not target:return
        if not target.lower().endswith('.csv'):target+='.csv'
        rows=self._article_quality_result.get("issues",[])
        with open(target,"w",newline="",encoding="utf-8-sig") as fh:
            writer=csv.writer(fh,delimiter=';')
            writer.writerow(("Niveau","Område","Kode","Artikel","Score","Fabrikat","Felt","Aktuel værdi","Problem","Forslag","Berørte artikler"))
            for row in rows:
                affected=", ".join(str(x) for x in row.get("articles",[])[:50])
                writer.writerow((row.get("severity",""),row.get("category",""),row.get("code",""),row.get("article_no",""),row.get("quality_score",""),row.get("manufacturer",""),row.get("field",""),row.get("value",""),row.get("message",""),row.get("suggestion",""),affected))

    def _build_bom_tab(self):
        tab=QWidget(); self.bom_tab=tab; root=QVBoxLayout(tab); root.setContentsMargins(10,10,10,10); root.setSpacing(8)
        hdr=QHBoxLayout(); view=QHBoxLayout()
        hdr.addWidget(QLabel("Vis rum"))
        self.bom_room_filter=QComboBox(); self.bom_room_filter.setMinimumWidth(175)
        self.bom_room_filter.addItem("Alle rum","")
        for room in sorted(list(getattr(self.window.project,"rooms",[]) or []),key=lambda r:core.room_display_text(r).casefold()):
            self.bom_room_filter.addItem(core.room_display_text(room),str(getattr(room,"uid","") or ""))
        self.bom_room_filter.addItem("Uden rum","__outside__")
        self.bom_room_filter.setToolTip("Alle rum viser den samlede BOM. Vælg et rum for kun at se og summere bidrag fra dette rum.")
        self.bom_room_filter.currentIndexChanged.connect(self._refresh_bom); hdr.addWidget(self.bom_room_filter)

        view.addWidget(QLabel("Grupper"))
        self.bom_group_by=QComboBox(); self.bom_group_by.setMinimumWidth(145)
        self.bom_group_by.addItem("Ingen gruppering","")
        self.bom_group_by.addItem("Rum","room_display")
        self.bom_group_by.addItem("Artikeltype","bom_category")
        self.bom_group_by.addItem("Monteringsprofil","mounting_zone_label")
        self.bom_group_by.addItem("Monteringshøjde","mounting_height_display")
        self.bom_group_by.addItem("Materialefarve","material_color")
        self.bom_group_by.addItem("Indkøbsstatus","purchase_status")
        self.bom_group_by.addItem("Hovedkategori","category")
        self.bom_group_by.addItem("Gruppe/kreds","circuit_display")
        self.bom_group_by.addItem("Stykliste / kilde","source_summary")
        self.bom_group_by.addItem("Fabrikat","manufacturer")
        self.bom_group_by.currentIndexChanged.connect(self._refresh_bom); view.addWidget(self.bom_group_by)

        hdr.addWidget(QLabel("Artikeltype"))
        self.bom_category_filter=QComboBox(); self.bom_category_filter.setMinimumWidth(155)
        self.bom_category_filter.addItem("Alle typer","")
        self.bom_category_filter.setToolTip("Vis kun én materialetype. Excel-eksporten følger valget og bevarer samtidig typen som en filterbar kolonne.")
        self.bom_category_filter.currentIndexChanged.connect(self._refresh_bom); hdr.addWidget(self.bom_category_filter)

        hdr.addWidget(QLabel("Hurtigfilter"))
        self.bom_quick_filter=QComboBox(); self.bom_quick_filter.setMinimumWidth(155)
        self.bom_quick_filter.addItem("Alle","")
        self.bom_quick_filter.addItem("Manglende pris","missing_price")
        self.bom_quick_filter.addItem("Fra stykliste","assembly")
        self.bom_quick_filter.addItem("Direkte / manuelt","manual")
        self.bom_quick_filter.addItem("Kabler","cable")
        self.bom_quick_filter.addItem("Artikel mangler","missing_article")
        self.bom_quick_filter.addItem("Forældet pris","stale_price")
        self.bom_quick_filter.addItem("Pakning skal kontrolleres","package")
        self.bom_quick_filter.addItem("Alle kontrolpunkter","warning")
        self.bom_quick_filter.currentIndexChanged.connect(self._refresh_bom); hdr.addWidget(self.bom_quick_filter)
        self.bom_show_cables=QCheckBox("Vis kabler")
        self.bom_show_cables.setChecked(True)
        self.bom_show_cables.setToolTip("Slå fra for at genberegne den aktuelle BOM, mangelliste, total og eksport uden kabelartikler.")
        self.bom_show_cables.toggled.connect(self._bom_cable_visibility_changed); hdr.addWidget(self.bom_show_cables)

        self.bom_status=QLabel(""); self.bom_status.setObjectName("accentText"); hdr.addWidget(self.bom_status,1)
        root.addLayout(hdr)
        view.addWidget(QLabel("Sortér efter"))
        self.bom_sort=QComboBox(); self.bom_sort.addItem("Artikelnummer","article_no"); self.bom_sort.addItem("Artikeltype","bom_category"); self.bom_sort.addItem("Rum","room_display"); self.bom_sort.addItem("Monteringsprofil","mounting_zone_label"); self.bom_sort.addItem("Monteringshøjde","mounting_height_mm"); self.bom_sort.addItem("Materialefarve","material_color"); self.bom_sort.addItem("Indkøbsstatus","purchase_status"); self.bom_sort.addItem("Beskrivelse","description"); self.bom_sort.addItem("Fabrikat","manufacturer")
        self.bom_sort.setToolTip("Vælg hvilket felt den viste artikel-BOM skal sorteres efter.")
        self.bom_sort.currentIndexChanged.connect(self._refresh_bom); view.addWidget(self.bom_sort)
        view.addWidget(QLabel("Montage"))
        self.bom_mounting_filter=QComboBox(); self.bom_mounting_filter.setMinimumWidth(135); self.bom_mounting_filter.addItem("Alle profiler","")
        self.bom_mounting_filter.currentIndexChanged.connect(self._refresh_bom); view.addWidget(self.bom_mounting_filter)
        view.addWidget(QLabel("Farve"))
        self.bom_material_color_filter=QComboBox(); self.bom_material_color_filter.setMinimumWidth(120); self.bom_material_color_filter.addItem("Alle farver","")
        self.bom_material_color_filter.currentIndexChanged.connect(self._refresh_bom); view.addWidget(self.bom_material_color_filter)
        view.addWidget(QLabel("Indkøb"))
        self.bom_purchase_filter=QComboBox(); self.bom_purchase_filter.setMinimumWidth(145)
        self.bom_purchase_filter.addItem("Alle",""); self.bom_purchase_filter.addItem("Mangler at købe","not_purchased"); self.bom_purchase_filter.addItem("Allerede købt","purchased")
        self.bom_purchase_filter.currentIndexChanged.connect(self._refresh_bom); view.addWidget(self.bom_purchase_filter); view.addStretch(1)
        root.addLayout(view)

        actions=QHBoxLayout()
        fit_cols=_set_role(QPushButton("Tilpas kolonner"), "quietButton"); fit_cols.clicked.connect(self._fit_active_bom_columns); actions.addWidget(fit_cols)
        reset_cols=_set_role(QPushButton("Nulstil bredder"), "quietButton"); reset_cols.clicked.connect(self._reset_active_bom_columns); actions.addWidget(reset_cols)
        source_btn=_set_role(QPushButton("Hvor kommer linjen fra?"),"quietButton"); source_btn.setToolTip("Vis de konkrete styklister, symboler, manuelle bindinger og kabler bag den valgte artikel."); source_btn.clicked.connect(self._open_selected_bom_sources); actions.addWidget(source_btn)
        show_plan=_set_role(QPushButton("Vis på plan"),"quietButton"); show_plan.setToolTip("Fremhæv alle forekomster af den valgte BOM-artikel på plantegningen."); show_plan.clicked.connect(self._show_active_bom_on_plan); actions.addWidget(show_plan)
        actions.addStretch(1)
        print_bom=_set_role(QPushButton("Udskriv / PDF…"),"primaryButton"); print_bom.setToolTip("Vis først en enkel A4-forhåndsvisning med priser; udskriv derefter direkte eller gem som PDF."); print_bom.clicked.connect(self._open_bom_print_preview); actions.addWidget(print_bom)
        export_xlsx=QPushButton("Eksportér Excel…"); export_xlsx.setToolTip("Eksportér den aktuelle BOM-visning som en formateret Excel-tabel (.xlsx)."); export_xlsx.clicked.connect(self._export_bom_xlsx); actions.addWidget(export_xlsx)
        export_csv=_set_role(QPushButton("Eksportér CSV…"), "quietButton"); export_csv.setToolTip("Eksportér den aktuelle BOM-visning som semikolonsepareret CSV."); export_csv.clicked.connect(self._export_bom_csv); actions.addWidget(export_csv)
        root.addLayout(actions)

        self.bom_view_tabs=QTabWidget()

        # 1) Klassisk artikel-BOM. Standardvisningen er fortsat en tabel, men
        # grupperingsvalg skifter til et kollapsbart træ uden at ændre data.
        article_page=QWidget(); article_layout=QVBoxLayout(article_page); article_layout.setContentsMargins(0,0,0,0)
        self.bom_article_stack=QStackedWidget()
        self.bom_table=QTableWidget(0,17)
        self.bom_table.setHorizontalHeaderLabels(["Artikelnummer","Rum","Beskrivelse","Fabrikat","Type/kategori","Montage / farve","Indkøbsstatus","Kilde / stykliste","EAN","EL-/LM-nr.","Enhed","Antal","Enhedspris","Prisstatus","Pris pr.","Sum","Grundlag"])
        # Legacy layout key reference: "bom_result_v05923"
        _configure_resizable_table(self.bom_table,"bom_result_v05977",(125,175,320,140,165,230,125,240,135,115,70,70,115,95,70,110,280))
        self.bom_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bom_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.bom_table.setMouseTracking(True); self.bom_table.viewport().setMouseTracking(True); self.bom_table.viewport().installEventFilter(self)
        self.bom_table.setToolTip("Hold musen kort over en artikelrække for at se produktbillede. Kilde-kolonnen viser om varen kommer fra en stykliste, direkte binding, Wago eller kabel. Dobbeltklik for at fremhæve alle forekomster på planen.")
        self.bom_table.itemDoubleClicked.connect(self._bom_row_activated)
        self.bom_article_stack.addWidget(self.bom_table)

        self.bom_group_tree=QTreeWidget(); self.bom_group_tree.setColumnCount(17)
        self.bom_group_tree.setHeaderLabels(["Artikelnummer / gruppe","Rum","Beskrivelse","Fabrikat","Type/kategori","Montage / farve","Indkøbsstatus","Kilde / stykliste","EAN","EL-/LM-nr.","Enhed","Antal","Enhedspris","Prisstatus","Pris pr.","Sum","Grundlag"])
        self.bom_group_tree.setAlternatingRowColors(True); self.bom_group_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.bom_group_tree.itemDoubleClicked.connect(self._bom_group_item_activated)
        self.bom_article_stack.addWidget(self.bom_group_tree)
        article_layout.addWidget(self.bom_article_stack)
        self.bom_view_tabs.addTab(article_page,"Artikler")

        # 2) De anvendte genbrugelige styklister som en kollapsbar styklistevisning.
        assembly_page=QWidget(); assembly_layout=QVBoxLayout(assembly_page); assembly_layout.setContentsMargins(0,0,0,0)
        assembly_hint=QLabel("Viser kun styklister som faktisk anvendes i den aktuelle BOM-visning. Fold en stykliste ud for at se dens artikelbidrag.")
        assembly_hint.setWordWrap(True); assembly_hint.setObjectName("sectionHint"); assembly_layout.addWidget(assembly_hint)
        self.bom_assembly_tree=QTreeWidget(); self.bom_assembly_tree.setColumnCount(9)
        self.bom_assembly_tree.setHeaderLabels(["Stykliste / artikel","Kategori","Variant","Rum","Brugt","Antal","Enhed","Enhedspris","Sum"])
        self.bom_assembly_tree.setAlternatingRowColors(True)
        self.bom_assembly_tree.itemDoubleClicked.connect(self._bom_assembly_item_activated)
        assembly_layout.addWidget(self.bom_assembly_tree,1)
        self.bom_view_tabs.addTab(assembly_page,"Styklister")

        # 3) Rå sporbarhed: én række pr. konkret kilde/bidrag.
        source_page=QWidget(); source_layout=QVBoxLayout(source_page); source_layout.setContentsMargins(0,0,0,0)
        source_hint=QLabel("Én række pr. konkret BOM-kilde. Dobbeltklik for at gå direkte til det symbol eller kabel, som skabte bidraget.")
        source_hint.setWordWrap(True); source_hint.setObjectName("sectionHint"); source_layout.addWidget(source_hint)
        self.bom_source_table=QTableWidget(0,10)
        self.bom_source_table.setHorizontalHeaderLabels(["Artikelnummer","Rum","Montage / farve","Indkøbsstatus","Kildetype","Stykliste / kilde","Symbol / kabel","Del","Bidrag","Detalje"])
        _configure_resizable_table(self.bom_source_table,"bom_sources_v05977",(130,175,220,120,105,225,180,170,95,320))
        self.bom_source_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.bom_source_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bom_source_table.itemDoubleClicked.connect(self._bom_source_row_activated)
        source_layout.addWidget(self.bom_source_table,1)
        self.bom_view_tabs.addTab(source_page,"Kilder")

        # 4) Handlingsorienteret kvalitetskontrol for den aktuelle BOM.
        quality_page=QWidget(); quality_layout=QVBoxLayout(quality_page); quality_layout.setContentsMargins(0,0,0,0); quality_layout.setSpacing(7)
        self.bom_quality_summary=QLabel(""); self.bom_quality_summary.setWordWrap(True); self.bom_quality_summary.setObjectName("accentText"); quality_layout.addWidget(self.bom_quality_summary)
        self.bom_quality_table=QTableWidget(0,5)
        self.bom_quality_table.setHorizontalHeaderLabels(["Niveau","Artikel / del","Område","Problem","Forslag"])
        _configure_resizable_table(self.bom_quality_table,"bom_quality_v05972",(95,180,110,360,360))
        self.bom_quality_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.bom_quality_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bom_quality_table.itemDoubleClicked.connect(self._open_bom_quality_article)
        quality_layout.addWidget(self.bom_quality_table,2)
        missing_title=QLabel("Symboldele / kabelstræk uden artikel eller stykliste"); missing_title.setObjectName("sectionTitle"); quality_layout.addWidget(missing_title)
        self.missing_table=QTableWidget(0,5)
        self.missing_table.setHorizontalHeaderLabels(["Type","Del/specifikation","Behov","Enhed","Bemærkning"])
        _configure_resizable_table(self.missing_table,"bom_missing",(130,360,95,80,440))
        self.missing_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        quality_layout.addWidget(self.missing_table,1)
        self.bom_view_tabs.addTab(quality_page,"Kontrol")

        root.addWidget(self.bom_view_tabs,2)

        total_row=QHBoxLayout(); total_row.addStretch(1)
        self.bom_total_label=QLabel(f"Summeret pris {price_display.vat_caption(self.price_vat_mode)} (aktuel visning): —")
        self.bom_total_label.setObjectName("accentText")
        total_font=self.bom_total_label.font(); total_font.setBold(True); total_font.setPointSizeF(total_font.pointSizeF()+1.0); self.bom_total_label.setFont(total_font)
        self.bom_total_label.setToolTip("Summerer linjesummerne efter aktuelt rum- og hurtigfilter. Linjer uden pris medregnes ikke.")
        total_row.addWidget(self.bom_total_label); root.addLayout(total_row)

        self._update_bom_price_headers()
        self.tabs.addTab(tab,"BOM")

    def eventFilter(self,obj,event):
        if hasattr(self,"bom_table") and obj is self.bom_table.viewport():
            et=event.type()
            if et==QEvent.Type.MouseMove:
                pos=event.position().toPoint(); item=self.bom_table.itemAt(pos); row=item.row() if item is not None else -1
                self._bom_hover_global_pos=self.bom_table.viewport().mapToGlobal(pos)
                if row!=self._bom_hover_row:
                    self._bom_hover_timer.stop(); self._hide_bom_hover_popup(); self._bom_hover_row=row
                    if row>=0:self._bom_hover_timer.start()
            elif et in (QEvent.Type.Leave,QEvent.Type.Hide):
                self._bom_hover_timer.stop(); self._bom_hover_row=-1; self._hide_bom_hover_popup()
        return super().eventFilter(obj,event)

    def _hide_bom_hover_popup(self):
        popup=getattr(self,"_bom_hover_popup",None)
        if popup is not None:popup.hide()

    def _show_bom_hover_popup(self):
        row=int(getattr(self,"_bom_hover_row",-1))
        if row<0 or row>=self.bom_table.rowCount():return
        article_item=self.bom_table.item(row,0); article_no=str(article_item.data(Qt.ItemDataRole.UserRole) or article_item.text() or "") if article_item else ""
        article=self._catalog_lookup().get(article_no,{})
        pos=getattr(self,"_bom_hover_global_pos",None)
        if not article or pos is None:return
        if self._bom_hover_popup is None:self._bom_hover_popup=BomArticleHoverPopup(self)
        self._bom_hover_popup.show_article(article,pos)

    # ---- katalog helpers ----------------------------------------------
    def _invalidate_catalog_cache(self):
        self._catalog_cache=None
        self._catalog_lookup_cache=None
        self._library_enriched_cache=None

    def _available_catalog(self):
        # Flere faner spørger efter samme sammensmeltede katalog under ét refresh.
        # Cache det, indtil en artikel eller pris faktisk ændres.  self.catalog
        # kommer fra den normaliserede kernedatabase, og price_book er allerede
        # normaliseret ved load; undgå derfor to fulde katalogpassager her.
        if self._catalog_cache is None:
            priced=user_library.apply_article_prices(
                self.catalog,self.price_book,assume_normalized=True,prices_normalized=True)
            self._catalog_cache=sorted(priced,key=lambda a:(str(a.get("manufacturer","")).casefold(),str(a.get("category","")).casefold(),a["article_no"].casefold()))
        return self._catalog_cache

    def _catalog_lookup(self):
        if self._catalog_lookup_cache is None:
            self._catalog_lookup_cache={r["article_no"]:r for r in self._available_catalog()}
        return self._catalog_lookup_cache

    def _ensure_project_article(self,article_no):
        article_no=str(article_no or "")
        if any(a["article_no"]==article_no for a in self.catalog): return True
        # Normalt findes artiklen allerede i den globale Artikeldatabase. Fallback
        # er kun til gamle globale styklister med et indlejret snapshot.
        src=next((a for a in getattr(self,"global_assembly_articles",[]) if a["article_no"]==article_no),None)
        if src is None:return False
        self.catalog.append(deepcopy(src)); self.catalog=core.normalize_article_catalog(self.catalog)
        try:user_library.save_core_article_catalog(self.catalog)
        except Exception:pass
        self._invalidate_catalog_cache()
        return True

    def _refresh_all(self, *, normalize_state=True):
        self._invalidate_catalog_cache()
        # Persistent stores already return normalized data. Re-normalize only
        # after mutations, never just because the dialog was opened.
        if normalize_state:
            self.catalog=core.normalize_article_catalog(self.catalog)
            self.assemblies=core.normalize_bom_assemblies(self.assemblies)
            self.bindings=core.normalize_symbol_article_bindings(self.bindings)
            self.assembly_bindings=core.normalize_symbol_assembly_bindings(self.assembly_bindings)
            self.cable_bindings=core.normalize_cable_article_bindings(self.cable_bindings)
        self._quality_audit_ready=False
        self._quality_profile_by_no={}
        # All top-level workflows become dirty, but only the visible one is
        # rebuilt now. This prevents article tables, cable lists and the BOM
        # from all doing work during the same dialog-open event.
        if hasattr(self,"_tab_keys"):
            self._tab_dirty=set(self._tab_keys.values())
            self._refresh_current_tab(force=True)
        else:
            self._refresh_symbol_combo(); self._refresh_article_picker(); self._refresh_assembly_picker()

    def _library_enriched_rows(self):
        if self._library_enriched_cache is None:
            # _available_catalog already contains the price overlay.  Applying
            # prices again here previously repeated a whole-catalogue pass.
            self._library_enriched_cache=build_article_search_index(self._available_catalog())
        return self._library_enriched_cache

    def _library_filter_controls(self):
        return (
            (self.lib_manufacturer,"Alle fabrikater","manufacturer"),
            (self.lib_category,"Alle kategorier","category_normalized"),
            (self.lib_type,"Alle typer","product_type"),
            (self.lib_design,"Alle familier","product_family"),
            (self.lib_variant,"Alle varianter","product_variant"),
            (self.lib_module,"Alle moduler","module_group"),
            (self.lib_color,"Alle farver","color"),
            (self.lib_diameter,"Alle diametre","diameter_mm"),
            (self.lib_cct,"Alle CCT","cct"),
            (self.lib_ip,"Alle IP","ip_rating"),
        )

    def _save_article_usage_settings(self):
        data=core.load_app_settings()
        data["favorite_articles"]=list(dict.fromkeys(self._favorite_article_nos))[:200]
        data["recent_articles"]=list(dict.fromkeys(self._recent_article_nos))[:24]
        core.save_app_settings(data)
        if hasattr(self.window,"app_settings"):
            self.window.app_settings=data

    def _remember_recent_article(self,article_no):
        article_no=str(article_no or "").strip()
        if not article_no:return
        self._recent_article_nos=[x for x in self._recent_article_nos if x!=article_no]
        self._recent_article_nos.insert(0,article_no); self._recent_article_nos=self._recent_article_nos[:24]
        self._save_article_usage_settings()
        if hasattr(self,"lib_scope") and str(self.lib_scope.currentData() or "")=="recent":self._refresh_library()

    def _toggle_library_favorite(self,*_):
        art=self._selected_library_article(); article_no=str(art.get("article_no","") or "").strip()
        if not article_no:return
        if article_no in self._favorite_article_nos:
            self._favorite_article_nos=[x for x in self._favorite_article_nos if x!=article_no]
        else:
            self._favorite_article_nos.insert(0,article_no)
        self._save_article_usage_settings(); self._refresh_library(); self._library_selection_changed()

    def _project_article_nos(self):
        if self._project_article_cache is None:
            try:self._project_article_cache={str(r.get("article_no","") or "") for r in self._bom_data("") if str(r.get("article_no","") or "")}
            except Exception:self._project_article_cache=set()
        return set(self._project_article_cache)

    def _library_scope_match(self,art):
        scope=str(self.lib_scope.currentData() or "") if hasattr(self,"lib_scope") else ""
        no=str(art.get("article_no","") or "")
        if scope=="favorites":return no in self._favorite_article_nos
        if scope=="recent":return no in self._recent_article_nos
        if scope=="project":return no in self._project_article_nos()
        if scope=="quality":
            profile=getattr(self,"_quality_profile_by_no",{}).get(no,{})
            return bool(profile and (profile.get("errors",0) or profile.get("warnings",0) or float(profile.get("score",100) or 100)<90))
        return True

    def _library_base_candidates(self,ignore_key="",include_query=True):
        controls=self._library_filter_controls()
        wanted={key:str(combo.currentData() or "") for combo,_label,key in controls}
        query=self.library_search.text().strip() if hasattr(self,"library_search") and include_query else ""
        terms=normalize_search_text(query).split()
        out=[]
        for art in self._library_enriched_rows():
            if not self._library_scope_match(art):continue
            if self.lib_only_price.isChecked() and str(art.get("unit_price","")).strip()=="":continue
            if getattr(self,"lib_only_complete",None) is not None and self.lib_only_complete.isChecked():
                profile=getattr(self,"_quality_profile_by_no",{}).get(str(art.get("article_no","") or ""),{})
                if profile and (profile.get("errors",0) or profile.get("warnings",0)):continue
            mismatch=False
            for key,value in wanted.items():
                if key==ignore_key:continue
                if value and str(art.get(key,"") or "")!=value:mismatch=True; break
            if mismatch:continue
            if terms and not all(term in str(art.get("_search_blob_folded",art.get("_search_blob","")) or "") for term in terms):continue
            out.append(art)
        return out

    def _refresh_library_filters(self):
        if not hasattr(self,"lib_manufacturer"):return
        controls=self._library_filter_controls()
        currents={key:str(combo.currentData() or "") for combo,_label,key in controls}
        module_order={"1M":1,"1½M":2,"2M":3,"2×1M":4,"2½M":5,"3M":6,"3½M":7,"2×1½M":8,"2×2M":9,"3×1½M":10}
        for combo,all_label,key in controls:
            blocker=QSignalBlocker(combo)
            current=currents.get(key,"")
            candidates=self._library_base_candidates(ignore_key=key,include_query=True)
            counts=facet_value_counts(candidates,key)
            combo.clear(); combo.addItem(f"{all_label} ({len(candidates)})","")
            names=sorted(counts,key=(lambda x:(module_order.get(x,99),x.casefold())) if key=="module_group" else str.casefold)
            for name in names:combo.addItem(f"{name} ({counts[name]})",name)
            pos=combo.findData(current); combo.setCurrentIndex(pos if pos>=0 else 0)
            del blocker

    def _library_filter_changed(self,*_):
        self._library_search_timer.stop(); self._ensure_library_quality_profile(); self._refresh_library_filters(); self._refresh_library()

    def _schedule_library_refresh(self,*_):
        self._library_search_timer.start()

    def _library_search_refresh(self):
        self._ensure_library_quality_profile(); self._refresh_library_filters(); self._refresh_library()

    def _clear_library_filters(self):
        self._library_search_timer.stop()
        controls=(self.library_search,self.lib_scope,*[c for c,_label,_key in self._library_filter_controls()],self.lib_only_price,self.lib_only_complete)
        blockers=[QSignalBlocker(control) for control in controls]
        self.library_search.clear(); self.lib_scope.setCurrentIndex(0)
        for combo,_label,_key in self._library_filter_controls():
            if combo.count():combo.setCurrentIndex(0)
        self.lib_only_price.setChecked(False); self.lib_only_complete.setChecked(False)
        del blockers
        self._refresh_library_filters(); self._refresh_library()

    def _selected_library_article(self):
        if not hasattr(self,"library_table"):
            return {}
        rows=sorted({i.row() for i in self.library_table.selectedIndexes()})
        return self.library_table_model.article_at(rows[0]) if rows else {}

    def _library_selection_changed(self):
        if not hasattr(self,"library_preview"):
            return
        art=self._selected_library_article()
        self.library_preview.set_article(art)
        enabled=bool(art)
        for name in ("library_edit_button","library_price_button","library_relations_button","library_favorite_button","library_usage_button"):
            if hasattr(self,name):getattr(self,name).setEnabled(enabled)
        if hasattr(self,"library_compare_button"):
            self.library_compare_button.setEnabled(bool(art and art.get("price_observations")))
        if not art:
            self.library_preview_title.setText("Vælg en artikel"); self.library_preview_specs.clear(); self.library_preview_meta.clear()
            for name in ("library_open_source","library_open_supplier","library_open_datasheet","library_reload_image","library_prev_variant","library_next_variant"):
                if hasattr(self,name):getattr(self,name).setEnabled(False)
            if hasattr(self,"library_favorite_button"):self.library_favorite_button.setText("☆ Favorit")
            if hasattr(self,"library_variant_hint"):self.library_variant_hint.clear()
            self._refresh_assignment_target_ui()
            return
        facets=core.article_filter_facets(art)
        self.library_preview_title.setText(f"{art.get('article_no','')} · {art.get('description','')}")
        tags=[str(art.get('category_normalized','') or ''),facets.get('product_type',''),str(art.get('function','') or ''),str(art.get('product_family','') or facets.get('product_family','')),str(art.get('product_variant','') or facets.get('product_variant','')),facets.get('module_size',''),facets.get('color','')]
        if art.get('diameter_mm'):tags.append(f"Ø{art['diameter_mm']} mm")
        if art.get('cct'):tags.append(str(art['cct']))
        if art.get('power_w'):tags.append(str(art['power_w']))
        self.library_preview_specs.setText("<b>Specifikation:</b> "+" &nbsp; · &nbsp; ".join(x for x in tags if x))
        meta=[]
        meta.extend(_article_price_meta_lines(art,self.price_vat_mode))
        meta.append(_article_packaging_meta_line(art))
        if art.get('el_no'):meta.append(f"EL-/LM-nr. {art['el_no']}")
        if art.get('ean'):meta.append(f"EAN {art['ean']}")
        if art.get('series'):meta.append(str(art['series']))
        if art.get('image_source'):meta.append(f"Foto: {art['image_source']} (online/cache)")
        if art.get('status'):meta.append(str(art['status']))
        if int(art.get('variant_count',1) or 1)>1:
            axes=', '.join(article_intelligence.spec_label(x) for x in art.get('variant_axes',[]) or [])
            meta.append(f"Variantgruppe: {int(art.get('variant_count',1))} artikler"+(f" · varierer på {axes}" if axes else ""))
        article_no=str(art.get('article_no','') or '')
        assembly_names=[]
        for assembly in self.assemblies:
            if any(str(item.get("article_no","") or "")==article_no for item in assembly.get("items",[]) or []):
                name=str(assembly.get("name","") or "").strip()
                if name and name not in assembly_names:assembly_names.append(name)
        if assembly_names:
            shown=", ".join(assembly_names[:3]); meta.append(f"Bruges i styklister: {shown}"+(f" +{len(assembly_names)-3}" if len(assembly_names)>3 else ""))
        profile=getattr(self,"_quality_profile_by_no",{}).get(article_no,{})
        if profile:meta.append(f"Datakvalitet: {profile.get('score',100)}/100 · {profile.get('status','')}")
        compat=article_intelligence.compatibility_text(art)
        if compat:meta.append("Kompatibilitet: "+compat)
        extra_specs=article_intelligence.technical_specs_text(art,limit=6)
        if extra_specs:meta.append("Egenskaber: "+" · ".join(extra_specs))
        self.library_preview_meta.setText("\n".join(meta))
        article_no=str(art.get("article_no","") or "")
        if hasattr(self,"library_favorite_button"):
            self.library_favorite_button.setText("★ Favorit" if article_no in self._favorite_article_nos else "☆ Favorit")
        variants=article_intelligence.variant_members(art,self._available_catalog())
        if hasattr(self,"library_prev_variant"):self.library_prev_variant.setEnabled(bool(variants))
        if hasattr(self,"library_next_variant"):self.library_next_variant.setEnabled(bool(variants))
        if hasattr(self,"library_variant_hint"):
            if variants:
                labels=[]
                for item in variants[:5]:
                    bits=[str(item.get("product_variant","") or ""),str(item.get("color","") or ""),str(item.get("module_size","") or "")]
                    label=" / ".join(x for x in bits if x) or str(item.get("article_no","") or "")
                    if label not in labels:labels.append(label)
                self.library_variant_hint.setText(f"{len(variants)+1} artikler i variantgruppen · "+" · ".join(labels)+(f" · +{len(variants)-5}" if len(variants)>5 else ""))
            else:self.library_variant_hint.setText("Ingen øvrige varianter i samme produktgruppe.")
        source=str(art.get('product_page','') or art.get('source','') or '')
        supplier=str(art.get('supplier_page','') or '')
        datasheet=str(art.get('datasheet_url','') or '')
        self.library_open_source.setEnabled(source.startswith(('http://','https://')))
        self.library_open_supplier.setEnabled(supplier.startswith(('http://','https://')))
        self.library_open_datasheet.setEnabled(datasheet.startswith(('http://','https://')))
        self.library_reload_image.setEnabled(bool(art.get('image_url')) or source.startswith(('http://','https://')))
        self._refresh_assignment_target_ui()

    def _select_adjacent_variant(self,direction):
        art=self._selected_library_article()
        if not art:return
        members=[dict(art)]+article_intelligence.variant_members(art,self._available_catalog())
        members=sorted(members,key=lambda r:(str(r.get("product_variant","") or "").casefold(),str(r.get("color","") or "").casefold(),str(r.get("module_size","") or "").casefold(),str(r.get("article_no","") or "").casefold()))
        current=str(art.get("article_no","") or "")
        try:index=next(i for i,r in enumerate(members) if str(r.get("article_no","") or "")==current)
        except StopIteration:return
        target=str(members[(index+(1 if int(direction)>=0 else -1))%len(members)].get("article_no","") or "")
        row=self.library_table_model.row_for_article_no(target)
        if row<0:
            # Variant may be hidden by active facets; clear only identity-changing facets, not search/scope.
            blockers=[QSignalBlocker(x) for x in (self.lib_variant,self.lib_module,self.lib_color)]
            for combo in (self.lib_variant,self.lib_module,self.lib_color):combo.setCurrentIndex(0)
            del blockers
            self._refresh_library_filters(); self._refresh_library(); row=self.library_table_model.row_for_article_no(target)
        if row>=0:
            self.library_table.selectRow(row); self.library_table.scrollTo(self.library_table_model.index(row,0),QAbstractItemView.ScrollHint.PositionAtCenter)

    def _open_library_source(self):
        art=self._selected_library_article(); url=str(art.get('product_page','') or art.get('source','') or '').strip()
        if url.startswith(('http://','https://')):QDesktopServices.openUrl(QUrl(url))

    def _open_library_supplier(self):
        art=self._selected_library_article(); url=str(art.get('supplier_page','') or '').strip()
        if url.startswith(('http://','https://')):QDesktopServices.openUrl(QUrl(url))

    def _open_library_datasheet(self):
        art=self._selected_library_article(); url=str(art.get('datasheet_url','') or '').strip()
        if url.startswith(('http://','https://')):QDesktopServices.openUrl(QUrl(url))

    def _refresh_standard_filters(self):
        controls=(
            (self.std_manufacturer,"Alle fabrikater","manufacturer"),
            (self.std_type,"Alle typer","product_type"),
            (self.std_design,"Alle familier","product_family"),
            (self.std_variant,"Alle varianter","product_variant"),
            (self.std_module,"Alle moduler","module_group"),
            (self.std_color,"Alle farver","color"),
            (self.std_diameter,"Alle diametre","diameter_mm"),
            (self.std_cct,"Alle CCT","cct"),
            (self.std_ip,"Alle IP","ip_rating"),
        )
        currents=[c.currentData() if c.count() else "" for c,_,_ in controls]
        blockers=[QSignalBlocker(c) for c,_,_ in controls]
        enriched=self._predefined_enriched
        for (combo,all_label,key),current in zip(controls,currents):
            combo.clear(); combo.addItem(all_label,"")
            vals={str(a.get(key,"") or "") for a in enriched if a.get(key)}
            if key=="module_group":
                order={"1M":1,"1½M":2,"2M":3,"2×1M":4,"2½M":5,"3M":6,"3½M":7,"2×1½M":8,"2×2M":9,"3×1½M":10}
                names=sorted(vals,key=lambda x:(order.get(x,99),x.casefold()))
            else: names=sorted(vals,key=str.casefold)
            for name in names: combo.addItem(name,name)
            idx=combo.findData(current); combo.setCurrentIndex(idx if idx>=0 else 0)
        del blockers

    def _schedule_predefined_refresh(self,*_):
        self._std_search_timer.start()

    def _clear_standard_filters(self):
        self._std_search_timer.stop()
        controls=(self.std_search,self.std_manufacturer,self.std_type,self.std_design,self.std_variant,self.std_module,self.std_color,self.std_diameter,self.std_cct,self.std_ip,self.std_only_price)
        blockers=[QSignalBlocker(control) for control in controls]
        self.std_search.clear()
        for combo in (self.std_manufacturer,self.std_type,self.std_design,self.std_variant,self.std_module,self.std_color,self.std_diameter,self.std_cct,self.std_ip):
            if combo.count(): combo.setCurrentIndex(0)
        self.std_only_price.setChecked(False)
        del blockers
        self._refresh_predefined()

    def _refresh_predefined(self,*_):
        if not hasattr(self,"std_table"):return
        self._std_search_timer.stop()
        selected_rows=sorted({i.row() for i in self.std_table.selectedIndexes()})
        selected_no=self.std_table_model.article_no_at(selected_rows[0]) if selected_rows else ""
        query=self.std_search.text().strip().casefold() if hasattr(self,"std_search") else ""
        wanted={
            "manufacturer":str(self.std_manufacturer.currentData() or "") if self.std_manufacturer.count() else "",
            "product_type":str(self.std_type.currentData() or "") if self.std_type.count() else "",
            "product_family":str(self.std_design.currentData() or "") if self.std_design.count() else "",
            "product_variant":str(self.std_variant.currentData() or "") if self.std_variant.count() else "",
            "module_group":str(self.std_module.currentData() or "") if self.std_module.count() else "",
            "color":str(self.std_color.currentData() or "") if self.std_color.count() else "",
            "diameter_mm":str(self.std_diameter.currentData() or "") if self.std_diameter.count() else "",
            "cct":str(self.std_cct.currentData() or "") if self.std_cct.count() else "",
            "ip_rating":str(self.std_ip.currentData() or "") if self.std_ip.count() else "",
        }
        visible=[]
        for art in self._predefined_enriched:
            if any(value and str(art.get(key,"") or "")!=value for key,value in wanted.items()): continue
            if self.std_only_price.isChecked() and str(art.get("unit_price","")).strip()=="": continue
            if query and query not in art.get("_search_blob",""):continue
            visible.append(art)
        self._predefined_visible=visible
        local={a["article_no"] for a in self.catalog}
        self.std_table_model.set_rows(visible,local)
        self.std_table.clearSelection()
        restore=self.std_table_model.row_for_article_no(selected_no)
        if self.std_table_model.rowCount():
            self.std_table.selectRow(restore if restore>=0 else 0)
        elif not self.std_table_model.rowCount():
            self._predefined_selection_changed()
        self.std_count.setText(f"{len(visible)} af {len(self.predefined)} standardartikler · ✓ = findes i artikelbasen")

    def _predefined_selection_changed(self):
        records=self._selected_standard_articles() if hasattr(self,"std_table") else []
        art=records[0] if records else {}
        self.std_preview.set_article(art)
        if not art:
            self.std_preview_title.setText("Vælg en artikel"); self.std_preview_specs.clear(); self.std_preview_meta.clear();
            if hasattr(self,"std_open_source"):self.std_open_source.setEnabled(False)
            if hasattr(self,"std_open_supplier"):self.std_open_supplier.setEnabled(False)
            if hasattr(self,"std_reload_image"):self.std_reload_image.setEnabled(False)
            if hasattr(self,"std_open_datasheet"):self.std_open_datasheet.setEnabled(False)
            if hasattr(self,"std_edit_price"):self.std_edit_price.setEnabled(False)
            return
        facets=core.article_filter_facets(art)
        self.std_preview_title.setText(f"{art.get('article_no','')} · {art.get('description','')}")
        tags=[facets.get('product_type',''),str(art.get('product_family','') or facets.get('product_family','')),str(art.get('product_variant','') or facets.get('product_variant','')),facets.get('module_size',''),facets.get('color','')]
        if art.get('diameter_mm'):tags.append(f"Ø{art['diameter_mm']} mm")
        if art.get('cct'):tags.append(str(art['cct']))
        if art.get('power_w'):tags.append(str(art['power_w']))
        tags=[x for x in tags if x]
        self.std_preview_specs.setText("<b>Specifikation:</b> "+" &nbsp; · &nbsp; ".join(tags))
        meta=[]
        meta.extend(_article_price_meta_lines(art,self.price_vat_mode))
        meta.append(_article_packaging_meta_line(art))
        if art.get('el_no'):meta.append(f"EL-/LM-nr. {art['el_no']}")
        if art.get('ean'):meta.append(f"EAN {art['ean']}")
        if art.get('series'):meta.append(str(art['series']))
        extra=[]
        if art.get('cutout_mm'):extra.append(f"udskæring Ø{art['cutout_mm']} mm")
        if art.get('ip_rating'):extra.append(str(art['ip_rating']))
        if art.get('environment'):extra.append(str(art['environment']))
        if extra:meta.append(" · ".join(extra))
        if art.get('image_source'):meta.append(f"Foto: {art['image_source']} (online/cache)")
        if art.get('status'):meta.append(str(art['status']))
        self.std_preview_meta.setText("\n".join(meta))
        has_source=bool(str(art.get('product_page','') or art.get('source','')).startswith(('http://','https://')))
        if hasattr(self,'std_open_source'):self.std_open_source.setEnabled(has_source)
        if hasattr(self,'std_open_supplier'):self.std_open_supplier.setEnabled(bool(str(art.get('supplier_page','')).startswith(('http://','https://'))))
        if hasattr(self,'std_reload_image'):self.std_reload_image.setEnabled(has_source or bool(art.get('image_url')))
        if hasattr(self,'std_open_datasheet'):self.std_open_datasheet.setEnabled(bool(str(art.get('datasheet_url','')).startswith(('http://','https://'))))
        if hasattr(self,'std_edit_price'):self.std_edit_price.setEnabled(True)

    def _rebuild_predefined_price_view(self):
        self.predefined=user_library.apply_article_prices(core.load_predefined_article_catalog(),self.price_book,assume_normalized=True,prices_normalized=True)
        self._predefined_enriched=build_article_search_index(self.predefined)
        self._invalidate_catalog_cache()

    def _edit_article_price(self,article):
        article_no=str(article.get("article_no","") or "").strip()
        if not article_no:return
        existing=deepcopy(self.price_book.get(article_no,{}))
        base_article=next((a for a in self.catalog if str(a.get("article_no","") or "")==article_no),None)
        if base_article is None:
            base_article=next((a for a in core.load_predefined_article_catalog() if str(a.get("article_no","") or "")==article_no),article)
        dlg=ArticlePriceDialog(self,base_article,existing,self.price_vat_mode)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        self._select_price_vat_mode(dlg.selected_vat_mode())
        rec=dlg.price_record()
        if rec is None:self.price_book.pop(article_no,None)
        else:self.price_book[article_no]=rec
        self._rebuild_predefined_price_view()
        self._invalidate_catalog_cache(); self._refresh_library_filters(); self._refresh_library(); self._refresh_article_picker(); self._refresh_cable_types(); self._refresh_bom()

    def _edit_standard_price(self):
        records=self._selected_standard_articles()
        if len(records)!=1:
            QMessageBox.information(self,"Pris","Vælg én artikel for at redigere pris/prisestimat."); return
        self._edit_article_price(records[0])

    def _edit_library_price(self):
        row=self._selected_library_row()
        if row<0 or row>=len(self.catalog):
            QMessageBox.information(self,"Pris","Vælg én artikel i databasen."); return
        priced={a["article_no"]:a for a in self._available_catalog()}
        art=priced.get(self.catalog[row].get("article_no"),self.catalog[row])
        self._edit_article_price(art)

    def _compare_library_prices(self):
        art=self._selected_library_article()
        article_no=str(art.get("article_no","") or "").strip()
        if not article_no:return
        record=deepcopy(self.price_book.get(article_no,{}) or {})
        if not record.get("price_observations"):record["price_observations"]=deepcopy(art.get("price_observations",[]) or [])
        dlg=PriceComparisonDialog(self,art,record,self.price_vat_mode)
        dlg.exec()
        self._select_price_vat_mode(dlg.selected_vat_mode())

    def _show_selected_article_usage(self):
        art=self._selected_library_article(); article_no=str(art.get("article_no","") or "").strip()
        if not article_no:return
        sources=[row for row in self._bom_source_data("") if str(row.get("article_no","") or "")==article_no]
        memberships=[]
        for assembly in core.normalize_bom_assemblies(self.assemblies):
            uses=self._assembly_usage_count(str(assembly.get("id","") or ""))
            for item in assembly.get("items",[]) or []:
                if str(item.get("article_no","") or "")!=article_no:continue
                memberships.append({
                    "assembly_name":assembly.get("name",""),"assembly_id":assembly.get("id",""),
                    "role":item.get("role",""),"qty":item.get("qty",1),
                    "optional":bool(item.get("optional",False)),
                    "included":bool(item.get("included",True)) if item.get("optional") else True,
                    "uses":uses,
                })
        ArticleUsageDialog(self,self.window,art,sources,memberships).exec()

    def _edit_article_relations(self):
        row=self._selected_library_row()
        if row<0 or row>=len(self.catalog):
            QMessageBox.information(self,"Relationer","Vælg én artikel i databasen."); return
        dlg=ArticleRelationsDialog(self,self.catalog[row],self.catalog)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        self.catalog[row]["relations"]=dlg.relations()
        self._refresh_all()

    def _open_standard_source(self):
        records=self._selected_standard_articles()
        art=records[0] if records else {}
        url=str(art.get('product_page','') or art.get('source','') or '').strip()
        if url.startswith(('http://','https://')):QDesktopServices.openUrl(QUrl(url))

    def _open_standard_supplier(self):
        records=self._selected_standard_articles()
        art=records[0] if records else {}
        url=str(art.get('supplier_page','') or '').strip()
        if url.startswith(('http://','https://')):QDesktopServices.openUrl(QUrl(url))

    def _open_standard_datasheet(self):
        records=self._selected_standard_articles()
        art=records[0] if records else {}
        url=str(art.get('datasheet_url','') or '').strip()
        if url.startswith(('http://','https://')):QDesktopServices.openUrl(QUrl(url))

    def _selected_standard_articles(self):
        rows=sorted({i.row() for i in self.std_table.selectedIndexes()})
        lookup={a.get("article_no"):a for a in self.predefined}
        records=[]
        for r in rows:
            no=self.std_table_model.article_no_at(r)
            if no in lookup: records.append(lookup[no])
        return records

    def _import_standard_records(self,records):
        # 0.45: artikelbasen er global kernedata og indeholder allerede alle
        # standardposter. Handlingen fungerer derfor som en eksplicit
        # "gendan fra medfølgende standard" i stedet for projekt-import.
        index={a["article_no"]:i for i,a in enumerate(self.catalog)}; changed=0
        for art in records:
            clean={k:deepcopy(v) for k,v in art.items() if not str(k).startswith("_")}
            no=clean.get("article_no","")
            if not no:continue
            if no in index:
                i=index[no]
                if self.catalog[i]!=clean:self.catalog[i]=clean; changed+=1
            else:
                index[no]=len(self.catalog); self.catalog.append(clean); changed+=1
        if changed:self._refresh_all()
        else:self._refresh_predefined()
        return changed

    def _import_selected_standard(self,*_):
        records=self._selected_standard_articles()
        if not records:return
        self._import_standard_records(records)

    def _import_all_visible_standard(self):
        if not self._predefined_visible:return
        self._import_standard_records(self._predefined_visible)

    @staticmethod
    def _article_no_from_combo(combo):
        text=str(combo.currentText() or "").strip()
        token=text.lstrip("★ ").split(" · ",1)[0].strip()
        if token:
            for i in range(combo.count()):
                if str(combo.itemData(i) or "")==token:
                    return token
        return str(combo.currentData() or "")

    # ---- styklister ----------------------------------------------------
    def _assembly_lookup(self):
        return {a["id"]:a for a in core.normalize_bom_assemblies(self.assemblies)}

    def _assembly_usage_count(self,assembly_id):
        return sum(1 for parts in self.assembly_bindings.values() for aid in parts.values() if aid==assembly_id)

    def _assembly_usage_placements(self,assembly_id):
        out=[]
        for puid,parts in self.assembly_bindings.items():
            if any(aid==assembly_id for aid in parts.values()) and puid not in out:out.append(puid)
        return out

    def _assembly_price_totals(self,assembly):
        lookup=self._catalog_lookup(); totals=defaultdict(float); priced=0; active=core.bom_assembly_effective_items(assembly)
        for row in active:
            art=lookup.get(str(row.get("article_no","") or ""),{})
            raw=art.get("effective_price",art.get("unit_price")); cur=str(art.get("price_currency","DKK") or "DKK").upper()
            if str(raw if raw is not None else "").strip()=="":continue
            try:price=float(raw); qty=float(row.get("qty",1) or 1)
            except (TypeError,ValueError):continue
            totals[cur]+=price*core.article_price_basis_quantity(art,qty); priced+=1
        return dict(totals),priced,len(active)

    def _refresh_assemblies(self,*_):
        if not hasattr(self,"assembly_table"):return
        selected=self._selected_assembly_id(); rows=core.normalize_bom_assemblies(self.assemblies)
        catalog_lookup=self._catalog_lookup()
        naming_by_id={a["id"]:assembly_naming.effective_naming_fields(a,catalog_lookup) for a in rows}

        def refill(combo, values, all_label):
            if combo is None:return
            current=str(combo.currentData() or "") if combo.count() else ""
            blocker=QSignalBlocker(combo); combo.clear(); combo.addItem(all_label,"")
            for value in sorted({str(v or "").strip() for v in values if str(v or "").strip()},key=str.casefold):combo.addItem(value,value)
            idx=combo.findData(current); combo.setCurrentIndex(idx if idx>=0 else 0); del blocker

        refill(getattr(self,"assembly_category_filter",None),(a.get("category","") for a in rows),"Alle kategorier")
        field_filters=(
            ("product_type","assembly_type_filter","Alle typer"),
            ("configuration","assembly_configuration_filter","Alle opbygninger"),
            ("function","assembly_function_filter","Alle funktioner"),
            ("system_series","assembly_system_filter","Alle systemer/serier"),
            ("mounting","assembly_mounting_filter","Alle monteringer"),
            ("color","assembly_color_filter","Alle farver"),
        )
        for key,attr,label in field_filters:
            refill(getattr(self,attr,None),(naming_by_id[a["id"]].get(key,"") for a in rows),label)

        query=self.assembly_search.text().strip().casefold() if hasattr(self,"assembly_search") else ""
        category=str(self.assembly_category_filter.currentData() or "") if hasattr(self,"assembly_category_filter") and self.assembly_category_filter.count() else ""
        wanted={key:str(getattr(self,attr).currentData() or "") if hasattr(self,attr) and getattr(self,attr).count() else "" for key,attr,_ in field_filters}
        used_only=bool(self.assembly_used_only.isChecked()) if hasattr(self,"assembly_used_only") else False
        visible=[]
        for assembly in rows:
            used=self._assembly_usage_count(assembly["id"]); naming=naming_by_id[assembly["id"]]
            if used_only and not used:continue
            if category and str(assembly.get("category","") or "")!=category:continue
            if any(value and str(naming.get(key,"") or "")!=value for key,value in wanted.items()):continue
            if query:
                item_nos=" ".join(str(x.get("article_no","") or "") for x in assembly.get("items",[]) or [])
                naming_text=" ".join(str(naming.get(k,"") or "") for k in assembly_naming.NAMING_KEYS)
                blob=" ".join((assembly.get("name",""),naming_text,assembly.get("description",""),assembly.get("category",""),assembly.get("variant","")," ".join(assembly.get("tags",[]) or []),item_nos)).casefold()
                if query not in blob:continue
            visible.append(assembly)

        header=self.assembly_table.horizontalHeader(); sort_col=header.sortIndicatorSection(); sort_order=header.sortIndicatorOrder()
        was_sorting=self.assembly_table.isSortingEnabled(); self.assembly_table.setSortingEnabled(False)
        self.assembly_table.setRowCount(len(visible))
        for r,assembly in enumerate(visible):
            naming=naming_by_id[assembly["id"]]
            counts=core.bom_assembly_item_counts(assembly); totals,priced,active=self._assembly_price_totals(assembly)
            price=" · ".join(self._fmt_display_price(v,k) for k,v in sorted(totals.items())) if totals else "—"
            comp=f"{active}/{counts['total']} aktive" if counts["optional"] else str(active)
            if counts["optional"]:comp+=f" · {counts['optional']} valgfri"
            vals=(
                assembly["name"],naming.get("product_type",""),naming.get("configuration",""),naming.get("function",""),naming.get("system_series",""),
                naming.get("mounting",""),naming.get("color",""),assembly.get("category",""),comp,str(self._assembly_usage_count(assembly["id"])),price,assembly.get("description","")
            )
            for c,val in enumerate(vals):self.assembly_table.setItem(r,c,_table_item(val,assembly["id"] if c==0 else None))
        self.assembly_table.setSortingEnabled(was_sorting)
        if was_sorting and 0<=sort_col<self.assembly_table.columnCount():self.assembly_table.sortItems(sort_col,sort_order)

        restore=-1
        for r in range(self.assembly_table.rowCount()):
            item=self.assembly_table.item(r,0)
            if item and str(item.data(Qt.ItemDataRole.UserRole) or "")==selected:restore=r; break
        if self.assembly_table.rowCount():self.assembly_table.selectRow(restore if restore>=0 else 0)
        else:self.assembly_summary.setText("Ingen styklister matcher de aktuelle filtre.") if hasattr(self,"assembly_summary") else None

    def _selected_assembly_id(self):
        if not hasattr(self,"assembly_table") or not self.assembly_table.selectedItems():return ""
        item=self.assembly_table.item(self.assembly_table.currentRow(),0)
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def _assembly_selection_changed(self):
        if not hasattr(self,"assembly_summary"):return
        aid=self._selected_assembly_id(); assembly=self._assembly_lookup().get(aid)
        if not assembly:self.assembly_summary.setText("Vælg en stykliste for at se anvendelser og indhold."); return
        counts=core.bom_assembly_item_counts(assembly); used=self._assembly_usage_count(aid); totals,priced,active=self._assembly_price_totals(assembly)
        price=" · ".join(self._fmt_display_price(v,k) for k,v in sorted(totals.items())) if totals else "—"
        tags=(" · Tags: "+", ".join(assembly.get("tags",[]) or [])) if assembly.get("tags") else ""
        params=assembly_naming.naming_summary(assembly_naming.effective_naming_fields(assembly,self._catalog_lookup()))
        param_text=(" · "+params) if params else ""
        opt=f" · {counts['included_optional']}/{counts['optional']} valgfrie aktive" if counts["optional"] else ""
        self.assembly_summary.setText(f"{active} aktive komponenter{opt} · brugt {used} gang(e) i aktuelt projekt · styklistepris {price} · pris på {priced}/{active}{param_text}{tags}")

    def _show_selected_assembly_on_plan(self):
        aid=self._selected_assembly_id()
        if not aid:return
        puids=self._assembly_usage_placements(aid)
        if not puids:
            QMessageBox.information(self,"Stykliste","Den valgte stykliste bruges ikke i det aktuelle projekt."); return
        if hasattr(self.window,"_select_scene_objects"):
            self.window._select_scene_objects(puids,[],True)
            if hasattr(self.window,"_notify"):self.window._notify(f"Stykliste: {len(puids)} forekomst(er) vist på plantegningen.",kind="info")

    def _ensure_assembly_articles(self,assembly):
        for row in assembly.get("items",[]) or []:
            self._ensure_project_article(row.get("article_no",""))

    def _new_assembly(self):
        dlg=AssemblyEditDialog(self,self._available_catalog(),vat_mode=self.price_vat_mode)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        rec=dlg.record(); self._ensure_assembly_articles(rec); self.assemblies.append(rec); self._refresh_all()
        for r in range(self.assembly_table.rowCount()):
            if self.assembly_table.item(r,0).data(Qt.ItemDataRole.UserRole)==rec["id"]:self.assembly_table.selectRow(r); break

    def _edit_assembly(self,*_):
        assembly_id=self._selected_assembly_id(); lookup=self._assembly_lookup(); old=lookup.get(assembly_id)
        if not old:return
        dlg=AssemblyEditDialog(self,self._available_catalog(),old,self.price_vat_mode)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        rec=dlg.record(); self._ensure_assembly_articles(rec)
        for i,a in enumerate(self.assemblies):
            if a.get("id")==assembly_id:self.assemblies[i]=rec; break
        self._refresh_all()

    def _duplicate_assembly(self):
        assembly_id=self._selected_assembly_id(); old=self._assembly_lookup().get(assembly_id)
        if not old:return
        rec=deepcopy(old); rec["id"]=uuid.uuid4().hex; rec["name"]=str(rec.get("name","") or "Stykliste")+" (kopi)"
        self.assemblies.append(rec); self._refresh_all()

    def _delete_assembly(self):
        assembly_id=self._selected_assembly_id(); old=self._assembly_lookup().get(assembly_id)
        if not old:return
        used=self._assembly_usage_count(assembly_id)
        msg=f"Slet den globale stykliste ‘{old.get('name','')}’?\n\nDen fjernes også fra styklistevælgeren i andre projekter på denne PC."
        if used:msg += f"\n\nDen bruges på {used} symboldel(e) i det aktuelle projekt. Disse skifter tilbage til deres manuelle konfiguration."
        if QMessageBox.question(self,"Slet stykliste",msg)!=QMessageBox.StandardButton.Yes:return
        self.assemblies=[a for a in self.assemblies if a.get("id")!=assembly_id]
        for symbol,parts in list(self.assembly_bindings.items()):
            self.assembly_bindings[symbol]={pid:aid for pid,aid in parts.items() if aid!=assembly_id}
            if not self.assembly_bindings[symbol]:self.assembly_bindings.pop(symbol,None)
        self._refresh_all()

    def _refresh_assembly_picker(self):
        if not hasattr(self,"assembly_picker"):return
        placement_uid=self._current_placement_uid(); part_id=self._current_part()
        active=self.assembly_bindings.get(placement_uid,{}).get(part_id,"")
        current=str(self.assembly_picker.currentData() or "") if self.assembly_picker.count() else active
        blocker=QSignalBlocker(self.assembly_picker); self.assembly_picker.clear()
        for assembly in sorted(self.assemblies,key=lambda a:str(a.get("name","")).casefold()):
            counts=core.bom_assembly_item_counts(assembly); meta=" · ".join(x for x in (str(assembly.get("category","") or ""),str(assembly.get("variant","") or "")) if x)
            label=f"{assembly.get('name','')} · {counts['active']} aktive"
            if counts["optional"]:label+=f"/{counts['total']}"
            if meta:label+=f" · {meta}"
            self.assembly_picker.addItem(label,assembly["id"])
        target=active or current; idx=self.assembly_picker.findData(target); self.assembly_picker.setCurrentIndex(idx if idx>=0 else (0 if self.assembly_picker.count() else -1)); del blocker
        self._part_changed()

    def _create_assembly_from_manual(self):
        placement_uid=self._current_placement_uid(); symbol=self._current_symbol(); part_id=self._current_part()
        rows=deepcopy(self.bindings.get(placement_uid,{}).get(part_id,[]))
        if not rows:
            QMessageBox.information(self,"Stykliste","Den valgte del har ingen manuel artikelkonfiguration at gemme."); return
        part_label=self.part_list.currentItem().text().split('  ·  ',1)[0] if self.part_list.currentItem() else 'del'
        default=f"{core.symbol_display_name(symbol)} · {part_label}"
        name,ok=QInputDialog.getText(self,"Gem manuel som stykliste","Navn på stykliste",QLineEdit.EchoMode.Normal,default)
        if not ok or not str(name).strip():return
        rec={"id":uuid.uuid4().hex,"name":str(name).strip(),"description":"Oprettet fra manuel symbolkonfiguration","category":core.symbol_display_name(symbol),"variant":part_label,"tags":["oprettet fra symbol"],"items":rows}
        self._ensure_assembly_articles(rec); self.assemblies.append(rec)
        self.assembly_bindings.setdefault(placement_uid,{})[part_id]=rec["id"]
        self._refresh_all()

    def _apply_assembly(self):
        placement_uid=self._current_placement_uid(); symbol=self._current_symbol(); part_id=self._current_part(); assembly_id=str(self.assembly_picker.currentData() or "")
        if not (placement_uid and symbol and part_id and assembly_id):return
        assembly=self._assembly_lookup().get(assembly_id)
        if assembly is None:return
        self._ensure_assembly_articles(assembly)
        self.assembly_bindings.setdefault(placement_uid,{})[part_id]=assembly_id
        self._symbol_changed(); self._refresh_assemblies(); self._refresh_bom()

    def _use_manual_binding(self):
        placement_uid=self._current_placement_uid(); part_id=self._current_part()
        if not (placement_uid and part_id):return
        self.assembly_bindings.get(placement_uid,{}).pop(part_id,None)
        if not self.assembly_bindings.get(placement_uid,{}):self.assembly_bindings.pop(placement_uid,None)
        self._symbol_changed(); self._refresh_assemblies(); self._refresh_bom()

    def _refresh_symbol_combo(self):
        current=self.symbol_combo.currentData() if self.symbol_combo.count() else self.focus_uid
        supported=[p for p in self.window.project.placements if core.bom_supported_symbol(p.symbol)]
        totals=defaultdict(int)
        for p in supported: totals[p.symbol]+=1
        seen=defaultdict(int)
        blocker=QSignalBlocker(self.symbol_combo); self.symbol_combo.clear()
        for p in supported:
            seen[p.symbol]+=1
            ident=str(getattr(p,"group","") or getattr(p,"label","") or "").strip()
            where=f" · {ident}" if ident else ""
            occurrence=f" · {seen[p.symbol]}/{totals[p.symbol]}" if totals[p.symbol]>1 else ""
            self.symbol_combo.addItem(f"{core.symbol_display_name(p.symbol)}{where}{occurrence}",p.uid)
        target=self.focus_uid if any(p.uid==self.focus_uid for p in supported) else current
        idx=self.symbol_combo.findData(target); self.symbol_combo.setCurrentIndex(idx if idx>=0 else (0 if self.symbol_combo.count() else -1)); del blocker
        self._symbol_changed()

    def _current_placement_uid(self):
        return str(self.symbol_combo.currentData() or "") if self.symbol_combo.currentIndex()>=0 else ""

    def _current_placement(self):
        uid=self._current_placement_uid()
        return next((p for p in self.window.project.placements if str(getattr(p,"uid","") or "")==uid),None)

    def _current_symbol(self):
        placement=self._current_placement()
        return str(getattr(placement,"symbol","") or "") if placement is not None else ""

    def _current_part(self):
        item=self.part_list.currentItem(); return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def _symbol_changed(self,*_):
        placement_uid=self._current_placement_uid(); symbol=self._current_symbol(); parts=core.bom_symbol_parts(symbol)
        current=self._current_part(); blocker=QSignalBlocker(self.part_list); self.part_list.clear()
        sb=self.bindings.get(placement_uid,{})
        sab=self.assembly_bindings.get(placement_uid,{})
        assembly_lookup=self._assembly_lookup()
        for part in parts:
            aid=sab.get(part["id"],"")
            assembly=assembly_lookup.get(aid)
            if assembly is not None:
                suffix=f"  ·  📋 {assembly.get('name','Stykliste')}"
            else:
                n=len(sb.get(part["id"],[])); suffix=f"  ·  {n} artikel" + ("er" if n!=1 else "") if n else ""
            item=QListWidgetItem(part["label"]+suffix); item.setData(Qt.ItemDataRole.UserRole,part["id"]); item.setData(Qt.ItemDataRole.UserRole+1,bool(part.get("required",True))); self.part_list.addItem(item)
        row=next((i for i in range(self.part_list.count()) if self.part_list.item(i).data(Qt.ItemDataRole.UserRole)==current),0)
        if self.part_list.count(): self.part_list.setCurrentRow(row)
        del blocker; self._part_changed()

    def _part_changed(self,*_):
        placement_uid=self._current_placement_uid(); symbol=self._current_symbol(); part_id=self._current_part(); lookup=self._catalog_lookup()
        manual_rows=self.bindings.get(placement_uid,{}).get(part_id,[])
        assembly_id=self.assembly_bindings.get(placement_uid,{}).get(part_id,"")
        assembly=self._assembly_lookup().get(assembly_id) if assembly_id else None
        rows=assembly.get("items",[]) if assembly is not None else manual_rows
        self.assignment_table.setRowCount(len(rows))
        for r,b in enumerate(rows):
            art=lookup.get(b["article_no"],{})
            self.assignment_table.setItem(r,0,_table_item(b["article_no"]))
            self.assignment_table.setItem(r,1,_table_item(art.get("description","") or ""))
            self.assignment_table.setItem(r,2,_table_item(self._fmt_qty(b.get("qty",1))))
        if hasattr(self,"assembly_picker"):
            blocker=QSignalBlocker(self.assembly_picker)
            idx=self.assembly_picker.findData(assembly_id)
            if idx>=0:self.assembly_picker.setCurrentIndex(idx)
            del blocker
        if assembly is not None:
            self.assignment_source.setText(f"Stykliste: {assembly.get('name','')}")
        else:
            self.assignment_source.setText("Manuel konfiguration")
        current_item=self.part_list.currentItem(); required=bool(current_item.data(Qt.ItemDataRole.UserRole+1)) if current_item else True
        note="Obligatorisk BOM-del · gælder kun dette symbol" if required else "Valgfri fællesdel · gælder kun dette symbol – brug fx til ramme, dåse eller fælles tilbehør."
        if assembly is not None and manual_rows:note += f" · {len(manual_rows)} manuel(le) artikelrække(r) er gemt og bliver aktive igen ved ‘Brug manuel’."
        self.part_note.setText(note)
        manual=assembly is None
        enabled=bool(placement_uid and symbol and part_id and self.article_picker.count() and manual)
        self.assign_add.setEnabled(enabled); self.article_picker.setEnabled(enabled); self.assignment_qty.setEnabled(manual); self.assignment_new.setEnabled(manual)
        self.assignment_remove.setEnabled(bool(manual_rows) and manual)
        self.assignment_new.setEnabled(bool(placement_uid and symbol and part_id and manual))
        self.assembly_from_manual.setEnabled(bool(placement_uid and symbol and part_id and manual_rows))
        self.assembly_apply.setEnabled(bool(placement_uid and symbol and part_id and self.assembly_picker.count()))
        self.assembly_manual.setEnabled(bool(assembly is not None))
        self._refresh_assignment_target_ui()

    def _placement_caption(self, placement=None):
        placement=placement or self._current_placement()
        if placement is None:return ""
        name=core.symbol_display_name(str(getattr(placement,"symbol","") or ""))
        group=str(getattr(placement,"group","") or "").strip(); label=str(getattr(placement,"label","") or "").strip()
        ident=" · ".join(x for x in (group,label) if x)
        return name+(f" · {ident}" if ident else "")

    def _current_part_label(self):
        item=self.part_list.currentItem() if hasattr(self,"part_list") else None
        if item is None:return ""
        text=str(item.text() or "")
        return text.split("  ·  ",1)[0].strip()

    def _refresh_assignment_target_ui(self):
        placement_uid=self._current_placement_uid(); part_id=self._current_part(); part_label=self._current_part_label(); caption=self._placement_caption()
        ready=bool(placement_uid and part_id)
        title=(f"{caption}  →  {part_label}" if ready else "Vælg symbol og fysisk del")
        hint=("Dobbeltklik en artikel i Artikeldatabasen for at tilknytte den direkte til denne del." if ready else "Artikler tilknyttes kun den valgte fysiske forekomst.")
        if hasattr(self,"assignment_target_title"):self.assignment_target_title.setText(title)
        if hasattr(self,"assignment_target_hint"):self.assignment_target_hint.setText(hint)
        if hasattr(self,"assignment_find_article"):self.assignment_find_article.setEnabled(ready)
        if hasattr(self,"library_target_title"):self.library_target_title.setText(("Tilknytter til: "+title) if ready else "Ingen tilknytningsdestination valgt")
        if hasattr(self,"library_target_hint"):self.library_target_hint.setText(("Dobbeltklik en artikel eller brug ‘Tilknyt valgt artikel’." if ready else "Vælg symbol og fysisk del under Tilknytning."))
        if hasattr(self,"library_assign_button"):
            art=self._selected_library_article() if hasattr(self,"library_table") else {}
            self.library_assign_button.setEnabled(bool(ready and art and str(art.get("kind","") or "")!="cable"))
        if hasattr(self,"library_assignment_qty") and hasattr(self,"assignment_qty"):
            blocker=QSignalBlocker(self.library_assignment_qty); self.library_assignment_qty.setValue(self.assignment_qty.value()); del blocker

    def _open_library_for_assignment(self):
        if not (self._current_placement_uid() and self._current_part()):return
        self._refresh_assignment_target_ui()
        self.tabs.setCurrentWidget(self.library_tab)
        self.library_assignment_status.setText("")
        self.library_search.setFocus(); self.library_search.selectAll()

    def _set_library_assignment_status(self, text: str, *, warning: bool=False):
        if not hasattr(self,"library_assignment_status"):return
        self.library_assignment_status.setObjectName("warningText" if warning else "positiveText")
        self.library_assignment_status.setText(str(text or ""))
        try:self.library_assignment_status.style().unpolish(self.library_assignment_status); self.library_assignment_status.style().polish(self.library_assignment_status)
        except Exception:pass

    def _assign_article_to_current_part(self, article_no: str, qty=None) -> bool:
        placement_uid=self._current_placement_uid(); symbol=self._current_symbol(); part_id=self._current_part()
        article_no=str(article_no or "").strip()
        if not (placement_uid and symbol and part_id and article_no):
            self._set_library_assignment_status("Vælg først symbol og fysisk del under Tilknytning.",warning=True); return False
        art=self._catalog_lookup().get(article_no,{})
        if str(art.get("kind","") or "") == "cable":
            self._set_library_assignment_status("Denne post er en kabelartikel. Tilknyt den under fanen Kabler.",warning=True); return False
        assembly_id=self.assembly_bindings.get(placement_uid,{}).get(part_id,"")
        if assembly_id:
            assembly=self._assembly_lookup().get(assembly_id,{})
            answer=QMessageBox.question(
                self,"Skift til manuel artikeltilknytning",
                f"Den valgte del bruger stykliste ‘{assembly.get('name','Stykliste')}’.\n\nSkift delen til manuel konfiguration og tilknyt {article_no}?",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.Yes)
            if answer!=QMessageBox.StandardButton.Yes:return False
            self.assembly_bindings.get(placement_uid,{}).pop(part_id,None)
            if not self.assembly_bindings.get(placement_uid,{}):self.assembly_bindings.pop(placement_uid,None)
        self._ensure_project_article(article_no)
        amount=float(qty if qty is not None else self.assignment_qty.value())
        rows=self.bindings.setdefault(placement_uid,{}).setdefault(part_id,[])
        existing=next((b for b in rows if b.get("article_no")==article_no),None)
        if existing:existing["qty"]=amount
        else:rows.append({"article_no":article_no,"qty":amount})
        self._remember_recent_article(article_no); self._project_article_cache=None
        self._symbol_changed(); self._refresh_bom(); self._refresh_library()
        desc=str(art.get("description","") or "").strip()
        target=f"{self._placement_caption()} / {self._current_part_label()}"
        self._set_library_assignment_status(f"✓ {article_no}"+(f" · {desc}" if desc else "")+f" tilknyttet til {target}.")
        return True

    def _assign_selected_library_article(self,*_):
        art=self._selected_library_article()
        if not art:
            self._set_library_assignment_status("Vælg en artikel i tabellen først.",warning=True); return
        qty=self.library_assignment_qty.value() if hasattr(self,"library_assignment_qty") else self.assignment_qty.value()
        if self._assign_article_to_current_part(str(art.get("article_no","") or ""),qty):
            if hasattr(self,"assignment_qty"):self.assignment_qty.setValue(qty)

    def _refresh_article_picker(self):
        current=self.article_picker.currentData() if self.article_picker.count() else ""
        blocker=QSignalBlocker(self.article_picker); self.article_picker.clear()
        for art in self._available_catalog():
            if str(art.get("kind","") or "") == "cable":continue
            prefix="" if any(a["article_no"]==art["article_no"] for a in self.catalog) else "★ "
            text=prefix+art["article_no"] + (f" · {art['description']}" if art.get("description") else "")
            self.article_picker.addItem(text,art["article_no"])
        idx=self.article_picker.findData(current); self.article_picker.setCurrentIndex(idx if idx>=0 else (0 if self.article_picker.count() else -1)); del blocker
        self._part_changed()

    def _add_binding(self):
        article_no=self._article_no_from_combo(self.article_picker)
        if article_no:self._assign_article_to_current_part(article_no,self.assignment_qty.value())

    def _remove_binding(self):
        placement_uid=self._current_placement_uid(); part_id=self._current_part(); rows_sel=sorted({i.row() for i in self.assignment_table.selectedIndexes()},reverse=True)
        rows=self.bindings.get(placement_uid,{}).get(part_id,[])
        for r in rows_sel:
            if 0<=r<len(rows):rows.pop(r)
        if not rows:
            self.bindings.get(placement_uid,{}).pop(part_id,None)
            if not self.bindings.get(placement_uid,{}):self.bindings.pop(placement_uid,None)
        self._symbol_changed(); self._refresh_bom()

    def _refresh_library(self,*_):
        if not hasattr(self,"library_table"):return
        self._library_search_timer.stop()
        selected_rows=sorted({i.row() for i in self.library_table.selectedIndexes()})
        selected_no=self.library_table_model.article_no_at(selected_rows[0]) if selected_rows else ""
        query=self.library_search.text().strip() if hasattr(self,"library_search") else ""
        favorite=set(self._favorite_article_nos); recent_rank={no:i for i,no in enumerate(self._recent_article_nos)}; project=self._project_article_nos()
        visible=[]
        for art in self._library_base_candidates(include_query=False):
            no=str(art.get("article_no","") or "")
            score=article_search_score(art,query,favorite=no in favorite,recent_rank=recent_rank.get(no),project=no in project)
            if score is None:continue
            row=dict(art); row["_search_score"]=score; row["_favorite_mark"]="★" if no in favorite else ""
            visible.append(row)
        # Free-text search is relevance-ranked. Without a query, favorites/project/recent
        # still get a small productivity boost while the stable catalogue order breaks ties.
        visible.sort(key=lambda a:(-float(a.get("_search_score",0) or 0),str(a.get("manufacturer","") or "").casefold(),str(a.get("category_normalized","") or "").casefold(),str(a.get("article_no","") or "").casefold()))
        self.library_table_model.set_rows(visible)
        self.library_table.clearSelection()
        restore=self.library_table_model.row_for_article_no(selected_no)
        if self.library_table_model.rowCount():self.library_table.selectRow(restore if restore>=0 else 0)
        else:self._library_selection_changed()
        scope=str(self.lib_scope.currentData() or "") if hasattr(self,"lib_scope") else ""
        scope_labels={"favorites":f"{len(self._favorite_article_nos)} favoritter","recent":f"{len(self._recent_article_nos)} senest anvendte","project":f"{len(project)} projektartikler","quality":"artikler med datakvalitetsfund"}
        if hasattr(self,"library_scope_hint"):self.library_scope_hint.setText(scope_labels.get(scope,"Facetterne viser kun valg, der fortsat kan give resultater."))
        self.library_count.setText(f"{len(visible)} vist · {len(self.catalog)} artikler i databasen")

    def _show_article_import_guide(self):
        ArticleImportGuideDialog(self).exec()

    def _import_article_library(self):
        path,_=QFileDialog.getOpenFileName(
            self,"Importér artikelbibliotek","",
            "Artikelbibliotek (*.json *.csv);;JSON (*.json);;CSV (*.csv);;Alle filer (*.*)"
        )
        if not path:return
        try:
            bundle=article_exchange.load_article_library(path)
        except Exception as exc:
            QMessageBox.critical(self,"Importér artikelbibliotek",f"Biblioteket kunne ikke læses:\n\n{exc}")
            return
        if not bundle.articles:
            QMessageBox.warning(self,"Importér artikelbibliotek","Filen indeholder ingen gyldige artikler med artikelnummer.")
            return
        box=QMessageBox(self); box.setWindowTitle("Importér artikelbibliotek"); box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"{len(bundle.articles)} gyldige artikler fundet i {bundle.source_format}-filen.")
        box.setInformativeText(
            "Flet sikkert tilføjer nye artikler og udfylder kun tomme felter på eksisterende artikler.\n\n"
            "Opdatér eksisterende lader ikke-tomme værdier fra importfilen erstatte eksisterende artikelmetadata. "
            "Prisbog og projektets konkrete artikeltilknytninger ændres ikke. Importen gemmes straks som kernedata."
        )
        merge_btn=box.addButton("Flet sikkert",QMessageBox.ButtonRole.AcceptRole)
        overwrite_btn=box.addButton("Opdatér eksisterende",QMessageBox.ButtonRole.ActionRole)
        cancel_btn=box.addButton(QMessageBox.StandardButton.Cancel); box.setDefaultButton(merge_btn); box.exec()
        clicked=box.clickedButton()
        if clicked is cancel_btn or clicked not in (merge_btn,overwrite_btn):return
        mode="overwrite" if clicked is overwrite_btn else "fill_missing"
        try:
            backup=user_library.backup_core_article_catalog("before_library_import")
            merged,stats=article_exchange.merge_article_catalog(self.catalog,bundle.articles,mode=mode)
            user_library.save_core_article_catalog(merged)
            self.catalog=deepcopy(merged); self._refresh_all()
        except Exception as exc:
            QMessageBox.critical(self,"Importér artikelbibliotek",f"Importen kunne ikke gennemføres:\n\n{exc}")
            return
        QMessageBox.information(
            self,"Artikelbibliotek importeret",
            f"Import færdig.\n\nNye: {stats['added']}\nOpdaterede: {stats['updated']}\n"
            f"Uændrede: {stats['unchanged']}\n\nBackup af artikelbasen:\n{backup}"
        )

    def _export_article_library(self):
        default=str(user_library.core_data_dir()/"artikelbibliotek.json")
        path,selected=QFileDialog.getSaveFileName(
            self,"Eksportér artikelbibliotek",default,
            "Elplan JSON artikelbibliotek (*.json);;CSV til Excel (*.csv)"
        )
        if not path:return
        target=Path(path)
        try:
            if selected.startswith("CSV") or target.suffix.casefold()==".csv":
                if target.suffix.casefold()!=".csv":target=target.with_suffix(".csv")
                article_exchange.save_article_library_csv(target,self.catalog)
            else:
                if target.suffix.casefold()!=".json":target=target.with_suffix(".json")
                article_exchange.save_article_library_json(target,self.catalog,app_version=APP_VERSION)
        except Exception as exc:
            QMessageBox.critical(self,"Eksportér artikelbibliotek",f"Biblioteket kunne ikke eksporteres:\n\n{exc}")
            return
        QMessageBox.information(self,"Eksportér artikelbibliotek",f"{len(self.catalog)} artikler eksporteret til:\n\n{target}")

    def _new_article(self):
        dlg=ArticleEditDialog(self)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        rec=dlg.record()
        if any(a["article_no"].lower()==rec["article_no"].lower() for a in self.catalog):
            QMessageBox.warning(self,"Artikel","Artikelnummeret findes allerede i artikelbasen."); return
        self.catalog.append(rec); self._refresh_all()

    def _new_article_from_assignment(self):
        before={a["article_no"] for a in self.catalog}; self._new_article(); after=[a["article_no"] for a in self.catalog if a["article_no"] not in before]
        if after:
            idx=self.article_picker.findData(after[-1]);
            if idx>=0:self.article_picker.setCurrentIndex(idx)

    def _selected_library_row(self):
        rows=sorted({i.row() for i in self.library_table.selectedIndexes()})
        if len(rows)!=1:return -1
        article_no=self.library_table_model.article_no_at(rows[0])
        return next((i for i,a in enumerate(self.catalog) if str(a.get("article_no","") or "")==article_no),-1)

    def _edit_article(self,*_):
        row=self._selected_library_row()
        if row<0 or row>=len(self.catalog):return
        old=deepcopy(self.catalog[row]); dlg=ArticleEditDialog(self,old)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        rec=dlg.record()
        if rec["article_no"].lower()!=old["article_no"].lower() and any(a["article_no"].lower()==rec["article_no"].lower() for i,a in enumerate(self.catalog) if i!=row):
            QMessageBox.warning(self,"Artikel","Artikelnummeret findes allerede."); return
        self.catalog[row]=rec
        if rec["article_no"]!=old["article_no"]:
            if old["article_no"] in self.price_book:
                self.price_book[rec["article_no"]]=self.price_book.pop(old["article_no"])
            for parts in self.bindings.values():
                for rows in parts.values():
                    for binding in rows:
                        if binding.get("article_no")==old["article_no"]:binding["article_no"]=rec["article_no"]
            for assembly in self.assemblies:
                for item in assembly.get("items",[]) or []:
                    if item.get("article_no")==old["article_no"]:item["article_no"]=rec["article_no"]
            for key,value in list(self.cable_bindings.items()):
                if value==old["article_no"]:self.cable_bindings[key]=rec["article_no"]
            # Relation targets use article numbers as stable references too.
            for article in self.catalog:
                relations=article.get("relations",[]) if isinstance(article.get("relations"),list) else []
                for relation in relations:
                    if isinstance(relation,dict) and str(relation.get("target_article_no","") or "")==old["article_no"]:
                        relation["target_article_no"]=rec["article_no"]
        self._refresh_all()

    def _delete_article(self):
        row=self._selected_library_row()
        if row<0 or row>=len(self.catalog):return
        art=self.catalog[row]
        standard_nos={a.get("article_no") for a in core.load_predefined_article_catalog()}
        if art.get("article_no") in standard_nos:
            QMessageBox.information(self,"Artikeldatabase","Denne artikel følger med programmets indbyggede basisdata og kan derfor ikke slettes permanent. Du kan redigere den direkte i Artikeldatabase.")
            return
        symbol_used=sum(1 for parts in self.bindings.values() for rows in parts.values() for b in rows if b.get("article_no")==art["article_no"])
        assembly_used=sum(1 for assembly in self.assemblies for b in assembly.get("items",[]) if b.get("article_no")==art["article_no"])
        cable_used=sum(1 for a in self.cable_bindings.values() if a==art["article_no"])
        used=symbol_used+assembly_used+cable_used
        text=f"Slet artikel {art['article_no']} fra artikelbasen?" + (f"\n\nDen bruges i {used} tilknytning(er), som også fjernes." if used else "")
        if QMessageBox.question(self,"Slet artikel",text)!=QMessageBox.StandardButton.Yes:return
        self.catalog.pop(row)
        for symbol,parts in list(self.bindings.items()):
            for part_id,rows in list(parts.items()):
                parts[part_id]=[b for b in rows if b.get("article_no")!=art["article_no"]]
                if not parts[part_id]:parts.pop(part_id,None)
            if not parts:self.bindings.pop(symbol,None)
        for assembly in self.assemblies:
            assembly["items"]=[b for b in assembly.get("items",[]) if b.get("article_no")!=art["article_no"]]
        self.cable_bindings={k:v for k,v in self.cable_bindings.items() if v!=art["article_no"]}
        # Do not leave broken confirmed relations after an explicit deletion.
        for article in self.catalog:
            if isinstance(article.get("relations"),list):
                article["relations"]=[r for r in article["relations"] if not (isinstance(r,dict) and str(r.get("target_article_no","") or "")==art["article_no"])]
        self._refresh_all()

    # ---- kabler --------------------------------------------------------
    def _cable_entries(self):
        factor,_desc=self.window._length_scale_info(); reserve=self.window._length_reserve_percent()
        entries=[]
        placement_by_uid={str(p.uid):p for p in (self.window.project.placements or [])}
        for index,cable in enumerate(self.window.project.cables,start=1):
            layer=str(getattr(cable,"layer",core.CABLE_LAYER) or core.CABLE_LAYER)
            spec=str(getattr(cable,"cable_spec","") or "").strip()
            circuit=str(getattr(cable,"circuit_id","") or "").strip()
            endpoint_names=[]
            for conn in core.cable_symbol_connections(cable):
                p=placement_by_uid.get(str(conn.get("symbol_uid","") or ""))
                if p is None:continue
                ident=" · ".join(x for x in (str(getattr(p,"group","") or "").strip(),str(getattr(p,"label","") or "").strip()) if x)
                endpoint_names.append(ident or core.symbol_display_name(str(getattr(p,"symbol","") or "")))
            endpoints=" → ".join(endpoint_names) or "frie ender"
            length=core.cable_estimated_length_metres(cable,factor,reserve) if factor is not None else None
            entries.append({"uid":str(getattr(cable,"uid","") or ""),"index":index,"cable":cable,"layer":layer,"spec":spec,"circuit":circuit,"endpoints":endpoints,"length":length})
        return entries

    def _refresh_cable_types(self):
        if not hasattr(self,"cable_type_list"):return
        current=self._current_cable_uid()
        entries=self._cable_entries(); self._cable_keys=[e["uid"] for e in entries]
        blocker=QSignalBlocker(self.cable_type_list); self.cable_type_list.clear()
        for e in entries:
            cable=e["cable"]
            ident=str(getattr(cable,"cable_id","") or "").strip() or f"Kabel {e['index']}"
            length=(f"{e['length']:.1f} m inkl. reserve".replace(".",",")) if e["length"] is not None else "skala mangler"
            text=f"{ident} · {e['circuit'] or 'uden gruppe'} · {e['endpoints']} · {e['spec'] or 'uden spec'} · {length}"
            item=QListWidgetItem(text); item.setData(Qt.ItemDataRole.UserRole,e["uid"]); self.cable_type_list.addItem(item)
        row=next((i for i in range(self.cable_type_list.count()) if self.cable_type_list.item(i).data(Qt.ItemDataRole.UserRole)==current),0)
        if self.cable_type_list.count():self.cable_type_list.setCurrentRow(row)
        del blocker; self._cable_type_changed()

    def _current_cable_uid(self):
        if not hasattr(self,"cable_type_list"):return ""
        item=self.cable_type_list.currentItem(); return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def _cable_type_changed(self,*_):
        uid=self._current_cable_uid()
        entry=next((e for e in self._cable_entries() if e["uid"]==uid),None)
        if not entry:
            self.cable_summary.setText("Intet kabelstræk valgt"); self.cable_current_article.setText("–"); self.cable_article_picker.clear(); self.cable_assign.setEnabled(False); self.cable_clear.setEnabled(False); return
        cable=entry["cable"]; layer=entry["layer"]; spec=entry["spec"]
        ident=str(getattr(cable,"cable_id","") or "").strip() or f"Kabel {entry['index']}"
        length=(f"{entry['length']:.2f} m inkl. reserve".replace(".",",")) if entry["length"] is not None else "Længde ukendt – skala/kalibrering mangler"
        self.cable_summary.setText(f"{ident} · {entry['circuit'] or 'uden gruppe'} · {entry['endpoints']}\n{core.cable_type_display(layer)} · {spec or 'uden specifikation'} · {length}")
        current_article=self.cable_bindings.get(uid,""); lookup=self._catalog_lookup(); art=lookup.get(current_article,{})
        self.cable_current_article.setText((current_article + (f" · {art.get('description','')}" if art.get("description") else "")) if current_article else "Ingen kabelartikel tilknyttet")
        old=self.cable_article_picker.currentData() if self.cable_article_picker.count() else current_article
        blocker=QSignalBlocker(self.cable_article_picker); self.cable_article_picker.clear()
        candidates=[]
        for a in self._available_catalog():
            if str(a.get("kind","") or "")!="cable":continue
            exact=(str(a.get("cable_spec","") or "").replace(" ","").casefold()==spec.replace(" ","").casefold()) if spec else False
            candidates.append((0 if exact else 1,a))
        project_article_nos={p["article_no"] for p in self.catalog}
        for _priority,a in sorted(candidates,key=lambda x:(x[0],str(x[1].get("series","")).casefold(),float(x[1].get("package_length_m",0) or 0),x[1]["article_no"])):
            package=float(a.get("package_length_m",0) or 0)
            pack="afmålt" if package<=0 else f"{package:g} m rulle"
            mark="★ " if a["article_no"] not in project_article_nos else ""
            self.cable_article_picker.addItem(f"{mark}{a['article_no']} · {a.get('series','')} · {a.get('cable_spec','')} · {pack} · {a.get('description','')}",a["article_no"])
        target=old or current_article; idx=self.cable_article_picker.findData(target); self.cable_article_picker.setCurrentIndex(idx if idx>=0 else (0 if self.cable_article_picker.count() else -1)); del blocker
        self.cable_assign.setEnabled(bool(uid and self.cable_article_picker.count())); self.cable_clear.setEnabled(bool(current_article))

    def _assign_cable_article(self):
        uid=self._current_cable_uid(); article_no=self._article_no_from_combo(self.cable_article_picker)
        if not (uid and article_no):return
        self._ensure_project_article(article_no); self.cable_bindings[uid]=article_no
        self._refresh_library(); self._cable_type_changed(); self._refresh_bom()

    def _clear_cable_article(self):
        uid=self._current_cable_uid()
        if uid:self.cable_bindings.pop(uid,None)
        self._cable_type_changed(); self._refresh_bom()

    @staticmethod
    def _fmt_qty(value):
        v=float(value or 0)
        return str(int(round(v))) if abs(v-round(v))<1e-9 else f"{v:.2f}".replace(".",",")

    @staticmethod
    def _fmt_price(value,currency="DKK"):
        if value is None or str(value).strip()=="":return "—"
        try:v=float(value)
        except (TypeError,ValueError):return "—"
        return f"{v:,.2f}".replace(",","X").replace(".",",").replace("X",".")+f" {str(currency or 'DKK').upper()}"

    def _fmt_display_price(self,value,currency="DKK"):
        converted=price_display.to_display_amount(value,getattr(self,"price_vat_mode","excl"))
        return self._fmt_price(converted,currency)

    def _selected_bom_room_uid(self):
        if not hasattr(self,"bom_room_filter"):return ""
        return str(self.bom_room_filter.currentData() or "")

    def _bom_room_caption(self,uid):
        uid=str(uid or "").strip()
        if not uid:return "Alle rum"
        if uid=="__outside__":return "Uden rum"
        room=next((r for r in (getattr(self.window.project,"rooms",[]) or []) if str(getattr(r,"uid","") or "")==uid),None)
        return core.room_display_text(room) if room is not None else "Ukendt rum"

    def _selected_bom_room_caption(self):
        return self._bom_room_caption(self._selected_bom_room_uid())

    def _bom_cable_inputs(self):
        include=not hasattr(self,"bom_show_cables") or self.bom_show_cables.isChecked()
        if include:return self.window.project.cables,self.cable_bindings
        return [],{}

    def _bom_cable_visibility_changed(self,checked):
        cable_index=self.bom_quick_filter.findData("cable") if hasattr(self,"bom_quick_filter") else -1
        if cable_index>=0:
            item=self.bom_quick_filter.model().item(cable_index)
            if item is not None:item.setEnabled(bool(checked))
        if not checked and hasattr(self,"bom_quick_filter") and str(self.bom_quick_filter.currentData() or "")=="cable":
            blocker=QSignalBlocker(self.bom_quick_filter)
            index=self.bom_quick_filter.findData(""); self.bom_quick_filter.setCurrentIndex(max(0,index)); del blocker
        self._refresh_bom()

    def _bom_data(self,room_uid=None):
        factor,_desc=self.window._length_scale_info(); reserve=self.window._length_reserve_percent()
        selected=self._selected_bom_room_uid() if room_uid is None else str(room_uid or "")
        cables,cable_bindings=self._bom_cable_inputs()
        return core.build_bom(
            self.window.project.placements,self._available_catalog(),self.bindings,
            cables,cable_bindings,factor,reserve,
            self.assemblies,self.assembly_bindings,
            rooms=self.window.project.rooms,room_filter_uid=selected,
            placement_room_additions=self.window.project.raw.get("placement_bom_room_additions",{}))

    def _bom_source_data(self,room_uid=None):
        factor,_desc=self.window._length_scale_info(); reserve=self.window._length_reserve_percent()
        selected=self._selected_bom_room_uid() if room_uid is None else str(room_uid or "")
        cables,cable_bindings=self._bom_cable_inputs()
        return core.bom_source_breakdown(
            self.window.project.placements,self._available_catalog(),self.bindings,
            self.window.project.rooms,cables,cable_bindings,
            self.assemblies,self.assembly_bindings,room_filter_uid=selected,
            placement_room_additions=self.window.project.raw.get("placement_bom_room_additions",{}),
            metres_per_unit=factor,reserve_percent=reserve)

    @staticmethod
    def _bom_sources_by_article(sources):
        out=defaultdict(list)
        for row in sources or []:
            ano=str(row.get("article_no","") or "").strip()
            if ano:out[ano].append(row)
        return out

    @staticmethod
    def _bom_sources_by_segment(sources):
        out=defaultdict(list)
        for row in sources or []:
            ano=str(row.get("article_no","") or "").strip()
            key=str(row.get("purchase_segment_key","") or core.bom_purchase_segment_key(ano,row))
            if key:out[key].append(row)
        return out

    @staticmethod
    def _bom_source_summary(rows):
        rows=list(rows or []); assembly_names=[]; kinds=[]
        for row in rows:
            kind=str(row.get("source_type","") or "")
            if kind=="assembly":
                name=str(row.get("assembly_name",row.get("source_label","")) or "").strip()
                if name and name not in assembly_names:assembly_names.append(name)
            elif kind and kind not in kinds:kinds.append(kind)
        parts=[]
        if assembly_names:
            shown=", ".join(assembly_names[:2]); extra=len(assembly_names)-2
            parts.append("Stykliste: "+shown+(f" +{extra}" if extra>0 else ""))
        labels={"manual":"Direkte","wago":"Wago","cable":"Kabel"}
        for kind in kinds:
            if kind in labels:parts.append(labels[kind])
        return " · ".join(parts) if parts else "—"

    def _bom_row_matches_quick_filter(self,row,sources):
        wanted_category=str(self.bom_category_filter.currentData() or "") if hasattr(self,"bom_category_filter") else ""
        if wanted_category and str(row.get("bom_category","") or "")!=wanted_category:return False
        wanted_mounting=str(self.bom_mounting_filter.currentData() or "") if hasattr(self,"bom_mounting_filter") else ""
        row_mounting=core.normalize_mounting_zone(row.get("mounting_zone",""))
        if wanted_mounting and row_mounting!=("" if wanted_mounting=="__none__" else wanted_mounting):return False
        wanted_color=str(self.bom_material_color_filter.currentData() or "") if hasattr(self,"bom_material_color_filter") else ""
        row_color=core.normalize_material_color(row.get("material_color",""))
        if wanted_color and row_color!=("" if wanted_color=="__none__" else wanted_color):return False
        purchase_filter=str(self.bom_purchase_filter.currentData() or "") if hasattr(self,"bom_purchase_filter") else ""
        if purchase_filter=="purchased" and not bool(row.get("already_purchased",False)):return False
        if purchase_filter=="not_purchased" and bool(row.get("already_purchased",False)):return False
        mode=str(self.bom_quick_filter.currentData() or "") if hasattr(self,"bom_quick_filter") else ""
        if not mode:return True
        kinds={str(x.get("source_type","") or "") for x in (sources or [])}
        quality_codes=set(row.get("_quality_codes",[]) or [])
        if mode=="missing_price":return row.get("line_total") is None
        if mode=="assembly":return "assembly" in kinds
        if mode=="manual":return bool(kinds & {"manual","wago"})
        if mode=="cable":return "cable" in kinds
        if mode=="missing_article":return "missing_article" in quality_codes
        if mode=="stale_price":return bool(quality_codes & {"stale_price","price_date_missing"})
        if mode=="package":return any(code.startswith(("package_","minimum_order_")) for code in quality_codes)
        if mode=="warning":return bool(quality_codes)
        return True

    def _refresh_bom_category_filter(self,rows):
        if not hasattr(self,"bom_category_filter"):return
        current=str(self.bom_category_filter.currentData() or "")
        values=sorted({str(row.get("bom_category","") or "").strip() for row in (rows or []) if str(row.get("bom_category","") or "").strip()},key=str.casefold)
        blocker=QSignalBlocker(self.bom_category_filter); self.bom_category_filter.clear(); self.bom_category_filter.addItem("Alle typer","")
        for value in values:self.bom_category_filter.addItem(value,value)
        index=self.bom_category_filter.findData(current); self.bom_category_filter.setCurrentIndex(index if index>=0 else 0); del blocker

    def _refresh_bom_procurement_filters(self,rows):
        rows=list(rows or [])
        if hasattr(self,"bom_mounting_filter"):
            current=str(self.bom_mounting_filter.currentData() or "")
            present={core.normalize_mounting_zone(row.get("mounting_zone","")) for row in rows}
            blocker=QSignalBlocker(self.bom_mounting_filter); self.bom_mounting_filter.clear(); self.bom_mounting_filter.addItem("Alle profiler","")
            for value,label in core.MOUNTING_ZONE_OPTIONS:
                if value in present:self.bom_mounting_filter.addItem(label,value if value else "__none__")
            index=self.bom_mounting_filter.findData(current); self.bom_mounting_filter.setCurrentIndex(index if index>=0 else 0); del blocker
        if hasattr(self,"bom_material_color_filter"):
            current=str(self.bom_material_color_filter.currentData() or "")
            present={core.normalize_material_color(row.get("material_color","")) for row in rows}
            blocker=QSignalBlocker(self.bom_material_color_filter); self.bom_material_color_filter.clear(); self.bom_material_color_filter.addItem("Alle farver","")
            for value in sorted(present,key=lambda x:(not bool(x),x.casefold())):
                self.bom_material_color_filter.addItem(value or "Ikke angivet",value if value else "__none__")
            index=self.bom_material_color_filter.findData(current); self.bom_material_color_filter.setCurrentIndex(index if index>=0 else 0); del blocker

    def _bom_filter_caption(self):
        parts=[]
        if hasattr(self,"bom_category_filter") and str(self.bom_category_filter.currentData() or ""):
            parts.append(str(self.bom_category_filter.currentText() or ""))
        if hasattr(self,"bom_quick_filter") and str(self.bom_quick_filter.currentData() or ""):
            parts.append(str(self.bom_quick_filter.currentText() or ""))
        for name in ("bom_mounting_filter","bom_material_color_filter","bom_purchase_filter"):
            combo=getattr(self,name,None)
            if combo is not None and str(combo.currentData() or ""):parts.append(str(combo.currentText() or ""))
        return " · ".join(x for x in parts if x) or "Alle"

    def _fit_active_bom_columns(self):
        tab=self.bom_view_tabs.currentIndex() if hasattr(self,"bom_view_tabs") else 0
        if tab==0:
            if self.bom_article_stack.currentIndex()==0:_fit_table_columns(self.bom_table)
            else:
                for c in range(self.bom_group_tree.columnCount()):self.bom_group_tree.resizeColumnToContents(c)
        elif tab==1:
            for c in range(self.bom_assembly_tree.columnCount()):self.bom_assembly_tree.resizeColumnToContents(c)
        elif tab==2:_fit_table_columns(self.bom_source_table)
        elif tab==3:_fit_table_columns(self.bom_quality_table)

    def _reset_active_bom_columns(self):
        tab=self.bom_view_tabs.currentIndex() if hasattr(self,"bom_view_tabs") else 0
        if tab==0 and self.bom_article_stack.currentIndex()==0:_reset_table_columns(self.bom_table)
        elif tab==2:_reset_table_columns(self.bom_source_table)
        elif tab==3:_reset_table_columns(self.bom_quality_table)
        else:self._fit_active_bom_columns()

    def _selected_bom_article_no(self):
        tab=self.bom_view_tabs.currentIndex() if hasattr(self,"bom_view_tabs") else 0
        if tab==0:
            if self.bom_article_stack.currentIndex()==0:
                item=self.bom_table.item(self.bom_table.currentRow(),0) if self.bom_table.currentRow()>=0 else None
                return str(item.data(Qt.ItemDataRole.UserRole) or item.text() or "") if item else ""
            item=self.bom_group_tree.currentItem()
            data=item.data(0,Qt.ItemDataRole.UserRole) if item else None
            return str(data.get("article_no","") or "") if isinstance(data,dict) else ""
        if tab==2:
            item=self.bom_source_table.item(self.bom_source_table.currentRow(),0) if self.bom_source_table.currentRow()>=0 else None
            return str(item.text() or "") if item else ""
        if tab==3:
            item=self.bom_quality_table.item(self.bom_quality_table.currentRow(),1) if self.bom_quality_table.currentRow()>=0 else None
            return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
        item=self.bom_assembly_tree.currentItem() if hasattr(self,"bom_assembly_tree") else None
        data=item.data(0,Qt.ItemDataRole.UserRole) if item else None
        return str(data.get("article_no","") or "") if isinstance(data,dict) else ""

    def _open_selected_bom_sources(self):
        article_no=self._selected_bom_article_no()
        if not article_no:
            QMessageBox.information(self,"BOM-kilder","Vælg først en artikelrække."); return
        rows=list(getattr(self,"_bom_current_sources_by_article",{}).get(article_no,[]) or [])
        if not rows:
            QMessageBox.information(self,"BOM-kilder",f"Der blev ikke fundet konkrete kilder til {article_no} i den aktuelle visning."); return
        BomSourceDialog(self,self.window,article_no,rows).exec()

    def _show_active_bom_on_plan(self):
        tab=self.bom_view_tabs.currentIndex() if hasattr(self,"bom_view_tabs") else 0
        if tab==2:
            self._bom_source_row_activated(None); return
        if tab==1:
            self._bom_assembly_item_activated(self.bom_assembly_tree.currentItem(),0); return
        article_no=self._selected_bom_article_no()
        if article_no:
            self.window.highlight_bom_article(article_no,self._selected_bom_room_uid())
            QTimer.singleShot(0,lambda:(self.raise_(),self.activateWindow()))

    def _open_bom_quality_article(self,*_args):
        row=self.bom_quality_table.currentRow() if hasattr(self,"bom_quality_table") else -1
        if row<0:return
        item=self.bom_quality_table.item(row,1); article_no=str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
        if not article_no:return
        self.tabs.setCurrentWidget(self.library_tab)
        self.library_search.setText(article_no); self._refresh_library()
        target=self.library_table_model.row_for_article_no(article_no)
        if target>=0:
            self.library_table.selectRow(target)
            self.library_table.scrollTo(self.library_table_model.index(target,0),QAbstractItemView.ScrollHint.PositionAtCenter)

    def _refresh_bom_quality(self,result):
        findings=list((result or {}).get("findings",[]) or []); summary=dict((result or {}).get("summary",{}) or {})
        self.bom_quality_table.setRowCount(len(findings))
        colors={"Fejl":"#f87171","Advarsel":"#fbbf24","Info":"#60a5fa"}
        for r,finding in enumerate(findings):
            values=(finding.get("severity",""),finding.get("label",finding.get("article_no","")),finding.get("area",""),finding.get("message",""),finding.get("suggestion",""))
            for c,value in enumerate(values):
                cell=_table_item(value,finding.get("article_no","") if c==1 else None)
                if c==0 and finding.get("severity") in colors:cell.setForeground(QBrush(QColor(colors[finding["severity"]])))
                self.bom_quality_table.setItem(r,c,cell)
        if findings:
            self.bom_quality_summary.setText(
                f"{summary.get('errors',0)} fejl · {summary.get('warnings',0)} advarsler · {summary.get('info',0)} informationer. "
                "Dobbeltklik på en artikel for at åbne den i artikeldatabasen.")
        else:self.bom_quality_summary.setText("✓ Ingen kontrolpunkter i den aktuelle BOM.")

    def _bom_group_item_activated(self,item,_column=0):
        data=item.data(0,Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(data,dict) or not data.get("article_no"):return
        self.window.highlight_bom_article(str(data.get("article_no")),self._selected_bom_room_uid())
        QTimer.singleShot(0,lambda:(self.raise_(),self.activateWindow()))

    def _bom_assembly_item_activated(self,item,_column=0):
        if item is None:return
        data=item.data(0,Qt.ItemDataRole.UserRole)
        if not isinstance(data,dict):return
        puids=list(data.get("placement_uids",[]) or [])
        if puids and hasattr(self.window,"_select_scene_objects"):
            self.window._select_scene_objects(puids,[],True)
            if hasattr(self.window,"_notify"):self.window._notify(f"Stykliste: {len(puids)} forekomst(er) vist på plantegningen.",kind="info")
        elif data.get("article_no"):
            self.window.highlight_bom_article(str(data.get("article_no")),self._selected_bom_room_uid())

    def _bom_source_row_activated(self,_item=None):
        row=self.bom_source_table.currentRow() if hasattr(self,"bom_source_table") else -1
        sources=list(getattr(self,"_bom_visible_sources",[]) or [])
        if not (0<=row<len(sources)):return
        src=sources[row]; puid=str(src.get("placement_uid","") or ""); cuid=str(src.get("cable_uid","") or "")
        if hasattr(self.window,"_select_scene_objects"):
            self.window._select_scene_objects([puid] if puid else [],[cuid] if cuid else [],True)
            if hasattr(self.window,"_notify"):self.window._notify("Valgt BOM-kilde vist på plantegningen.",kind="info")

    def _refresh_bom_group_tree(self,rows):
        self.bom_group_tree.clear()
        key=str(self.bom_group_by.currentData() or "") if hasattr(self,"bom_group_by") else ""
        self.bom_article_stack.setCurrentIndex(1 if key else 0)
        if not key:return
        groups=defaultdict(list)
        for row in rows:
            label=str(row.get(key,"") or "").strip() or ("Ukategoriseret" if key in {"category","bom_category"} else "Uden værdi")
            groups[label].append(row)
        for label,members in sorted(groups.items(),key=lambda x:x[0].casefold()):
            currencies=defaultdict(float); priced=0
            for row in members:
                if row.get("line_total") is not None:
                    cur=str(row.get("price_currency","DKK") or "DKK").upper(); currencies[cur]+=float(row.get("line_total") or 0); priced+=1
            total=" · ".join(self._fmt_display_price(v,k) for k,v in sorted(currencies.items())) if currencies else "—"
            parent=QTreeWidgetItem([f"{label}  ({len(members)} linjer)","","","","","","","","","","",self._fmt_qty(sum(float(x.get('qty',0) or 0) for x in members)),"","","",total,f"Pris på {priced}/{len(members)} linjer"])
            parent.setData(0,Qt.ItemDataRole.UserRole,{"kind":"group","label":label})
            font=parent.font(0); font.setBold(True); parent.setFont(0,font)
            self.bom_group_tree.addTopLevelItem(parent)
            for row in members:
                vals=[row["article_no"],row.get("room_display","Uden rum"),row["description"],row["manufacturer"],row.get("bom_category","Ukategoriseret"),row.get("mounting_summary","Ikke angivet"),row.get("purchase_status","Mangler at købe"),row.get("source_summary","—"),row.get("ean",""),row.get("el_no",""),row["unit"],self._fmt_qty(row["qty"]),self._fmt_display_price(row.get("unit_price"),row.get("price_currency","DKK")),row.get("price_status",row.get("price_kind","")),row.get("price_unit",row.get("unit","")),self._fmt_display_price(row.get("line_total"),row.get("price_currency","DKK")),str(row.get("detail","") or "")]
                child=QTreeWidgetItem([str(x) for x in vals]); child.setData(0,Qt.ItemDataRole.UserRole,{"kind":"article","article_no":row["article_no"]}); parent.addChild(child)
        self.bom_group_tree.expandAll()

    def _refresh_bom_assembly_tree(self,selected_room,visible_article_nos=None):
        self.bom_assembly_tree.clear()
        rows=core.bom_assembly_usage(
            self.window.project.placements,self._available_catalog(),self.bindings,self.window.project.rooms,
            self.assemblies,self.assembly_bindings,room_filter_uid=selected_room,
            placement_room_additions=self.window.project.raw.get("placement_bom_room_additions",{}))
        mode=str(self.bom_quick_filter.currentData() or "") if hasattr(self,"bom_quick_filter") else ""
        if mode in {"manual","cable"}:rows=[]
        if mode=="missing_price":rows=[r for r in rows if int(r.get("priced_items",0) or 0)<len(r.get("items",[]) or [])]
        if hasattr(self,"bom_category_filter") and str(self.bom_category_filter.currentData() or "") and visible_article_nos is not None:
            rows=[r for r in rows if any(str(item.get("article_no","") or "") in visible_article_nos for item in (r.get("items",[]) or []))]
        if mode in {"missing_article","stale_price","package","warning"} and visible_article_nos is not None:
            rows=[r for r in rows if any(str(item.get("article_no","") or "") in visible_article_nos for item in (r.get("items",[]) or []))]
        for row in rows:
            totals=" · ".join(self._fmt_display_price(v,k) for k,v in sorted((row.get("totals_by_currency",{}) or {}).items())) if row.get("totals_by_currency") else "—"
            parent=QTreeWidgetItem([row.get("name",""),row.get("category",""),row.get("variant","")," | ".join(row.get("rooms",[]) or []),f"{int(row.get('uses',0) or 0)}×","","","",totals])
            parent.setData(0,Qt.ItemDataRole.UserRole,{"kind":"assembly","assembly_id":row.get("assembly_id",""),"placement_uids":row.get("placement_uids",[])})
            font=parent.font(0); font.setBold(True); parent.setFont(0,font); self.bom_assembly_tree.addTopLevelItem(parent)
            for child_row in row.get("items",[]) or []:
                vals=[f"↳ {child_row.get('article_no','')} · {child_row.get('description','')}","","","","",self._fmt_qty(child_row.get("qty",0)),child_row.get("unit",""),self._fmt_display_price(child_row.get("unit_price"),child_row.get("price_currency","DKK")),self._fmt_display_price(child_row.get("line_total"),child_row.get("price_currency","DKK"))]
                child=QTreeWidgetItem(vals); child.setData(0,Qt.ItemDataRole.UserRole,{"kind":"assembly_article","article_no":child_row.get("article_no",""),"placement_uids":row.get("placement_uids",[])})
                parent.addChild(child)
            parent.setExpanded(True)
        return rows

    def _refresh_bom_source_table(self,sources,visible_segment_keys):
        mode=str(self.bom_quick_filter.currentData() or "") if hasattr(self,"bom_quick_filter") else ""
        visible=[]
        for src in sources or []:
            segment=str(src.get("purchase_segment_key","") or core.bom_purchase_segment_key(src.get("article_no",""),src))
            if segment not in visible_segment_keys:continue
            kind=str(src.get("source_type","") or "")
            if mode=="assembly" and kind!="assembly":continue
            if mode=="manual" and kind not in {"manual","wago"}:continue
            if mode=="cable" and kind!="cable":continue
            visible.append(src)
        self._bom_visible_sources=visible
        self.bom_source_table.setRowCount(len(visible))
        labels={"assembly":"Stykliste","manual":"Direkte","wago":"Wago","cable":"Kabel"}
        for r,row in enumerate(visible):
            vals=[row.get("article_no",""),row.get("room_display",""),row.get("mounting_summary","Ikke angivet"),row.get("purchase_status","Mangler at købe"),labels.get(row.get("source_type"),row.get("source_type","")),row.get("source_label",""),row.get("object_label",row.get("symbol_name","")),row.get("part_label",""),f"{self._fmt_qty(row.get('qty',0))} {row.get('unit','')}",row.get("detail","")]
            for c,val in enumerate(vals):self.bom_source_table.setItem(r,c,_table_item(val,r if c==0 else None))

    def _prepare_bom_rows_for_export(self, rows, selected_room, sources=None):
        """Tilføj rum/kildekontekst og brug samme sortering som den synlige BOM."""
        rows=[dict(row or {}) for row in (rows or [])]
        source_rows=list(self._bom_source_data(selected_room) if sources is None else (sources or []))
        source_by_segment=self._bom_sources_by_segment(source_rows)
        source_by_article=self._bom_sources_by_article(source_rows)
        if selected_room:
            caption=self._bom_room_caption(selected_room)
            for row in rows:row["room_display"]=caption
        else:
            for row in rows:
                ano=str(row.get("article_no","") or "")
                segment_key=str(row.get("purchase_segment_key","") or core.bom_purchase_segment_key(ano,row))
                own=source_by_segment.get(segment_key,source_by_article.get(ano,[]))
                room_values=[]
                for src in own:
                    for value in str(src.get("room_display","") or "Uden rum").split("|"):
                        value=value.strip()
                        if value and value not in room_values:room_values.append(value)
                row["room_display"]=" | ".join(room_values) if room_values else "Uden rum"
        lookup=self._catalog_lookup()
        for row in rows:
            ano=str(row.get("article_no","") or "")
            segment_key=str(row.get("purchase_segment_key","") or core.bom_purchase_segment_key(ano,row))
            row["purchase_segment_key"]=segment_key
            own=source_by_segment.get(segment_key,source_by_article.get(ano,[]))
            row["source_summary"]=self._bom_source_summary(own)
            row["source_types"]=sorted({str(x.get("source_type","") or "") for x in own if str(x.get("source_type","") or "")})
            circuits=[]
            for src in own:
                value=str(src.get("group_circuit","") or "").strip()
                if value and value not in circuits:circuits.append(value)
            row["circuit_display"]=" | ".join(circuits) if circuits else "Uden gruppe/kreds"
            art=lookup.get(ano,{})
            row["category"]=str(art.get("category_normalized","") or art.get("product_type","") or art.get("category","") or "Ukategoriseret")
            row["article_color"]=str(art.get("color","") or "")
            roles=[str(x.get("component_role","") or "") for x in own if str(x.get("component_role","") or "").strip()]
            row["bom_category"]=core.bom_article_category(art,roles,row["source_types"])
        sort_key=str(self.bom_sort.currentData() or "article_no") if hasattr(self,"bom_sort") else "article_no"
        def sort_value(row):
            if sort_key=="mounting_height_mm":
                value=core.normalize_mounting_height_mm(row.get(sort_key))
                return (value is None,float(value or 0.0),str(row.get("article_no","") or "").casefold())
            return (False,str(row.get(sort_key,"") or "").casefold(),str(row.get("article_no","") or "").casefold())
        rows.sort(key=sort_value)
        return rows

    def _bom_rows_by_room_for_export(self):
        """Byg en rumopdelt eksport med præcis ét konkret rum pr. række.

        Den samlede BOM må ikke eksploderes direkte efter rum, fordi ekstra
        BOM-rum er additive: et fysisk symbol kan med vilje høre til både sit
        fysiske rum og et ekstra BOM-rum. Derfor beholdes hovedarket som den
        autoritative projekttotal, mens dette datasæt er den filtervenlige
        rumvisning. Kabelmængder beregnes af ``build_bom`` for den faktiske
        del af ruten i hvert rum.
        """
        scopes=[]
        rooms=sorted(list(getattr(self.window.project,"rooms",[]) or []),key=lambda r:core.room_display_text(r).casefold())
        for room in rooms:
            uid=str(getattr(room,"uid","") or "").strip()
            if uid:scopes.append(uid)
        scopes.append("__outside__")
        out=[]
        for uid in scopes:
            room_rows,_missing=self._bom_data(uid)
            if not room_rows:continue
            source_rows=self._bom_source_data(uid); source_by_article=self._bom_sources_by_article(source_rows); source_by_segment=self._bom_sources_by_segment(source_rows)
            prepared=self._prepare_bom_rows_for_export(room_rows,uid,source_rows)
            quality=bom_quality.audit_bom(prepared,_missing)
            for row in prepared:
                row["_quality_codes"]=[x.get("code","") for x in quality.get("by_article",{}).get(str(row.get("article_no","") or ""),[])]
            prepared=[row for row in prepared if self._bom_row_matches_quick_filter(
                row,source_by_segment.get(str(row.get("purchase_segment_key","") or core.bom_purchase_segment_key(row.get("article_no",""),row)),source_by_article.get(str(row.get("article_no","") or ""),[])))]
            out.extend(prepared)
        sort_key=str(self.bom_sort.currentData() or "article_no") if hasattr(self,"bom_sort") else "article_no"
        out.sort(key=lambda row:(
            str(row.get("room_display","") or "").casefold(),
            str(row.get(sort_key,"") or "").casefold(),
            str(row.get("article_no","") or "").casefold(),
        ))
        return out

    def _bom_row_activated(self,item):
        row=item.row() if item is not None else self.bom_table.currentRow()
        if row<0:return
        article_item=self.bom_table.item(row,0)
        article_no=str(article_item.data(Qt.ItemDataRole.UserRole) or article_item.text() or "") if article_item else ""
        if not article_no:return
        self.window.highlight_bom_article(article_no,self._selected_bom_room_uid())
        QTimer.singleShot(0,lambda:(self.raise_(),self.activateWindow()))

    def _refresh_bom(self,*_):
        self._project_article_cache=None
        if hasattr(self.window,"clear_bom_article_highlight") and (getattr(self.window,"_bom_highlight_placement_uids",set()) or getattr(self.window,"_bom_highlight_cable_uids",set())):
            self.window.clear_bom_article_highlight()
        selected_room=self._selected_bom_room_uid()
        rows,missing=self._bom_data(selected_room)
        sources=self._bom_source_data(selected_room)
        rows=self._prepare_bom_rows_for_export(rows,selected_room,sources)
        self._refresh_bom_category_filter(rows)
        self._refresh_bom_procurement_filters(rows)
        quality_result=bom_quality.audit_bom(rows,missing)
        for row in rows:
            findings=quality_result.get("by_article",{}).get(str(row.get("article_no","") or ""),[])
            row["_quality_codes"]=[x.get("code","") for x in findings]
            row["quality_status"]=" · ".join(dict.fromkeys(x.get("severity","") for x in findings))
        self._bom_quality_result=quality_result
        self._refresh_bom_quality(quality_result)
        total_unfiltered=len(rows)
        sources_by_article=self._bom_sources_by_article(sources)
        sources_by_segment=self._bom_sources_by_segment(sources)
        self._bom_current_sources_by_article=sources_by_article
        enriched=[]
        for raw in rows:
            row=dict(raw or {}); ano=str(row.get("article_no","") or "")
            segment=str(row.get("purchase_segment_key","") or core.bom_purchase_segment_key(ano,row))
            if self._bom_row_matches_quick_filter(row,sources_by_segment.get(segment,sources_by_article.get(ano,[]))):enriched.append(row)
        rows=enriched
        self._bom_current_rows=rows

        self._bom_hover_timer.stop(); self._bom_hover_row=-1; self._hide_bom_hover_popup()
        self.bom_table.setRowCount(len(rows))
        totals_by_currency=defaultdict(float); priced_lines=0
        for r,row in enumerate(rows):
            unit_price=self._fmt_display_price(row.get("unit_price"),row.get("price_currency","DKK"))
            line_total=self._fmt_display_price(row.get("line_total"),row.get("price_currency","DKK"))
            if row.get("line_total") is not None:
                totals_by_currency[str(row.get("price_currency","DKK") or "DKK").upper()]+=float(row.get("line_total") or 0); priced_lines+=1
            values=[row["article_no"],row.get("room_display","Uden rum"),row["description"],row["manufacturer"],row.get("bom_category","Ukategoriseret"),row.get("mounting_summary","Ikke angivet"),row.get("purchase_status","Mangler at købe"),row.get("source_summary","—"),row.get("ean",""),row.get("el_no",""),row["unit"],self._fmt_qty(row["qty"]),unit_price,row.get("price_status",row.get("price_kind","")),row.get("price_unit",row.get("unit","")),line_total,str(row.get("detail","") or "")]
            for c,value in enumerate(values):
                user_data=row["article_no"] if c==0 else None
                self.bom_table.setItem(r,c,_table_item(value,user_data))

        self._refresh_bom_group_tree(rows)
        visible_article_nos={str(x.get("article_no","") or "") for x in rows}
        visible_segment_keys={str(x.get("purchase_segment_key","") or core.bom_purchase_segment_key(x.get("article_no",""),x)) for x in rows}
        assembly_rows=self._refresh_bom_assembly_tree(selected_room,visible_article_nos)
        self._refresh_bom_source_table(sources,visible_segment_keys)

        self.missing_table.setRowCount(len(missing))
        for r,row in enumerate(missing):
            values=[row["symbol_name"],row["part_label"],self._fmt_qty(row["qty"]),row.get("unit","stk"),row.get("detail","")]
            for c,value in enumerate(values):self.missing_table.setItem(r,c,_table_item(value))
        missing_symbols=sum(int(row.get("count",0) or 0) for row in missing if row.get("symbol")!="__cable__")
        missing_cables=sum(int(row.get("count",0) or 0) for row in missing if row.get("symbol")=="__cable__")
        missing_bits=[]
        if missing_symbols: missing_bits.append(f"{missing_symbols} symboldele uden tilknytning")
        if missing_cables: missing_bits.append(f"{missing_cables} kabelstræk uden tilknytning")
        price_text=" · ".join(f"{self._fmt_display_price(total,currency)}" for currency,total in sorted(totals_by_currency.items())) if totals_by_currency else "ingen priser angivet"
        if hasattr(self,"bom_total_label"):
            vat_caption=price_display.vat_caption(self.price_vat_mode)
            if totals_by_currency:
                coverage="" if priced_lines==len(rows) else f" · ⚠ {len(rows)-priced_lines} af {len(rows)} viste linjer mangler pris"
                self.bom_total_label.setText(f"Summeret pris {vat_caption} (aktuel visning): {price_text}{coverage}")
            else:
                coverage=f" · {len(rows)} viste linjer" if rows else ""
                self.bom_total_label.setText(f"Summeret pris {vat_caption} (aktuel visning): —{coverage} · ingen priser angivet")
        warning=(" · ⚠ " + " / ".join(missing_bits)) if missing_bits else " · alle BOM-relevante dele er tilknyttet"
        if self._legacy_type_bindings_present:warning += " · ældre typebaserede tilknytninger ignoreres"
        scope=self._selected_bom_room_caption(); filter_caption=self._bom_filter_caption()
        filtered=f" · filter: {filter_caption} ({len(rows)}/{total_unfiltered})" if filter_caption!="Alle" else ""
        cable_filter=" · kabler skjult" if hasattr(self,"bom_show_cables") and not self.bom_show_cables.isChecked() else ""
        checks=quality_result.get("summary",{}).get("total",0)
        quality_text=f" · {checks} kontrolpunkt(er)" if checks else " · BOM-kontrol OK"
        unique_articles=len({str(row.get("article_no","") or "") for row in rows})
        self.bom_status.setText(f"{scope} · {len(rows)} BOM-linjer / {unique_articles} artikelnumre · {len(assembly_rows)} anvendte styklister{filtered}{cable_filter}{warning}{quality_text} · pris på {priced_lines}/{len(rows)} linjer · total {price_text}")

    def _current_bom_export_data(self):
        """Den aktuelle, filtrerede BOM som fælles grundlag for alle eksportformer."""
        selected_room=self._selected_bom_room_uid()
        rows,missing=self._bom_data(selected_room)
        source_rows=self._bom_source_data(selected_room); source_by_article=self._bom_sources_by_article(source_rows); source_by_segment=self._bom_sources_by_segment(source_rows)
        rows=self._prepare_bom_rows_for_export(rows,selected_room,source_rows)
        quality=bom_quality.audit_bom(rows,missing)
        for row in rows:
            row["_quality_codes"]=[x.get("code","") for x in quality.get("by_article",{}).get(str(row.get("article_no","") or ""),[])]
        rows=[row for row in rows if self._bom_row_matches_quick_filter(
            row,source_by_segment.get(str(row.get("purchase_segment_key","") or core.bom_purchase_segment_key(row.get("article_no",""),row)),source_by_article.get(str(row.get("article_no","") or ""),[])))]
        return {
            "rows":rows,"missing":missing,"selected_room":selected_room,
            "room_scope":self._selected_bom_room_caption(),
            "filter_caption":self._bom_filter_caption(),
            "include_cables":not hasattr(self,"bom_show_cables") or self.bom_show_cables.isChecked(),
        }

    def _open_bom_print_preview(self):
        data=self._current_bom_export_data()
        if not data["rows"]:
            QMessageBox.information(self,"BOM","Der er endnu ingen tilknyttede artikler at udskrive."); return
        project_name="Elplan-projekt"
        if self.window.project.path:project_name=self.window.project.path.stem.replace(".elplan","")
        try:
            BomPrintPreviewDialog(
                self,data["rows"],data["missing"],project_name=project_name,
                room_scope=data["room_scope"],price_vat_mode=self.price_vat_mode,
                filter_caption=data["filter_caption"],include_cables=data["include_cables"],
                suggested_path=self._bom_export_filename("pdf"),
                room_rows=(self._bom_rows_by_room_for_export()
                           if not data["selected_room"] and bool(getattr(self.window.project,"rooms",[]) or []) else []),
            ).exec()
        except Exception as exc:QMessageBox.critical(self,"BOM",f"Forhåndsvisningen kunne ikke oprettes:\n{exc}")

    def _bom_export_filename(self,suffix):
        suffix=str(suffix or "").lstrip(".")
        suggested=f"BOM.{suffix}"
        if self.window.project.path:
            stem=self.window.project.path.stem.replace('.elplan','')
            suggested=str(self.window.project.path.with_name(f"{stem}_BOM.{suffix}"))
        return suggested

    def _export_bom_xlsx(self):
        data=self._current_bom_export_data(); selected_room=data["selected_room"]
        rows=data["rows"]; missing=data["missing"]
        if not rows:
            QMessageBox.information(self,"BOM","Der er endnu ingen tilknyttede artikler at eksportere."); return
        path,_=QFileDialog.getSaveFileName(self,"Eksportér BOM til Excel",self._bom_export_filename("xlsx"),"Excel-projektmappe (*.xlsx)")
        if not path:return
        if not path.lower().endswith(".xlsx"):path += ".xlsx"
        project_name=""
        if self.window.project.path:
            project_name=self.window.project.path.stem.replace('.elplan','')
        try:
            room_rows=self._bom_rows_by_room_for_export() if not selected_room else []
            export_scope=self._selected_bom_room_caption()
            if self._bom_filter_caption()!="Alle":export_scope+=f" · filter: {self._bom_filter_caption()}"
            if hasattr(self,"bom_show_cables") and not self.bom_show_cables.isChecked():export_scope+=" · kabler skjult"
            final_path=write_bom_xlsx(
                path,rows,missing,room_scope=export_scope,project_name=project_name,
                room_rows=room_rows,price_vat_mode=self.price_vat_mode)
        except Exception as exc:
            QMessageBox.critical(self,"BOM",f"Kunne ikke eksportere Excel-fil:\n{exc}"); return
        QMessageBox.information(
            self,"BOM",
            f"BOM eksporteret som formateret Excel-tabel:\n{final_path}\n\n"
            + f"Prisfelter er eksporteret {price_display.vat_caption(self.price_vat_mode)}.\n\n"
            + "Type, monteringsprofil, højde, materialefarve og indkøbsstatus kan filtreres og sorteres direkte i Excel.\n\n"
            + ("Fanen ‘BOM pr. rum’ kan filtreres direkte på ét konkret rum.\n\n" if not selected_room else "")
            + "CSV-eksport er stadig tilgængelig ved siden af Excel-knappen.")

    def _export_bom_csv(self):
        data=self._current_bom_export_data(); rows=data["rows"]; missing=data["missing"]
        if not rows:
            QMessageBox.information(self,"BOM","Der er endnu ingen tilknyttede artikler at eksportere."); return
        path,_=QFileDialog.getSaveFileName(self,"Eksportér BOM",self._bom_export_filename("csv"),"CSV (*.csv)")
        if not path:return
        if not path.lower().endswith(".csv"):path += ".csv"
        try:
            export_rows=price_display.convert_bom_rows(rows,self.price_vat_mode)
            vat_caption=price_display.vat_caption(self.price_vat_mode)
            with open(path,"w",encoding="utf-8-sig",newline="") as f:
                w=csv.writer(f,delimiter=";")
                w.writerow(["Artikelnummer","Rum","Beskrivelse","Fabrikat","Type/kategori","Monteringsprofil","Monteringshøjde [mm]","Materialefarve","Artikelfarve","Indkøbsstatus","Kilde / stykliste","EAN","EL-/LM-nr.","Enhed","Antal","Antal tilbage at købe","Indkøbsantal","Indkøbsantal tilbage",f"Estimeret pris {vat_caption}",f"Manuel pris {vat_caption}",f"Anvendt enhedspris {vat_caption}","Pris pr.","Valuta","Prisstatus",f"Linjesum {vat_caption}",f"Beløb tilbage {vat_caption}","Priskilde","Pris opdateret","Grundlag","Produktlink","Leverandørlink"])
                for row in export_rows:
                    price_cell=lambda key: "" if row.get(key) is None else f"{float(row[key]):.2f}".replace(".",",")
                    w.writerow([row["article_no"],row.get("room_display","Uden rum"),row["description"],row["manufacturer"],row.get("bom_category","Ukategoriseret"),row.get("mounting_zone_label","Ikke angivet"),row.get("mounting_height_mm","") or "",row.get("material_color",""),row.get("article_color",""),row.get("purchase_status","Mangler at købe"),row.get("source_summary",""),row.get("ean",""),row.get("el_no",""),row["unit"],self._fmt_qty(row["qty"]),self._fmt_qty(row.get("quantity_to_buy",row["qty"])),self._fmt_qty(row.get("purchase_quantity",0)),self._fmt_qty(row.get("purchase_quantity_to_buy",row.get("purchase_quantity",0))),price_cell("estimated_price"),price_cell("manual_price"),price_cell("unit_price"),row.get("price_unit",row.get("unit","")),row.get("price_currency","DKK"),row.get("price_status",row.get("price_kind","")),price_cell("line_total"),price_cell("line_total_to_buy"),row.get("price_source",""),row.get("price_checked",""),row.get("detail",""),row.get("product_page",""),row.get("supplier_page","")])
                if missing:
                    w.writerow([]); w.writerow(["IKKE TILKNYTTET","Type","Del/specifikation","Behov","Enhed","Bemærkning"])
                    for row in missing:w.writerow(["",row["symbol_name"],row["part_label"],self._fmt_qty(row["qty"]),row.get("unit","stk"),row.get("detail","")])
        except Exception as exc:
            QMessageBox.critical(self,"BOM",f"Kunne ikke eksportere CSV:\n{exc}"); return
        QMessageBox.information(self,"BOM",f"BOM eksporteret {price_display.vat_caption(self.price_vat_mode)} til:\n{path}")

    def _save_and_close(self):
        self._remember_current_tab(); self._persist_ui_state()
        new_catalog=core.normalize_article_catalog(self.catalog)
        new_assemblies=core.normalize_bom_assemblies(self.assemblies)
        valid_placement_uids={str(getattr(p,"uid","") or "") for p in self.window.project.placements}
        valid_cable_uids={str(getattr(c,"uid","") or "") for c in self.window.project.cables}
        new_bindings={uid:parts for uid,parts in core.normalize_symbol_article_bindings(self.bindings).items() if uid in valid_placement_uids}
        new_assembly_bindings={uid:parts for uid,parts in core.normalize_symbol_assembly_bindings(self.assembly_bindings).items() if uid in valid_placement_uids}
        new_cables={uid:article for uid,article in core.normalize_cable_article_bindings(self.cable_bindings).items() if uid in valid_cable_uids}
        try:
            user_library.save_core_article_catalog(new_catalog)
            user_library.save_article_prices(self.price_book)
            user_library.save_global_bom_assemblies(new_assemblies,self._available_catalog())
        except Exception as exc:
            QMessageBox.critical(self,"Artikelbibliotek",f"Kernedata (artikelbase/prisbog/styklister) kunne ikke gemmes:\n{exc}\n\nIngen projektdata er ændret.")
            return
        old_bindings=core.normalize_symbol_article_bindings(self.window.project.raw.get("placement_articles",{}))
        old_assembly_bindings=core.normalize_symbol_assembly_bindings(self.window.project.raw.get("placement_assemblies",{}))
        old_cables=core.normalize_cable_article_bindings(self.window.project.raw.get("cable_instance_articles",{}))
        legacy_assemblies_present=bool(core.normalize_bom_assemblies(self.window.project.raw.get("bom_assemblies",[])))
        if new_bindings!=old_bindings or new_assembly_bindings!=old_assembly_bindings or new_cables!=old_cables or legacy_assemblies_present or "article_catalog" in self.window.project.raw:
            self.window.project.raw.pop("article_catalog",None)
            self.window.project.raw.pop("bom_assemblies",None)
            self.window.project.raw["placement_articles"]=new_bindings
            self.window.project.raw["placement_assemblies"]=new_assembly_bindings
            self.window.project.raw["cable_instance_articles"]=new_cables
            self.window.project.dirty=True; self.window._update_title()
        self.window.global_bom_assemblies=deepcopy(new_assemblies)
        self.accept()

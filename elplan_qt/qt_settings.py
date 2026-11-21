from __future__ import annotations

"""Categorised application settings shared across Elplan work areas."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

import core_logic as core
from elplan_catalog import price_display
from elplan_project import pl_daase_api
from elplan_project import project_storage
from elplan_catalog import user_library
from elplan_qt.qt_ui import configure_modern_dialog, make_dialog_header


class ApplicationSettingsDialog(QDialog):
    """First shared settings surface; categories can grow without menu sprawl."""

    def __init__(self, parent=None, *, settings=None, appearance_mode="light", dark_canvas=True):
        super().__init__(parent)
        self.window=parent
        self.settings=dict(settings or {})
        configure_modern_dialog(self, title="Indstillinger", minimum_size=(720, 470), size=(780, 520))
        root=QVBoxLayout(self); root.setContentsMargins(16, 14, 16, 14); root.setSpacing(12)
        root.addWidget(make_dialog_header(
            "Indstillinger",
            "Globale valg er samlet efter område og gælder på tværs af projekter.",
            eyebrow="PROGRAM",
        ))
        body=QHBoxLayout(); body.setSpacing(14); root.addLayout(body, 1)
        self.categories=QListWidget(); self.categories.setFixedWidth(190); body.addWidget(self.categories)
        self.pages=QStackedWidget(); body.addWidget(self.pages, 1)
        self._add_category("Visning", self._view_page(appearance_mode, dark_canvas))
        self._add_category("Priser og BOM", self._price_page())
        self._add_category("Lager og synkronisering", self._storage_page())
        self._add_category("Integrationer", self._integration_page())
        self.categories.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.categories.setCurrentRow(1)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _add_category(self, title, page):
        self.categories.addItem(title); self.pages.addWidget(page)

    @staticmethod
    def _page(title, description):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(4, 2, 4, 4); layout.setSpacing(12)
        heading=QLabel(title); heading.setObjectName("sectionTitle"); layout.addWidget(heading)
        hint=QLabel(description); hint.setWordWrap(True); hint.setObjectName("sectionHint"); layout.addWidget(hint)
        return page, layout

    def _view_page(self, appearance_mode, dark_canvas):
        page, layout=self._page("Visning", "Udseendet er en lokal programindstilling. PDF og print beholder deres tekniske papirfarver.")
        form=QFormLayout(); form.setSpacing(10)
        self.appearance=QComboBox()
        for key, label in core.APPEARANCE_MODES.items():self.appearance.addItem(label, key)
        self.appearance.setCurrentIndex(max(0, self.appearance.findData(core.normalize_appearance_mode(appearance_mode))))
        form.addRow("Programtema", self.appearance)
        self.dark_canvas=QCheckBox("Brug mørk tegneflade i mørkt tema")
        self.dark_canvas.setChecked(bool(dark_canvas)); self.dark_canvas.setToolTip("Påvirker kun skærmvisningen, ikke PDF eller print.")
        form.addRow("Tegneflade", self.dark_canvas)
        layout.addLayout(form); layout.addStretch(1)
        return page

    def _price_page(self):
        page, layout=self._page(
            "Priser og BOM",
            "Dette valg bruges i symbol-hover, Artikler/BOM, styklister, prissammenligning og eksport. De gemte grundpriser forbliver ekskl. moms.",
        )
        form=QFormLayout(); form.setSpacing(10)
        self.price_vat=QComboBox()
        self.price_vat.addItem("Ekskl. moms", price_display.VAT_MODE_EXCL)
        self.price_vat.addItem("Inkl. moms", price_display.VAT_MODE_INCL)
        wanted=price_display.normalize_vat_mode(self.settings.get("price_vat_mode"))
        self.price_vat.setCurrentIndex(max(0, self.price_vat.findData(wanted)))
        form.addRow("Vis priser", self.price_vat)
        layout.addLayout(form)
        note=QLabel("Momsvalget ændrer kun visningen. Prisbog, projekter og BOM-beregning mister derfor ikke deres fælles nettoprisgrundlag.")
        note.setWordWrap(True); note.setObjectName("sectionHint"); layout.addWidget(note); layout.addStretch(1)
        return page

    def _storage_page(self):
        page, layout=self._page(
            "Lager og synkronisering",
            "Projektlager og globale artikeldata konfigureres hver for sig. Artikeldata bliver dermed uafhængige af de enkelte projekter.",
        )
        self.project_storage_summary=QLabel(); self.project_storage_summary.setWordWrap(True)
        self.article_storage_summary=QLabel(); self.article_storage_summary.setWordWrap(True)
        project_button=QPushButton("Konfigurér projektlager…"); project_button.clicked.connect(self._open_project_storage)
        article_button=QPushButton("Konfigurér artikeldata…"); article_button.clicked.connect(self._open_article_storage)
        layout.addWidget(self.project_storage_summary); layout.addWidget(project_button)
        layout.addSpacing(8); layout.addWidget(self.article_storage_summary); layout.addWidget(article_button)
        layout.addStretch(1); self._refresh_storage_summaries()
        return page

    def _integration_page(self):
        page, layout=self._page(
            "Integrationer",
            "PL-dåse-PWA'en bruges som read-only feltdokumentation. Kun fysiske kabelindføringer, noter og fotos importeres; lederfordelingen forbliver i Elplan.",
        )
        form=QFormLayout(); form.setSpacing(10)
        self.pl_daase_url=QLineEdit(str(self.settings.get("pl_daase_url","") or ""))
        self.pl_daase_url.setPlaceholderText("https://pl.dit-domæne.dk")
        self.pl_daase_token=QLineEdit(str(self.settings.get("pl_daase_token","") or ""))
        self.pl_daase_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.pl_daase_token.setPlaceholderText("pl_…")
        form.addRow("PL-dåse API",self.pl_daase_url)
        form.addRow("API-token",self.pl_daase_token)
        layout.addLayout(form)
        actions=QHBoxLayout()
        self.pl_daase_test=QPushButton("Test forbindelse")
        self.pl_daase_test.clicked.connect(self._test_pl_daase_connection)
        self.pl_daase_test_status=QLabel(""); self.pl_daase_test_status.setWordWrap(True)
        actions.addWidget(self.pl_daase_test); actions.addWidget(self.pl_daase_test_status,1)
        layout.addLayout(actions)
        note=QLabel("Tokenet gemmes kun i programmets lokale indstillinger og skrives ikke i projektfilen eller eksporterne.")
        note.setWordWrap(True); note.setObjectName("sectionHint"); layout.addWidget(note); layout.addStretch(1)
        return page

    def _test_pl_daase_connection(self):
        self.pl_daase_test.setEnabled(False); self.pl_daase_test_status.setText("Kontakter serveren…")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result=pl_daase_api.fetch_export(self.pl_daase_url.text(),self.pl_daase_token.text(),timeout=8)
            count=len(result.get("boxes",[])); user=str(result.get("user","") or "")
            self.pl_daase_test_status.setObjectName("positiveText")
            self.pl_daase_test_status.setText(f"Forbindelse OK · {count} dåse(r)"+(f" · bruger {user}" if user else ""))
        except (ValueError,pl_daase_api.PLDaaseApiError) as exc:
            self.pl_daase_test_status.setObjectName("dangerText"); self.pl_daase_test_status.setText(str(exc))
        finally:
            QApplication.restoreOverrideCursor(); self.pl_daase_test.setEnabled(True)
            self.pl_daase_test_status.style().unpolish(self.pl_daase_test_status); self.pl_daase_test_status.style().polish(self.pl_daase_test_status)

    def _refresh_storage_summaries(self):
        settings=core.load_app_settings()
        project_mode, project_root=project_storage.configured_storage(settings)
        project_labels={
            project_storage.MODE_LEGACY:"Frit filvalg",
            project_storage.MODE_LOCAL:"Lokalt projektbibliotek",
            project_storage.MODE_SYNCED:"Synkroniseret projektbibliotek",
        }
        project_path=str(project_root) if project_root is not None else "Ingen fast mappe"
        self.project_storage_summary.setText(f"<b>Projekter</b><br>{project_labels.get(project_mode, project_mode)} · {project_path}")
        article_mode, article_root=user_library.configured_core_data(settings)
        article_label="Synkroniseret mappe / OneDrive" if article_mode==user_library.CORE_DATA_MODE_SYNCED else "Lokalt på denne pc"
        self.article_storage_summary.setText(f"<b>Artikeldata</b><br>{article_label} · {Path(article_root)}")

    def _open_project_storage(self):
        if self.window is not None and hasattr(self.window, "configure_project_storage"):
            self.window.configure_project_storage(); self._refresh_storage_summaries()

    def _open_article_storage(self):
        if self.window is not None and hasattr(self.window, "configure_core_data_storage"):
            self.window.configure_core_data_storage(); self._refresh_storage_summaries()

    def values(self):
        return {
            "appearance_mode":core.normalize_appearance_mode(self.appearance.currentData()),
            "dark_canvas":bool(self.dark_canvas.isChecked()),
            "price_vat_mode":price_display.normalize_vat_mode(self.price_vat.currentData()),
            "pl_daase_url":self.pl_daase_url.text().strip(),
            "pl_daase_token":self.pl_daase_token.text().strip(),
        }


class ApplicationSettingsMixin:
    def open_application_settings(self) -> None:
        before=dict(core.load_app_settings())
        dlg=ApplicationSettingsDialog(
            self, settings=before, appearance_mode=getattr(self, "appearance_mode", "light"),
            dark_canvas=getattr(self, "dark_canvas", True),
        )
        if dlg.exec()!=QDialog.DialogCode.Accepted:
            return
        values=dlg.values(); current=core.load_app_settings()
        old_vat=price_display.normalize_vat_mode(current.get("price_vat_mode"))
        old_appearance=core.normalize_appearance_mode(getattr(self, "appearance_mode", "light"))
        old_canvas=bool(getattr(self, "dark_canvas", True))
        current.update(values); core.save_app_settings(current); self.app_settings=current
        self.appearance_mode=values["appearance_mode"]; self.dark_canvas=values["dark_canvas"]
        if old_appearance!=self.appearance_mode or old_canvas!=self.dark_canvas:
            self._apply_appearance(persist=False)
        else:
            self._update_appearance_actions()
        if old_vat!=values["price_vat_mode"]:
            self._hover_bom_cache.clear(); self._hover_info_popup.hide()
        self._notify(
            f"Indstillinger gemt · priser vises {price_display.vat_caption(values['price_vat_mode'])}.",
            kind="success",
        )

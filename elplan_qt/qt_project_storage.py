from __future__ import annotations

"""Settings dialogs for independent project and global article storage."""

from pathlib import Path
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from elplan_project import project_storage
import core_logic as core
from elplan_catalog import user_library
from elplan_qt.qt_ui import configure_modern_dialog


class ProjectStorageDialog(QDialog):
    def __init__(self,parent=None,*,mode: str=project_storage.MODE_LEGACY,root: str="",prefer_synced: bool=False):
        super().__init__(parent)
        self.setWindowTitle("Projektlager")
        configure_modern_dialog(self,minimum_size=(610,330))
        layout=QVBoxLayout(self); layout.setSpacing(12)
        intro=QLabel(
            "Projektlager er valgfrit. En synkroniseret mappe (fx OneDrive) bruges som en almindelig lokal mappe; "
            "Elplan kræver ikke Microsoft-login eller internetforbindelse."
        )
        intro.setWordWrap(True); intro.setObjectName("sectionHint"); layout.addWidget(intro)
        form=QFormLayout(); form.setSpacing(10)
        self.mode=QComboBox()
        self.mode.addItem("Som hidtil · frit filvalg",project_storage.MODE_LEGACY)
        self.mode.addItem("Lokalt projektbibliotek",project_storage.MODE_LOCAL)
        self.mode.addItem("Synkroniseret mappe / OneDrive",project_storage.MODE_SYNCED)
        wanted=project_storage.normalize_storage_mode(mode)
        if prefer_synced and wanted==project_storage.MODE_LEGACY: wanted=project_storage.MODE_SYNCED
        idx=self.mode.findData(wanted); self.mode.setCurrentIndex(max(0,idx))
        form.addRow("Placeringstype",self.mode)
        row=QWidget(); row_layout=QHBoxLayout(row); row_layout.setContentsMargins(0,0,0,0); row_layout.setSpacing(6)
        self.path=QLineEdit(str(root or "")); self.path.setPlaceholderText("Vælg mappe til Elplan-projekter")
        browse=QPushButton("Vælg…"); browse.clicked.connect(self._browse)
        row_layout.addWidget(self.path,1); row_layout.addWidget(browse)
        form.addRow("Projektbibliotek",row)
        candidates=project_storage.detect_onedrive_candidates()
        self.onedrive=QComboBox(); self.onedrive.setVisible(bool(candidates))
        for candidate in candidates:self.onedrive.addItem(str(candidate),str(candidate))
        self.use_onedrive=QPushButton("Brug fundet OneDrive"); self.use_onedrive.setVisible(bool(candidates)); self.use_onedrive.clicked.connect(self._use_onedrive)
        odrow=QWidget(); odlay=QHBoxLayout(odrow); odlay.setContentsMargins(0,0,0,0); odlay.addWidget(self.onedrive,1); odlay.addWidget(self.use_onedrive)
        if candidates: form.addRow("Fundet OneDrive",odrow)
        layout.addLayout(form)
        preview=QLabel(
            "Ny projektstruktur:\n"
            "Projekt/\n"
            "  project.elplan.json\n"
            "  drawing/\n"
            "  backups/\n"
            "  exports/\n"
            "  project-info.json"
        )
        preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        preview.setObjectName("sectionHint"); layout.addWidget(preview)
        layout.addStretch(1)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self._accept); self.buttons.rejected.connect(self.reject); layout.addWidget(self.buttons)
        self.mode.currentIndexChanged.connect(self._sync_enabled); self._sync_enabled()
        if not self.path.text().strip() and candidates and wanted==project_storage.MODE_SYNCED:
            self.path.setText(str(candidates[0]/"Elplan"/"Projekter"))

    def _sync_enabled(self):
        enabled=self.mode.currentData()!=project_storage.MODE_LEGACY
        self.path.setEnabled(enabled)

    def _browse(self):
        start=self.path.text().strip() or str(Path.home())
        value=QFileDialog.getExistingDirectory(self,"Vælg projektbibliotek",start)
        if value:self.path.setText(value)

    def _use_onedrive(self):
        raw=str(self.onedrive.currentData() or self.onedrive.currentText() or "").strip()
        if raw:self.path.setText(str(Path(raw)/"Elplan"/"Projekter"))

    def _accept(self):
        if self.mode.currentData()!=project_storage.MODE_LEGACY:
            raw=self.path.text().strip()
            if not raw:
                QMessageBox.warning(self,"Projektlager","Vælg en mappe til projektbiblioteket."); return
            try:Path(raw).expanduser().mkdir(parents=True,exist_ok=True)
            except Exception as exc:
                QMessageBox.warning(self,"Projektlager",f"Mappen kunne ikke oprettes:\n{exc}"); return
        self.accept()

    def values(self)->tuple[str,str]:
        return project_storage.normalize_storage_mode(self.mode.currentData()),self.path.text().strip()


class CoreDataStorageDialog(QDialog):
    """Vælg en global artikelplacering, som er adskilt fra projekterne."""

    def __init__(self,parent=None,*,mode: str=user_library.CORE_DATA_MODE_LOCAL,root: str=""):
        super().__init__(parent)
        self.setWindowTitle("Placering af artikeldata")
        configure_modern_dialog(self,minimum_size=(650,350))
        layout=QVBoxLayout(self); layout.setSpacing(12)
        intro=QLabel(
            "Artikeldata er globale for Elplan og bruges på tværs af alle projekter. "
            "De ligger i deres egen mappe og bliver ikke en del af projektlageret."
        )
        intro.setWordWrap(True); intro.setObjectName("sectionHint"); layout.addWidget(intro)
        form=QFormLayout(); form.setSpacing(10)
        self.mode=QComboBox()
        self.mode.addItem("Lokalt på denne pc",user_library.CORE_DATA_MODE_LOCAL)
        self.mode.addItem("Synkroniseret mappe / OneDrive",user_library.CORE_DATA_MODE_SYNCED)
        wanted=user_library.normalize_core_data_mode(mode)
        self.mode.setCurrentIndex(max(0,self.mode.findData(wanted)))
        form.addRow("Placeringstype",self.mode)
        row=QWidget(); row_layout=QHBoxLayout(row); row_layout.setContentsMargins(0,0,0,0); row_layout.setSpacing(6)
        self.path=QLineEdit(str(root or "")); self.path.setPlaceholderText("Vælg separat mappe til Elplans artikeldata")
        self.browse=QPushButton("Vælg…"); self.browse.clicked.connect(self._browse)
        row_layout.addWidget(self.path,1); row_layout.addWidget(self.browse)
        form.addRow("Artikelmappe",row)
        candidates=project_storage.detect_onedrive_candidates()
        self.onedrive=QComboBox(); self.onedrive.setVisible(bool(candidates))
        for candidate in candidates:self.onedrive.addItem(str(candidate),str(candidate))
        self.use_onedrive=QPushButton("Brug fundet OneDrive"); self.use_onedrive.setVisible(bool(candidates)); self.use_onedrive.clicked.connect(self._use_onedrive)
        odrow=QWidget(); odlay=QHBoxLayout(odrow); odlay.setContentsMargins(0,0,0,0); odlay.addWidget(self.onedrive,1); odlay.addWidget(self.use_onedrive)
        if candidates:form.addRow("Fundet OneDrive",odrow)
        layout.addLayout(form)
        details=QLabel(
            "Flyttes og synkroniseres: artikelkatalog, prisbog og globale styklister.\n"
            "Forbliver lokalt: indstillinger, cache og logs. Projektfiler ændres ikke.\n\n"
            "Eksisterende data kopieres og flettes sikkert; den gamle placering slettes ikke."
        )
        details.setWordWrap(True); details.setObjectName("sectionHint"); layout.addWidget(details)
        layout.addStretch(1)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self._accept); self.buttons.rejected.connect(self.reject); layout.addWidget(self.buttons)
        if candidates and (wanted==user_library.CORE_DATA_MODE_LOCAL or not self.path.text().strip()):
            self.path.setText(str(candidates[0]/"Elplan"/"Artikeldata"))
        self.mode.currentIndexChanged.connect(self._sync_enabled); self._sync_enabled()

    def _sync_enabled(self):
        enabled=self.mode.currentData()==user_library.CORE_DATA_MODE_SYNCED
        self.path.setEnabled(enabled); self.browse.setEnabled(enabled); self.onedrive.setEnabled(enabled); self.use_onedrive.setEnabled(enabled)

    def _browse(self):
        start=self.path.text().strip() or str(Path.home())
        value=QFileDialog.getExistingDirectory(self,"Vælg mappe til artikeldata",start)
        if value:self.path.setText(value)

    def _use_onedrive(self):
        raw=str(self.onedrive.currentData() or self.onedrive.currentText() or "").strip()
        if raw:self.path.setText(str(Path(raw)/"Elplan"/"Artikeldata"))

    def _accept(self):
        if self.mode.currentData()==user_library.CORE_DATA_MODE_SYNCED and not self.path.text().strip():
            QMessageBox.warning(self,"Artikeldata","Vælg en separat mappe til artikeldataene."); return
        self.accept()

    def values(self)->tuple[str,str]:
        return user_library.normalize_core_data_mode(self.mode.currentData()),self.path.text().strip()


def configure_core_data_storage(window) -> bool:
    """Kør dialog og skift først indstilling, når datakopien er gennemført."""
    settings=core.load_app_settings()
    mode,source=user_library.configured_core_data(settings)
    dlg=CoreDataStorageDialog(window,mode=mode,root=str(source if mode==user_library.CORE_DATA_MODE_SYNCED else ""))
    if dlg.exec()!=QDialog.DialogCode.Accepted:return False
    new_mode,new_root=dlg.values()
    target=user_library.user_data_dir() if new_mode==user_library.CORE_DATA_MODE_LOCAL else Path(new_root).expanduser()
    _project_mode,project_root=project_storage.configured_storage(settings)
    if project_root is not None:
        resolved_target=target.resolve(strict=False); resolved_projects=project_root.resolve(strict=False)
        if resolved_target==resolved_projects or resolved_projects in resolved_target.parents:
            QMessageBox.warning(window,"Artikeldata","Artikelmappen skal ligge uden for projektlageret."); return False
    try:
        user_library.load_core_article_catalog()
        result=user_library.migrate_core_data_directory(source,target)
        settings["core_data_storage_mode"]=new_mode
        settings["core_data_root"]=str(target) if new_mode==user_library.CORE_DATA_MODE_SYNCED else ""
        core.save_app_settings(settings); window.app_settings=settings
        user_library.invalidate_core_data_caches(); window.global_article_catalog=user_library.load_core_article_catalog()
        window.global_bom_assemblies=deepcopy(user_library.load_global_bom_assemblies())
    except Exception as exc:
        QMessageBox.critical(window,"Artikeldata",f"Artikeldataene kunne ikke flyttes:\n{exc}"); return False
    label="Synkroniseret mappe" if new_mode==user_library.CORE_DATA_MODE_SYNCED else "Lokal mappe"
    window._notify(f"Artikeldata: {label}",kind="success")
    suffix="\n\nEksisterende måldata blev sikkerhedskopieret før fletningen." if result.get("backup") else ""
    QMessageBox.information(window,"Artikeldata flyttet",f"Artikeldata bruges nu fra:\n{target}\n\n{result['articles']} artikler · {result['prices']} priser · {result['assemblies']} globale styklister.\nDen tidligere placering er bevaret som sikkerhedskopi.{suffix}")
    return True

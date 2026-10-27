from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QMessageBox, QGraphicsItem

import project_collaboration
import project_storage
from project_model import APP_VERSION
from project_revision_backup import create_pre_external_project_backup


class ProjectCollaborationMixin:
    """Optional lock/external-change safety for structured project folders."""

    def _init_project_collaboration_state(self) -> None:
        self._project_session_token=project_collaboration.new_session_token()
        self._project_read_only=False
        self._project_conflict=False
        self._project_lock_path=None
        self._project_file_snapshot=None
        self._external_prompted_hash=""
        self._readonly_disabled_actions={}

    def _setup_project_collaboration_ui(self) -> None:
        self.status_storage=QLabel("Lokal")
        self.status_storage.setObjectName("storageStatusPill")
        self.status_storage.setProperty("statusState","local")
        self.statusBar().addPermanentWidget(self.status_storage)
        self._collab_monitor_timer=QTimer(self)
        self._collab_monitor_timer.setInterval(4000)
        self._collab_monitor_timer.timeout.connect(self._poll_external_project_change)
        self._collab_monitor_timer.start()
        self._collab_heartbeat_timer=QTimer(self)
        self._collab_heartbeat_timer.setInterval(30000)
        self._collab_heartbeat_timer.timeout.connect(self._refresh_project_lock_heartbeat)
        self._collab_heartbeat_timer.start()
        self._refresh_project_storage_status()

    def _refresh_project_storage_status(self) -> None:
        path=getattr(getattr(self,"project",None),"path",None)
        mode=project_storage.storage_mode_for_project(path)
        if self._project_conflict or self._project_read_only:
            text="Konflikt"
            tip="Projektet er ændret/låst af en anden computer. Denne åbning er skrivebeskyttet." if self._project_read_only else "Der er registreret en ekstern ændring af projektfilen."
            state="conflict"
        elif mode==project_storage.MODE_SYNCED:
            text="Synkroniseret mappe"
            tip="Projektet ligger i et synkroniseret projektbibliotek. Elplan arbejder fortsat på lokale filer."
            state="synced"
        else:
            text="Lokal"
            tip="Projektet redigeres lokalt."
            state="local"
        label=getattr(self,"status_storage",None)
        if label is not None:
            label.setText(text); label.setToolTip(tip); label.setProperty("statusState",state)
            label.style().unpolish(label); label.style().polish(label); label.update()
        self._update_title()

    def _project_lock_owner_text(self,info) -> str:
        computer=str(getattr(info,"computer","") or "en anden computer")
        opened=str(getattr(info,"opened_at","") or "")
        extra=f"\nÅbnet: {opened}" if opened else ""
        return f"{computer}{extra}"

    def _prepare_project_open_collaboration(self,project_path: Path):
        result=project_collaboration.acquire_lock(project_path,token=self._project_session_token,app_version=APP_VERSION)
        if result.acquired:
            return {"path":Path(project_path),"read_only":False,"lock_acquired":True}
        info=result.info
        box=QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Projektet redigeres allerede")
        box.setText("Projektet ser ud til at være åbent til redigering på en anden computer.")
        box.setInformativeText(
            f"Aktiv lås: {self._project_lock_owner_text(info)}\n\n"
            "For at undgå OneDrive/synkroniseringskonflikter kan projektet kun åbnes skrivebeskyttet."
        )
        read_btn=box.addButton("Åbn skrivebeskyttet",QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Annuller",QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton()!=read_btn: return None
        return {"path":Path(project_path),"read_only":True,"lock_acquired":False}

    def _abort_project_open_collaboration(self,access) -> None:
        if access and access.get("lock_acquired"):
            target=Path(access.get("path"))
            current=getattr(getattr(self,"project",None),"path",None)
            if current is None or Path(current).resolve()!=target.resolve():
                project_collaboration.release_lock(target,token=self._project_session_token)

    def _commit_project_open_collaboration(self,project_path: Path,access) -> None:
        old=getattr(self,"_project_lock_path",None)
        new=Path(project_path)
        if old is not None:
            try:same=Path(old).resolve()==new.resolve()
            except Exception:same=str(old)==str(new)
            if not same: project_collaboration.release_lock(old,token=self._project_session_token)
        self._project_lock_path=(new if access and access.get("lock_acquired") else None)
        self._project_read_only=bool(access and access.get("read_only"))
        self._project_conflict=self._project_read_only
        self._project_file_snapshot=project_collaboration.file_snapshot(new)
        self._external_prompted_hash=""
        self._apply_project_read_only_ui()
        self._refresh_project_storage_status()

    def _adopt_saved_project_collaboration(self,project_path) -> None:
        path=Path(project_path)
        old=getattr(self,"_project_lock_path",None)
        if old is not None:
            try:same=Path(old).resolve()==path.resolve()
            except Exception:same=False
            if not same: project_collaboration.release_lock(old,token=self._project_session_token)
        result=project_collaboration.acquire_lock(path,token=self._project_session_token,app_version=APP_VERSION)
        self._project_lock_path=path if result.acquired else None
        self._project_read_only=not result.acquired
        self._project_conflict=not result.acquired
        self._project_file_snapshot=project_collaboration.file_snapshot(path)
        self._external_prompted_hash=""
        self._apply_project_read_only_ui(); self._refresh_project_storage_status()

    def _refresh_project_lock_heartbeat(self) -> None:
        path=getattr(self,"_project_lock_path",None)
        if path is None or self._project_read_only:return
        ok=project_collaboration.refresh_lock(path,token=self._project_session_token,app_version=APP_VERSION)
        if not ok:
            self._project_conflict=True
            self._project_read_only=True
            self._apply_project_read_only_ui(); self._refresh_project_storage_status()
            self._notify("Projektlåsen er mistet · projektet er nu skrivebeskyttet",kind="warning",timeout=3500)

    def _release_current_project_lock(self) -> None:
        path=getattr(self,"_project_lock_path",None)
        if path is not None: project_collaboration.release_lock(path,token=self._project_session_token)
        self._project_lock_path=None

    def _project_file_changed_on_disk(self):
        path=getattr(getattr(self,"project",None),"path",None)
        if path is None:return False,None
        changed,current=project_collaboration.content_changed(path,self._project_file_snapshot)
        return changed,current

    def _note_project_saved_for_collaboration(self,path) -> None:
        self._project_file_snapshot=project_collaboration.file_snapshot(path)
        self._project_conflict=False
        self._external_prompted_hash=""
        self._refresh_project_storage_status()

    def _can_write_current_project(self) -> bool:
        if self._project_read_only:
            QMessageBox.information(self,"Skrivebeskyttet projekt","Projektet er åbnet skrivebeskyttet, fordi en anden computer har redigeringslåsen.\n\nBrug Gem som… hvis du vil oprette en separat kopi.")
            return False
        changed,current=self._project_file_changed_on_disk()
        if changed:
            self._project_conflict=True
            self._refresh_project_storage_status()
            self._handle_external_project_change(current,from_save=True)
            return False
        return True

    def _poll_external_project_change(self) -> None:
        path=getattr(getattr(self,"project",None),"path",None)
        if path is None or self._project_file_snapshot is None:return
        if getattr(getattr(self,"busy_overlay",None),"isVisible",lambda:False)():return
        changed,current=self._project_file_changed_on_disk()
        if not changed or current is None:return
        if current.sha256==self._external_prompted_hash:return
        self._external_prompted_hash=current.sha256
        self._project_conflict=True; self._refresh_project_storage_status()
        if self._project_read_only:
            self._project_file_snapshot=current
            self._notify("Den eksterne projektversion er opdateret · visningen er fortsat skrivebeskyttet",kind="warning",timeout=2600)
            return
        self._handle_external_project_change(current,from_save=False)

    def _handle_external_project_change(self,current_snapshot,*,from_save: bool=False) -> None:
        path=getattr(getattr(self,"project",None),"path",None)
        if path is None:return
        box=QMessageBox(self); box.setIcon(QMessageBox.Icon.Warning); box.setWindowTitle("Ekstern projektændring registreret")
        box.setText("Projektfilen er blevet ændret uden for denne Elplan-session.")
        dirty=bool(getattr(self.project,"dirty",False))
        info="Det kan være en anden computer eller en synkroniseringsklient."
        if dirty: info += "\n\nDu har også lokale, ikke-gemte ændringer. De bliver sikkerhedskopieret før en ekstern version kan indlæses."
        elif from_save: info += "\n\nGem er stoppet for at undgå at overskrive den eksterne revision."
        else: info += "\n\nDen aktuelle lokale revision sikkerhedskopieres automatisk, hvis du indlæser den eksterne version."
        box.setInformativeText(info)
        reload_btn=box.addButton("Indlæs ekstern version",QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Senere",QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton()==reload_btn:
            self._reload_external_project_version()

    def _reload_external_project_version(self) -> bool:
        path=getattr(getattr(self,"project",None),"path",None)
        if path is None:return False
        source=self._resolve_project_source(self.project)
        try:
            backup=create_pre_external_project_backup(
                project_data=self.project.to_dict(),project_path=path,current_cad=source,loaded_doc=getattr(self,"doc",None)
            )
        except Exception as exc:
            QMessageBox.critical(self,"Revisionsbackup mislykkedes","Den eksterne projektversion er ikke indlæst, fordi den nuværende revision ikke kunne sikkerhedskopieres først.\n\n"+str(exc))
            return False
        # The ordinary open path re-evaluates project.lock. If the other PC is
        # still editing, the fresh external version is opened read-only.
        ok=self._open_project_path(path,confirm_discard=False)
        if ok:self._notify(f"Ekstern projektversion indlæst · lokal revision gemt i {backup.directory.name}",kind="success",timeout=3600)
        return bool(ok)

    def _apply_project_read_only_ui(self) -> None:
        readonly=bool(self._project_read_only)
        names=(
            "act_save","act_update_cad","act_migrate_project","act_cable","act_cable_categories","act_cable_marking",
            "act_configurator","act_paste","act_delete","act_associate","act_clear_assoc","act_rotate","act_spot_line",
            "act_spot_rect","act_text","act_length_settings","act_bom","act_project_control","act_undo","act_redo","act_cable_routes",
        )
        if readonly:
            if not self._readonly_disabled_actions:
                for name in names:
                    action=getattr(self,name,None)
                    if action is not None:
                        self._readonly_disabled_actions[name]=action.isEnabled()
            for name in names:
                action=getattr(self,name,None)
                if action is not None: action.setEnabled(False)
        else:
            for name,enabled in dict(getattr(self,"_readonly_disabled_actions",{})).items():
                action=getattr(self,name,None)
                if action is not None: action.setEnabled(bool(enabled))
            self._readonly_disabled_actions={}
        for dock_name in ("palette_dock","inspector_dock"):
            dock=getattr(self,dock_name,None)
            if dock is not None:dock.setEnabled(not readonly)
        # Prevent accidental drag-moves while preserving selection/zoom/search.
        for item in list(getattr(self,"symbol_items",{}).values())+list(getattr(self,"text_items",{}).values()):
            try:item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,not readonly)
            except Exception:pass

    def _clear_project_collaboration_for_unsaved_project(self) -> None:
        self._release_current_project_lock()
        self._project_read_only=False
        self._project_conflict=False
        self._project_file_snapshot=None
        self._external_prompted_hash=""
        self._apply_project_read_only_ui()
        self._refresh_project_storage_status()

    def _collaboration_title_suffix(self) -> str:
        return " · SKRIVEBESKYTTET" if self._project_read_only else (" · KONFLIKT" if self._project_conflict else "")

from __future__ import annotations

"""Project/CAD opening workflow with explicit full-window busy feedback."""

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

import core_logic as core
from elplan_project import project_storage
from elplan_project.project_model import ProjectDocument
from elplan_project.project_revision_backup import create_pre_cad_update_backup


class ProjectOpenMixin:
    def _begin_busy(self, title: str, detail: str = "") -> None:
        self._set_status(f"{title} {detail}".strip())
        overlay = getattr(self, "busy_overlay", None)
        if overlay is not None:
            overlay.show_busy(title, detail)
        QApplication.processEvents()

    def _update_busy(self, detail: str) -> None:
        overlay = getattr(self, "busy_overlay", None)
        if overlay is not None and overlay.isVisible():
            overlay.set_detail(detail)
        self._set_status(detail)
        QApplication.processEvents()

    def _end_busy(self, *, success: bool = False, detail: str = "") -> None:
        overlay = getattr(self, "busy_overlay", None)
        if overlay is not None:
            overlay.hide_busy(success=success, detail=detail)
        QApplication.processEvents()

    def _open_project_path(self, path, *, confirm_discard: bool = True) -> bool:
        value = str(path or "").strip()
        if not value:
            return False
        project_path = Path(value).expanduser()
        if not project_path.is_file():
            self._forget_recent_project(project_path)
            QMessageBox.warning(self, "Åbn seneste", f"Projektfilen findes ikke længere:\n{project_path}")
            return False
        if confirm_discard and not self._confirm_discard_changes("åbner et andet projekt"):
            return False
        access=self._prepare_project_open_collaboration(project_path)
        if access is None:
            return False
        self._begin_busy("Åbner projekt…", project_path.name)
        opened_ok = False
        try:
            self._update_busy("Indlæser projektfil…")
            project = ProjectDocument.load(project_path)
            self._update_busy("Finder projektets DWG/DXF…")
            source = self._resolve_project_source(project)
            relocated = False
            if source is None or not source.is_file():
                self._end_busy()
                locate, _ = QFileDialog.getOpenFileName(self, "Find projektets DWG/DXF", "", "CAD (*.dwg *.dxf)")
                if not locate:
                    return False
                source = Path(locate)
                project.source_file = str(source)
                relocated = True
                self._begin_busy("Åbner projekt…", project_path.name)
            self._update_busy(f"Indlæser {source.name}…")
            if hasattr(self, "_reset_visual_workspace_transients"):
                self._reset_visual_workspace_transients()
            elif hasattr(self, "_focus_group_id"):
                self._focus_group_id = ""
            self._load_cad_and_scene(str(source), project=project)
            self._update_busy("Gør arbejdsfladen klar…")
            if relocated:
                self.project.dirty = True
            self._remember_recent_project(project.path or project_path)
            self._commit_project_open_collaboration(project.path or project_path,access)
            self._update_title()
            opened_ok = True
            return True
        except Exception as exc:
            self._end_busy()
            QMessageBox.critical(self, "Kunne ikke åbne projekt", str(exc))
            return False
        finally:
            if opened_ok:
                self._end_busy(success=True, detail=project_path.name)
            else:
                self._abort_project_open_collaboration(access)

    def open_recent_project(self, path) -> None:
        self._open_project_path(path, confirm_discard=True)

    def open_project(self) -> None:
        start_dir = ""
        recent = self._recent_project_paths(True)
        if recent:
            start_dir = str(Path(recent[0]).parent)
        else:
            _mode, storage_root = project_storage.configured_storage(getattr(self,"app_settings",{}))
            if storage_root is not None:
                start_dir = str(storage_root)
        path, _ = QFileDialog.getOpenFileName(self, "Åbn Elplan-projekt", start_dir, "Elplan projekt (*.elplan.json);;JSON (*.json)")
        if path:
            self._open_project_path(path, confirm_discard=True)

    def _project_source_reference(self, source: Path) -> str:
        """Store a CAD source relative to the project when possible."""
        resolved = Path(source).expanduser().resolve()
        project_path = getattr(self.project, "path", None)
        if project_path is not None:
            try:
                return os.path.relpath(str(resolved), str(Path(project_path).resolve().parent))
            except (OSError, ValueError):
                pass
        return str(resolved)

    @staticmethod
    def _cad_primitive_extents(primitives):
        boxes = []
        for primitive in primitives or []:
            try:
                box = core._primitive_bbox(primitive)
            except Exception:
                box = None
            if box is not None:
                boxes.append(box)
        if not boxes:
            return None
        return (
            min(row[0] for row in boxes),
            min(row[1] for row in boxes),
            max(row[2] for row in boxes),
            max(row[3] for row in boxes),
        )

    def _cad_update_looks_shifted(self, old_primitives, new_primitives) -> bool:
        """Only flag very large origin/scale changes; normal plan edits stay silent."""
        old_box = self._cad_primitive_extents(old_primitives)
        new_box = self._cad_primitive_extents(new_primitives)
        if old_box is None or new_box is None:
            return False
        old_w=max(old_box[2]-old_box[0],1e-9); old_h=max(old_box[3]-old_box[1],1e-9)
        new_w=max(new_box[2]-new_box[0],1e-9); new_h=max(new_box[3]-new_box[1],1e-9)
        old_span=max(old_w,old_h); new_span=max(new_w,new_h)
        scale_ratio=max(old_span/new_span,new_span/old_span)
        old_c=((old_box[0]+old_box[2])*0.5,(old_box[1]+old_box[3])*0.5)
        new_c=((new_box[0]+new_box[2])*0.5,(new_box[1]+new_box[3])*0.5)
        shift=((old_c[0]-new_c[0])**2+(old_c[1]-new_c[1])**2)**0.5
        # Deliberately conservative. An architect adding an outlying detail should
        # not create warnings; this is meant to catch changed DWG origins/scales.
        return bool(scale_ratio > 4.0 or shift > max(old_span,new_span)*0.85)

    def _replace_project_cad_background(self, source: Path) -> bool:
        """Replace only the CAD background, preserving all Elplan project data."""
        source=Path(source).expanduser()
        current_source=self._resolve_project_source(self.project)
        if current_source is None:
            QMessageBox.warning(self,"Opdatér plantegning","Projektets nuværende plantegning kan ikke identificeres. Opdateringen er afbrudt, fordi den gamle revision ikke kan sikkerhedskopieres.")
            return False
        current_source=Path(current_source).expanduser()
        if not source.is_file():
            QMessageBox.warning(self,"Opdatér plantegning",f"CAD-filen findes ikke:\n{source}")
            return False
        self._begin_busy("Opdaterer plantegning…",source.name)
        updated=False
        try:
            self._update_busy("Indlæser den nye DWG/DXF…")
            # Parse first. Nothing in the active project/scene is changed before
            # both document loading and primitive extraction have succeeded.
            new_doc=core.load_document(str(source))
            self._update_busy("Kontrollerer lag og geometri…")
            new_primitives,_counts=core.extract_cad_primitives(new_doc)

            old_primitives=list(getattr(self,"cad_primitives",[]) or [])
            if (self.project.placements or self.project.cables or self.project.rooms or self.project.texts) and self._cad_update_looks_shifted(old_primitives,new_primitives):
                self._end_busy()
                answer=QMessageBox.warning(
                    self,
                    "Muligt ændret koordinatsystem",
                    "Den nye plantegning ser ud til at have en markant anden placering eller skala.\n\n"
                    "Elplan-symboler, kabler, rum og tekster bevares på deres eksisterende koordinater. "
                    "Hvis DWG/DXF'ens nulpunkt er flyttet, kan de derfor komme til at ligge forkert.\n\n"
                    "Vil du fortsætte med opdateringen?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return False
                self._begin_busy("Opdaterer plantegning…",source.name)

            # Backup is mandatory and happens before any active project/CAD state
            # is replaced. The project copy serialises the *current in-memory*
            # state, so unsaved Elplan edits are included in the restore point.
            self._update_busy("Gemmer original plantegning og projektkopi…")
            try:
                revision_backup=create_pre_cad_update_backup(
                    project_data=self.project.to_dict(),
                    project_path=getattr(self.project,"path",None),
                    current_cad=current_source,
                    target_cad=source,
                    loaded_doc=getattr(self,"doc",None),
                )
            except Exception as backup_exc:
                self._end_busy()
                QMessageBox.critical(
                    self,
                    "Sikkerhedskopi kunne ikke oprettes",
                    "Plantegningen er ikke blevet ændret. Opdateringen kræver, at både den gamle plantegning og projektet kan sikkerhedskopieres først.\n\n"
                    f"Fejl: {backup_exc}",
                )
                return False
            self._begin_busy("Opdaterer plantegning…",source.name) if not getattr(getattr(self,"busy_overlay",None),"isVisible",lambda:False)() else None

            # Preserve the user's current view; updating the architect background
            # should not unexpectedly zoom the user away from the working area.
            view_center=None
            try:
                vp=self.view.viewport().rect().center()
                view_center=self.view.mapToScene(vp)
            except Exception:
                pass

            self._update_busy("Udskifter CAD-baggrunden…")
            if hasattr(self,"_reset_visual_workspace_transients"):
                self._reset_visual_workspace_transients()
            self._hover_bom_cache.clear()
            current_snap=getattr(self,"snap_engine",None)
            self.doc=new_doc
            self.cad_primitives=new_primitives
            # QtSnapEngine lives in qt_app; use the existing snap engine type so
            # this mixin does not need a second graphics import dependency.
            snap_type=type(current_snap) if current_snap is not None else None
            if snap_type is None:
                # The normal application always already has a snap engine when a
                # project is open. Fall back to the same helper used by qt_app.
                from elplan_qt.qt_graphics import QtSnapEngine
                snap_type=QtSnapEngine
            self.snap_engine=snap_type(self.cad_primitives,lambda layer:self.project.layer_visibility.get(layer,True))
            self.view.set_snap_engine(self.snap_engine)
            self.project.source_file=self._project_source_reference(source)
            self.project.dirty=True
            self._rebuild_scene()
            if view_center is not None:
                try:self.view.centerOn(view_center)
                except Exception:pass
            self._refresh_welcome_page()
            self._update_title()
            self._set_status(f"Plantegning opdateret: {source.name} · {len(new_primitives)} CAD-objekter · Backup: {revision_backup.directory.name}")
            self._notify("Plantegningen er opdateret · original + projektkopi er gemt i Elplan_backups",kind="success",timeout=3200)
            updated=True
            return True
        except Exception as exc:
            QMessageBox.critical(self,"Kunne ikke opdatere plantegning",self._friendly_cad_error(exc))
            return False
        finally:
            self._end_busy(success=updated,detail=source.name if updated else "")

    def update_cad(self) -> None:
        """Reload the current CAD file or choose a revised DWG/DXF for this project."""
        current=self._resolve_project_source(self.project)
        target=None
        if current is not None and current.is_file():
            box=QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle("Opdatér plantegning")
            box.setText("Hvordan vil du opdatere projektets plantegning?")
            box.setInformativeText(
                f"Aktuel fil: {current.name}\n\n"
                "Alle Elplan-data bevares. Før opdateringen gemmes automatisk en kopi af både den nuværende plantegning og projektet i Elplan_backups."
            )
            reload_button=box.addButton("Genindlæs nuværende",QMessageBox.ButtonRole.AcceptRole)
            choose_button=box.addButton("Vælg anden DWG/DXF…",QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            clicked=box.clickedButton()
            if clicked is reload_button:
                target=current
            elif clicked is choose_button:
                start_dir=str(current.parent)
                picked,_=QFileDialog.getOpenFileName(self,"Vælg opdateret DWG/DXF",start_dir,"CAD (*.dwg *.dxf)")
                if picked: target=Path(picked)
            else:
                return
        else:
            start_dir=str(self.project.path.parent) if getattr(self.project,"path",None) else ""
            picked,_=QFileDialog.getOpenFileName(self,"Vælg opdateret DWG/DXF",start_dir,"CAD (*.dwg *.dxf)")
            if picked: target=Path(picked)
        if target is not None:
            self._replace_project_cad_background(target)

    def open_cad(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Åbn DWG/DXF", "", "CAD (*.dwg *.dxf)")
        if not path or not self._confirm_discard_changes("åbner en anden tegning"):
            return
        source_path = Path(path)
        self._begin_busy("Åbner tegning…", source_path.name)
        opened_ok = False
        try:
            project = ProjectDocument.from_cad(path)
            self._update_busy(f"Indlæser {source_path.name}…")
            if hasattr(self, "_reset_visual_workspace_transients"):
                self._reset_visual_workspace_transients()
            elif hasattr(self, "_focus_group_id"):
                self._focus_group_id = ""
            self._load_cad_and_scene(path, project=project)
            self._clear_project_collaboration_for_unsaved_project()
            self._update_busy("Gør arbejdsfladen klar…")
            self.project.dirty = True
            self._update_title()
            opened_ok = True
        except Exception as exc:
            self._end_busy()
            QMessageBox.critical(self, "Kunne ikke åbne tegning", self._friendly_cad_error(exc))
        finally:
            if opened_ok:
                self._end_busy(success=True, detail=source_path.name)

    @staticmethod
    def _friendly_cad_error(exc: Exception) -> str:
        text = str(exc)
        if "ODAFileConverter" in text or exc.__class__.__name__.startswith("ODA"):
            return "DWG kræver ODA File Converter. Brug knappen 'ODA File Converter…' og vælg ODAFileConverter.exe.\n\n" + text
        return text

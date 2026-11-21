from __future__ import annotations

"""Atomic pre-update backups for project + CAD revisions."""

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from elplan_shared.storage_utils import atomic_write_text
from elplan_project import project_storage


@dataclass(frozen=True)
class RevisionBackup:
    directory: Path
    project_path: Path
    cad_path: Path


def _project_base_name(project_path: Path | None) -> str:
    if project_path is None:
        return "Elplan_projekt"
    name=project_path.name
    lower=name.lower()
    if lower.endswith(".elplan.json"):
        return name[:-len(".elplan.json")]
    return project_path.stem or "Elplan_projekt"


def _unique_backup_dir(parent: Path, stamp: str) -> Path:
    root=project_storage.backup_root_for_project_parent(parent)
    base=root / f"{stamp}_før_plantegningsopdatering"
    candidate=base
    index=2
    while candidate.exists():
        candidate=root / f"{stamp}_før_plantegningsopdatering_{index:02d}"
        index += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except Exception:
        return str(a.absolute()) == str(b.absolute())


def _write_loaded_cad_snapshot(doc: Any, source_suffix: str, target: Path) -> None:
    suffix=str(source_suffix or "").lower()
    if doc is None:
        raise RuntimeError("Den indlæste originaltegning er ikke tilgængelig i hukommelsen.")
    if suffix == ".dxf":
        doc.saveas(str(target))
        return
    if suffix == ".dwg":
        # The application already relies on ODA File Converter for DWG input.
        # Export the still-loaded old document, so a source file that has been
        # overwritten externally can still be backed up as the previous revision.
        from ezdxf.addons import odafc
        odafc.export_dwg(doc, str(target), replace=True)
        return
    raise ValueError("Kun DWG og DXF kan sikkerhedskopieres som plantegning.")


def create_pre_cad_update_backup(
    *,
    project_data: dict[str, Any],
    project_path: str | Path | None,
    current_cad: str | Path,
    target_cad: str | Path,
    loaded_doc: Any = None,
    now: datetime | None = None,
) -> RevisionBackup:
    """Create a restorable project/CAD pair before changing the CAD background.

    If the update reloads the *same* CAD path, the file may already have been
    overwritten by an architect. In that case the in-memory CAD document is
    exported, preserving the revision currently visible in Elplan. If a new
    path is selected, the old source file is copied byte-for-byte when possible.
    """
    current=Path(current_cad).expanduser()
    target=Path(target_cad).expanduser()
    project=Path(project_path).expanduser() if project_path else None
    parent=(project.parent if project is not None else current.parent).resolve()
    stamp=(now or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir=_unique_backup_dir(parent, stamp)

    cad_name=f"{current.stem}_original{current.suffix.lower()}"
    cad_backup=backup_dir/cad_name
    project_backup=backup_dir/f"{_project_base_name(project)}_før_opdatering.elplan.json"

    try:
        # Reloading the same pathname is special: the on-disk file may already
        # be the new revision. Export the still-loaded document instead.
        use_memory_snapshot=_same_path(current,target) or not current.is_file()
        if use_memory_snapshot:
            _write_loaded_cad_snapshot(loaded_doc,current.suffix,cad_backup)
        else:
            shutil.copy2(current,cad_backup)

        data=dict(project_data or {})
        data["source_file"]=cad_backup.name  # backup pair lives in same directory
        payload=json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)
        atomic_write_text(project_backup,payload)
        return RevisionBackup(backup_dir,project_backup,cad_backup)
    except Exception:
        # Never leave a half-created backup and never allow the caller to update
        # the active drawing after a backup failure.
        shutil.rmtree(backup_dir,ignore_errors=True)
        raise


def create_pre_external_project_backup(
    *,
    project_data: dict[str, Any],
    project_path: str | Path,
    current_cad: str | Path | None,
    loaded_doc: Any = None,
    now: datetime | None = None,
) -> RevisionBackup:
    """Snapshot the currently loaded revision before accepting an external project file.

    The in-memory Elplan data is authoritative for the backup.  For CAD we
    prefer exporting the already-loaded document, so an external OneDrive sync
    cannot silently replace the old drawing before the restore point is made.
    """
    project=Path(project_path).expanduser()
    parent=project.parent.resolve()
    stamp=(now or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    root=project_storage.backup_root_for_project_parent(parent)
    candidate=root/f"{stamp}_før_ekstern_projektopdatering"
    index=2
    while candidate.exists():
        candidate=root/f"{stamp}_før_ekstern_projektopdatering_{index:02d}"; index += 1
    candidate.mkdir(parents=True,exist_ok=False)
    cad=Path(current_cad).expanduser() if current_cad else None
    suffix=(cad.suffix.lower() if cad is not None else ".dxf")
    cad_name=f"{cad.stem if cad is not None else 'plantegning'}_lokal_revision{suffix}"
    cad_backup=candidate/cad_name
    project_backup=candidate/f"{_project_base_name(project)}_lokal_revision.elplan.json"
    try:
        if cad is not None:
            try:
                _write_loaded_cad_snapshot(loaded_doc,cad.suffix,cad_backup)
            except Exception:
                if cad.is_file(): shutil.copy2(cad,cad_backup)
                else: raise
        else:
            raise RuntimeError("Projektets plantegning kunne ikke identificeres til revisionsbackup.")
        data=dict(project_data or {})
        data["source_file"]=cad_backup.name
        atomic_write_text(project_backup,json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False))
        return RevisionBackup(candidate,project_backup,cad_backup)
    except Exception:
        shutil.rmtree(candidate,ignore_errors=True)
        raise

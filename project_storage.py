from __future__ import annotations

"""Optional local/synchronised project-library support for Elplan.

The application remains local-first. A "synced" storage root is simply a normal
local folder (for example OneDrive) which another client is responsible for
synchronising. No cloud API or login is required by Elplan.
"""

import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from storage_utils import atomic_write_text

STORAGE_SCHEMA_VERSION = 1
MODE_LEGACY = "legacy"
MODE_LOCAL = "local_library"
MODE_SYNCED = "synced_library"
VALID_MODES = {MODE_LEGACY, MODE_LOCAL, MODE_SYNCED}
PROJECT_FILENAME = "project.elplan.json"
PROJECT_INFO_FILENAME = "project-info.json"
DRAWING_DIRNAME = "drawing"
BACKUP_DIRNAME = "backups"
EXPORT_DIRNAME = "exports"


@dataclass(frozen=True)
class ProjectLayout:
    root: Path
    project_file: Path
    drawing_dir: Path
    backups_dir: Path
    exports_dir: Path
    info_file: Path


@dataclass(frozen=True)
class ProjectMigrationResult:
    layout: ProjectLayout
    drawing_file: Path
    source_reference: str
    copied_backup_items: int = 0


def normalize_storage_mode(value: Any) -> str:
    text=str(value or "").strip().lower()
    aliases={
        "":MODE_LEGACY, "legacy":MODE_LEGACY, "classic":MODE_LEGACY, "free":MODE_LEGACY,
        "local":MODE_LOCAL, "library":MODE_LOCAL, "local_library":MODE_LOCAL,
        "synced":MODE_SYNCED, "cloud":MODE_SYNCED, "onedrive":MODE_SYNCED,
        "synced_library":MODE_SYNCED,
    }
    return aliases.get(text, MODE_LEGACY)


def configured_storage(settings: Mapping[str, Any] | None) -> tuple[str, Path | None]:
    data=settings if isinstance(settings,Mapping) else {}
    mode=normalize_storage_mode(data.get("project_storage_mode"))
    raw=str(data.get("project_storage_root","") or "").strip()
    if mode == MODE_LEGACY or not raw:
        return mode,None
    return mode,Path(raw).expanduser()


def detect_onedrive_candidates(env: Mapping[str,str] | None = None) -> list[Path]:
    values=env if env is not None else os.environ
    out=[]; seen=set()
    for key in ("OneDriveCommercial","OneDriveConsumer","OneDrive"):
        raw=str(values.get(key,"") or "").strip()
        if not raw: continue
        p=Path(raw).expanduser()
        norm=os.path.normcase(str(p))
        if norm in seen: continue
        seen.add(norm); out.append(p)
    # Common fallback when OneDrive environment variables are missing.
    home=Path.home()
    try:
        for p in sorted(home.glob("OneDrive*")):
            norm=os.path.normcase(str(p))
            if p.is_dir() and norm not in seen:
                seen.add(norm); out.append(p)
    except OSError:
        pass
    return out


def sanitize_project_name(value: Any, fallback: str = "Elplan projekt") -> str:
    name=str(value or "").strip()
    if name.lower().endswith(".elplan.json"):
        name=name[:-len(".elplan.json")]
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]+',' ',name)
    name=re.sub(r'\s+',' ',name).strip(' .')
    return name[:90] or fallback


def project_name_from_path(project_path: str | Path | None, source_file: str | Path | None = None) -> str:
    if project_path:
        p=Path(project_path)
        if p.name.lower() == PROJECT_FILENAME and (p.parent/PROJECT_INFO_FILENAME).is_file():
            try:
                info=json.loads((p.parent/PROJECT_INFO_FILENAME).read_text(encoding="utf-8"))
                value=sanitize_project_name(info.get("project_name"),"")
                if value: return value
            except Exception:
                pass
        return sanitize_project_name(p.name)
    if source_file:
        return sanitize_project_name(Path(source_file).stem)
    return "Elplan projekt"


def layout_for(root: str | Path, project_name: Any) -> ProjectLayout:
    base=Path(root).expanduser()
    name=sanitize_project_name(project_name)
    project_root=base/name
    return ProjectLayout(
        root=project_root,
        project_file=project_root/PROJECT_FILENAME,
        drawing_dir=project_root/DRAWING_DIRNAME,
        backups_dir=project_root/BACKUP_DIRNAME,
        exports_dir=project_root/EXPORT_DIRNAME,
        info_file=project_root/PROJECT_INFO_FILENAME,
    )


def _unique_layout(root: str | Path, project_name: Any) -> ProjectLayout:
    initial=layout_for(root,project_name)
    if not initial.root.exists(): return initial
    base_name=sanitize_project_name(project_name)
    index=2
    while True:
        candidate=layout_for(root,f"{base_name} ({index})")
        if not candidate.root.exists(): return candidate
        index += 1


def is_structured_project(project_path: str | Path | None) -> bool:
    if not project_path: return False
    p=Path(project_path).expanduser()
    return p.name.lower() == PROJECT_FILENAME and (p.parent/PROJECT_INFO_FILENAME).is_file()


def project_root_for(project_path: str | Path | None) -> Path | None:
    if not is_structured_project(project_path): return None
    return Path(project_path).expanduser().parent


def backup_root_for_project_parent(parent: str | Path) -> Path:
    base=Path(parent).expanduser()
    # New structured project folder.
    if (base/PROJECT_INFO_FILENAME).is_file() or (base/DRAWING_DIRNAME).is_dir():
        return base/BACKUP_DIRNAME
    # Legacy layout stays unchanged for backward compatibility.
    return base/"Elplan_backups"


def _unique_destination(directory: Path, filename: str) -> Path:
    candidate=directory/filename
    if not candidate.exists(): return candidate
    stem=candidate.stem; suffix=candidate.suffix; index=2
    while True:
        option=directory/f"{stem}_{index:02d}{suffix}"
        if not option.exists(): return option
        index += 1


def _copy_legacy_backups(project_path: Path | None, target_dir: Path) -> int:
    if project_path is None: return 0
    parent=project_path.parent
    sources=[]
    for name in ("Elplan_backups",BACKUP_DIRNAME):
        source=parent/name
        if source.is_dir() and source.resolve() != target_dir.resolve(): sources.append(source)
    copied=0
    for source in sources:
        for child in source.iterdir():
            target=_unique_destination(target_dir,child.name)
            if child.is_dir(): shutil.copytree(child,target)
            elif child.is_file(): shutil.copy2(child,target)
            else: continue
            copied += 1
    return copied


def _project_info_payload(*, project_name: str, mode: str, project_file: Path, drawing_file: Path, created_at: str | None = None) -> dict[str,Any]:
    now=datetime.now().astimezone().isoformat(timespec="seconds")
    return {
        "schema_version":STORAGE_SCHEMA_VERSION,
        "project_name":sanitize_project_name(project_name),
        "storage_mode":normalize_storage_mode(mode),
        "project_file":project_file.name,
        "drawing_file":f"{DRAWING_DIRNAME}/{drawing_file.name}",
        "created_at":created_at or now,
        "updated_at":now,
    }


def create_structured_project(
    *,
    storage_root: str | Path,
    project_name: Any,
    project_data: Mapping[str,Any],
    source_cad: str | Path,
    storage_mode: str = MODE_SYNCED,
    original_project_path: str | Path | None = None,
    copy_existing_backups: bool = False,
) -> ProjectMigrationResult:
    """Create a self-contained project folder without deleting source files."""
    root=Path(storage_root).expanduser()
    root.mkdir(parents=True,exist_ok=True)
    if not root.is_dir(): raise ValueError("Projektlageret er ikke en mappe.")
    source=Path(source_cad).expanduser()
    if not source.is_file(): raise FileNotFoundError(f"Plantegningen findes ikke: {source}")
    name=sanitize_project_name(project_name)
    final=_unique_layout(root,name)
    temp=root/f".{final.root.name}.elplan-migrering-{uuid.uuid4().hex[:8]}"
    temp_layout=ProjectLayout(
        root=temp,
        project_file=temp/PROJECT_FILENAME,
        drawing_dir=temp/DRAWING_DIRNAME,
        backups_dir=temp/BACKUP_DIRNAME,
        exports_dir=temp/EXPORT_DIRNAME,
        info_file=temp/PROJECT_INFO_FILENAME,
    )
    try:
        temp_layout.drawing_dir.mkdir(parents=True,exist_ok=False)
        temp_layout.backups_dir.mkdir(parents=True,exist_ok=False)
        temp_layout.exports_dir.mkdir(parents=True,exist_ok=False)
        drawing_name=source.name
        drawing_target=temp_layout.drawing_dir/drawing_name
        shutil.copy2(source,drawing_target)
        data=dict(project_data or {})
        data["source_file"]=f"{DRAWING_DIRNAME}/{drawing_name}"
        payload=json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)
        atomic_write_text(temp_layout.project_file,payload)
        info=_project_info_payload(
            project_name=final.root.name,
            mode=storage_mode,
            project_file=temp_layout.project_file,
            drawing_file=drawing_target,
        )
        atomic_write_text(temp_layout.info_file,json.dumps(info,indent=2,ensure_ascii=False))
        copied=0
        if copy_existing_backups:
            old_path=Path(original_project_path).expanduser() if original_project_path else None
            copied=_copy_legacy_backups(old_path,temp_layout.backups_dir)
        temp.replace(final.root)
        drawing_final=final.drawing_dir/drawing_name
        return ProjectMigrationResult(final,drawing_final,f"{DRAWING_DIRNAME}/{drawing_name}",copied)
    except Exception:
        shutil.rmtree(temp,ignore_errors=True)
        raise


def touch_project_info(project_path: str | Path | None, *, source_file: str | Path | None = None) -> None:
    if not is_structured_project(project_path): return
    project=Path(project_path).expanduser(); info_path=project.parent/PROJECT_INFO_FILENAME
    try:
        current=json.loads(info_path.read_text(encoding="utf-8")) if info_path.is_file() else {}
        if not isinstance(current,dict): current={}
    except Exception:
        current={}
    current["schema_version"]=STORAGE_SCHEMA_VERSION
    current["project_name"]=sanitize_project_name(current.get("project_name") or project.parent.name)
    current["project_file"]=PROJECT_FILENAME
    if source_file:
        current["drawing_file"]=str(source_file).replace('\\','/')
    current.setdefault("created_at",datetime.now().astimezone().isoformat(timespec="seconds"))
    current["updated_at"]=datetime.now().astimezone().isoformat(timespec="seconds")
    atomic_write_text(info_path,json.dumps(current,indent=2,ensure_ascii=False))


def storage_mode_for_project(project_path: str | Path | None) -> str:
    """Return the storage mode recorded by a structured project."""
    if not is_structured_project(project_path): return MODE_LEGACY
    info_path=Path(project_path).expanduser().parent/PROJECT_INFO_FILENAME
    try:
        raw=json.loads(info_path.read_text(encoding="utf-8"))
        if isinstance(raw,dict): return normalize_storage_mode(raw.get("storage_mode"))
    except Exception:
        pass
    return MODE_LOCAL

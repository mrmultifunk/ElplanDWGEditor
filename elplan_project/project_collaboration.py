from __future__ import annotations

"""Small local-first collaboration helpers for structured Elplan projects.

The module deliberately knows nothing about OneDrive APIs.  A synchronized
project folder is still a normal folder; a heartbeat lock and content hashes
are enough to prevent the most common accidental multi-PC overwrite.
"""

import hashlib
import json
import os
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from elplan_shared.storage_utils import atomic_write_text
from elplan_project import project_storage

LOCK_FILENAME = "project.lock"
LOCK_SCHEMA_VERSION = 1
LOCK_STALE_SECONDS = 180.0


@dataclass(frozen=True)
class FileSnapshot:
    mtime_ns: int
    size: int
    sha256: str


@dataclass(frozen=True)
class LockInfo:
    path: Path | None
    token: str = ""
    computer: str = ""
    pid: int = 0
    opened_at: str = ""
    heartbeat_at: str = ""
    app_version: str = ""
    stale: bool = False
    owned_by_us: bool = False


@dataclass(frozen=True)
class LockAcquireResult:
    acquired: bool
    info: LockInfo
    created: bool = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat(timespec="seconds")


def _parse_iso(value: Any) -> datetime | None:
    text=str(value or "").strip()
    if not text: return None
    try:
        dt=datetime.fromisoformat(text.replace("Z","+00:00"))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def new_session_token() -> str:
    return uuid.uuid4().hex


def lock_path_for_project(project_path: str | Path | None) -> Path | None:
    if not project_storage.is_structured_project(project_path):
        return None
    return Path(project_path).expanduser().parent / LOCK_FILENAME


def _lock_payload(token: str, *, app_version: str, opened_at: str | None = None) -> dict[str,Any]:
    now=_iso_now()
    return {
        "schema_version":LOCK_SCHEMA_VERSION,
        "token":str(token or ""),
        "computer":socket.gethostname() or "Ukendt computer",
        "pid":int(os.getpid()),
        "opened_at":opened_at or now,
        "heartbeat_at":now,
        "app_version":str(app_version or ""),
    }


def _read_lock(path: Path, *, own_token: str = "", stale_seconds: float = LOCK_STALE_SECONDS) -> LockInfo:
    try:
        raw=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw,dict): raw={}
    except Exception:
        raw={}
    heartbeat=_parse_iso(raw.get("heartbeat_at") or raw.get("opened_at"))
    age=10**9 if heartbeat is None else max(0.0,(_utc_now()-heartbeat).total_seconds())
    token=str(raw.get("token","") or "")
    return LockInfo(
        path=path,
        token=token,
        computer=str(raw.get("computer","") or "Ukendt computer"),
        pid=int(raw.get("pid",0) or 0),
        opened_at=str(raw.get("opened_at","") or ""),
        heartbeat_at=str(raw.get("heartbeat_at","") or ""),
        app_version=str(raw.get("app_version","") or ""),
        stale=bool(age > float(stale_seconds)),
        owned_by_us=bool(own_token and token and token==own_token),
    )


def inspect_lock(project_path: str | Path | None, *, own_token: str = "") -> LockInfo:
    path=lock_path_for_project(project_path)
    if path is None or not path.exists(): return LockInfo(path=path)
    return _read_lock(path,own_token=own_token)


def acquire_lock(project_path: str | Path | None, *, token: str, app_version: str) -> LockAcquireResult:
    path=lock_path_for_project(project_path)
    if path is None:
        return LockAcquireResult(True,LockInfo(path=None,token=token,owned_by_us=True),False)
    path.parent.mkdir(parents=True,exist_ok=True)
    # Existing own lock: refresh rather than replacing it.
    if path.exists():
        info=_read_lock(path,own_token=token)
        if info.owned_by_us:
            refresh_lock(project_path,token=token,app_version=app_version)
            return LockAcquireResult(True,inspect_lock(project_path,own_token=token),False)
        if info.stale:
            try:path.unlink()
            except FileNotFoundError:pass
            except OSError:return LockAcquireResult(False,info,False)
        else:
            return LockAcquireResult(False,info,False)
    payload=_lock_payload(token,app_version=app_version)
    # Atomic create prevents two PCs that see an empty folder simultaneously
    # from both believing they own the project.
    try:
        fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL)
        with os.fdopen(fd,"w",encoding="utf-8") as handle:
            json.dump(payload,handle,indent=2,ensure_ascii=False)
            handle.flush(); os.fsync(handle.fileno())
        return LockAcquireResult(True,_read_lock(path,own_token=token),True)
    except FileExistsError:
        return LockAcquireResult(False,_read_lock(path,own_token=token),False)


def refresh_lock(project_path: str | Path | None, *, token: str, app_version: str) -> bool:
    path=lock_path_for_project(project_path)
    if path is None: return True
    if not path.exists(): return False
    info=_read_lock(path,own_token=token)
    if not info.owned_by_us: return False
    payload=_lock_payload(token,app_version=app_version,opened_at=info.opened_at or None)
    atomic_write_text(path,json.dumps(payload,indent=2,ensure_ascii=False))
    return True


def release_lock(project_path: str | Path | None, *, token: str) -> bool:
    path=lock_path_for_project(project_path)
    if path is None or not path.exists(): return True
    info=_read_lock(path,own_token=token)
    if not info.owned_by_us: return False
    try:path.unlink(); return True
    except FileNotFoundError:return True
    except OSError:return False


def file_snapshot(path: str | Path | None) -> FileSnapshot | None:
    if not path: return None
    p=Path(path).expanduser()
    try:
        st=p.stat()
        h=hashlib.sha256()
        with p.open("rb") as handle:
            for chunk in iter(lambda:handle.read(1024*1024),b""):
                h.update(chunk)
        return FileSnapshot(int(st.st_mtime_ns),int(st.st_size),h.hexdigest())
    except (OSError,FileNotFoundError):
        return None


def content_changed(path: str | Path | None, baseline: FileSnapshot | None) -> tuple[bool,FileSnapshot | None]:
    current=file_snapshot(path)
    if baseline is None: return False,current
    if current is None: return True,None
    return current.sha256 != baseline.sha256,current

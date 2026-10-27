from __future__ import annotations

"""Portable core-data and project packages for Elplan DWG Editor.

The two package types are deliberately separate:

* ``.elplancore`` contains user-scoped application data (article database,
  global BOM assemblies, price book and portable application settings).
* ``.elplanproj`` contains one project JSON and its DWG/DXF source only.

Both formats are ZIP containers with a small manifest and SHA-256 checksums.
"""

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import core_logic as core
import user_library
from storage_utils import atomic_write_json, read_json

CORE_PACKAGE_FORMAT = "elplan-core-data"
PROJECT_PACKAGE_FORMAT = "elplan-project-package"
PACKAGE_VERSION = 1
CORE_EXTENSION = ".elplancore"
PROJECT_EXTENSION = ".elplanproj"

# These values are specific to one Windows installation and are intentionally
# not transported as part of the user's core working data.
_MACHINE_LOCAL_SETTINGS = {
    "oda_exec_path",
    "recent_projects",
    "window_geometry",
    "qt_window_geometry",
    "qt_window_state",
    # Appearance belongs to the workstation/user, not to transported core data.
    # A dark workstation must not force the same choice on another PC.
    "appearance_mode",
    "dark_canvas",
    "project_storage_mode",
    "project_storage_root",
    "core_data_storage_mode",
    "core_data_root",
    "price_vat_mode",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(data: Any) -> bytes:
    return json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8")


def _manifest_base(package_format: str, app_version: str) -> dict[str, Any]:
    return {
        "format": package_format,
        "package_version": PACKAGE_VERSION,
        "application_version": str(app_version or ""),
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "files": {},
    }


def _write_zip(target: str | Path, manifest: dict[str, Any], files: dict[str, bytes]) -> Path:
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = deepcopy(manifest)
    manifest["files"] = {
        name: {"sha256": _sha256_bytes(data), "size": len(data)} for name, data in sorted(files.items())
    }
    payload = _json_bytes(manifest)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    os.close(fd)
    tmp = Path(temp_name)
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.writestr("manifest.json", payload)
            for name, data in sorted(files.items()):
                zf.writestr(name, data)
        os.replace(tmp, target)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return target


def _read_validated_package(path: str | Path, expected_format: str) -> tuple[dict[str, Any], dict[str, bytes]]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with zipfile.ZipFile(path, "r") as zf:
        names = set(zf.namelist())
        if "manifest.json" not in names:
            raise ValueError("Pakken mangler manifest.json.")
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        if not isinstance(manifest, dict) or manifest.get("format") != expected_format:
            raise ValueError("Den valgte fil er ikke den forventede Elplan-pakketype.")
        if int(manifest.get("package_version", 0) or 0) > PACKAGE_VERSION:
            raise ValueError("Pakken er lavet med et nyere pakkeformat og kan ikke importeres sikkert.")
        file_meta = manifest.get("files", {})
        if not isinstance(file_meta, dict):
            raise ValueError("Pakkens filliste er ugyldig.")
        files: dict[str, bytes] = {}
        for name, meta in file_meta.items():
            pure = PurePosixPath(str(name))
            if pure.is_absolute() or ".." in pure.parts or str(name) not in names:
                raise ValueError(f"Ugyldig filsti i pakken: {name}")
            data = zf.read(str(name))
            checksum = str((meta or {}).get("sha256", "") or "") if isinstance(meta, dict) else ""
            if checksum and _sha256_bytes(data) != checksum:
                raise ValueError(f"Checksum stemmer ikke for {name}.")
            files[str(name)] = data
        return manifest, files


def portable_settings(settings: dict | None) -> dict:
    data = dict(settings or {})
    return {k: deepcopy(v) for k, v in data.items() if k not in _MACHINE_LOCAL_SETTINGS}


def core_data_summary() -> dict[str, int]:
    articles = user_library.load_core_article_catalog()
    assemblies = user_library.load_global_bom_assemblies()
    prices = user_library.load_article_prices()
    settings = portable_settings(core.load_app_settings())
    return {
        "articles": len(articles),
        "assemblies": len(assemblies),
        "prices": len(prices),
        "settings": len(settings),
    }


def export_core_data(path: str | Path, app_version: str) -> Path:
    articles = user_library.load_core_article_catalog()
    assemblies, assembly_articles = user_library.load_global_bom_library()
    prices = user_library.load_article_prices()
    settings = portable_settings(core.load_app_settings())
    files = {
        "core/articles.json": _json_bytes({"version": user_library.ARTICLE_CATALOG_VERSION, "articles": articles}),
        "core/bom_assemblies.json": _json_bytes({"version": user_library.BOM_LIBRARY_VERSION, "assemblies": assemblies, "articles": assembly_articles}),
        "core/article_prices.json": _json_bytes({"version": user_library.PRICEBOOK_VERSION, "prices": prices}),
        "core/settings.json": _json_bytes({"version": 1, "settings": settings}),
    }
    manifest = _manifest_base(CORE_PACKAGE_FORMAT, app_version)
    manifest["summary"] = {
        "articles": len(articles),
        "assemblies": len(assemblies),
        "prices": len(prices),
    }
    return _write_zip(path, manifest, files)


def _decode_json_file(files: dict[str, bytes], name: str, default: Any) -> Any:
    data = files.get(name)
    if data is None:
        return deepcopy(default)
    value = json.loads(data.decode("utf-8"))
    return value


def backup_current_core_data(app_version: str = "") -> Path:
    directory = user_library.core_data_dir() / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return export_core_data(directory / f"core-before-import-{stamp}{CORE_EXTENSION}", app_version)


def import_core_data(path: str | Path, *, replace: bool = True, app_version: str = "") -> dict[str, Any]:
    manifest, files = _read_validated_package(path, CORE_PACKAGE_FORMAT)
    article_raw = _decode_json_file(files, "core/articles.json", {})
    assembly_raw = _decode_json_file(files, "core/bom_assemblies.json", {})
    price_raw = _decode_json_file(files, "core/article_prices.json", {})
    settings_raw = _decode_json_file(files, "core/settings.json", {})

    incoming_articles = core.normalize_article_catalog(article_raw.get("articles", []) if isinstance(article_raw, dict) else article_raw)
    incoming_assemblies = core.normalize_bom_assemblies(assembly_raw.get("assemblies", []) if isinstance(assembly_raw, dict) else [])
    incoming_assembly_articles = core.normalize_article_catalog(assembly_raw.get("articles", []) if isinstance(assembly_raw, dict) else [])
    incoming_prices = user_library.normalize_article_prices(price_raw)
    incoming_settings = portable_settings(settings_raw.get("settings", {}) if isinstance(settings_raw, dict) else {})

    backup = backup_current_core_data(app_version)

    if replace:
        articles = incoming_articles
        assemblies = incoming_assemblies
        assembly_articles = incoming_assembly_articles
        prices = incoming_prices
    else:
        article_map = {a["article_no"]: a for a in user_library.load_core_article_catalog()}
        article_map.update({a["article_no"]: a for a in incoming_articles})
        articles = core.normalize_article_catalog(article_map.values())
        current_assemblies, current_assembly_articles = user_library.load_global_bom_library()
        assembly_map = {a["id"]: a for a in current_assemblies}
        assembly_map.update({a["id"]: a for a in incoming_assemblies})
        assemblies = core.normalize_bom_assemblies(assembly_map.values())
        aa_map = {a["article_no"]: a for a in current_assembly_articles}
        aa_map.update({a["article_no"]: a for a in incoming_assembly_articles})
        assembly_articles = core.normalize_article_catalog(aa_map.values())
        prices = user_library.load_article_prices()
        prices.update(incoming_prices)

    user_library.save_core_article_catalog(articles)
    # Preserve the assembly article snapshot exactly as a transport fallback.
    assembly_catalog = core.normalize_article_catalog(list(articles) + list(assembly_articles))
    user_library.save_global_bom_assemblies(assemblies, assembly_catalog)
    user_library.save_article_prices(prices)

    current_settings = core.load_app_settings()
    machine_local = {k: deepcopy(v) for k, v in current_settings.items() if k in _MACHINE_LOCAL_SETTINGS}
    if replace:
        new_settings = dict(incoming_settings)
    else:
        new_settings = portable_settings(current_settings)
        new_settings.update(incoming_settings)
    new_settings.update(machine_local)
    core.save_app_settings(new_settings)

    return {
        "manifest": manifest,
        "backup": str(backup),
        "articles": len(articles),
        "assemblies": len(assemblies),
        "prices": len(prices),
    }


def _binding_article_numbers(project_data: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    bindings = core.normalize_symbol_article_bindings(project_data.get("placement_articles", {}))
    for parts in bindings.values():
        for rows in parts.values():
            for row in rows:
                no = str(row.get("article_no", "") or "").strip()
                if no:
                    out.add(no)
    for no in core.normalize_cable_article_bindings(project_data.get("cable_instance_articles", {})).values():
        if no:
            out.add(str(no))
    return out


def _binding_assembly_ids(project_data: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for parts in core.normalize_symbol_assembly_bindings(project_data.get("placement_assemblies", {})).values():
        for value in parts.values():
            if value:
                out.add(str(value))
    return out


def _custom_symbol_codes(project_data: dict[str, Any]) -> set[str]:
    out=set()
    for row in project_data.get("placements", []) or []:
        if isinstance(row,dict):
            code=str(row.get("symbol","") or "")
            if core.is_custom_combo_symbol(code):out.add(code)
    return out


def sanitize_project_data(data: dict[str, Any], *, source_file: str) -> dict[str, Any]:
    """Remove user-scoped library data from a project payload."""
    out = deepcopy(data)
    out["source_file"] = str(source_file)
    for key in ("article_catalog", "bom_assemblies", "custom_symbols"):
        out.pop(key, None)
    return out


def export_project_package(project_path: str | Path, source_path: str | Path, output_path: str | Path, app_version: str) -> Path:
    project_path = Path(project_path)
    source_path = Path(source_path)
    if not project_path.is_file():
        raise FileNotFoundError("Projektfilen findes ikke.")
    if not source_path.is_file():
        raise FileNotFoundError("Projektets DWG/DXF-kildefil findes ikke.")
    data = json.loads(project_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Projektfilen er ugyldig.")
    project_name = project_path.name
    source_name = source_path.name
    portable = sanitize_project_data(data, source_file=f"../source/{source_name}")
    files = {
        f"project/{project_name}": _json_bytes(portable),
        f"source/{source_name}": source_path.read_bytes(),
    }
    manifest = _manifest_base(PROJECT_PACKAGE_FORMAT, app_version)
    manifest.update({
        "project_file": f"project/{project_name}",
        "source_file": f"source/{source_name}",
        "project_name": project_path.stem.replace(".elplan", ""),
        "dependencies": {
            "article_numbers": sorted(_binding_article_numbers(portable)),
            "assembly_ids": sorted(_binding_assembly_ids(portable)),
            "custom_symbol_codes": sorted(_custom_symbol_codes(portable)),
        },
    })
    return _write_zip(output_path, manifest, files)


def inspect_project_package(path: str | Path) -> dict[str, Any]:
    manifest, _files = _read_validated_package(path, PROJECT_PACKAGE_FORMAT)
    return manifest


def import_project_package(path: str | Path, destination_dir: str | Path) -> dict[str, Path | dict]:
    manifest, files = _read_validated_package(path, PROJECT_PACKAGE_FORMAT)
    project_member = str(manifest.get("project_file", "") or "")
    source_member = str(manifest.get("source_file", "") or "")
    if project_member not in files or source_member not in files:
        raise ValueError("Projektpakken mangler projektfil eller DWG/DXF-kilde.")

    root = Path(destination_dir)
    root.mkdir(parents=True, exist_ok=True)
    project_dir = root / "project"
    source_dir = root / "source"
    project_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    project_target = project_dir / Path(PurePosixPath(project_member).name)
    source_target = source_dir / Path(PurePosixPath(source_member).name)

    source_target.write_bytes(files[source_member])
    project_data = json.loads(files[project_member].decode("utf-8"))
    if not isinstance(project_data, dict):
        raise ValueError("Projektdata i pakken er ugyldige.")
    project_data = sanitize_project_data(project_data, source_file=os.path.relpath(source_target, project_target.parent))
    atomic_write_json(project_target, project_data)
    return {"manifest": manifest, "project": project_target, "source": source_target}

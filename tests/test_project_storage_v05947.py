import json
from pathlib import Path

import project_storage


def test_onedrive_detection_and_mode_normalization(tmp_path):
    env={"OneDriveCommercial":str(tmp_path/"OneDrive - Firma"),"OneDrive":str(tmp_path/"OneDrive - Firma")}
    rows=project_storage.detect_onedrive_candidates(env)
    assert rows==[tmp_path/"OneDrive - Firma"]
    assert project_storage.normalize_storage_mode("onedrive")==project_storage.MODE_SYNCED


def test_structured_project_migration_keeps_original_and_uses_relative_cad(tmp_path):
    old=tmp_path/"old"; old.mkdir()
    cad=old/"hus.dxf"; cad.write_text("0\nEOF\n",encoding="utf-8")
    project=old/"hus.elplan.json"; project.write_text("{}",encoding="utf-8")
    backup=old/"Elplan_backups"/"rev1"; backup.mkdir(parents=True); (backup/"note.txt").write_text("old",encoding="utf-8")
    data={"version":"0.59.81","source_file":str(cad),"placements":[]}
    result=project_storage.create_structured_project(
        storage_root=tmp_path/"OneDrive"/"Elplan"/"Projekter",project_name="Hus",project_data=data,
        source_cad=cad,storage_mode=project_storage.MODE_SYNCED,original_project_path=project,copy_existing_backups=True,
    )
    assert project.exists() and cad.exists()
    assert result.layout.project_file.is_file()
    payload=json.loads(result.layout.project_file.read_text(encoding="utf-8"))
    assert payload["source_file"]=="drawing/hus.dxf"
    assert result.drawing_file.read_text(encoding="utf-8")==cad.read_text(encoding="utf-8")
    assert result.layout.info_file.is_file()
    assert (result.layout.backups_dir/"rev1"/"note.txt").read_text(encoding="utf-8")=="old"


def test_structured_backup_root(tmp_path):
    (tmp_path/project_storage.PROJECT_INFO_FILENAME).write_text("{}",encoding="utf-8")
    assert project_storage.backup_root_for_project_parent(tmp_path)==tmp_path/"backups"
    legacy=tmp_path/"legacy"; legacy.mkdir()
    assert project_storage.backup_root_for_project_parent(legacy)==legacy/"Elplan_backups"

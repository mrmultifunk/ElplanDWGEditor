import json
from datetime import datetime, timedelta, timezone

import project_collaboration as collab
import project_storage


def _structured(tmp_path):
    root=tmp_path/'P'; root.mkdir(); (root/'drawing').mkdir(); (root/'backups').mkdir(); (root/'exports').mkdir()
    project=root/project_storage.PROJECT_FILENAME; project.write_text('{"version":"0.59.73"}',encoding='utf-8')
    (root/project_storage.PROJECT_INFO_FILENAME).write_text(json.dumps({'storage_mode':project_storage.MODE_SYNCED}),encoding='utf-8')
    return project


def test_lock_acquire_foreign_and_release(tmp_path):
    project=_structured(tmp_path)
    one=collab.acquire_lock(project,token='one',app_version='0.59.73')
    assert one.acquired and (project.parent/'project.lock').is_file()
    two=collab.acquire_lock(project,token='two',app_version='0.59.73')
    assert not two.acquired and two.info.token=='one'
    assert not collab.release_lock(project,token='two')
    assert collab.release_lock(project,token='one')


def test_stale_lock_can_be_reclaimed(tmp_path):
    project=_structured(tmp_path); lock=project.parent/'project.lock'
    old=(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat()
    lock.write_text(json.dumps({'token':'old','computer':'OLD','heartbeat_at':old}),encoding='utf-8')
    result=collab.acquire_lock(project,token='new',app_version='0.59.73')
    assert result.acquired
    assert collab.inspect_lock(project,own_token='new').owned_by_us


def test_file_snapshot_detects_external_content(tmp_path):
    project=_structured(tmp_path); before=collab.file_snapshot(project)
    project.write_text('{"version":"external"}',encoding='utf-8')
    changed,after=collab.content_changed(project,before)
    assert changed and after.sha256 != before.sha256


def test_structured_project_reports_synced_mode(tmp_path):
    project=_structured(tmp_path)
    assert project_storage.storage_mode_for_project(project)==project_storage.MODE_SYNCED

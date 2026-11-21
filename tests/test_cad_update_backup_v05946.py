import json
from datetime import datetime
from pathlib import Path

from elplan_project.project_revision_backup import create_pre_cad_update_backup

ROOT=Path(__file__).resolve().parents[1]


class FakeDxfDoc:
    def __init__(self, content="LOADED ORIGINAL"):
        self.content=content
    def saveas(self, path):
        Path(path).write_text(self.content,encoding="utf-8")


def test_backup_pair_for_new_cad_path_copies_old_source_and_retargets_project(tmp_path):
    project_path=tmp_path/'house.elplan.json'
    old=tmp_path/'plan_old.dxf'; old.write_text('OLD CAD',encoding='utf-8')
    new=tmp_path/'plan_new.dxf'; new.write_text('NEW CAD',encoding='utf-8')
    result=create_pre_cad_update_backup(
        project_data={'version':'0.59.85','source_file':'plan_old.dxf','placements':[{'uid':'S1'}]},
        project_path=project_path,current_cad=old,target_cad=new,
        loaded_doc=FakeDxfDoc(),now=datetime(2026,8,30,15,10,0),
    )
    assert result.cad_path.read_text(encoding='utf-8')=='OLD CAD'
    data=json.loads(result.project_path.read_text(encoding='utf-8'))
    assert data['source_file']==result.cad_path.name
    assert data['placements']==[{'uid':'S1'}]
    assert result.directory.parent.name=='Elplan_backups'


def test_same_path_reload_uses_loaded_original_not_overwritten_disk_file(tmp_path):
    project_path=tmp_path/'house.elplan.json'
    cad=tmp_path/'plan.dxf'; cad.write_text('NEW REVISION ON DISK',encoding='utf-8')
    result=create_pre_cad_update_backup(
        project_data={'version':'0.59.85','source_file':'plan.dxf'},
        project_path=project_path,current_cad=cad,target_cad=cad,
        loaded_doc=FakeDxfDoc('OLD REVISION STILL LOADED'),now=datetime(2026,8,30,15,11,0),
    )
    assert result.cad_path.read_text(encoding='utf-8')=='OLD REVISION STILL LOADED'


def test_update_flow_requires_backup_before_active_doc_replacement():
    source=(ROOT/'elplan_qt/qt_project_open.py').read_text(encoding='utf-8')
    backup=source.index('revision_backup=create_pre_cad_update_backup')
    replace=source.index('self.doc=new_doc')
    assert backup < replace
    assert 'Sikkerhedskopi kunne ikke oprettes' in source
    assert 'Elplan_backups' in source

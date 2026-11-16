import json
from datetime import datetime
from pathlib import Path

import project_storage
from project_revision_backup import create_pre_external_project_backup


def test_external_revision_backup_preserves_project_and_cad(tmp_path):
    root=tmp_path/'P'; (root/'drawing').mkdir(parents=True); (root/'backups').mkdir(); (root/'exports').mkdir()
    project=root/'project.elplan.json'
    (root/'project-info.json').write_text(json.dumps({'storage_mode':'synced_library'}),encoding='utf-8')
    cad=root/'drawing'/'plan.dxf'; cad.write_text('OLD CAD',encoding='utf-8')
    project.write_text('{}',encoding='utf-8')
    data={'version':'0.59.82','source_file':'drawing/plan.dxf','placements':[{'uid':'local'}]}
    result=create_pre_external_project_backup(project_data=data,project_path=project,current_cad=cad,loaded_doc=None,now=datetime(2026,9,1,12,0,0))
    assert result.directory.parent==root/'backups'
    restored=json.loads(result.project_path.read_text(encoding='utf-8'))
    assert restored['placements']==[{'uid':'local'}]
    assert result.cad_path.read_text(encoding='utf-8')=='OLD CAD'

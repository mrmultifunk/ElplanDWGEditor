import json
import os
import zipfile
from pathlib import Path

import core_logic as core
import portability
import user_library
from project_model import ProjectDocument, APP_VERSION


def _set_user_dir(tmp_path, monkeypatch):
    user_dir=tmp_path/'userdata'
    monkeypatch.setenv('ELPLAN_USER_DATA_DIR',str(user_dir))
    return user_dir


def test_core_package_contains_core_data_only(tmp_path, monkeypatch):
    _set_user_dir(tmp_path,monkeypatch)
    user_library.save_core_article_catalog([
        {'article_no':'USR-1','description':'Brugerartikel','manufacturer':'Test','unit':'stk','kind':'component'}
    ])
    user_library.save_article_prices({'USR-1':{'unit_price':12.5,'price_currency':'DKK'}})
    user_library.save_global_bom_assemblies([
        {'id':'asm1','name':'Testliste','items':[{'article_no':'USR-1','qty':2}]}
    ],user_library.load_core_article_catalog())
    core.save_app_settings({'favorite_symbols':['socket'],'oda_exec_path':'C:/machine/ODAFileConverter.exe','recent_projects':['C:/x.elplan.json'],'qt_window_geometry':'abc','qt_window_state':'def'})
    out=portability.export_core_data(tmp_path/'core.elplancore',APP_VERSION)
    with zipfile.ZipFile(out) as zf:
        names=set(zf.namelist())
        assert 'core/articles.json' in names
        assert 'core/bom_assemblies.json' in names
        assert 'core/article_prices.json' in names
        assert 'core/settings.json' in names
        assert not any(name.startswith('project/') or name.startswith('source/') for name in names)
        settings=json.loads(zf.read('core/settings.json'))['settings']
        assert settings['favorite_symbols']==['socket']
        assert 'oda_exec_path' not in settings
        assert 'recent_projects' not in settings
        assert 'qt_window_geometry' not in settings
        assert 'qt_window_state' not in settings


def test_project_package_contains_project_and_cad_but_no_core_database(tmp_path, monkeypatch):
    _set_user_dir(tmp_path,monkeypatch)
    cad=tmp_path/'plan.dxf'; cad.write_text('0\nSECTION\n0\nEOF\n',encoding='utf-8')
    project=tmp_path/'house.elplan.json'
    raw={
        'version':'0.44.5','source_file':str(cad),
        'placements':[],'cables':[],'texts':[],'layer_visibility':{},
        'article_catalog':[{'article_no':'A1','description':'Must not travel','unit':'stk'}],
        'bom_assemblies':[{'id':'a','name':'Must not travel','items':[]}],
        'custom_symbols':[{'code':'custom_combo|switch_1|none','name':'Mine'}],
        'placement_articles':{'p1':{'symbol':[{'article_no':'A1','qty':1}]}},
        'placement_assemblies':{'p1':{'symbol':'asm1'}},
        'cable_instance_articles':{},
    }
    project.write_text(json.dumps(raw),encoding='utf-8')
    out=portability.export_project_package(project,cad,tmp_path/'house.elplanproj',APP_VERSION)
    with zipfile.ZipFile(out) as zf:
        names=set(zf.namelist())
        assert any(n.startswith('project/') for n in names)
        assert any(n.startswith('source/') for n in names)
        assert not any(n.startswith('core/') for n in names)
        manifest=json.loads(zf.read('manifest.json'))
        pdata=json.loads(zf.read(manifest['project_file']))
        assert 'article_catalog' not in pdata
        assert 'bom_assemblies' not in pdata
        assert 'custom_symbols' not in pdata
        assert pdata['placement_articles']
        assert manifest['dependencies']['article_numbers']==['A1']
        assert manifest['dependencies']['assembly_ids']==['asm1']


def test_project_package_import_uses_relative_cad_link(tmp_path, monkeypatch):
    _set_user_dir(tmp_path,monkeypatch)
    cad=tmp_path/'plan.dxf'; cad.write_text('0\nSECTION\n0\nEOF\n',encoding='utf-8')
    project=tmp_path/'house.elplan.json'
    project.write_text(json.dumps({'version':APP_VERSION,'source_file':str(cad),'placements':[],'cables':[],'texts':[],'layer_visibility':{}}),encoding='utf-8')
    pkg=portability.export_project_package(project,cad,tmp_path/'house.elplanproj',APP_VERSION)
    result=portability.import_project_package(pkg,tmp_path/'imported')
    pdata=json.loads(Path(result['project']).read_text(encoding='utf-8'))
    assert not Path(pdata['source_file']).is_absolute()
    resolved=Path(result['project']).parent/pdata['source_file']
    assert resolved.resolve()==Path(result['source']).resolve()
    assert resolved.is_file()


def test_core_import_restores_articles_assemblies_prices_and_preserves_machine_settings(tmp_path, monkeypatch):
    _set_user_dir(tmp_path,monkeypatch)
    user_library.save_core_article_catalog([{'article_no':'FROM-PC1','description':'x','unit':'stk'}])
    user_library.save_global_bom_assemblies([{'id':'asm-pc1','name':'PC1','items':[]}],user_library.load_core_article_catalog())
    user_library.save_article_prices({'FROM-PC1':{'unit_price':99,'price_currency':'DKK'}})
    core.save_app_settings({'favorite_symbols':['socket'],'oda_exec_path':'C:/pc1/oda.exe'})
    pkg=portability.export_core_data(tmp_path/'transfer.elplancore',APP_VERSION)

    # Simulate different PC state in the same isolated data directory.
    user_library.save_core_article_catalog([{'article_no':'LOCAL','description':'local','unit':'stk'}])
    user_library.save_global_bom_assemblies([],[])
    user_library.save_article_prices({})
    core.save_app_settings({'favorite_symbols':['spot'],'oda_exec_path':'D:/pc2/ODAFileConverter.exe'})
    result=portability.import_core_data(pkg,replace=True,app_version=APP_VERSION)
    articles={a['article_no'] for a in user_library.load_core_article_catalog()}
    assert 'FROM-PC1' in articles
    assert 'LOCAL' not in articles
    assert any(a['id']=='asm-pc1' for a in user_library.load_global_bom_assemblies())
    assert user_library.load_article_prices()['FROM-PC1']['unit_price']==99
    settings=core.load_app_settings()
    assert settings['favorite_symbols']==['socket']
    assert settings['oda_exec_path']=='D:/pc2/ODAFileConverter.exe'
    assert Path(result['backup']).is_file()


def test_project_document_0450_does_not_serialize_core_libraries(tmp_path):
    doc=ProjectDocument()
    doc.source_file='plan.dxf'
    doc.raw={
        'article_catalog':[{'article_no':'A1','description':'x','unit':'stk'}],
        'bom_assemblies':[{'id':'x','name':'x','items':[]}],
        'custom_symbols':[{'code':'custom_combo|switch_1|none','name':'x'}],
        'placement_articles':{'uid':{'symbol':[{'article_no':'A1','qty':1}]}}
    }
    data=doc.to_dict()
    assert data['version']=='0.59.82'
    assert 'article_catalog' not in data
    assert 'bom_assemblies' not in data
    assert 'custom_symbols' not in data
    assert data['placement_articles']


def test_legacy_project_core_data_migrates_out_of_project(tmp_path, monkeypatch):
    _set_user_dir(tmp_path,monkeypatch)
    raw={
        'article_catalog':[{'article_no':'LEGACY-A','description':'Legacy','unit':'stk'}],
        'bom_assemblies':[{'id':'legacy-asm','name':'Legacy list','items':[{'article_no':'LEGACY-A','qty':1}]}],
        'custom_symbols':[{'code':'custom_combo|switch_1|none','name':'Legacy custom'}],
        'placement_articles':{'p':{'symbol':[{'article_no':'LEGACY-A','qty':1}]}}
    }
    result=user_library.migrate_legacy_project_core_data(raw)
    assert result['changed'] is True
    assert 'article_catalog' not in raw
    assert 'bom_assemblies' not in raw
    assert 'custom_symbols' not in raw
    assert raw['placement_articles']  # project relation remains project data
    assert 'LEGACY-A' in {a['article_no'] for a in user_library.load_core_article_catalog()}
    assert 'legacy-asm' in {a['id'] for a in user_library.load_global_bom_assemblies()}
    assert any(r.get('code')=='custom_combo|switch_1|none' for r in core.load_app_settings().get('custom_symbols',[]))


def test_reopening_legacy_project_cannot_roll_back_newer_core_article(tmp_path, monkeypatch):
    _set_user_dir(tmp_path,monkeypatch)
    # First migration creates a legacy-only custom article.
    raw={'article_catalog':[{'article_no':'LEG-CUSTOM','description':'Old project copy','unit':'stk'}]}
    user_library.migrate_legacy_project_core_data(raw)
    articles=user_library.load_core_article_catalog()
    for article in articles:
        if article['article_no']=='LEG-CUSTOM':
            article['description']='Newer core edit'
    user_library.save_core_article_catalog(articles)
    # Simulate reopening an unsaved old project containing the stale snapshot.
    raw2={'article_catalog':[{'article_no':'LEG-CUSTOM','description':'Old project copy','unit':'stk'}]}
    user_library.migrate_legacy_project_core_data(raw2)
    lookup={a['article_no']:a for a in user_library.load_core_article_catalog()}
    assert lookup['LEG-CUSTOM']['description']=='Newer core edit'


def test_qt_menu_exposes_separate_core_and_project_transfer_actions():
    source=Path('qt_app.py').read_text(encoding='utf-8')
    assert 'Eksportér kernedata…' in source
    assert 'Importér kernedata…' in source
    assert 'Eksportér projektpakke…' in source
    assert 'Importér projektpakke…' in source
    assert 'file_menu.addMenu("Overfør / backup")' in source

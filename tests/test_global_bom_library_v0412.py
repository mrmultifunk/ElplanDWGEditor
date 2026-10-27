from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import core_logic as core
import user_library


def test_global_bom_library_is_user_scoped_and_self_contained():
    old=os.environ.get('ELPLAN_USER_DATA_DIR')
    try:
        with tempfile.TemporaryDirectory() as td:
            os.environ['ELPLAN_USER_DATA_DIR']=td
            assemblies=[{
                'id':'global-test','name':'FUGA test','description':'global',
                'items':[{'article_no':'A-1','qty':2}],
            }]
            catalog=[{
                'article_no':'A-1','description':'Testartikel','manufacturer':'LK',
                'unit':'stk','ean':'5700000000000',
            }]
            path=user_library.save_global_bom_assemblies(assemblies,catalog)
            assert path.parent==Path(td)
            assert path.is_file()
            loaded,articles=user_library.load_global_bom_library()
            assert loaded[0]['id']=='global-test'
            assert loaded[0]['items']==[{'article_no':'A-1','qty':2.0}]
            assert articles[0]['article_no']=='A-1'
            assert articles[0]['ean']=='5700000000000'
            raw=json.loads(path.read_text(encoding='utf-8'))
            assert raw['version']==5
            assert raw['assemblies'][0]['name']=='FUGA test'
    finally:
        if old is None: os.environ.pop('ELPLAN_USER_DATA_DIR',None)
        else: os.environ['ELPLAN_USER_DATA_DIR']=old


def test_merge_migrates_legacy_project_assembly_without_overwriting_global():
    old=os.environ.get('ELPLAN_USER_DATA_DIR')
    try:
        with tempfile.TemporaryDirectory() as td:
            os.environ['ELPLAN_USER_DATA_DIR']=td
            user_library.save_global_bom_assemblies([
                {'id':'same','name':'Global version','items':[{'article_no':'G','qty':1}]}
            ],[{'article_no':'G','description':'Global','unit':'stk'}])
            merged,added=user_library.merge_global_bom_assemblies([
                {'id':'same','name':'Old project version','items':[{'article_no':'OLD','qty':1}]},
                {'id':'new','name':'Migreret','items':[{'article_no':'N','qty':1}]},
            ],[{'article_no':'N','description':'Ny','unit':'stk'}])
            lookup={a['id']:a for a in merged}
            assert added==1
            assert lookup['same']['name']=='Global version'
            assert lookup['new']['name']=='Migreret'
            _,articles=user_library.load_global_bom_library()
            assert {a['article_no'] for a in articles}>={'G','N'}
    finally:
        if old is None: os.environ.pop('ELPLAN_USER_DATA_DIR',None)
        else: os.environ['ELPLAN_USER_DATA_DIR']=old


def test_global_assembly_can_drive_bom_in_another_project():
    assemblies=[{'id':'x','name':'Standard','items':[{'article_no':'A','qty':2}]}]
    p1=core.Placement(symbol='switch_1',x=0,y=0)
    rows,missing=core.build_bom(
        [p1],
        [{'article_no':'A','description':'Artikel','unit':'stk'}],
        {},[],{},None,0,assemblies,{p1.uid:{'symbol':'x'}},
    )
    assert not missing
    assert rows[0]['article_no']=='A'
    assert rows[0]['qty']==2


def test_article_picker_uses_debounce_and_model_population():
    source=Path('qt_articles.py').read_text(encoding='utf-8')
    assert 'self._search_timer.setInterval(180)' in source
    assert 'self._search_timer.timeout.connect(self._refresh)' in source
    assert 'self.table_model.set_rows(visible)' in source
    picker=source[source.index('class ArticlePickerDialog'):source.index('class AssemblyEditDialog')]
    assert 'def _populate_visible_chunk' not in picker
    assert 'self.std_table_model.set_rows(visible,local)' in source
    assert 'self._predefined_enriched' in source

from pathlib import Path

import core_logic as core
from elplan_project.project_model import ProjectDocument


def test_one_explicit_socket_binding_does_not_spread_to_same_symbol_type():
    placements=[core.Placement('socket',i*100,0) for i in range(19)]
    catalog=[{'article_no':'S1','description':'Stikkontakt','unit':'stk'}]
    bindings={placements[0].uid:{'symbol':[{'article_no':'S1','qty':1}]}}
    rows,missing=core.build_bom(placements,catalog,bindings)
    assert [(row['article_no'],row['qty']) for row in rows]==[('S1',1.0)]
    assert len(missing)==1
    assert missing[0]['count']==18
    assert missing[0]['detail']=='Ingen artikel/stykliste tilknyttet'


def test_one_explicit_cable_binding_does_not_spread_to_same_cable_spec():
    cables=[core.CablePlacement(points=[(0,0),(10,0)],cable_spec='3G1,5') for _ in range(3)]
    catalog=[{'article_no':'K1','description':'Afmålt kabel','kind':'cable','unit':'m','package_length_m':0}]
    rows,missing=core.build_bom([],catalog,{},cables,{cables[0].uid:'K1'},1.0,0.0)
    assert len(rows)==1 and rows[0]['qty']==10.0
    assert len(missing)==1 and missing[0]['count']==2


def test_cable_uid_is_added_to_legacy_project_and_roundtrips(tmp_path):
    path=tmp_path/'legacy.elplan.json'
    path.write_text('{"version":"0.42.2","source_file":"","placements":[],"cables":[{"points":[[0,0],[10,0]],"cable_spec":"3G1,5"}],"texts":[]}',encoding='utf-8')
    doc=ProjectDocument.load(path)
    assert doc.cables[0].uid
    uid=doc.cables[0].uid
    doc.save(path)
    loaded=ProjectDocument.load(path)
    assert loaded.cables[0].uid==uid


def test_qt_bom_manager_uses_instance_fields_not_legacy_type_fields():
    source=Path('elplan_qt/qt_articles.py').read_text(encoding='utf-8')
    manager=source[source.index('class BomManagerDialog'):]
    assert 'window.project.raw.get("placement_articles",{})' in manager
    assert 'window.project.raw.get("placement_assemblies",{})' in manager
    assert 'window.project.raw.get("cable_instance_articles",{})' in manager
    assert 'self.symbol_combo.addItem' in manager and ',p.uid)' in manager
    assert 'self.cable_bindings[uid]=article_no' in manager

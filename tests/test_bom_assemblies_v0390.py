from pathlib import Path
import tempfile

import core_logic as core
from project_model import ProjectDocument, APP_VERSION


def placement(symbol, uid=None):
    return core.Placement(uid=uid or ('u'+symbol), symbol=symbol, x=0, y=0, rotation=0, size=500)


def test_assembly_overrides_manual_without_deleting_manual_rows():
    catalog=[
        {'article_no':'A','description':'Indsats','unit':'stk'},
        {'article_no':'B','description':'Tangent','unit':'stk'},
        {'article_no':'M','description':'Manuel','unit':'stk'},
    ]
    assemblies=[{'id':'slim1','name':'SLIM 1M','items':[{'article_no':'A','qty':1},{'article_no':'B','qty':2}]}]
    p1=placement('switch_1','p1')
    manual={p1.uid:{'symbol':[{'article_no':'M','qty':1}]}}
    selected={p1.uid:{'symbol':'slim1'}}
    rows,missing=core.build_bom([p1],catalog,manual,assemblies=assemblies,assembly_bindings=selected)
    got={r['article_no']:r['qty'] for r in rows}
    assert got=={'A':1.0,'B':2.0}
    assert missing==[]
    # Den manuelle række må fortsat ligge i den separate model.
    assert core.normalize_symbol_article_bindings(manual)['p1']['symbol'][0]['article_no']=='M'


def test_manual_is_used_when_no_assembly_selected():
    catalog=[{'article_no':'M','unit':'stk'}]
    p1=placement('switch_1','p1')
    manual={p1.uid:{'symbol':[{'article_no':'M','qty':1.5}]}}
    rows,missing=core.build_bom([p1],catalog,manual,assemblies=[],assembly_bindings={})
    assert len(rows)==1 and rows[0]['article_no']=='M' and rows[0]['qty']==1.5
    assert missing==[]


def test_combo_parts_can_use_different_assemblies():
    symbol=core.make_custom_combo_code(['switch_1','switch_1','switch_2way'],'socket')
    catalog=[{'article_no':x,'unit':'stk'} for x in ('P1','P2','K','S','F')]
    assemblies=[
        {'id':'p1','name':'1P A','items':[{'article_no':'P1','qty':1}]},
        {'id':'p2','name':'1P B','items':[{'article_no':'P2','qty':1}]},
        {'id':'k','name':'Korr','items':[{'article_no':'K','qty':1}]},
        {'id':'s','name':'Stik','items':[{'article_no':'S','qty':1}]},
        {'id':'f','name':'Fælles','items':[{'article_no':'F','qty':1}]},
    ]
    placements=[placement(symbol,'c1'),placement(symbol,'c2')]
    part_sel={'module:1':'p1','module:2':'p2','module:3':'k','socket':'s','common':'f'}
    selected={p.uid:part_sel for p in placements}
    rows,missing=core.build_bom(placements,catalog,{},assemblies=assemblies,assembly_bindings=selected)
    got={r['article_no']:r['qty'] for r in rows}
    assert got=={'F':2.0,'K':2.0,'P1':2.0,'P2':2.0,'S':2.0}
    assert missing==[]


def test_assembly_edit_propagates_to_all_uses():
    catalog=[{'article_no':'A','unit':'stk'},{'article_no':'B','unit':'stk'}]
    placements=[placement('switch_1','s1'),placement('switch_1','s2')]
    selected={p.uid:{'symbol':'std'} for p in placements}
    first=[{'id':'std','name':'Standard','items':[{'article_no':'A','qty':1}]}]
    rows,_=core.build_bom(placements,catalog,{},assemblies=first,assembly_bindings=selected)
    assert {r['article_no']:r['qty'] for r in rows}=={'A':2.0}
    changed=[{'id':'std','name':'Standard','items':[{'article_no':'A','qty':1},{'article_no':'B','qty':1}]}]
    rows,_=core.build_bom(placements,catalog,{},assemblies=changed,assembly_bindings=selected)
    assert {r['article_no']:r['qty'] for r in rows}=={'A':2.0,'B':2.0}


def test_project_roundtrip_assemblies():
    doc=ProjectDocument.from_cad(str(Path(__file__).resolve().parents[1] / 'examples' / 'demo_floor.dxf'))
    doc.raw['article_catalog']=[{'article_no':'A','unit':'stk'}]
    doc.raw['bom_assemblies']=[{'id':'std','name':'Standard','items':[{'article_no':'A','qty':1}]}]
    doc.placements=[placement('switch_1','p1')]
    doc.raw['placement_assemblies']={'p1':{'symbol':'std'}}
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/'x.elplan.json'
        doc.save(path)
        loaded=ProjectDocument.load(path)
        assert loaded.raw['version']==APP_VERSION=='0.59.80'
        assert loaded.raw['bom_assemblies']==[]  # 0.45: global core data is not serialized in project files
        assert loaded.raw['placement_assemblies']['p1']['symbol']=='std'

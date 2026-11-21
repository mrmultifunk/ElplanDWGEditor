from pathlib import Path
import tempfile

import core_logic as core
from elplan_project.project_model import ProjectDocument, APP_VERSION


def test_standalone_switch_bom_aggregates_placements():
    placements=[core.Placement('switch_1',0,0),core.Placement('switch_1',100,0)]
    catalog=[{'article_no':'A1','description':'1-polet indsats','manufacturer':'Test','unit':'stk'}]
    bindings={p.uid:{'symbol':[{'article_no':'A1','qty':1}]} for p in placements}
    rows,missing=core.build_bom(placements,catalog,bindings)
    assert not missing
    assert rows[0]['article_no']=='A1'
    assert rows[0]['qty']==2


def test_combo_is_split_into_physical_modules_and_socket():
    symbol='combo_row_2x1_2way_socket'
    parts=core.bom_symbol_parts(symbol)
    assert [p['id'] for p in parts]==['module:1','module:2','module:3','socket','common']
    assert parts[0]['base']=='switch_1'
    assert parts[1]['base']=='switch_1'
    assert parts[2]['base']=='switch_2way'
    assert parts[3]['base']=='socket'
    assert parts[4]['required'] is False


def test_combo_modules_can_have_distinct_articles_even_when_same_type():
    symbol='combo_row_2x1_2way_socket'
    placements=[core.Placement(symbol,0,0),core.Placement(symbol,100,0)]
    catalog=[
        {'article_no':'M1','description':'1P venstre','unit':'stk'},
        {'article_no':'M2','description':'1P højre','unit':'stk'},
        {'article_no':'K','description':'Korrespondance','unit':'stk'},
        {'article_no':'S','description':'Stikkontakt','unit':'stk'},
        {'article_no':'R','description':'Ramme','unit':'stk'},
    ]
    part_bindings={
        'module:1':[{'article_no':'M1','qty':1}],
        'module:2':[{'article_no':'M2','qty':1}],
        'module:3':[{'article_no':'K','qty':1}],
        'socket':[{'article_no':'S','qty':1}],
        'common':[{'article_no':'R','qty':1}],
    }
    bindings={p.uid:part_bindings for p in placements}
    rows,missing=core.build_bom(placements,catalog,bindings)
    assert not missing
    assert {r['article_no']:r['qty'] for r in rows}=={'K':2,'M1':2,'M2':2,'R':2,'S':2}


def test_missing_combo_parts_are_reported_but_common_is_optional():
    symbol='combo_switch_1_socket'
    placements=[core.Placement(symbol,0,0)]
    catalog=[{'article_no':'A','unit':'stk'}]
    bindings={placements[0].uid:{'module:1':[{'article_no':'A','qty':1}]}}
    rows,missing=core.build_bom(placements,catalog,bindings)
    assert rows[0]['qty']==1
    assert len(missing)==1
    assert missing[0]['part_id']=='socket'


def test_custom_combo_keeps_module_indices():
    symbol=core.make_custom_combo_code(['switch_1','switch_1','switch_2way'],'socket_earth')
    parts=core.bom_symbol_parts(symbol)
    assert [(p['id'],p['base']) for p in parts[:4]]==[
        ('module:1','switch_1'),('module:2','switch_1'),('module:3','switch_2way'),('socket','socket_earth')
    ]


def test_multiple_articles_per_part_and_fractional_qty():
    placements=[core.Placement('socket_earth',0,0),core.Placement('socket_earth',10,0)]
    catalog=[{'article_no':'I','unit':'stk'},{'article_no':'T','unit':'stk'}]
    bindings={p.uid:{'symbol':[{'article_no':'I','qty':1},{'article_no':'T','qty':2}]} for p in placements}
    rows,missing=core.build_bom(placements,catalog,bindings)
    assert not missing
    assert {r['article_no']:r['qty'] for r in rows}=={'I':2,'T':4}


def test_project_roundtrip_preserves_bom_data():
    doc=ProjectDocument()
    doc.placements=[core.Placement('switch_1',0,0)]
    doc.raw['article_catalog']=[{'article_no':'A1','description':'Test','unit':'stk'}]
    doc.raw['placement_articles']={doc.placements[0].uid:{'symbol':[{'article_no':'A1','qty':1}]}}
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/'bom.elplan.json'
        doc.save(path)
        loaded=ProjectDocument.load(path)
        assert loaded.raw['version']==APP_VERSION=='0.59.85'
        assert loaded.raw['article_catalog']==[]  # 0.45: article database is core data, not project data
        assert loaded.raw['placement_articles'][doc.placements[0].uid]['symbol'][0]['article_no']=='A1'


def test_binding_one_of_many_symbols_does_not_assign_the_others():
    placements=[core.Placement('socket',i*100,0) for i in range(19)]
    catalog=[{'article_no':'A1','description':'Stik','unit':'stk'}]
    bindings={placements[0].uid:{'symbol':[{'article_no':'A1','qty':1}]}}
    rows,missing=core.build_bom(placements,catalog,bindings)
    assert {r['article_no']:r['qty'] for r in rows}=={'A1':1.0}
    assert len(missing)==1
    assert missing[0]['symbol']=='socket'
    assert missing[0]['count']==18
    assert missing[0]['qty']==18


def test_legacy_symbol_type_binding_is_not_applied_automatically():
    placements=[core.Placement('socket',0,0),core.Placement('socket',100,0)]
    catalog=[{'article_no':'A1','unit':'stk'}]
    rows,missing=core.build_bom(placements,catalog,{'socket':{'symbol':[{'article_no':'A1','qty':1}]}})
    assert rows==[]
    assert missing[0]['count']==2

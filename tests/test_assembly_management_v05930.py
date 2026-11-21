from pathlib import Path

import core_logic as core


def placement(uid='p1'):
    return core.Placement('socket', 10, 10, uid=uid)


def test_assembly_metadata_and_optional_items_roundtrip():
    rows=core.normalize_bom_assemblies([{
        'id':'asm','name':'FUGA montage','description':'Komplet løsning','category':'Stikkontakter',
        'variant':'AIR standard','tags':['FUGA','Bolig','fuga'],'notes':'Brug blå AIR-dåse',
        'items':[
            {'article_no':'A','qty':1,'role':'Indsats'},
            {'article_no':'B','qty':1,'role':'Ekstra ramme','optional':True,'included':False},
        ],
    }])
    assert len(rows)==1
    row=rows[0]
    assert row['category']=='Stikkontakter'
    assert row['variant']=='AIR standard'
    assert row['tags']==['FUGA','Bolig']
    assert row['notes']=='Brug blå AIR-dåse'
    assert row['items'][1]['optional'] is True
    assert row['items'][1]['included'] is False
    assert [x['article_no'] for x in core.bom_assembly_effective_items(row)]==['A']
    assert core.bom_assembly_item_counts(row)=={'total':2,'required':1,'optional':1,'included_optional':0,'active':1}


def test_optional_excluded_component_does_not_enter_bom_or_traceability():
    catalog=[{'article_no':'A','unit':'stk'},{'article_no':'B','unit':'stk'}]
    assembly={'id':'asm','name':'Montage','items':[
        {'article_no':'A','qty':1},
        {'article_no':'B','qty':2,'optional':True,'included':False},
    ]}
    p=placement()
    selected={p.uid:{'symbol':'asm'}}
    rows,missing=core.build_bom([p],catalog,{},assemblies=[assembly],assembly_bindings=selected)
    assert {r['article_no']:r['qty'] for r in rows}=={'A':1.0}
    assert not missing
    sources=core.bom_source_breakdown([p],catalog,{},assemblies=[assembly],assembly_bindings=selected)
    assert {r['article_no'] for r in sources}=={'A'}


def test_optional_included_component_is_counted_and_usage_preserves_metadata():
    catalog=[{'article_no':'A','unit':'stk','unit_price':10},{'article_no':'B','unit':'stk','unit_price':5}]
    assembly={'id':'asm','name':'Montage','category':'Stikkontakter','variant':'AIR','tags':['FUGA'],'items':[
        {'article_no':'A','qty':1},
        {'article_no':'B','qty':2,'optional':True,'included':True},
    ]}
    p=placement(); selected={p.uid:{'symbol':'asm'}}
    rows,_=core.build_bom([p],catalog,{},assemblies=[assembly],assembly_bindings=selected)
    assert {r['article_no']:r['qty'] for r in rows}=={'A':1.0,'B':2.0}
    usage=core.bom_assembly_usage([p],catalog,{},assemblies=[assembly],assembly_bindings=selected)
    assert usage[0]['category']=='Stikkontakter'
    assert usage[0]['variant']=='AIR'
    assert usage[0]['tags']==['FUGA']
    assert usage[0]['totals_by_currency']['DKK']==20.0


def test_assembly_management_ui_exposes_v2_features():
    source=Path('elplan_qt/qt_articles.py').read_text(encoding='utf-8')
    for token in (
        'Styklister','Kun brugt i projekt','Vis anvendelser på plan',
        'Valgfri komponent','Medtag i BOM','Styklistepreview','category','variant','tags',
    ):
        assert token in source

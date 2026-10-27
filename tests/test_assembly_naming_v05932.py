from pathlib import Path

import assembly_naming
import core_logic as core


def test_structured_naming_roundtrips_through_global_assembly_model():
    rows=core.normalize_bom_assemblies([{
        'id':'s1','name':'Helt manuelt navn','naming':{
            'product_type':'Stikkontakt','configuration':'2×1M','function':'Med jord',
            'system_series':'LK FUGA SLIM','mounting':'Forfra','color':'Koksgrå','extra':'køkken',
        },'items':[{'article_no':'A','qty':1}],
    }])
    naming=rows[0]['naming']
    assert naming['product_type']=='Stikkontakt'
    assert naming['configuration']=='2×1M'
    assert naming['system_series']=='LK FUGA SLIM'
    assert naming['mounting']=='Forfra'
    assert rows[0]['name']=='Helt manuelt navn'  # structured fields never lock the free name


def test_unknown_system_is_not_promoted_to_structured_filter_value():
    rows=core.normalize_bom_assemblies([{
        'id':'s1','name':'Manuel specialliste','naming':{'system_series':'FUGA FANTASY'},
        'items':[{'article_no':'A','qty':1}],
    }])
    assert rows[0]['naming']['system_series']==''
    assert rows[0]['name']=='Manuel specialliste'


def test_stylist_library_exposes_all_naming_parameters_for_filter_and_sort():
    src=Path('qt_articles.py').read_text(encoding='utf-8')
    for token in ('assembly_type_filter','assembly_configuration_filter','assembly_function_filter',
                  'assembly_system_filter','assembly_mounting_filter','assembly_color_filter'):
        assert token in src
    for heading in ('"Type"','"Opbygning"','"Funktion"','"System / serie"','"Montering"','"Farve"'):
        assert heading in src
    assert 'self.assembly_table.setSortingEnabled(True)' in src
    assert 'QPushButton("Ryd navneparametre")' in src
    assert 'self.tabs.addTab(tab,"Styklister")' in src
    assert 'Styklister / montager' not in src

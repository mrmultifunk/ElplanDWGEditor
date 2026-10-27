from pathlib import Path

import article_quality
import core_logic as core


def test_module_filter_parser_is_conservative_and_rejects_measurement_like_numbers():
    assert core.normalize_article_module('1M') == '1M'
    assert core.normalize_article_module('1,5M') == '1½M'
    assert core.normalize_article_module('½M') == '½M'
    assert core.normalize_article_module('2 x 1,5M') == '2×1½M'
    assert core.normalize_article_module('451200M') == ''
    assert core.normalize_article_module('100M') == ''
    assert core._module_label('Kabel 3G1,5 · tromle 100 m') == ''
    assert core._module_label('LK FUGA ramme 1½M hvid') == '1½M'


def test_invalid_explicit_module_is_preserved_as_source_but_not_exposed_as_filter_facet():
    raw={'article_no':'X1','description':'Test 451200M','manufacturer':'Test','module_size':'451200M'}
    normalized=core.normalize_article_catalog([raw])[0]
    assert normalized['module_size'] == '451200M'
    facets=core.article_filter_facets(normalized)
    assert facets['module_size'] == ''
    assert facets['module_group'] == ''


def test_color_filter_collapses_trivial_variants_without_overwriting_source_value():
    assert core.normalize_article_color('  HVID ') == 'Hvid'
    assert core.normalize_article_color('transparent/orange') == 'Transparent / orange'
    raw={'article_no':'X2','description':'Test','manufacturer':'Test','color':'HVID'}
    normalized=core.normalize_article_catalog([raw])[0]
    assert normalized['color'] == 'HVID'
    assert core.article_filter_facets(normalized)['color'] == 'Hvid'
    # A producer colour concept must not be silently mapped to a different LK colour.
    inferred=core.article_filter_facets({'article_no':'X3','description':'Produkt antracit','manufacturer':'Test'})
    assert inferred['color'] == 'Antracit'


def test_quality_audit_reports_bad_module_duplicate_color_and_identity_gaps_without_mutating():
    rows=[
        {'article_no':'A','description':'Ramme','manufacturer':'Maker','module_size':'451200M','color':'HVID','ean':'5700000000006','source':'https://example.test/a','source_checked':'2026-08-26'},
        {'article_no':'B','description':'Ramme','manufacturer':'Maker','color':'hvid','ean':'','source':'https://example.test/b','source_checked':'2026-08-26'},
    ]
    before=[dict(r) for r in rows]
    result=article_quality.audit_article_catalog(rows)
    codes={i['code'] for i in result['issues']}
    assert 'invalid_module' in codes
    assert 'duplicate_color_spelling' in codes
    assert 'missing_ean' in codes
    assert rows == before


def test_article_manager_exposes_non_destructive_data_quality_tab():
    source=(Path(__file__).resolve().parents[1]/'qt_articles.py').read_text(encoding='utf-8')
    for token in ('Datakvalitet','Aktiv artikeldatabase','Medfølgende grunddata','Kør audit','Eksportér audit CSV','_run_article_quality_audit'):
        assert token in source

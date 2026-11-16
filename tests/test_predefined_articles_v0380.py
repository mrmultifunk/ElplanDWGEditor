import math
from pathlib import Path
import tempfile

import core_logic as core
from project_model import ProjectDocument, APP_VERSION


def test_predefined_library_contains_expected_families_and_known_refs():
    rows=core.load_predefined_article_catalog()
    assert len(rows) >= 190
    lookup={r['article_no']:r for r in rows}
    assert lookup['542D6001']['el_no']=='1017054433'
    assert lookup['542D6001']['ean']=='5703302153935'
    slim = {
        '504D3510': ('1017059030', '5703302155731'),
        '504D3515': ('1017059043', '5703302155847'),
        '504D3520': ('1017059056', '5703302155953'),
        '504D3525': ('1017059069', '5703302156066'),
    }
    for article_no, (el_no, ean) in slim.items():
        assert lookup[article_no]['el_no'] == el_no
        assert lookup[article_no]['ean'] == ean
        assert lookup[article_no]['series'] == 'LK FUGA AIR'
        assert lookup[article_no]['product_family'] == 'LK FUGA AIR'
        assert lookup[article_no]['product_variant'] == 'SLIM'
    assert lookup['CCT501801']['series'].startswith('Wiser')
    assert lookup['662425']['manufacturer']=='Waskönig+Walter'
    assert lookup['662425']['cable_spec']=='3G1,5'
    assert math.isclose(lookup['662425']['package_length_m'],100.0)
    assert lookup['731947']['unit']=='m'
    assert math.isclose(lookup['731947'].get('package_length_m',0),0.0)
    assert len({r['article_no'].casefold() for r in rows})==len(rows)


def test_normalize_preserves_standard_metadata():
    row=core.normalize_article_catalog([{
        'article_no':'X1','description':'Test','manufacturer':'M','unit':'rulle',
        'category':'K','series':'S','el_no':'123','ean':'456','status':'Aktiv',
        'kind':'cable','cable_spec':'3G1,5','source':'https://example.test',
        'source_checked':'2026-08-21','package_length_m':100,
    }])[0]
    assert row['category']=='K' and row['series']=='S'
    assert row['kind']=='cable' and row['cable_spec']=='3G1,5'
    assert row['package_length_m']==100.0


def cable(length, spec='3G1,5'):
    return core.CablePlacement(points=[(0,0),(length,0)], layer=core.CABLE_LAYER, cable_spec=spec)


def test_cable_bom_measured_length_and_roll_rounding_after_aggregation():
    std={r['article_no']:r for r in core.load_predefined_article_catalog()}
    key=core.cable_article_key(core.CABLE_LAYER,'3G1,5')
    # Afmålt: 10 + 20 drawing units, factor 1m/unit, 10% reserve = 33m.
    cables=[cable(10),cable(20)]
    rows,missing=core.build_bom([], [std['731947']], {}, cables, {c.uid:'731947' for c in cables}, 1.0, 10.0)
    assert not missing
    assert len(rows)==1 and rows[0]['article_no']=='731947'
    assert math.isclose(rows[0]['qty'],33.0, rel_tol=1e-9)
    assert rows[0]['unit']=='m'
    assert '33.00 m' in rows[0]['detail']

    # Rulle: to stræk á 60m summeres før afrunding -> 120m -> 2 x 100m.
    cables=[cable(60),cable(60)]
    rows,missing=core.build_bom([], [std['662425']], {}, cables, {c.uid:'662425' for c in cables}, 1.0, 0.0)
    assert not missing
    assert rows[0]['qty']==2.0 and rows[0]['unit']=='rulle'
    assert '120.00 m' in rows[0]['detail'] and '2 × 100 m' in rows[0]['detail']


def test_unassigned_cable_appears_in_missing_and_scale_missing_is_explicit():
    key=core.cable_article_key(core.CABLE_LAYER,'5G1,5')
    rows,missing=core.build_bom([], [], {}, [cable(12,'5G1,5')], {}, 1.0, 10.0)
    assert rows==[] and len(missing)==1
    assert missing[0]['part_id']==key and missing[0]['unit']=='m'
    assert math.isclose(missing[0]['qty'],13.2)

    rows,missing=core.build_bom([], [], {}, [cable(12,'5G1,5')], {}, None, 10.0)
    assert missing[0]['qty']==1 and missing[0]['unit']=='stræk' and 'skala/kalibrering mangler' in missing[0]['detail']


def test_project_roundtrip_cable_article_binding_and_version():
    doc=ProjectDocument.from_cad('demo.dxf')
    c=core.CablePlacement(points=[(0,0),(10,0)],cable_spec='3G1,5')
    doc.cables=[c]
    doc.raw['cable_instance_articles']={c.uid:'662425'}
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/'p.elplan.json'; doc.save(path); loaded=ProjectDocument.load(path)
        assert loaded.raw['version']==APP_VERSION=='0.59.82'
        assert loaded.raw['cable_instance_articles']==doc.raw['cable_instance_articles']
        assert loaded.cables[0].uid==c.uid


def test_slim_design_frames_complete_and_filterable():
    rows=core.load_predefined_article_catalog()
    lookup={r['article_no']:r for r in rows}
    expected={
        '560D6710':('1M','Hvid','1017059797','5703302160988'),
        '560D8710':('1M','Koksgrå','1017059807','5703302160995'),
        '560D0410':('1M','Stål','1017059894','5703302161077'),
        '560D6715':('1½M','Hvid','1017059810','5703302161008'),
        '560D8715':('1½M','Koksgrå','1017059823','5703302161015'),
        '560D0415':('1½M','Stål','1017059904','5703302161084'),
        '560D6720':('2×1M','Hvid','1017059836','5703302161022'),
        '560D8720':('2×1M','Koksgrå','1017059849','5703302161039'),
        '560D0420':('2×1M','Stål','1017059917','5703302161091'),
        '560D6725':('2½M','Hvid','1017059852','5703302161046'),
        '560D8725':('2½M','Koksgrå','1017059865','5703302161053'),
        '560D0425':('2½M','Stål','1017059920','5703302161107'),
    }
    for no,(module,color,el,ean) in expected.items():
        row=lookup[no]; facets=core.article_filter_facets(row)
        assert facets['product_type']=='Ramme'
        assert facets['design_family']=='SLIM'
        assert facets['module_size']==module
        assert facets['color']==color
        assert row['el_no']==el and row['ean']==ean
    tech=lookup['560D0725']; f=core.article_filter_facets(tech)
    assert (f['product_type'],f['design_family'],f['module_size'])==('Teknisk monteringsramme','SLIM','2½M')
    assert tech['el_no']=='1017059975' and tech['ean']=='5703302161152'


def test_article_facets_support_63_slim_boxes_and_do_not_treat_cable_rolls_as_modules():
    rows=core.load_predefined_article_catalog(); lookup={r['article_no']:r for r in rows}
    base=core.article_filter_facets(lookup['560D64101L'])
    assert base['design_family']=='BASE 63' and base['product_type']=='Ramme' and base['module_size']=='1M'
    box=core.article_filter_facets(lookup['504D3515'])
    assert box['design_family']=='' and box['product_family']=='LK FUGA AIR' and box['product_variant']=='SLIM'
    assert box['product_type']=='Forfradåse' and box['module_size']=='1½M'
    cable=core.article_filter_facets(lookup['662425'])
    assert cable['product_type']=='Kabel' and cable['module_size']==''


def test_qt_article_browser_has_visual_preview_and_spec_filters_without_importing_qt():
    source=((Path(__file__).resolve().parents[1] / 'qt_articles.py')).read_text(encoding='utf-8')
    assert 'class ArticleVisualPreview' in source
    for token in ('self.std_type','self.std_design','self.std_variant','self.std_module','self.std_color','Nulstil filtre'):
        assert token in source
    assert 'setFilterMode(Qt.MatchFlag.MatchContains)' in source

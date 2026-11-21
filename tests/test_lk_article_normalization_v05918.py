from elplan_catalog import article_normalization as norm
import core_logic as core
from elplan_catalog.lk_catalog_sync import extract_product_refs, merge_lk_articles, parse_product_page


def test_image_asset_refs_are_not_products_but_real_schneider_codes_are_kept():
    html='''<img src="/katalog/foto/jpg/502U6510_3.jpg">
            <img src="/katalog/foto/jpg/MEG4010-6534_web.jpg">
            <img src="/katalog/foto/jpg/504N3007.jpg">
            <a href="?vnr=MEG4010-6534">produkt</a>'''
    refs=extract_product_refs(html)
    assert '502U6510_3' not in refs
    assert 'MEG4010-6534_web' not in refs
    assert '504N3007' in refs
    assert 'MEG4010-6534' in refs


def test_parser_prefers_requested_vnr_and_uses_adjacent_colour_field():
    html='''<html><body><h1>OPUS 66 dåse for kanalinstallation 2½ modul</h1>
      <div>Farve</div><div>Hvid</div>
      <div>LK nummer</div><div>504N3007</div>
      <div>EL nummer</div><div>1017031317</div>
      <div>EAN nummer</div><div>5703302058629</div>
      <div>Varianter:</div><div>LK nummer: 504N2015 Kopier</div>
    </body></html>'''
    row=parse_product_page(html, fallback_article_no='504N3007')
    assert row['article_no']=='504N3007'
    assert row['color']=='hvid'
    assert row['color_raw']=='Hvid'
    assert row['module_size']=='2½M'


def test_color_web_noise_and_configuration_do_not_pollute_colour_taxonomy():
    assert norm.normalize_color('LK nummer: 530D5062 Kopier', trusted_source_field=True)==('', '')
    color,note=norm.normalize_color('uden afdækning', trusted_source_field=True)
    assert color=='' and 'uden afdækning' in note
    assert norm.normalize_color('Hvid, antibakteriel', trusted_source_field=True)==('hvid','Egenskab: antibakteriel')
    assert norm.normalize_color('Børstet alu', trusted_source_field=True)[0]=='børstet aluminium'


def test_material_words_are_not_assumed_to_be_colours_in_legacy_records():
    screw={'article_no':'020S0556','description':'Tilbehør skrue undersænket 4-40 mm','manufacturer':'Schneider Electric / Lauritz Knudsen','color':'stål'}
    frame={'article_no':'560D0410','description':'LK FUGA design ramme SLIM 55 stål 1 modul','manufacturer':'Schneider Electric / Lauritz Knudsen','color':'stål'}
    a,_=norm.normalize_lk_article(screw)
    b,_=norm.normalize_lk_article(frame)
    assert 'color' not in a
    assert b['color']=='stål'


def test_module_rules_reject_measurements_and_allow_documented_resi9_rows():
    for bad in ('451200M','600x400M','0M','44x44M','15M'):
        assert norm.normalize_module(bad)==''
    assert norm.normalize_module('2 x 1,5M')=='2×1½M'
    assert norm.normalize_module('4x13M')=='4×13M'
    assert norm.normalize_module('3x18M')=='3×18M'
    assert core.normalize_article_module('4x13M')=='4×13M'
    assert core.normalize_article_module('451200M')==''


def test_merge_cleans_existing_lk_pollution_and_removes_safe_assets():
    existing=[
        {'article_no':'504N3007','description':'OPUS 66 dåse 2½ modul','manufacturer':'Schneider Electric / Lauritz Knudsen','color':'LK nummer: 504N3007 Kopier','module_size':'451200M'},
        {'article_no':'502U6510_3','description':'image','manufacturer':'Schneider Electric / Lauritz Knudsen','image_url':'https://www1.lk.dk/katalog/foto/jpg/502U6510_3.jpg'},
        {'article_no':'MAN-1','description':'Manuel artikel','manufacturer':'Egen','color':'stål'},
    ]
    incoming=[{'article_no':'504N3007','description':'OPUS 66 dåse 2½ modul','manufacturer':'Schneider Electric / Lauritz Knudsen','color':'Hvid','color_raw':'Hvid'}]
    merged,stats=merge_lk_articles(existing,incoming)
    by={r['article_no']:r for r in merged}
    assert '502U6510_3' not in by
    assert by['504N3007']['color']=='hvid'
    assert by['504N3007']['module_size']=='2½M'
    assert by['MAN-1']['color']=='stål'
    assert stats['cleanup_removed']>=1


def test_legacy_module_must_match_explicit_context_or_safe_module_product():
    cable={'article_no':'210A5095','description':'Forlængerledning 5 m 2-pol med jord','manufacturer':'Schneider Electric / Lauritz Knudsen','module_size':'5M'}
    thermostat={'article_no':'506D5201','description':'LK FUGA indsats termostat med gulvføler med 4 m. kabel','manufacturer':'Schneider Electric / Lauritz Knudsen','module_size':'4M'}
    tangent={'article_no':'530D5934','description':'LK FUGA reservedele afbryder 13 A tangent for krone afbryder','manufacturer':'Schneider Electric / Lauritz Knudsen','module_size':'½M'}
    explicit={'article_no':'R9H13424','description':'Afdækning Resi9 CX dør 4x13 mod Hvid','manufacturer':'Schneider Electric / Lauritz Knudsen','module_size':'600x400M'}
    a,_=norm.normalize_lk_article(cable); b,_=norm.normalize_lk_article(thermostat); c,_=norm.normalize_lk_article(tangent); d,_=norm.normalize_lk_article(explicit)
    assert 'module_size' not in a and a['module_size_raw']=='5M'
    assert 'module_size' not in b and b['module_size_raw']=='4M'
    assert c['module_size']=='½M'
    assert d['module_size']=='4×13M' and d['module_size_raw']=='600x400M'

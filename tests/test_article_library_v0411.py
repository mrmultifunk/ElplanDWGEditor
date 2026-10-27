import core_logic as core


def _lookup():
    return {r['article_no']: r for r in core.load_predefined_article_catalog()}


def test_501d0412_is_filterable_and_has_verified_procurement_data():
    r = _lookup()['501D0412']
    assert r['el_no'] == '1017056224'
    assert r['ean'] == '5703302157087'
    assert r['product_type'] == 'Stikkontakt / udtag'
    assert r['module_size'] == '2M'
    assert r['color'] == 'Uden afdækning'
    assert 'lemu.dk' in r.get('supplier_page', '')


def test_fuga_core_reference_holes_are_now_present():
    rows = _lookup()
    required = {
        '501D6022','501D0032','501D6032','501D0034','501D6034','501D0062','501D6062',
        '501D0072','501D6072','541D0822','541D6822','501D0621','501D6621','501D0631',
        '501D6631','501D0661','501D6661','501D0671','501D6671','522D5006','522D6006',
        '522D5066','522D6066','542D0505','542D0009','542D6009','542D0015','542D6015',
        '501D0022','541D0721','541D0731','541D6731','541D6212','506D0712',
        '500D5012','500D6012','500D8012','580D6012','500D5022','500D6022','500D8022',
    }
    assert required <= rows.keys()


def test_verified_new_rows_have_ean_except_intentionally_unresolved_cover():
    rows = _lookup()
    for no in ('501D6022','501D0032','501D6032','501D0062','501D6062','541D0822','542D0505',
               '541D0721','541D0731','541D6731','541D6212','506D0712','500D5022','500D8022'):
        assert rows[no]['el_no']
        assert rows[no]['ean']
    assert rows['500D6022'].get('ean','') == ''

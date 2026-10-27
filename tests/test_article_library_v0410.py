import json
from pathlib import Path

import core_logic as core
from predefined_articles_data import ARTICLES as FALLBACK


def test_library_is_unique_normalized_and_has_product_links():
    rows=core.load_predefined_article_catalog()
    assert len(rows) >= 395
    assert len({r['article_no'].casefold() for r in rows}) == len(rows)
    assert all(str(r.get('product_page','')).startswith(('http://','https://')) for r in rows)
    for row in rows:
        ean=str(row.get('ean','') or '')
        if ean:
            assert ean.isdigit() and len(ean) in (8,12,13,14)
    lk=[r for r in rows if 'Lauritz Knudsen' in r.get('manufacturer','')]
    assert lk
    assert all(r['description'].startswith('LK ') for r in lk)
    assert all(r['product_page']==f"https://www.lk.dk/produkter?iid={r['article_no']}" for r in lk)


def test_fuga_cover_audit_contains_core_families_and_verified_metadata():
    rows=core.load_predefined_article_catalog(); lookup={r['article_no']:r for r in rows}
    expected={
        '540D6320':('1017055021','5703302155038'),
        '540D6321':('1017054983','5703302155007'),
        '530D6932':('1017040340','5703302100625'),
        '530D6934':('1017040421','5703302100700'),
        '530D6906':('1017038174','5703302099479'),
        '530D6907':('1017038213','5703302099516'),
        '530D6811':('1017042814','5703302112840'),
        '530D6912':('1017039720','5703302099714'),
        '530D6921':('1017040081','5703302100076'),
        '530D6922':('1017040120','5703302100250'),
        '530D6920':('1017040049','5703302100038'),
        '530D6916':('1017039885','5703302099875'),
        '530D6111':('1017057715','5703302158305'),
        '530D6521':('1017057744','5703302158336'),
        '530D6213':('1017058031','5703302158978'),
        '530D6061':('1017060456','5703302166447'),
        '530D6062':('1017060579','5703302166560'),
        '530D6071':('1017059755','5703302160964'),
        '500D6018':('1020007914','5703302153690'),
        '500D6512':('1020007972','5703302153751'),
        '508D6706':('1088000827','5703302159098'),
        '580D6011':('1088011311','5703302150330'),
        '530D6940':('1087004455','5703302103794'),
        '530D5909':('1017038284','5703302099585'),
        '540D6326':('1017055209','5703302155168'),
        '530D6315':('1092002497','5703302162371'),
        '540D6341':('1017055238','5703302155182'),
        '530D6511':('1067004226','5703302143813'),
        '530D6703':('1092002523','5703302162425'),
    }
    for no,(el,ean) in expected.items():
        row=lookup[no]
        assert row['el_no']==el and row['ean']==ean
        assert row.get('product_type')=='Tangent / afdækning'
        assert row.get('product_page')
    covers=[r for r in rows if r.get('manufacturer')=='Schneider Electric / Lauritz Knudsen' and r.get('product_type')=='Tangent / afdækning']
    assert len(covers) >= 100


def test_json_and_python_fallback_are_kept_in_sync():
    payload=json.loads(Path('predefined_articles.json').read_text(encoding='utf-8'))
    json_rows=core.normalize_article_catalog(payload['articles'])
    py_rows=core.normalize_article_catalog(FALLBACK)
    assert json_rows==py_rows


def test_assembly_article_picker_is_faceted_sortable_and_link_aware_without_importing_qt():
    source=Path('qt_articles.py').read_text(encoding='utf-8')
    assert 'class ArticlePickerDialog' in source
    for token in ('self.manufacturer','self.product_type','self.design','self.module','self.color','self.status','self.only_ean'):
        assert token in source
    assert 'self.table.setSortingEnabled(True)' in source
    assert 'EAN' in source and 'EL-/LM-nr.' in source
    assert 'self.open_product' in source and 'self.open_supplier' in source
    assert 'Find artikel…' in source

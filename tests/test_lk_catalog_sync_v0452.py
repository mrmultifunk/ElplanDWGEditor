from elplan_catalog.lk_catalog_sync import (
    extract_category_ids, extract_product_refs, parse_product_page,
    merge_lk_articles, product_detail_url,
)


def test_extracts_iids_and_product_refs_from_href_and_javascript():
    html='''
    <a href="nmkatalog.ph7?iid=195">FUGA</a>
    <div onclick="location='nmkatalog.ph7?iid=247'"></div>
    <a href="nkatalog.ph7?aktion=content&amp;urlref=%2Fprodukt%2F5703302158732">Produkt</a>
    <script>go('urlref=/produkt/3606487280385')</script>
    '''
    assert {195,247} <= extract_category_ids(html)
    assert {'5703302158732','3606487280385'} <= extract_product_refs(html)


def test_parse_legacy_lk_product_page():
    html='''<html><body>
    <h1>Image LK FUGA® ·tilbehør afbryder 16 A tangent 1 modul</h1>
    <div>Farve: hvid</div>
    <div>LK nummer: 540D6320</div>
    <div>EL nummer: 1017055021</div>
    <div>EAN nummer: 5703302155038</div>
    <div>Pakkestørrelse: 10 stk.</div>
    </body></html>'''
    row=parse_product_page(html,source_url='https://example.test/product')
    assert row
    assert row['article_no']=='540D6320'
    assert row['el_no']=='1017055021'
    assert row['ean']=='5703302155038'
    assert row['series']=='LK FUGA'
    assert row['color'].casefold()=='hvid'
    assert row['status']=='Aktiv/ukendt'
    assert 'tangent' in row['description'].lower()
    assert row['image_url'].endswith('/540D6320.jpg')
    assert row['product_page'].endswith('?iid=540D6320')


def test_parse_discontinued_product_status():
    html='''<h1>Stikprop 2-pol</h1><p>Udgået – sælges så længe lager haves</p>
    <p>LK nummer: 210A5247 EL nummer: 1028009037 EAN: 5703302066341</p>'''
    row=parse_product_page(html)
    assert row['status']=='Udgået – sælges så længe lager haves'


def test_merge_refreshes_official_fields_but_preserves_manual_supplier_note():
    old=[{'article_no':'540D6320','description':'Gammel','supplier_page':'https://grossist.test/x','note':'Min note','manufacturer':'LK'}]
    incoming=[{'article_no':'540D6320','description':'Ny officiel','manufacturer':'Schneider Electric / Lauritz Knudsen','ean':'5703302155038','note':'Pakkestørrelse: 10 stk.'},
              {'article_no':'545U6615','description':'LK One relæ'}]
    merged,stats=merge_lk_articles(old,incoming)
    by={r['article_no']:r for r in merged}
    assert stats['added']==1 and stats['updated']==1
    assert by['540D6320']['description']=='Ny officiel'
    assert by['540D6320']['supplier_page']=='https://grossist.test/x'
    assert by['540D6320']['note']=='Min note'
    assert by['540D6320']['ean']=='5703302155038'


def test_product_detail_url_encodes_catalog_reference():
    url=product_detail_url('5703302158732')
    assert 'aktion=content' in url
    assert '5703302158732' in url


def test_parse_direct_vnr_catalog_page_uses_varenummer_label():
    html="""<html><body><h1>LK FUGA® reservedele afbryder 13 A afbryder 1-pol med lampe 230 V</h1>
    <div>Produktbeskrivelse:</div><div>Farve</div><div>lysegrå</div>
    <div>Varenummer</div><div>522D5201</div><div>EL nummer</div><div>1017055814</div>
    <div>EAN nummer</div><div>5703302162715</div></body></html>"""
    row=parse_product_page(html)
    assert row and row['article_no']=='522D5201'
    assert row['color'].casefold()=='lysegrå'
    assert row['el_no']=='1017055814' and row['ean']=='5703302162715'


def test_qt_article_database_uses_model_table_and_exposes_lk_sync_action():
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1] / 'elplan_qt/qt_articles.py').read_text(encoding='utf-8')
    block=source[source.index('def _build_library_tab'):source.index('def _build_bom_tab')]
    assert 'self.library_table=QTableView()' in block
    assert 'ArticleTableModel' in block
    assert 'Synkronisér LK.dk…' in block
    assert 'backup_core_article_catalog' in block


def test_extracts_product_refs_from_current_legacy_product_images():
    html='''
    <div onmousedown="showProduct('5703302158732')">
      <img src="/katalog/foto/jpg/588D6693.jpg?rev=2" alt="Keystone">
    </div>
    <img src="foto/jpg/Fuga.jpg">
    <img src="/katalog/foto/jpg/506U6128.jpg">
    '''
    refs=extract_product_refs(html)
    assert '5703302158732' in refs
    assert '588D6693' in refs
    assert '506U6128' in refs
    assert 'Fuga' not in refs


def test_parser_uses_lk_number_from_image_discovery_as_safe_fallback():
    html='''<html><head><title>LK FUGA® ramme</title></head><body>
    <h1>LK FUGA® designramme</h1><p>Tekniske data</p></body></html>'''
    row=parse_product_page(html, fallback_article_no='560D8015')
    assert row is not None
    assert row['article_no']=='560D8015'
    assert row['image_url'].endswith('/560D8015.jpg')
    # A bare EAN is not an LK article number and must not become one.
    assert parse_product_page(html, fallback_article_no='5703302157308') is None


def test_all_html_attribute_values_are_discovery_candidates():
    html='''<div onmousedown="location='nmkatalog.ph7?iid=384'"
                 data-product="urlref=/produkt/5703302158732"></div>'''
    assert 384 in extract_category_ids(html)
    assert '5703302158732' in extract_product_refs(html)


def test_full_catalog_collection_works_when_index_exposes_only_product_images(monkeypatch):
    import urllib.parse
    from elplan_catalog import lk_catalog_sync as sync

    article_nos=[f'500D{i:04d}' for i in range(100)]
    index='<html><body>'+''.join(
        f'<img src="/katalog/foto/jpg/{no}.jpg">' for no in article_nos
    )+'</body></html>'

    def fake_fetch(url, **_kwargs):
        if url == sync.CATALOG_ROOT:
            return index
        parsed=urllib.parse.urlparse(url)
        query=urllib.parse.parse_qs(parsed.query)
        if 'vnr' in query:
            no=query['vnr'][0]
            num=int(no[-4:])
            return f'''<html><body><h1>LK FUGA® testprodukt {num}</h1>
                <div>Varenummer: {no}</div>
                <div>EL nummer: {1017000000+num}</div>
                <div>EAN nummer: {5703302000000+num:013d}</div>
                </body></html>'''
        raise AssertionError(url)

    monkeypatch.setattr(sync, 'fetch_text', fake_fetch)
    snapshot=sync.collect_catalog(max_products=500, request_delay_min=0, request_delay_max=0)
    assert len(snapshot.articles)==100
    assert snapshot.stats.product_refs==100
    assert {row['article_no'] for row in snapshot.articles}==set(article_nos)

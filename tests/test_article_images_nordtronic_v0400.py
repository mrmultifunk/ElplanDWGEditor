import core_logic as core


def test_catalog_contains_nordtronic_and_online_image_metadata():
    rows=core.load_predefined_article_catalog()
    lookup={r['article_no']:r for r in rows}
    assert len(rows) >= 290
    assert lookup['542D6001']['image_source']=='Lemvigh-Müller'
    assert lookup['542D6001']['image_url'].startswith('https://assets.cdnlemu.dk/product/image/')
    assert lookup['560D6710']['product_page']=='https://www.lk.dk/produkter?iid=560D6710'
    assert lookup['560D6710']['supplier_page'].startswith('https://www.lemu.dk/da/produkt/')

    uni=lookup['12200000']
    assert uni['manufacturer']=='Nordtronic A/S'
    assert uni['ean']=='5704629005556'
    assert uni['product_type']=='Downlight'
    assert uni['cutout_mm']=='75' and uni['diameter_mm']=='87'
    assert uni['product_page'].startswith('https://nordtronic.dk/shop/')

    lp=lookup['35511013']
    assert lp['ean']=='5704629002654'
    assert lp['cct']=='3000K'
    assert lp['power_w']=='4,5W'
    assert lp['image_url'].endswith('LPflex55_d_35511012-14.jpg')


def test_nordtronic_core_families_and_fronts_are_unique():
    rows=core.load_predefined_article_catalog()
    nt=[r for r in rows if r.get('manufacturer')=='Nordtronic A/S']
    assert len(nt) >= 75
    ids={r['article_no'] for r in nt}
    for no in ('12000000','12200000','11220000','70010000','70090000','98423051','98426061','35711012','35811017'):
        assert no in ids
    assert len(ids)==len(nt)


def test_new_media_and_lighting_metadata_survive_normalization():
    row=core.normalize_article_catalog([{
        'article_no':'N1','description':'Spot','manufacturer':'Nordtronic A/S','unit':'stk',
        'product_page':'https://example.test/product','image_url':'https://example.test/i.jpg',
        'datasheet_url':'https://example.test/d.pdf','image_source':'Test',
        'diameter_mm':'87','cutout_mm':'75','cct':'3000K','power_w':'6W',
        'ip_rating':'IP44 / IP20','shape':'Rund','environment':'Inden- og udendørs',
    }])[0]
    for key in ('product_page','image_url','datasheet_url','image_source','diameter_mm','cutout_mm','cct','power_w','ip_rating','shape','environment'):
        assert row.get(key)

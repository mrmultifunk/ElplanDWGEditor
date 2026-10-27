from pathlib import Path

from article_index import build_article_search_index, article_search_score, facet_value_counts, normalize_search_text


def test_search_normalization_is_danish_and_fraction_friendly():
    assert normalize_search_text("FUGA forfradåse 1½M") == normalize_search_text("FUGA forfradase 1,5M")
    assert normalize_search_text("Ø57") == normalize_search_text("O57")


def test_rank_exact_identity_before_description_and_usage_boosts_ties():
    rows=build_article_search_index([
        {"article_no":"504D3010","description":"LK FUGA AIR forfradåse 1 modul","ean":"5703302156080","manufacturer":"LK"},
        {"article_no":"X1","description":"Tilbehør til 504D3010","manufacturer":"LK"},
    ])
    assert article_search_score(rows[0],"504D3010") > article_search_score(rows[1],"504D3010")
    base=article_search_score(rows[0],"FUGA")
    boosted=article_search_score(rows[0],"FUGA",favorite=True,project=True,recent_rank=0)
    assert boosted > base


def test_facets_return_counts_not_just_names():
    rows=build_article_search_index([
        {"article_no":"1","description":"A","manufacturer":"LK","color":"Hvid"},
        {"article_no":"2","description":"B","manufacturer":"LK","color":"Hvid"},
        {"article_no":"3","description":"C","manufacturer":"WAGO","color":"Orange"},
    ])
    assert facet_value_counts(rows,"manufacturer")=={"LK":2,"WAGO":1}
    assert facet_value_counts(rows,"color")=={"Hvid":2,"Orange":1}


def test_article_browser_source_has_productivity_scopes_cascading_facets_and_variants():
    source=Path("qt_articles.py").read_text(encoding="utf-8")
    for text in ("★ Favoritter","Senest anvendte","Brugt i projekt","Kun komplette data","facet_value_counts","_select_adjacent_variant","Bruges i styklister"):
        assert text in source
    assert 'data["favorite_articles"]' in source
    assert 'data["recent_articles"]' in source

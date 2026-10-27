from pathlib import Path

import core_logic as core


def test_wago_articles_have_bundled_preview_images_and_2273_series():
    rows=core.load_predefined_article_catalog()
    lookup={r["article_no"]:r for r in rows}
    root=Path(__file__).resolve().parents[1]
    for article_no in ("221-412","221-413","221-415","221-420","2273-202","2273-203","2273-204","2273-205","2273-208"):
        row=lookup[article_no]
        assert row["image_source"] == "WAGO"
        assert row["image_url"].startswith("https://www.wago.com/")
        local=row.get("image_local_path","")
        assert local.startswith("assets/article_images/")
        assert (root/local).exists()


def test_wago_2273_articles_are_selectable_in_pl_config_capacity_map():
    assert core.pl_wago_article_capacity("2273-202") == 2
    assert core.pl_wago_article_capacity("2273-203") == 3
    assert core.pl_wago_article_capacity("2273-204") == 4
    assert core.pl_wago_article_capacity("2273-205") == 5
    assert core.pl_wago_article_capacity("2273-208") == 8
    # standardanbefalinger forbliver 221-serien af hensyn til bagudkompatibilitet
    assert core.pl_recommended_wago_article(1, True) == "221-412"
    assert core.pl_recommended_wago_article(2, True) == "221-413"

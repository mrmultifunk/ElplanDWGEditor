import json
from pathlib import Path
from tempfile import TemporaryDirectory

from elplan_catalog import retail_price_sync as retail
from elplan_catalog import user_library


def _wago():
    return {
        "article_no":"221-412",
        "description":"WAGO 221 fjedersamlemuffe, 2-leder",
        "ean":"4050821808435",
        "el_no":"7821100470",
        "unit":"stk",
    }


def test_wattoo_pack_price_is_normalized_to_each_price():
    html='''<html><meta property="og:title" content="WAGO 221-412 - 100 stk"><script type="application/ld+json">'''+json.dumps({
        "@type":"Product","gtin13":"4050821808435","sku":"221-412",
        "offers":{"price":"331.00","priceCurrency":"DKK"}
    })+'''</script><body>Pakke á 100 stk. | inkl. moms 331,00 kr.</body></html>'''
    obs=retail.parse_product_page(
        html,_wago(),provider=retail.PROVIDERS[0],
        url="https://www.wattoo.dk/wago-serie-221-med-2-stk-huller-100-stk-4821214123",
    )
    assert obs is not None
    assert obs.package_quantity == 100
    assert obs.raw_price_incl_vat == 331.0
    assert obs.price_incl_vat == 3.31
    assert obs.price_excl_vat == 2.648
    assert obs.price_unit == "stk"
    assert obs.normalization_version == 3


def test_blister_pack_text_is_normalized_even_when_shop_says_pr_stk():
    article={**_wago(),"article_no":"221-413","ean":"4066966001907","el_no":"5401008944"}
    html='''<html><meta property="og:title" content="WAGO 221-413 - 12 stk gør-det-selv pakke"><script type="application/ld+json">'''+json.dumps({
        "@type":"Product","gtin13":"4066966001907","sku":"5401008944",
        "offers":{"price":"65.50","priceCurrency":"DKK","unitText":"stk"}
    })+'''</script><body>Blisterpakke med 12 stk. pr. stk. | inkl. moms 65,50 kr.</body></html>'''
    obs=retail.parse_product_page(html,article,provider=retail.PROVIDERS[0],url="https://www.wattoo.dk/fjedersamlemuffe-blisterpakke-5401008944")
    assert obs is not None
    assert obs.package_quantity == 12
    assert round(obs.price_incl_vat,4) == round(65.5/12,4)
    assert round(obs.price_excl_vat,4) == round((65.5/1.25)/12,4)


def test_ambiguous_variant_pack_page_is_rejected_instead_of_guessing():
    html='''<script type="application/ld+json">'''+json.dumps({
        "@type":"Product","gtin13":"4050821808435","offers":{"price":"331","priceCurrency":"DKK"}
    })+'''</script><body>Pakke á 100 stk. Pakke á 25 stk. Pakke á 50 stk.</body>'''
    assert retail.parse_product_page(html,_wago(),provider=retail.PROVIDERS[0],url="https://www.wattoo.dk/variant-side") is None


def test_url_uses_last_n_stk_so_two_holes_is_not_two_piece_pack():
    qty,label,amb=retail._package_quantity_from_page(
        "", "https://www.wattoo.dk/samlemuffe-med-2-stk-huller-10-stk-9900900070"
    )
    assert not amb
    assert qty == 10
    assert "10" in label


def test_pricebook_v3_webshop_estimate_is_invalidated_but_manual_price_survives():
    old=user_library.os.environ.get("ELPLAN_USER_DATA_DIR")
    try:
        with TemporaryDirectory() as td:
            user_library.os.environ["ELPLAN_USER_DATA_DIR"]=td
            path=Path(td)/"article_prices.json"
            path.write_text(json.dumps({"version":3,"prices":{"221-412":{
                "estimated_price":264.8,"estimated_price_source":"Webshops: WATTOO",
                "manual_price":2.50,"manual_price_source":"Egen nettopris",
                "price_currency":"DKK","price_unit":"stk",
                "price_observations":[{"provider":"WATTOO","provider_key":"wattoo","price_incl_vat":331,"price_excl_vat":264.8,"currency":"DKK","price_unit":"stk","checked":"2026-08-26"}],
            }}}),encoding="utf-8")
            loaded=user_library.load_article_prices()
            assert loaded["221-412"]["manual_price"] == 2.50
            assert loaded["221-412"]["unit_price"] == 2.50
            assert "estimated_price" not in loaded["221-412"]
            assert "price_observations" not in loaded["221-412"]
    finally:
        if old is None:user_library.os.environ.pop("ELPLAN_USER_DATA_DIR",None)
        else:user_library.os.environ["ELPLAN_USER_DATA_DIR"]=old

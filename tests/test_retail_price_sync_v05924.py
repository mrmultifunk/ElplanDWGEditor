import json
from pathlib import Path
from tempfile import TemporaryDirectory

from elplan_catalog import retail_price_sync as retail
from elplan_catalog import user_library


def _article(**extra):
    row={"article_no":"504D3010","description":"LK FUGA AIR forfradåse 1 modul","ean":"5703302156080","el_no":"1017059373","unit":"stk"}
    row.update(extra); return row


def test_jsonld_exact_ean_price_is_converted_to_ex_vat():
    html='''<html><script type="application/ld+json">'''+json.dumps({
        "@context":"https://schema.org","@type":"Product","name":"LK FUGA AIR",
        "gtin13":"5703302156080","sku":"504D3010",
        "offers":{"@type":"Offer","price":"30.00","priceCurrency":"DKK"}
    })+'''</script></html>'''
    obs=retail.parse_product_page(html,_article(),provider=retail.PROVIDERS[0],url="https://www.wattoo.dk/test")
    assert obs is not None
    assert obs.matched_by == "EAN"
    assert obs.price_incl_vat == 30.0
    assert obs.price_excl_vat == 24.0
    assert obs.currency == "DKK"


def test_mismatched_product_is_rejected_even_when_price_exists():
    html='''<script type="application/ld+json">'''+json.dumps({
        "@type":"Product","gtin13":"5703302156097","sku":"504D3015",
        "offers":{"price":"34.75","priceCurrency":"DKK"}
    })+'''</script>'''
    assert retail.parse_product_page(html,_article(),provider=retail.PROVIDERS[0],url="https://www.wattoo.dk/wrong") is None


def test_estimator_uses_average_for_two_and_median_for_three_sources():
    two=[
        {"provider":"A","provider_key":"a","price_excl_vat":19.2,"currency":"DKK","price_unit":"stk","checked":"2026-08-26"},
        {"provider":"B","provider_key":"b","price_excl_vat":24.0,"currency":"DKK","price_unit":"stk","checked":"2026-08-26"},
    ]
    e=retail.estimate_from_observations(two,article_unit="stk")
    assert e["estimated_price"] == 21.6
    assert e["estimated_price_method"] == "Gennemsnit"
    assert e["estimated_price_confidence"] == "Middel"
    three=two+[{"provider":"C","provider_key":"c","price_excl_vat":20.0,"currency":"DKK","price_unit":"stk","checked":"2026-08-26"}]
    e=retail.estimate_from_observations(three,article_unit="stk")
    assert e["estimated_price"] == 20.0
    assert e["estimated_price_method"] == "Median"
    assert e["estimated_price_confidence"] == "Høj"


def test_manual_price_survives_webshop_estimate_merge():
    book={"A1":{"manual_price":42.0,"manual_price_source":"Egen nettopris","price_currency":"DKK","price_unit":"stk"}}
    estimates={"A1":{
        "estimated_price":55.0,"estimated_price_source":"Webshops: A + B","estimated_price_checked":"2026-08-26",
        "estimated_price_confidence":"Middel","estimated_price_method":"Gennemsnit","estimated_price_sources":2,
        "estimated_price_min":50.0,"estimated_price_max":60.0,"price_currency":"DKK","price_unit":"stk",
        "price_observations":[{"provider":"A","provider_key":"a","price_incl_vat":62.5,"price_excl_vat":50.0,"currency":"DKK","price_unit":"stk","url":"https://a.example/p","matched_by":"EAN","matched_value":"1","checked":"2026-08-26","confidence":"Høj","vat_rate":0.25}]
    }}
    merged=user_library.merge_price_estimates(book,estimates)
    assert merged["A1"]["manual_price"] == 42.0
    assert merged["A1"]["estimated_price"] == 55.0
    row=user_library.apply_article_prices([{"article_no":"A1","description":"x","unit":"stk"}],merged)[0]
    assert row["unit_price"] == 42.0
    assert row["price_status"] == "Manuel"


def test_pricebook_v3_persists_webshop_observations():
    old=user_library.os.environ.get("ELPLAN_USER_DATA_DIR")
    try:
        with TemporaryDirectory() as td:
            user_library.os.environ["ELPLAN_USER_DATA_DIR"]=td
            rec={"A1":{"estimated_price":10.0,"price_currency":"DKK","price_unit":"stk","price_observations":[{
                "provider":"WATTOO","provider_key":"wattoo","price_incl_vat":12.5,"price_excl_vat":10.0,"currency":"DKK","price_unit":"stk","url":"https://www.wattoo.dk/x","matched_by":"EAN","matched_value":"123","checked":"2026-08-26","confidence":"Høj","vat_rate":0.25
            }]}}
            user_library.save_article_prices(rec)
            raw=json.loads((Path(td)/"article_prices.json").read_text(encoding="utf-8"))
            assert raw["version"] == 5
            loaded=user_library.load_article_prices()
            assert loaded["A1"]["price_observations"][0]["provider"] == "WATTOO"
    finally:
        if old is None:user_library.os.environ.pop("ELPLAN_USER_DATA_DIR",None)
        else:user_library.os.environ["ELPLAN_USER_DATA_DIR"]=old

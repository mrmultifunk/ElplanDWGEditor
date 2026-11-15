import json
from pathlib import Path
from tempfile import TemporaryDirectory

import retail_price_sync as retail
import user_library
import core_logic as core
from project_model import APP_VERSION


def _wago(**extra):
    row={
        "article_no":"221-412",
        "description":"WAGO 221 fjedersamlemuffe, 2-leder",
        "manufacturer":"WAGO",
        "product_type":"Samlemuffe",
        "ean":"4050821808435",
        "el_no":"7821100470",
        "unit":"stk",
        "sales_package_quantity":100,
    }
    row.update(extra)
    return row


def test_version():
    assert APP_VERSION == core.APP_VERSION == "0.59.81"


def _product_html(price, *, name="WAGO 221-412"):
    return '<script type="application/ld+json">'+json.dumps({
        "@type":"Product","name":name,"gtin13":"4050821808435","sku":"221-412",
        "offers":{"price":str(price),"priceCurrency":"DKK","unitText":"stk"},
    })+'</script>'


def test_json_product_name_package_is_converted_to_each_price():
    obs=retail.parse_product_page(
        _product_html(331,name="WAGO 221-412 · 100 stk"),_wago(),
        provider=retail.PROVIDERS[0],url="https://www.wattoo.dk/wago-221-412",
    )
    assert obs is not None
    assert obs.package_quantity == 100
    assert obs.raw_price_incl_vat == 331
    assert obs.price_incl_vat == 3.31
    assert obs.price_excl_vat == 2.648
    assert obs.price_unit == "stk"
    assert obs.normalization_version == 3


def test_wago_catalog_package_fallback_handles_shop_calling_box_one_piece():
    obs=retail.parse_product_page(
        _product_html(331),_wago(),provider=retail.PROVIDERS[0],
        url="https://www.wattoo.dk/wago-221-412",
    )
    assert obs is not None
    assert obs.package_quantity == 100
    assert "artikeldata" in obs.package_label
    assert obs.price_excl_vat == 2.648


def test_real_single_wago_price_is_not_divided_by_catalog_package():
    obs=retail.parse_product_page(
        _product_html(6.25),_wago(),provider=retail.PROVIDERS[0],
        url="https://www.wattoo.dk/wago-221-412",
    )
    assert obs is not None
    assert obs.package_quantity == 1
    assert obs.price_incl_vat == 6.25
    assert obs.price_excl_vat == 5.0


def test_pricebook_v4_wago_package_estimate_is_removed_but_manual_price_survives():
    raw={"version":4,"prices":{"221-412":{
        "estimated_price":264.8,"estimated_price_source":"Webshops: WATTOO",
        "manual_price":2.50,"manual_price_source":"Egen nettopris",
        "price_currency":"DKK","price_unit":"stk",
        "price_observations":[{
            "provider":"WATTOO","provider_key":"wattoo","price_incl_vat":331,
            "price_excl_vat":264.8,"currency":"DKK","price_unit":"stk",
            "checked":"2026-09-04","normalization_version":2,
        }],
    }}}
    normalized=user_library.normalize_article_prices(raw)
    assert normalized["221-412"]["manual_price"] == 2.50
    assert "estimated_price" not in normalized["221-412"]
    assert "price_observations" not in normalized["221-412"]


def test_existing_catalog_wago_pack_price_is_migrated_to_bundled_each_estimate():
    previous=user_library.os.environ.get("ELPLAN_USER_DATA_DIR")
    try:
        with TemporaryDirectory() as directory:
            user_library.os.environ["ELPLAN_USER_DATA_DIR"]=directory
            Path(directory,"articles.json").write_text(json.dumps({"version":2,"articles":[{
                "article_no":"221-412","description":"WAGO gammel pris","manufacturer":"WAGO",
                "unit":"stk","unit_price":331.0,"price_unit":"stk",
            }]}),encoding="utf-8")
            user_library.invalidate_core_data_caches()
            lookup={row["article_no"]:row for row in user_library.load_core_article_catalog()}
            row=lookup["221-412"]
            assert row["unit_price"] == 4.83
            assert row["price_unit"] == "stk"
            assert float(row["sales_package_quantity"]) == 100
            assert float(row["catalog_price_revision"]) == 2
            saved=json.loads(Path(directory,"articles.json").read_text(encoding="utf-8"))
            saved_row=next(item for item in saved["articles"] if item["article_no"]=="221-412")
            assert saved_row["unit_price"] == 4.83
    finally:
        if previous is None:user_library.os.environ.pop("ELPLAN_USER_DATA_DIR",None)
        else:user_library.os.environ["ELPLAN_USER_DATA_DIR"]=previous
        user_library.invalidate_core_data_caches()

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import core_logic as core
from elplan_catalog import user_library


def test_manual_price_overrides_estimate_without_destroying_it():
    catalog=[{
        "article_no":"A1","description":"Test","unit":"stk",
        "estimated_price":50.0,"price_currency":"DKK",
        "estimated_price_source":"Katalog","estimated_price_checked":"2026-08-26",
    }]
    pricebook={"A1":{"manual_price":42.0,"price_currency":"DKK","manual_price_source":"Egen pris"}}
    row=user_library.apply_article_prices(catalog,pricebook)[0]
    assert row["estimated_price"] == 50.0
    assert row["manual_price"] == 42.0
    assert row["effective_price"] == row["unit_price"] == 42.0
    assert row["price_status"] == "Manuel"
    assert row["price_source"] == "Egen pris"

    # Et senere katalogestimat må gerne ændres; den manuelle pris vinder stadig.
    catalog[0]["estimated_price"] = 55.0
    row=user_library.apply_article_prices(catalog,pricebook)[0]
    assert row["estimated_price"] == 55.0
    assert row["unit_price"] == 42.0


def test_legacy_pricebook_migrates_to_v2_and_keeps_compatibility_aliases():
    old=os.environ.get("ELPLAN_USER_DATA_DIR")
    try:
        with TemporaryDirectory() as td:
            os.environ["ELPLAN_USER_DATA_DIR"]=td
            user_library.save_article_prices({"A1":{"unit_price":99.95,"price_kind":"Manuel nettopris","price_currency":"DKK"}})
            raw=json.loads((Path(td)/"article_prices.json").read_text(encoding="utf-8"))
            assert raw["version"] == 5
            assert raw["prices"]["A1"]["manual_price"] == 99.95
            assert "unit_price" not in raw["prices"]["A1"]
            loaded=user_library.load_article_prices()
            assert loaded["A1"]["manual_price"] == 99.95
            assert loaded["A1"]["unit_price"] == 99.95
            assert loaded["A1"]["price_status"] == "Manuel"
    finally:
        if old is None: os.environ.pop("ELPLAN_USER_DATA_DIR",None)
        else: os.environ["ELPLAN_USER_DATA_DIR"]=old


def test_bom_uses_actual_cable_metres_when_price_is_per_metre():
    cable=core.CablePlacement(points=[(0,0),(250,0)],cable_spec="3G1,5")
    catalog=[{
        "article_no":"R100","description":"100 m rulle","unit":"rulle","kind":"cable",
        "cable_spec":"3G1,5","package_length_m":100,
        "unit_price":8.0,"effective_price":8.0,"price_unit":"m","price_currency":"DKK","price_status":"Manuel",
    }]
    rows,missing=core.build_bom([],catalog,{},[cable],{cable.uid:"R100"},1.0,0.0)
    assert not missing
    assert rows[0]["qty"] == 3  # indkøbsbehov: tre ruller
    assert rows[0]["price_basis_qty"] == 250.0
    assert rows[0]["line_total"] == 2000.0
    assert rows[0]["price_unit"] == "m"


def test_estimate_only_is_marked_as_estimate():
    row=user_library.apply_article_prices(
        [{"article_no":"A1","description":"Test","unit":"stk"}],
        {"A1":{"estimated_price":12.5,"price_currency":"DKK","price_unit":"stk"}},
    )[0]
    assert row["unit_price"] == 12.5
    assert row["price_status"] == "Estimeret"

import os
import tempfile
from pathlib import Path

import core_logic as core
import user_library


def test_article_price_normalization_and_overlay():
    catalog=[{"article_no":"A1","description":"Test","unit":"stk"}]
    prices={"A1":{"unit_price":12.5,"price_currency":"dkk","price_kind":"Estimat","price_source":"Test"}}
    rows=user_library.apply_article_prices(catalog,prices)
    assert rows[0]["unit_price"]==12.5
    assert rows[0]["price_currency"]=="DKK"
    assert rows[0]["price_kind"]=="Estimat"


def test_global_pricebook_roundtrip():
    old=os.environ.get("ELPLAN_USER_DATA_DIR")
    try:
        with tempfile.TemporaryDirectory() as td:
            os.environ["ELPLAN_USER_DATA_DIR"]=td
            data={"A1":{"unit_price":99.95,"price_currency":"DKK","price_kind":"Manuel nettopris","price_checked":"2026-08-21"}}
            path=user_library.save_article_prices(data)
            assert path==Path(td)/"article_prices.json"
            loaded=user_library.load_article_prices()
            assert loaded["A1"]["unit_price"]==99.95
            assert loaded["A1"]["price_kind"]=="Manuel"
            assert loaded["A1"]["manual_price"]==99.95
    finally:
        if old is None: os.environ.pop("ELPLAN_USER_DATA_DIR",None)
        else: os.environ["ELPLAN_USER_DATA_DIR"]=old


def test_bom_has_unit_price_and_total():
    placements=[core.Placement('switch_1',0,0),core.Placement('switch_1',100,0)]
    catalog=[{'article_no':'A1','description':'1P','unit':'stk','unit_price':25.0,'price_currency':'DKK','price_kind':'Estimat'}]
    bindings={p.uid:{'symbol':[{'article_no':'A1','qty':1}]} for p in placements}
    rows,missing=core.build_bom(placements,catalog,bindings)
    assert not missing
    assert rows[0]['qty']==2
    assert rows[0]['unit_price']==25.0
    assert rows[0]['line_total']==50.0
    assert rows[0]['price_currency']=='DKK'


def test_cable_roll_price_multiplies_roll_quantity():
    cable=core.CablePlacement(points=[(0,0),(250,0)],cable_spec='3G1,5')
    catalog=[{'article_no':'R100','description':'100 m rulle','unit':'rulle','kind':'cable','cable_spec':'3G1,5','package_length_m':100,'unit_price':500.0,'price_currency':'DKK'}]
    rows,missing=core.build_bom([],catalog,{},[cable],{cable.uid:'R100'},1.0,0.0)
    assert not missing
    assert rows[0]['qty']==3
    assert rows[0]['line_total']==1500.0

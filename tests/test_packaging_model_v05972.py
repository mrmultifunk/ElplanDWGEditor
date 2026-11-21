from types import SimpleNamespace

from elplan_catalog import article_exchange
import core_logic as core


def test_component_packaging_is_numeric_and_rounds_purchase():
    row=core.normalize_article_catalog([{
        "article_no":"P50","description":"Pakkevare","unit":"stk",
        "consumption_unit":"stk","sales_unit":"pakke",
        "sales_package_quantity":"50","minimum_order_quantity":"2",
    }])[0]
    assert row["sales_package_quantity"] == 50.0
    assert row["minimum_order_quantity"] == 2.0
    purchase=core.article_purchase_requirement(row,7)
    assert purchase["purchase_quantity"] == 2.0
    assert purchase["purchased_consumption_quantity"] == 100.0
    assert purchase["surplus_quantity"] == 93.0


def test_legacy_cable_roll_derives_new_model_without_changing_unit():
    row=core.normalize_article_catalog([{
        "article_no":"R100","kind":"cable","unit":"rulle","package_length_m":100,
    }])[0]
    assert row["unit"] == "rulle"
    assert row["consumption_unit"] == "m"
    assert row["sales_unit"] == "rulle"
    assert row["sales_package_quantity"] == 100.0


def test_price_basis_distinguishes_piece_and_package_price():
    base={"unit":"stk","consumption_unit":"stk","sales_unit":"pakke","sales_package_quantity":50}
    assert core.article_price_basis_quantity({**base,"price_unit":"stk"},71)==71
    assert core.article_price_basis_quantity({**base,"price_unit":"pakke"},71)==2


def test_build_bom_uses_package_price_once_for_small_requirement():
    placement=SimpleNamespace(symbol="socket",uid="S1",x=0,y=0,pl_box_splices=[])
    catalog=[{"article_no":"P50","description":"Pakkevare","unit":"stk",
              "consumption_unit":"stk","sales_unit":"pakke","sales_package_quantity":50,
              "unit_price":125,"price_unit":"pakke"}]
    rows,missing=core.build_bom([placement],catalog,{"S1":{"symbol":[{"article_no":"P50","qty":7}]}})
    assert not missing
    assert rows[0]["qty"] == 7
    assert rows[0]["purchase_quantity"] == 1
    assert rows[0]["line_total"] == 125
    assert rows[0]["surplus_quantity"] == 43


def test_article_exchange_v4_includes_packaging_fields():
    assert article_exchange.FORMAT_VERSION == 4
    for field in ("consumption_unit","sales_unit","sales_package_quantity","minimum_order_quantity","package_label"):
        assert field in article_exchange.CSV_FIELDS


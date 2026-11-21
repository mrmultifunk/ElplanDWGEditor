from datetime import date

from elplan_catalog import bom_quality


def test_quality_audit_collects_price_packaging_and_binding_findings():
    rows=[
        {"article_no":"OK","unit_price":10,"price_checked":"2026-09-10","consumption_unit":"stk","sales_unit":"stk","sales_package_quantity":1,"minimum_order_quantity":1},
        {"article_no":"OLD","unit_price":20,"price_checked":"2026-07-01","consumption_unit":"stk","sales_unit":"stk","sales_package_quantity":1,"minimum_order_quantity":1},
        {"article_no":"PACK","unit_price":None,"consumption_unit":"stk","sales_unit":"stk","sales_package_quantity":50,"minimum_order_quantity":1},
        {"article_no":"MISS","missing_article":True,"unit_price":None,"consumption_unit":"stk","sales_unit":"stk","sales_package_quantity":1,"minimum_order_quantity":1},
    ]
    missing=[{"part_label":"Stikkontakt · indsats"}]
    result=bom_quality.audit_bom(rows,missing,today=date(2026,9,14),stale_days=30)
    assert result["summary"]["errors"] == 2
    assert result["summary"]["warnings"] == 4
    assert {x["code"] for x in result["by_article"]["OLD"]} == {"stale_price"}
    assert {x["code"] for x in result["by_article"]["PACK"]} == {"missing_price","package_unit_ambiguous"}


def test_quality_audit_accepts_well_formed_package():
    result=bom_quality.audit_bom([{
        "article_no":"P50","unit_price":2.5,"price_checked":"2026-09-14",
        "consumption_unit":"stk","sales_unit":"pakke","sales_package_quantity":50,
        "minimum_order_quantity":1,
    }],today=date(2026,9,14))
    assert result["findings"] == []


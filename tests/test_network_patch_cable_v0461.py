import core_logic as core


def test_helukabel_patch_cable_meterware_is_bundled():
    lookup={r["article_no"]:r for r in core.load_predefined_article_catalog()}
    row=lookup["802184"]
    assert row["manufacturer"]=="HELUKABEL"
    assert row["kind"]=="cable" and row["unit"]=="m"
    assert row["cable_spec"]=="CAT7 S/FTP"
    assert row["ean"]=="4060892314254"
    assert row.get("package_length_m",0.0)==0.0
    assert row["product_page"].startswith("https://shop.helu.com/")
    assert row["image_url"].endswith("M802184_PF_1520x1160.jpg")
    assert row["datasheet_url"].endswith("HELU_M802184_DE.pdf")


def test_cat7_patch_cable_matches_existing_network_preset():
    source=open("elplan_qt/qt_app.py",encoding="utf-8").read()+open("elplan_qt/qt_cable_panel.py",encoding="utf-8").read()
    assert '"CAT7 S/FTP"' in source

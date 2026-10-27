import json
from pathlib import Path

import core_logic as core

ROOT = Path(__file__).resolve().parents[1]


def test_nordtronic_article_is_in_both_catalog_sources():
    payload = json.loads((ROOT / "predefined_articles.json").read_text(encoding="utf-8"))
    raw = next(a for a in payload["articles"] if a.get("article_no") == "98425033")
    assert raw["ean"] == "5704629006065"
    assert raw["manufacturer"] == "Nordtronic A/S"
    assert raw["category"] == "Nordtronic · Lysstyring"
    assert "P" in raw["note"] and "COM" in raw["note"]

    loaded = {a["article_no"]: a for a in core.load_predefined_article_catalog()}
    art = loaded["98425033"]
    assert art["ean"] == "5704629006065"
    assert art["product_page"].startswith("https://nordtronic.dk/")
    assert art["datasheet_url"].endswith("Datablad_DK_98425033.pdf")
    assert art["manual_url"].endswith("Manual_CeilingOutletDimmerZigbee_98425033.pdf")


def test_nordtronic_outlet_profile_exposes_all_physical_functions():
    profile = core.pl_outlet_profile("nordtronic_zigbee", ["a"])
    assert profile["article_no"] == "98425033"
    assert profile["ean"] == "5704629006065"
    terminals = {t["label"]: t for t in profile["terminals"]}
    assert set(terminals) == {"P", "COM", "PE", "N", "~", "L"}
    assert terminals["P"]["function_id"] == "switch:a"
    assert terminals["COM"]["function_id"] == "com"
    assert terminals["~"]["function_id"] == "dimmed_out"
    assert terminals["L"]["function_id"] == "l"
    assert terminals["N"]["function_id"] == "n"
    assert terminals["PE"]["function_id"] == "pe"


def test_nordtronic_table_options_make_p_com_and_dimmed_output_assignable():
    options = dict(core.pl_wiring_function_options(["a"], "nordtronic_zigbee"))
    assert options["switch:a"].startswith("P")
    assert "COM" in options["com"]
    assert "Dæmpet udgang" in options["dimmed_out"]
    assert core.pl_wiring_function_caption("switch:a", ["a"], "nordtronic_zigbee").startswith("P")
    assert core.pl_wiring_function_caption("com", ["a"], "nordtronic_zigbee").startswith("COM")


def test_nordtronic_aliases_are_stable():
    assert core.normalize_pl_outlet_type("Nordtronic") == "nordtronic_zigbee"
    assert core.normalize_pl_outlet_type("98425033") == "nordtronic_zigbee"


def test_light_connection_can_be_explicitly_bound_to_article_without_becoming_required():
    parts = core.bom_symbol_parts("light_connection")
    assert len(parts) == 1
    assert parts[0]["id"] == "outlet"
    assert parts[0]["required"] is False

    lamp = core.Placement("light_connection", 0, 0, uid="lamp-1")
    catalog = core.load_predefined_article_catalog()
    rows, missing = core.build_bom(
        [lamp], catalog, {"lamp-1": {"outlet": [{"article_no": "98425033", "qty": 1.0}]}},
    )
    assert not missing
    assert next(r for r in rows if r["article_no"] == "98425033")["qty"] == 1.0

from pathlib import Path

from elplan_catalog import assembly_naming
import core_logic as core
from elplan_project.project_model import APP_VERSION


def test_version_and_name_builder_uses_canonical_verified_system_name():
    assert APP_VERSION == core.APP_VERSION
    assert assembly_naming.build_assembly_name(
        product_type="Stikkontakt",
        configuration="2×1M",
        system_series="LK FUGA SLIM",
        mounting="Forfra",
        color="Koksgrå",
    ) == "2×1M FUGA SLIM Forfra Stikkontakt Koksgrå"
    # 0.59.31 aliases are still accepted, but are canonicalised.
    assert assembly_naming.build_assembly_name(
        product_type="Stikkontakt", execution="2×1M", system="FUGA SLIM", color="Koksgrå"
    ).startswith("2×1M FUGA SLIM Stikkontakt")


def test_system_series_registry_is_controlled_and_unknown_values_do_not_become_filters():
    assert "LK FUGA SLIM" in assembly_naming.SYSTEM_OPTIONS
    assert "LK FUGA AIR" in assembly_naming.SYSTEM_OPTIONS
    assert "LK FUGA SOFTLINE 63" in assembly_naming.SYSTEM_OPTIONS
    assert "Wiser" in assembly_naming.SYSTEM_OPTIONS
    assert assembly_naming.normalize_naming_fields({"system_series":"FUGA SLIM"})["system_series"] == "LK FUGA SLIM"
    assert assembly_naming.normalize_naming_fields({"system_series":"FUGA SUPER RANDOM"})["system_series"] == ""


def test_name_assistant_can_recover_existing_manual_convention_into_structured_fields():
    values = assembly_naming.infer_assembly_name_fields({
        "name": "2X1M FUGA SLIM FORFRA STIKKONTAKT KOKSGRÅ",
        "category": "Stikkontakter",
        "variant": "",
        "items": [],
    })
    assert values["product_type"] == "Stikkontakt"
    assert values["configuration"] == "2×1M"
    assert values["system_series"] == "LK FUGA SLIM"
    assert values["mounting"] == "Forfra"
    assert values["color"] == "Koksgrå"
    assert values["extra"] == ""


def test_component_metadata_is_only_a_suggestion_source():
    catalog = [{
        "article_no": "504D3520",
        "description": "LK FUGA AIR dåser SLIM forfradåse 2 modul blå",
        "product_family": "LK FUGA AIR",
        "variant": "SLIM",
        "color": "Blå",
    }]
    values = assembly_naming.infer_assembly_name_fields({
        "name": "",
        "category": "",
        "variant": "",
        "items": [{"article_no": "504D3520", "qty": 1}],
    }, catalog)
    assert values["system_series"] == "LK FUGA AIR SLIM"
    assert values["color"] == "Blå"
    assert values["configuration"] == ""  # do not guess stykliste geometry from one component
    assert values["mounting"] == "Forfra"


def test_editor_keeps_name_field_manual_and_assistant_is_opt_in():
    source = Path("elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    assert 'QPushButton("Navneassistent…")' in source
    assert 'self.name.setText(generated)' in source
    assert 'self.name.setReadOnly(True)' not in source
    assert 'setText("Brug navn og parametre")' in source
    assert 'self._load_naming_controls(dlg.naming_fields())' in source
    assert 'self.tabs.addTab(tab,"Styklister")' in source

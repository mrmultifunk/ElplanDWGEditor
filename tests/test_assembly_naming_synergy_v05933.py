from pathlib import Path

import assembly_naming
import core_logic as core
from project_model import APP_VERSION


def test_version_and_compact_name_keep_canonical_filter_value_separate():
    assert APP_VERSION == core.APP_VERSION == "0.59.85"
    fields=assembly_naming.normalize_naming_fields({
        "product_type":"Stikkontakt", "configuration":"2×1M",
        "function":"Med jord", "system_series":"FUGA SLIM",
        "mounting":"Forfra", "color":"Koksgrå",
    })
    assert fields["system_series"] == "LK FUGA SLIM"
    assert assembly_naming.build_assembly_name(**fields) == "2×1M FUGA SLIM Forfra Stikkontakt Med jord Koksgrå"


def test_stylist_editor_exposes_same_naming_fields_as_assistant():
    src=Path("qt_articles.py").read_text(encoding="utf-8")
    for token in (
        "self.naming_type", "self.naming_configuration", "self.naming_function",
        "self.naming_system", "self.naming_mounting", "self.naming_color",
        "self.naming_extra",
    ):
        assert token in src
    assert 'QGroupBox("Navneparametre")' in src
    assert 'QPushButton("Dan navn")' in src
    assert 'QPushButton("Udfyld fra stykliste")' in src
    assert 'QPushButton("Ryd navneparametre")' in src
    assert 'self._load_naming_controls(dlg.naming_fields())' in src
    assert '"naming":deepcopy(self._collect_naming_controls())' in src


def test_manual_name_remains_supported_and_parameter_refresh_is_explicit():
    src=Path("qt_articles.py").read_text(encoding="utf-8")
    assert 'self.name.setReadOnly(True)' not in src
    assert 'aktuelt navn er manuelt' in src
    assert 'record["naming"]={}' in src  # assistant can re-infer from current content
    assert '"naming":{},' in src         # main editor can do the same

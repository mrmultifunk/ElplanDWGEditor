from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


ROOT=Path(__file__).resolve().parents[1]


def test_version_and_task_based_property_workflow_source():
    assert APP_VERSION==core.APP_VERSION=="0.59.83"
    app=(ROOT/"qt_app.py").read_text(encoding="utf-8")
    theme=(ROOT/"qt_theme.py").read_text(encoding="utf-8")
    for token in ('("connect","Forbind")','("data","Data")','("purchase","Indkøb")'):
        assert token in app
    assert "def _set_properties_workflow" in app
    assert "def _apply_properties_workflow_visibility" in app
    assert 'preferred="connect"' in app
    assert 'self.property_actions_widget.setVisible(key in {"data","purchase"}' in app
    assert "QPushButton#propertyWorkflowTab:checked" in theme


def test_solar_symbols_are_vector_based_and_use_a_dedicated_layer():
    group=core.SYMBOL_GROUPS["Solceller / energi"]
    assert group=={
        "Solcellepanel(er)":"solar_panel",
        "Solcelleinverter":"solar_inverter",
        "Solcellebatteri":"solar_battery",
    }
    assert core.SOLAR_LAYER=="EL-SOLCELLER"
    assert core.GENERATED_LAYER_COLORS[core.SOLAR_LAYER]==3
    for symbol in group.values():
        assert core.symbol_layer(symbol)==core.SOLAR_LAYER
        primitives=core.symbol_primitives(symbol,100.0)
        assert len(primitives)>=8
        assert all(row[0]!="text" for row in primitives)
        x1,y1,x2,y2=core.symbol_local_bbox(symbol,100.0)
        assert x2>x1 and y2>y1


def test_solar_connection_and_mount_points_match_physical_use():
    assert len(core.symbol_connection_points("solar_panel",100.0))==3
    assert len(core.symbol_connection_points("solar_inverter",100.0))==4
    assert len(core.symbol_connection_points("solar_battery",100.0))==3
    assert core.symbol_mount_points("solar_panel",100.0)==[]
    assert core.symbol_mount_points("solar_inverter",100.0)==[(0.0,0.0)]
    assert core.symbol_mount_points("solar_battery",100.0)==[(0.0,0.0)]


def test_solar_components_support_explicit_articles_and_bom():
    for symbol in ("solar_panel","solar_inverter","solar_battery"):
        parts=core.bom_symbol_parts(symbol)
        assert len(parts)==1
        assert parts[0]["id"]=="symbol"
        assert parts[0]["required"] is True
        assert parts[0]["base"]==symbol
        assert core.bom_supported_symbol(symbol)

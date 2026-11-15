from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def _cable(category="switch_cable"):
    cable=core.CablePlacement(
        points=[(0,0),(100,0)], uid="c1", cable_id="K01", cable_spec="5G1,5",
        cable_category=category, color="#ea580c", line_style="dashdot",
    )
    core.set_cable_symbol_connections(cable,[{"point_index":0,"symbol_uid":"lamp1","symbol_port":0}])
    return cable


def test_version_05021():
    assert APP_VERSION == core.APP_VERSION == "0.59.78"


def test_pl_cable_legs_keep_category_and_contour_metadata():
    leg=core.cable_legs_at_symbol([_cable()],"lamp1")[0]
    assert leg["cable_category"] == "switch_cable"
    assert leg["line_style"] == "dashdot"
    assert leg["color"] == "#ea580c"


def test_pl_configurator_exposes_project_cable_categories_visually():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8") + Path("qt_app.py").read_text(encoding="utf-8")
    assert "cable_categories=None" in source
    assert "self.category_legend=QLabel()" in source
    assert 'form.addRow("Kategori",self.category_value)' in source
    assert "def _category_for_leg" in source
    assert "def _category_icon" in source
    assert 'category_name=str(category.get("name") or "Øvrige")' in source
    assert 'self._category_pen_style(category.get("line_style"))' in source
    assert "cable_categories=self._cable_categories()" in source
    docs=Path("docs/history/PL_BOX_CATEGORIES_0.50.21.md").read_text(encoding="utf-8")
    assert "PL-dåse og kabelkategorier" in docs


def test_leader_distribution_cards_show_cable_category_between_id_and_spec():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8") + Path("qt_app.py").read_text(encoding="utf-8")
    assert "self._category_records=core.default_cable_category_records()" in source
    assert "cable_categories=None" in source
    assert "category=self._category_for_leg(leg)" in source
    assert 'meta_text=" · ".join(x for x in [category_name,spec,side] if x)' in source
    assert 'PLBoxDiagramWidget._category_pen_style(category.get("line_style"))' in source
    assert "self.splices,self.cable_categories" in source

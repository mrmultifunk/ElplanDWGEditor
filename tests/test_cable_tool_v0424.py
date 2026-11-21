from pathlib import Path

import core_logic as core


def test_direct_cable_binding_remains_instance_specific():
    cables=[
        core.CablePlacement(points=[(0,0),(8,0)],cable_spec='5G6',cable_id='K01'),
        core.CablePlacement(points=[(0,10),(8,10)],cable_spec='5G6',cable_id='K02'),
    ]
    catalog=[{'article_no':'CABLE-5G6','description':'5G6','kind':'cable','unit':'m','package_length_m':0}]
    rows,missing=core.build_bom([],catalog,{},cables,{cables[0].uid:'CABLE-5G6'},1.0,0.0)
    assert [(r['article_no'],r['qty']) for r in rows]==[('CABLE-5G6',8.0)]
    assert len(missing)==1 and missing[0]['count']==1


def test_cable_dock_has_direct_article_workflow_and_scroll_area():
    panel=Path('elplan_qt/qt_cable_panel.py').read_text(encoding='utf-8')
    main=Path('elplan_qt/qt_app.py').read_text(encoding='utf-8')
    assert 'scroll = QScrollArea()' in panel
    assert 'QGroupBox("Artikel / BOM")' in panel
    assert 'def choose_cable_article(self)' in main
    assert 'kind_filter="cable"' in main
    assert 'self.project.raw["cable_instance_articles"]' in main
    assert 'self._pending_cable_article_no=""' in main


def test_symbol_selection_raises_properties_and_leaves_cable_tool():
    source=Path('elplan_qt/qt_app.py').read_text(encoding='utf-8')
    selection=source[source.index('    def _selection_changed(self) -> None:'):source.index('    def _selected_symbol_item', source.index('    def _selection_changed(self) -> None:'))]
    assert 'self.close_cable_tool()' in selection
    assert 'self._show_inspector_page(' in selection
    assert '"properties"' in selection


def test_other_drawing_tools_close_cable_workspace_first():
    source=Path('elplan_qt/qt_app.py').read_text(encoding='utf-8')
    assert 'if self._cable_tool_is_open(): self.close_cable_tool()\n        self.view.start_symbol_placement' in source
    assert 'if self._cable_tool_is_open(): self.close_cable_tool()\n        self.view.start_text_tool' in source
    assert 'if self._cable_tool_is_open(): self.close_cable_tool()\n        self.view.start_spot_pattern("line",config)' in source

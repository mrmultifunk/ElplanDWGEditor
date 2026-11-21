from pathlib import Path


def test_parallel_cable_controls_and_route_snap_are_wired():
    app=Path('elplan_qt/qt_app.py').read_text(encoding='utf-8') + Path('elplan_qt/qt_cable_panel.py').read_text(encoding='utf-8')
    graphics=Path('elplan_qt/qt_graphics.py').read_text(encoding='utf-8')
    assert 'Snap til eksisterende kabelruter' in app
    assert 'Adskil fælles kabelruter i parallelle baner' in app
    assert 'Vis ×N på fælles ruter med 3+ kabler' in app
    assert 'Fremhæv kabler ved valgt symbol' in app
    assert 'snap_routes=self.cable_snap_routes.isChecked()' in app
    assert 'def snap_to_existing_cable_route' in graphics
    assert '"KABELRUTE"' in graphics

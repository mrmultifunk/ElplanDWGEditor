from pathlib import Path


def test_cable_assistant_is_non_modal_and_exposes_shortcuts():
    source=Path('qt_app.py').read_text(encoding='utf-8') + Path('qt_cable_panel.py').read_text(encoding='utf-8')
    graphics=Path('qt_graphics.py').read_text(encoding='utf-8')
    assert 'class CableAssistantPopup(QFrame)' in source
    assert 'Interaktiv kabel-assistent' in source
    assert 'Afslut her' in source
    assert 'Afslut + nyt herfra' in source
    assert 'Kun forbi' in source
    assert 'Fortryd punkt' in source
    assert 'QInputDialog' not in source[source.index('class CableAssistantPopup'):source.index('class ComboConfiguratorDialog')]
    assert 'cablePointCommitted = Signal(object)' in graphics


def test_assistant_can_convert_symbol_click_to_waypoint():
    graphics=Path('qt_graphics.py').read_text(encoding='utf-8')
    body=graphics[graphics.index('    def convert_last_cable_connection_to_waypoint'):graphics.index('    def _append_cable_point', graphics.index('    def convert_last_cable_connection_to_waypoint'))]
    assert '_cable_connections' in body
    assert 'point_index' in body
    assert '_update_cable_preview' in body


def test_assistant_restart_seeds_next_cable_at_same_symbol():
    source=Path('qt_app.py').read_text(encoding='utf-8') + Path('qt_cable_panel.py').read_text(encoding='utf-8')
    graphics=Path('qt_graphics.py').read_text(encoding='utf-8')
    assert '_pending_cable_restart_anchor' in source
    assert 'def _start_cable_from_assistant_anchor' in source
    assert 'self.view.seed_cable_start' in source
    assert 'def seed_cable_start' in graphics
    assert 'self._set_next_cable_id()' in source[source.index('    def _cable_finished'):source.index('    def _add_cable')]


def test_assistant_shows_existing_cables_and_duplicate_warning():
    source=Path('qt_app.py').read_text(encoding='utf-8') + Path('qt_cable_panel.py').read_text(encoding='utf-8')
    assert 'def _existing_cables_at_symbol' in source
    assert 'Eksisterende kabler ved symbolet' in source
    assert 'symbolet er allerede registreret tidligere på det aktive kabel' in source

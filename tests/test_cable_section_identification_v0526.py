from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_version_and_section_identification_source():
    assert APP_VERSION == core.APP_VERSION == "0.59.76"
    source = Path("qt_cable_sections.py").read_text(encoding="utf-8")
    assert 'group=str(getattr(placement,"group","") or "").strip()' in source
    assert 'label=str(getattr(placement,"label","") or "").strip()' in source
    assert 'return " · ".join(parts)' in source


def test_section_title_still_uses_connection_name_for_both_ends():
    source = Path("qt_cable_sections.py").read_text(encoding="utf-8")
    assert "self._cable_connection_name(section[\'a\'])" in source
    assert "self._cable_connection_name(section[\'b\'])" in source

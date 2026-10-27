from pathlib import Path

from project_model import APP_VERSION
import core_logic as core

ROOT=Path(__file__).resolve().parents[1]


def test_version_05941():
    assert APP_VERSION == core.APP_VERSION == "0.59.74"


def test_grouped_spot_drag_expands_to_all_members_and_blocks_partial_locked_move():
    source=(ROOT/"qt_app.py").read_text(encoding="utf-8")
    assert 'for member in self._spot_group_members(gid):' in source
    assert 'expanded[member.uid]=member_item' in source
    assert 'self._group_drag_blocked=any' in source
    assert 'Spotgruppen indeholder låste spots' in source


def test_spot_alignment_prioritises_other_spots_and_ignores_group_members():
    source=(ROOT/"qt_graphics.py").read_text(encoding="utf-8")
    assert 'if symbol=="spot"' in source
    assert 'row[0]=="spot"' in source
    assert 'ignored.update(str(uid) for uid in ignore_uids)' in source
    assert 'parts.append("SPOT")' in source

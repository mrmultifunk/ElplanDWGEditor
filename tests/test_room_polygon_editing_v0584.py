from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_v0584_room_polygon_editing_is_directly_exposed():
    assert APP_VERSION == core.APP_VERSION == "0.59.74"
    src = Path("qt_rooms.py").read_text(encoding="utf-8")
    assert "def edit_room_boundary(self,room,zoom=False):" in src
    assert "boundary_edit=menu.addAction('Redigér afgrænsning')" in src
    assert "('Redigér afgrænsning',self._boundary)" in src
    assert "self.window.edit_room_boundary(room,zoom=True)" in src
    assert "self.act_room_edit=QAction(\"Redigér rumafgrænsninger\"" in src


def test_room_polygon_vertex_editing_keeps_undo_redo_path():
    src = Path("qt_rooms.py").read_text(encoding="utf-8")
    assert "RoomVertexHandle" in src
    assert "boundary._sync_handles()" in src
    assert "def _room_vertices_moved" in src
    assert "EditRoomCommand(self,room.uid,{\"points\":before},{\"points\":after}" in src
    assert "self.setSelected(True); self._sync_handles()" in src

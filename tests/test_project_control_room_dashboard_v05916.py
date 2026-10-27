from pathlib import Path
from types import SimpleNamespace

import core_logic as core


def _room(name, x0, y0, x1, y1):
    return core.RoomPlacement(name=name, code="", points=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)], label_x=(x0+x1)/2, label_y=(y0+y1)/2)


def test_project_control_collects_actionable_missing_bom_and_cable_items():
    room=_room("Køkken",0,0,10,10)
    p=core.Placement(symbol="socket",x=5,y=5,label="Køl")
    c=core.CablePlacement(points=[(0,0),(2,0)],cable_spec="3G1,5",cable_id="K001")
    project=SimpleNamespace(placements=[p],cables=[c],rooms=[room],raw={"placement_articles":{},"placement_assemblies":{},"cable_instance_articles":{}})
    window=SimpleNamespace(project=project,global_bom_assemblies=[])
    issues=core.project_control_issues(project.placements,project.cables,project.rooms,project.raw,[])
    titles="\n".join(x["title"] for x in issues)
    assert "Køl mangler artikel" in titles
    assert "K001 mangler kabelartikel" in titles
    assert "K001 mangler ekstra mærkning" in titles


def test_ui_sources_expose_project_control_room_dashboard_and_bom_to_plan_navigation():
    root=Path(__file__).resolve().parents[1]
    app=(root/"qt_app.py").read_text(encoding="utf-8")
    rooms=(root/"qt_rooms.py").read_text(encoding="utf-8")
    articles=(root/"qt_articles.py").read_text(encoding="utf-8")
    control=(root/"qt_project_control.py").read_text(encoding="utf-8")
    visual=(root/"qt_visual_workspace.py").read_text(encoding="utf-8")
    for token in ("Projektkontrol…","open_project_control","Ekstra BOM-rum…","open_bom_manager_for_room"):
        assert token in app
    for token in ("class RoomDashboardDialog","Vis kun dette rum","Åbn rum-BOM…","class PlacementBomRoomsDialog"):
        assert token in rooms
    assert "itemDoubleClicked.connect(self._bom_row_activated)" in articles
    assert "Vis på plan" in articles
    assert "def highlight_bom_article" in control
    assert "_bom_highlight_placement_uids" in visual and "_focus_room_id" in visual

from pathlib import Path

import core_logic as core
from project_model import ProjectDocument, APP_VERSION


def _lamp(uid, group, orientation):
    return core.Placement(
        symbol="light_connection", x=0, y=0, uid=uid, group=group,
        lamp_outlet_type="wiser_dimmer", pl_box_orientation=orientation,
    )


def _cable(uid, lamp_uid, cable_id, spec="5G1,5"):
    cable=core.CablePlacement(points=[(0,0),(100,0)],uid=uid,cable_id=cable_id,cable_spec=spec)
    core.set_cable_symbol_connections(cable,[{"point_index":0,"symbol_uid":lamp_uid,"symbol_port":0}])
    return cable


def test_current_version_is_05012():
    assert APP_VERSION == core.APP_VERSION == "0.59.73"


def test_pl_box_orientation_layout_rotates_port_numbers_physically():
    assert core.pl_box_port_layout(0)[1] == ("top",0)
    assert core.pl_box_port_layout(90)[1] == ("right",0)
    assert core.pl_box_port_layout(180)[1] == ("bottom",2)
    assert core.pl_box_port_layout(270)[1] == ("left",2)
    assert core.pl_box_port_layout(90)[4] == ("left",0)


def test_project_roundtrip_preserves_pl_box_orientation(tmp_path: Path):
    lamp=_lamp("lamp1","G11",270)
    doc=ProjectDocument.from_cad(tmp_path/"plan.dxf")
    doc.placements=[lamp]
    path=tmp_path/"orientation.elplan.json"
    doc.save(path)
    loaded=ProjectDocument.load(path)
    assert loaded.placements[0].pl_box_orientation == 270


def test_pl_box_report_pdf_is_created(tmp_path: Path):
    lamp1=_lamp("lamp1","G11",0)
    lamp2=_lamp("lamp2","G12",90)
    c1=_cable("c1","lamp1","K01","5G1,5")
    c2=_cable("c2","lamp2","K02","3G1,5")
    legs1=core.cable_legs_at_symbol([c1,c2],"lamp1")
    legs2=core.cable_legs_at_symbol([c1,c2],"lamp2")
    lamp1.pl_box_entries=core.auto_assign_pl_box_entries(legs1)
    lamp2.pl_box_entries=core.auto_assign_pl_box_entries(legs2)
    out=tmp_path/"pl_report.pdf"
    result=core.export_pl_box_report_pdf(out,[lamp1,lamp2],[c1,c2],"Testprojekt")
    assert Path(result).exists()
    data=Path(result).read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 2500


def test_qt_pl_box_dialog_exposes_orientation_and_report_action():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8") + Path("qt_app.py").read_text(encoding="utf-8")
    assert 'QLabel("Fysisk orientering:")' in source
    assert 'QPushButton("Rotér 90°")' in source
    assert 'QAction("PL-dåserapport…", self)' in source
    assert 'core.export_pl_box_report_pdf' in source

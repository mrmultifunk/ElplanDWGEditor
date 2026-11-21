from pathlib import Path

import core_logic as core
from elplan_project.project_model import APP_VERSION


def _cable(uid, lamp_uid, cable_id, spec="5G1,5"):
    cable=core.CablePlacement(points=[(0,0),(100,0)],uid=uid,cable_id=cable_id,cable_spec=spec)
    core.set_cable_symbol_connections(cable,[{"point_index":0,"symbol_uid":lamp_uid,"symbol_port":0}])
    return cable


def test_version_05012():
    assert APP_VERSION == core.APP_VERSION == "0.59.85"


def test_report_wiring_rows_show_direct_wago_and_loose_destinations():
    lamp=core.Placement(symbol="light_connection",x=0,y=0,uid="lamp1",group="G11",lamp_outlet_type="wiser_dimmer")
    cables=[
        _cable("c1","lamp1","K01","5G1,5"),
        _cable("c2","lamp1","K02","5G1,5"),
        _cable("c3","lamp1","K03","3G1,5"),
    ]
    legs=core.cable_legs_at_symbol(cables,"lamp1")
    lamp.pl_box_entries=core.auto_assign_pl_box_entries(legs)
    wiring=core.reconcile_pl_box_wiring([],legs)
    for row in wiring:
        if row["core_id"]=="brown" and row["cable_uid"]=="c1":
            row["function"]="l"
    lamp.pl_box_wiring=wiring
    for row in wiring:
        if row["core_id"]=="blue":
            row["function"]="n"
    lamp.pl_box_wiring=wiring
    blue=[core.pl_box_conductor_key(x) for x in wiring if x["core_id"]=="blue"]
    lamp.pl_box_splices=[{
        "id":"w1","function":"n",
        "members":[core.pl_box_conductor_ref(k) for k in blue],
        "article_no":"221-415","connects_to_outlet":True,
    }]

    rows=core.pl_report_wiring_rows(lamp,[lamp],cables)
    assert len(rows)==13
    blues=[r for r in rows if r["core_id"]=="blue"]
    assert len(blues)==3
    assert all(r["route"]=="wago_outlet" for r in blues)
    assert all("WAGO 221-415 -> N" in r["destination"] for r in blues)
    brown_c1=next(r for r in rows if r["core_id"]=="brown" and r["cable"]=="K01")
    assert brown_c1["route"]=="direct"
    assert brown_c1["destination"]=="L - direkte"
    brown_c2=next(r for r in rows if r["core_id"]=="brown" and r["cable"]=="K02")
    assert brown_c2["route"]=="loose"


def test_pdf_report_source_has_dedicated_wiring_section_and_one_box_per_page():
    source=Path("elplan_core/export/pl_report.py").read_text(encoding="utf-8")
    assert "Lederfordeling - fysisk montage" in source
    assert "Hver række er én fysisk leder" in source
    assert "pl_report_wiring_rows" in source
    assert "max_per_col=21" in source
    assert "én tydelig PL-dåse pr. side" in source

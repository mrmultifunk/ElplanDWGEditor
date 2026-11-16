from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def _member(uid, core_id="blue"):
    return {"cable_uid": uid, "point_index": 0, "leg": "endpoint", "core_id": core_id}


def test_version_0505():
    assert APP_VERSION == core.APP_VERSION == "0.59.82"


def test_wago_articles_are_bundled_with_ean():
    lookup={a["article_no"]:a for a in core.load_predefined_article_catalog()}
    expected={
        "221-412":"4050821808435",
        "221-413":"4050821808442",
        "221-415":"4055143234658",
        "221-420":"4066966611663",
    }
    for article_no,ean in expected.items():
        assert article_no in lookup
        assert lookup[article_no].get("manufacturer")=="WAGO"
        assert lookup[article_no].get("ean")==ean
        assert lookup[article_no].get("product_type")=="Samlemuffe"


def test_wago_article_recommendation_includes_bridge():
    assert core.pl_recommended_wago_article(1)=="221-412"
    assert core.pl_recommended_wago_article(2)=="221-413"
    assert core.pl_recommended_wago_article(3)=="221-415"
    assert core.pl_recommended_wago_article(4)=="221-415"
    assert core.pl_recommended_wago_article(5)=="221-420"
    assert core.pl_recommended_wago_article(9)=="221-420"
    assert core.pl_recommended_wago_article(10)==""


def test_splice_preserves_selected_article():
    splice={"id":"w1","function":"n","members":[_member("c1"),_member("c2")],"article_no":"221-413","note":"N"}
    got=core.normalize_pl_box_splices([splice])
    assert len(got)==1
    assert got[0]["article_no"]=="221-413"


def test_wago_article_is_counted_in_bom():
    lamp=core.Placement(
        "light_connection",0,0,
        pl_box_splices=[{"id":"w1","function":"n","members":[_member("c1"),_member("c2")],"article_no":"221-413"}],
    )
    rows,missing=core.build_bom([lamp],core.load_predefined_article_catalog(),{},[],{})
    row=next(r for r in rows if r["article_no"]=="221-413")
    assert row["qty"]==1
    assert not any(x.get("symbol")=="__pl_wago__" for x in missing)


def test_wago_without_article_is_reported_as_missing_bom_part():
    lamp=core.Placement(
        "light_connection",0,0,
        pl_box_splices=[{"id":"w1","function":"n","members":[_member("c1"),_member("c2")]}],
    )
    rows,missing=core.build_bom([lamp],core.load_predefined_article_catalog(),{},[],{})
    assert not any(r["article_no"].startswith("221-") for r in rows)
    row=next(x for x in missing if x.get("symbol")=="__pl_wago__")
    assert row["detail"]=="Ingen Wago-artikel valgt"


def test_delete_key_soft_curve_and_removed_cable_sheath_are_in_qt_source():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "Qt.Key.Key_Delete,Qt.Key.Key_Backspace" in source
    assert 'self.functionAssigned.emit(tuple(self._selected_key),"")' in source
    assert "path.cubicTo(cp1,cp2,end)" in source
    assert "path.lineTo(knee)" not in source
    assert "sheath=QPen(cable_color,14.0)" not in source
    assert "Wago-type" in source

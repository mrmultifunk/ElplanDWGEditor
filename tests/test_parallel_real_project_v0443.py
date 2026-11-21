from pathlib import Path
import math
import core_logic as core

PANEL_UID='9e5a0e4a8a0a4271aabdc0c127a07669'


def _real_cables():
    # Reduced verbatim geometry from the real 0.44.2 project that exposed the
    # rendering issue. Both cables leave exactly the same group-board port and
    # share a long first segment before diverging.
    g01=core.CablePlacement(
        points=[
            (4710.706449018688,2025.75309179326),
            (-12259.475585910606,2025.75309179326),
            (-12259.475585910606,2604.2551708801852),
        ], cable_id='G01', cable_spec='3G1,5', uid='013b66eb72bf4ff0b42b6e2e08bf1877',
        start_symbol_uid=PANEL_UID, start_symbol_port=0,
        symbol_connections=[{'point_index':0,'symbol_uid':PANEL_UID,'symbol_port':0}],
        orthogonal=True,
    )
    k01=core.CablePlacement(
        points=[
            (4710.706449018688,2025.75309179326),
            (-1862.262739987466,2025.75309179326),
            (-1862.262739987466,2344.896347165778),
        ], cable_id='K01', cable_spec='3G1,5', uid='eab38f7fbdca4a34b46712f4fdee6b1f',
        start_symbol_uid=PANEL_UID, start_symbol_port=0,
        symbol_connections=[{'point_index':0,'symbol_uid':PANEL_UID,'symbol_port':0}],
        orthogonal=True,
    )
    return g01,k01


def test_real_panel_departure_is_ten_pixels_apart_at_six_percent_zoom():
    a,b=_real_cables()
    scale=.06
    gap_px=10.0
    paths,meta,_=core.cable_visual_layout([a,b],gap_px/scale,fan_length=21.0/scale)
    assert meta[id(a)]['max_parallel']==meta[id(b)]['max_parallel']==2
    # First point remains the common physical panel terminal.
    assert paths[id(a)][0]==paths[id(b)][0]==a.points[0]
    # The first full lane points must be exactly the requested 10 px apart on screen.
    ya=paths[id(a)][1][1]; yb=paths[id(b)][1][1]
    assert math.isclose(abs(ya-yb)*scale,gap_px,rel_tol=0,abs_tol=1e-6)
    # And the long horizontal paths remain visibly distinct after fan-out.
    assert not math.isclose(paths[id(a)][2][1],paths[id(b)][2][1],abs_tol=1e-9)


def test_qt_render_pipeline_receives_calculated_path_directly():
    app=Path('elplan_qt/qt_app.py').read_text(encoding='utf-8')
    graphics=Path('elplan_qt/qt_graphics.py').read_text(encoding='utf-8')
    assert 'item.set_visual_points(self._cable_visual_cache.get(id(cable),cable.points),refresh=False)' in app
    assert 'self._visual_points_override' in graphics
    assert 'if self._edit_before is not None:' in graphics
    # Selection by itself must not collapse the paint path back to centreline.
    display_block=graphics.split('def display_points(self)',1)[1].split('def refresh(',1)[0]
    assert 'self.isSelected()' not in display_block

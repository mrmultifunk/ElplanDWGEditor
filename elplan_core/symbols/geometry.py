"""Qt-uafhængig vektorgeometri og montagepunkter for symboler."""

from __future__ import annotations

import math
from functools import lru_cache

from elplan_core.cables.geometry import rotate_point
from elplan_core.constants import SYMBOL_NAMES_BY_CODE
from elplan_core.models import Placement
from elplan_core.symbols.registry import (
    combo_modules,
    combo_socket_kind,
    is_combo_row_symbol,
    is_combo_symbol,
    parse_custom_combo_symbol,
)


# Stikkontakternes synlige grundform skal have samme mål ved samme ``size``.
# 3F+N+PE beholder sit historiske væganker på 1,48 x size, så eksisterende
# projekter ikke flytter sig, men selve grundformen forskydes tilsvarende og
# får samme 1,00 x size stamme som de øvrige stikkontakter.
SOCKET_STEM_FACTOR = 1.00


EXTENDED_SOCKET_MOUNT_FACTOR = 1.48


SOCKET_3FN_BODY_OFFSET_FACTOR = EXTENDED_SOCKET_MOUNT_FACTOR - SOCKET_STEM_FACTOR


@lru_cache(maxsize=2048)
def symbol_primitives(symbol: str, size: float):
    """Returnér rene vektorprimitiver for installationstegningssymbolerne.

    Stikkontaktfamilien er i v0.4.1 konstrueret direkte efter proportionerne i
    brugerens Cubus-reference: en lodret stamme, en øvre halvcirkel under
    samlingspunktet og de særlige tillæg for jord, pillesikring, afbryder,
    3F+N+PE, skilletransformer og tele/data.

    ``size`` svarer omtrent til bredden af buen på en almindelig stikkontakt.
    Ingen bitmap anvendes; alle elementer forbliver LINE/ARC/LWPOLYLINE/TEXT
    ved DXF/DWG-eksport. ``upright_text`` følger symbolets position, men ikke
    dets rotation; det bruges til korte interne mærkninger, som altid skal
    kunne læses vandret.

    Formater:
      ("line", x1,y1,x2,y2)
      ("circle", cx,cy,r)
      ("arc", cx,cy,r,start,end)
      ("polyline", [(x,y), ...])
      ("text", x,y,text,height)
      ("upright_text", x,y,text,height)
    """
    s = max(float(size), 1e-9)
    p = []

    def line(x1, y1, x2, y2): p.append(("line", x1, y1, x2, y2))
    def circle(x, y, r): p.append(("circle", x, y, r))
    def arc(x, y, r, a1, a2): p.append(("arc", x, y, r, a1, a2))
    def poly(points): p.append(("polyline", points))
    def mark(x, y, value, h):
        """Centreret intern symbolmærkning, som altid forbliver læsbar."""
        p.append(("upright_text", x, y, value, s*h))

    def ellipse_poly(cx, cy, rx, ry, steps=48):
        # Lukket CAD-vektorpolyline. Bruges kun til shaver-transformerens
        # to ovale viklinger, som ikke er cirkler i referencegrafikken.
        pts = []
        for i in range(steps + 1):
            a = 2.0 * math.pi * i / steps
            pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        poly(pts)

    def socket_arch(stem=SOCKET_STEM_FACTOR, top_y=0.0):
        # Cubus-reference (normaliseret efter buens bredde):
        # - lodret stamme ~= 1 x buebredde
        # - buen er øverste halvdel af en cirkel med diameter = buebredde
        # - samlingspunktet ligger i buens top, ikke i cirklens centrum.
        line(0, top_y, 0, top_y + s * stem)
        arc(0, top_y - s * 0.50, s * 0.50, 0, 180)

    def switch_base():
        circle(0, 0, s * 0.205)

    def switch_arm(angle_deg=64, reach=0.72, end_len=0.20):
        a = math.radians(angle_deg)
        r0 = s * 0.205
        x1, y1 = r0 * math.cos(a), r0 * math.sin(a)
        x2, y2 = s * reach * math.cos(a), s * reach * math.sin(a)
        line(x1, y1, x2, y2)
        b = a - math.radians(70)
        line(x2, y2, x2 + s * end_len * math.cos(b), y2 + s * end_len * math.sin(b))

    def draw_switch_kind(kind, ox=0.0, oy=0.0, scale=1.0):
        ss=s*scale
        circle(ox, oy, ss * 0.205)
        def arm(angle_deg=64, reach=0.72, end_len=0.20):
            a = math.radians(angle_deg)
            r0 = ss * 0.205
            x1, y1 = ox + r0 * math.cos(a), oy + r0 * math.sin(a)
            x2, y2 = ox + ss * reach * math.cos(a), oy + ss * reach * math.sin(a)
            line(x1, y1, x2, y2)
            b = a - math.radians(70)
            line(x2, y2, x2 + ss * end_len * math.cos(b), y2 + ss * end_len * math.sin(b))
        if kind=="switch_1":
            arm()
        elif kind=="switch_2way":
            arm(64); arm(244)
        elif kind=="switch_crown":
            arm(64); arm(29,reach=.70)
        elif kind=="switch_cross":
            arm(64); arm(116); arm(244); arm(296)
        elif kind=="switch_double_2way":
            arm(64); arm(244); mark(ox+ss*.35, oy-ss*.10, "2", .24*scale)
        elif kind=="pushbutton":
            arm(); line(ox-ss*.18, oy-ss*.31, ox+ss*.18, oy-ss*.31)
        elif kind=="pushbutton_indicator":
            arm(); line(ox-ss*.18, oy-ss*.31, ox+ss*.18, oy-ss*.31); circle(ox, oy-ss*.48, ss*.06)

    def draw_socket_kind(ox=0.0, top_y=0.0, stem_len=None):
        socket_r = s * 0.205
        if stem_len is None:
            stem_len = s * 1.02
        line(ox, top_y, ox, top_y + stem_len)
        arc(ox, top_y - socket_r, socket_r, 0, 180)

    def combo_base(kind):
        # Lodret kombinationssymbol: væg/montage øverst, afbryder i midten og
        # stikkontakt nederst. Linjen skal ikke skære gennem afbrydercirklen.
        r=s*.205; gap=0.0
        socket_top = -s*.82
        line(0,r+gap,0,s*1.02)
        line(0,-r-gap,0,socket_top)
        draw_socket_kind(0.0, socket_top, stem_len=(0.0-r-gap)-socket_top)
        draw_switch_kind(kind, 0.0, 0.0)

    def combo_row_base(kinds, socket_kind="socket"):
        # Kompakt lodret modulrække. Ved 2+ afbrydere reduceres modulgeometrien
        # lidt og centerafstanden holdes tæt, men uden at cirkler/arme flyder sammen.
        if not kinds:return
        multi=len(kinds)>1
        module_scale=.82 if multi else 1.0
        ms=s*module_scale; r=ms*.205; gap=0.0
        step=s*(.70 if multi else .82)
        ys=[(len(kinds)-1-i)*step for i in range(len(kinds))]
        top_y=ys[0]
        top_stem=s*(.72 if multi else 1.02)
        line(0, top_y+r+gap, 0, top_y+top_stem)
        for idx,kind in enumerate(kinds):
            cy=ys[idx]
            # Lokal variant med mindre modulskala for kompakte stakke.
            old_s=s
            # draw_switch_kind bruger scale-parameter via indlejret wrapper nedenfor.
            draw_switch_kind(kind,0.0,cy,module_scale)
            if idx<len(ys)-1:
                ny=ys[idx+1]; line(0,cy-r-gap,0,ny+r+gap)
        if socket_kind in {"socket","socket_earth"}:
            bottom_y=ys[-1]; socket_top=bottom_y-s*(.62 if multi else .82)
            line(0,bottom_y-r-gap,0,socket_top)
            socket_r=ms*.205
            arc(0,socket_top-socket_r,socket_r,0,180)
            if socket_kind=="socket_earth":line(-socket_r,socket_top,socket_r,socket_top)

    # --- KOMBI / SYMBOLKONFIGURATOR ------------------------------------
    parsed_custom=parse_custom_combo_symbol(symbol)
    if parsed_custom:
        combo_row_base(parsed_custom[0],parsed_custom[1])
    elif symbol == "combo_switch_1_socket":
        combo_base("switch_1")
    elif symbol == "combo_switch_2way_socket":
        combo_base("switch_2way")
    elif symbol == "combo_switch_crown_socket":
        combo_base("switch_crown")
    elif symbol == "combo_switch_cross_socket":
        combo_base("switch_cross")
    elif symbol == "combo_switch_double_2way_socket":
        combo_base("switch_double_2way")
    elif symbol == "combo_pushbutton_socket":
        combo_base("pushbutton")
    elif symbol == "combo_pushbutton_indicator_socket":
        combo_base("pushbutton_indicator")
    elif symbol == "combo_row_2x1_socket":
        combo_row_base(["switch_1", "switch_1"])
    elif symbol == "combo_row_1_2way_socket":
        combo_row_base(["switch_1", "switch_2way"])
    elif symbol == "combo_row_2way_2way_socket":
        combo_row_base(["switch_2way", "switch_2way"])
    elif symbol == "combo_row_crown_1_socket":
        combo_row_base(["switch_crown", "switch_1"])
    elif symbol == "combo_row_3x1_socket":
        combo_row_base(["switch_1", "switch_1", "switch_1"])
    elif symbol == "combo_row_2x1_2way_socket":
        combo_row_base(["switch_1", "switch_1", "switch_2way"])
    elif symbol == "combo_row_crown_2x1_socket":
        combo_row_base(["switch_crown", "switch_1", "switch_1"])

    # --- STIKKONTAKTER -------------------------------------------------
    elif symbol == "socket":
        socket_arch(stem=1.0)

    elif symbol == "socket_earth":
        socket_arch(stem=1.0)
        # Reference: jordstregen går omtrent fra side til side over buens top.
        line(-s * 0.50, 0, s * 0.50, 0)

    elif symbol == "socket_childsafe":
        socket_arch(stem=1.0)
        # Pillesikker: samme bue, men en vandret forlængelse fra begge
        # nederste ender. Samlet bredde er ca. dobbelt normal stikkontakt.
        y_side = -s * 0.50
        line(-s * 1.00, y_side, -s * 0.50, y_side)
        line( s * 0.50, y_side,  s * 1.00, y_side)

    elif symbol == "socket_switch":
        # Kombinationssymbolet i referencen har en længere lodret stamme.
        socket_arch(stem=EXTENDED_SOCKET_MOUNT_FACTOR)
        # Afbryderarmen starter i samme knudepunkt som buen/stammen.
        line(0, 0, s * 0.78, s * 1.33)
        line(s * 0.78, s * 1.33, s * 1.19, s * 1.11)

    elif symbol == "socket_3fn":
        # Det historiske væganker ligger ved 1,48 x size. Forskyd grundformen
        # 0,48 x size i stedet for at forlænge stammen; dermed står den på samme
        # væglinje og får samme synlige mål som en almindelig stikkontakt.
        top_y=s * SOCKET_3FN_BODY_OFFSET_FACTOR
        socket_arch(top_y=top_y)
        line(-s * 0.50, top_y, s * 0.50, top_y)
        mark(0, top_y - s * 0.50, "3N", 0.44)

    elif symbol == "socket_shaver":
        # To overlappende, flade transformerviklinger som på referencebilledet.
        # Dimensionerne er afledt af referenceforholdet ca. 27:20 px.
        rx, ry = s * 0.50, s * 0.37
        upper_cy = 0.0
        lower_cy = -s * 0.52
        ellipse_poly(0, upper_cy, rx, ry)
        ellipse_poly(0, lower_cy, rx, ry)
        line(0, upper_cy + ry, 0, s * 0.82)
        # De to ben starter inde i nederste vikling, så de visuelt overlapper
        # på samme måde som originalsymbolet.
        line(-rx, -s * 0.72, -rx, -s * 1.18)
        line( rx, -s * 0.72,  rx, -s * 1.18)

    elif symbol == "socket_double_box":
        # Forenklet dobbeltstik: almindelig stikkontakt med et lille, klart
        # læseligt 2-tal. Tallet tegnes som CAD-tekst, så symbolet stadig er
        # ren vektorgrafik i både viewer, PDF og DXF/DWG.
        socket_arch(stem=1.0)
        mark(0, -s * 0.50, "2", 0.44)

    elif symbol == "socket_triple_box":
        socket_arch(stem=1.0)
        mark(0, -s * 0.50, "3", 0.44)

    elif symbol == "socket_double_box_earth":
        socket_arch(stem=1.0)
        line(-s * 0.50, 0, s * 0.50, 0)
        mark(0, -s * 0.50, "2", 0.44)

    elif symbol == "socket_triple_box_earth":
        socket_arch(stem=1.0)
        line(-s * 0.50, 0, s * 0.50, 0)
        mark(0, -s * 0.50, "3", 0.44)

    elif symbol == "socket_double":
        # To fulde stikkontakter samlet som ét symbol.
        r = s * 0.24
        spacing = s * 0.34
        for cx in (-spacing, spacing):
            line(cx, 0, cx, s * 0.72)
            arc(cx, -r, r, 0, 180)

    elif symbol == "socket_triple":
        # Tre fulde stikkontakter samlet som ét symbol.
        r = s * 0.24
        spacing = s * 0.58
        for cx in (-spacing, 0.0, spacing):
            line(cx, 0, cx, s * 0.72)
            arc(cx, -r, r, 0, 180)

    elif symbol == "socket_double_earth":
        r = s * 0.24
        spacing = s * 0.34
        for cx in (-spacing, spacing):
            line(cx, 0, cx, s * 0.72)
            arc(cx, -r, r, 0, 180)
            line(cx-r, 0, cx+r, 0)

    elif symbol == "socket_triple_earth":
        r = s * 0.24
        spacing = s * 0.58
        for cx in (-spacing, 0.0, spacing):
            line(cx, 0, cx, s * 0.72)
            arc(cx, -r, r, 0, 180)
            line(cx-r, 0, cx+r, 0)

    elif symbol == "socket_tele":
        # Åben stikdåse: vandret overkant, to lodrette sider og stamme op.
        line(0, 0, 0, s * 1.00)
        line(-s * 0.50, 0, s * 0.50, 0)
        line(-s * 0.50, 0, -s * 0.50, -s * 0.52)
        line( s * 0.50, 0,  s * 0.50, -s * 0.52)
    elif symbol == "patch_panel":
        # Kompakt patchpanel/datacentral. Tolv porte (2×6) er både synlige og
        # egentlige kabel-snapporte, så netværkskabler kan afsluttes individuelt.
        w,h=s*1.86,s*.72
        line(-w/2,-h/2,w/2,-h/2); line(w/2,-h/2,w/2,h/2); line(w/2,h/2,-w/2,h/2); line(-w/2,h/2,-w/2,-h/2)
        port_w,port_h=s*.22,s*.18
        xs=[-s*.68,-s*.41,-s*.14,s*.14,s*.41,s*.68]
        ys=[s*.14,-s*.14]
        for py in ys:
            for px in xs:
                line(px-port_w/2,py-port_h/2,px+port_w/2,py-port_h/2)
                line(px+port_w/2,py-port_h/2,px+port_w/2,py+port_h/2)
                line(px+port_w/2,py+port_h/2,px-port_w/2,py+port_h/2)
                line(px-port_w/2,py+port_h/2,px-port_w/2,py-port_h/2)

    # --- KONTAKTER -----------------------------------------------------
    elif symbol == "switch_1":
        switch_base(); switch_arm()
    elif symbol == "switch_crown":
        switch_base(); switch_arm(64); switch_arm(29, reach=.70)
    elif symbol == "switch_2way":
        switch_base(); switch_arm(64); switch_arm(244)
    elif symbol == "switch_cross":
        switch_base(); switch_arm(64); switch_arm(116); switch_arm(244); switch_arm(296)
    elif symbol == "switch_double_2way":
        switch_base(); switch_arm(64); switch_arm(244); mark(s*.35, -s*.10, "2", .24)
    elif symbol == "pushbutton":
        switch_base(); switch_arm(); line(-s*.18, -s*.31, s*.18, -s*.31)
    elif symbol == "pushbutton_indicator":
        switch_base(); switch_arm(); line(-s*.18, -s*.31, s*.18, -s*.31); circle(0, -s*.48, s*.06)
    elif symbol == "pushbutton_4":
        switch_base(); switch_arm(); mark(s*.35, -s*.08, "4", .24)

    # --- BELYSNING -----------------------------------------------------
    elif symbol == "light_connection":
        line(-s*.48, -s*.48, s*.48, s*.48); line(-s*.48, s*.48, s*.48, -s*.48)
    elif symbol == "wall_light_outlet":
        # Lampeudtag i almindelig vægdåse: lampestedskryds, stamme og en lille
        # vægstreg ved det fysiske montagepunkt.
        q=s*.34
        line(-q,-q,q,q); line(-q,q,q,-q)
        line(0,q,0,s*.92); line(-s*.18,s*.92,s*.18,s*.92)
    elif symbol == "light_fixture":
        circle(0, 0, s*.47); line(-s*.35, -s*.35, s*.35, s*.35); line(-s*.35, s*.35, s*.35, -s*.35)
    elif symbol == "fluorescent":
        line(-s*.50, 0, s*.50, 0); line(-s*.50, -s*.16, -s*.50, s*.16); line(s*.50, -s*.16, s*.50, s*.16)
    elif symbol == "fluorescent_fixed":
        line(-s*.50, 0, s*.50, 0); line(-s*.50, -s*.16, -s*.50, s*.16); line(s*.50, -s*.16, s*.50, s*.16)
        line(-s*.24, -s*.30, s*.24, s*.30); line(-s*.24, s*.30, s*.24, -s*.30)
    elif symbol == "emergency_light":
        q=s*.45; line(-q,-q,q,-q); line(q,-q,q,q); line(q,q,-q,q); line(-q,q,-q,-q); mark(0,0,"N",.34)
    elif symbol == "spot":
        circle(0,0,s*.42); circle(0,0,s*.10)

    # --- BRUGSGENSTANDE / DIVERSE ------------------------------------
    elif symbol == "fan":
        q=s*.45; line(-q,-q,q,-q); line(q,-q,q,q); line(q,q,-q,q); line(-q,q,-q,-q)
        poly([(-s*.24,-s*.10),(-s*.14,-s*.20),(0,-s*.08),(s*.14,-s*.20),(s*.24,-s*.10),(s*.24,s*.10),(s*.14,s*.20),(0,s*.08),(-s*.14,s*.20),(-s*.24,s*.10),(-s*.24,-s*.10)])
    elif symbol == "ev_charger":
        # Intuitivt, rent vektorsymbol for ladeboks: kapsling + ladestik/lyn.
        w,h=s*.72,s*.96
        line(-w/2,-h/2,w/2,-h/2); line(w/2,-h/2,w/2,h/2); line(w/2,h/2,-w/2,h/2); line(-w/2,h/2,-w/2,-h/2)
        # Lyn uden afhængighed af CAD-font.
        poly([(-s*.08,s*.28),(s*.10,s*.28),(-s*.01,s*.04),(s*.16,s*.04),(-s*.14,-s*.31),(-s*.04,-s*.07),(-s*.20,-s*.07),(-s*.08,s*.28)])
        # Kort kabel/stik i siden.
        line(w/2, s*.12, s*.54, s*.12); line(s*.54,s*.12,s*.54,-s*.12); line(s*.49,-s*.12,s*.59,-s*.12)
    elif symbol == "solar_panel":
        # Solcellemodul med cellegitter. Ren vektorgrafik gør symbolet tydeligt
        # i paletten og bevarer alle linjer i PDF/DXF.
        w,h=s*1.10,s*.70
        line(-w/2,-h/2,w/2,-h/2); line(w/2,-h/2,w/2,h/2); line(w/2,h/2,-w/2,h/2); line(-w/2,h/2,-w/2,-h/2)
        line(-w/6,-h/2,-w/6,h/2); line(w/6,-h/2,w/6,h/2)
        line(-w/2,0,w/2,0)
        # Kort understel adskiller panelet fra en generisk tavlekapsling.
        line(-s*.20,-h/2,-s*.30,-s*.52); line(s*.20,-h/2,s*.30,-s*.52); line(-s*.36,-s*.52,s*.36,-s*.52)
    elif symbol == "solar_inverter":
        # Inverter: DC-symbolik til venstre og en stiliseret sinus til højre.
        w,h=s*.92,s*.88
        line(-w/2,-h/2,w/2,-h/2); line(w/2,-h/2,w/2,h/2); line(w/2,h/2,-w/2,h/2); line(-w/2,h/2,-w/2,-h/2)
        line(0,-h/2,0,h/2)
        line(-s*.34,s*.12,-s*.12,s*.12); line(-s*.34,-s*.12,-s*.12,-s*.12)
        poly([(s*.08,0),(s*.14,s*.13),(s*.22,s*.13),(s*.30,0),(s*.38,-s*.13),(s*.44,-s*.13)])
        line(-s*.08,-s*.27,s*.12,s*.27)
    elif symbol == "solar_battery":
        # Stationært batteri med to terminaler og tre ladningsfelter.
        w,h=s*.82,s*.88
        line(-w/2,-h/2,w/2,-h/2); line(w/2,-h/2,w/2,h/2); line(w/2,h/2,-w/2,h/2); line(-w/2,h/2,-w/2,-h/2)
        line(-s*.25,h/2,-s*.25,s*.55); line(-s*.34,s*.55,-s*.16,s*.55)
        line(s*.25,h/2,s*.25,s*.55); line(s*.16,s*.55,s*.34,s*.55)
        line(-s*.24,s*.18,s*.24,s*.18); line(-s*.24,0,s*.24,0); line(-s*.24,-s*.18,s*.24,-s*.18)
    elif symbol == "distribution_board":
        w,h=s*.90,s*.50; line(-w/2,-h/2,w/2,-h/2); line(w/2,-h/2,w/2,h/2); line(w/2,h/2,-w/2,h/2); line(-w/2,h/2,-w/2,-h/2)
    elif symbol == "group_board":
        # Gruppetavle: kapsling med modulopdeling, tydelig også i lille skala.
        w,h=s*1.00,s*.66
        line(-w/2,-h/2,w/2,-h/2); line(w/2,-h/2,w/2,h/2); line(w/2,h/2,-w/2,h/2); line(-w/2,h/2,-w/2,-h/2)
        line(-w*.26,-h/2,-w*.26,h/2); line(0,-h/2,0,h/2); line(w*.26,-h/2,w*.26,h/2)
        line(-w/2,0,w/2,0)
    elif symbol == "meter_board":
        # Målertavle: tavlekapsling med den internationalt genkendelige
        # målercirkel og M-mærkning. Mærkningen holdes læsbar ved rotation.
        w,h=s*.92,s*.68
        line(-w/2,-h/2,w/2,-h/2); line(w/2,-h/2,w/2,h/2); line(w/2,h/2,-w/2,h/2); line(-w/2,h/2,-w/2,-h/2)
        circle(0,0,s*.23); mark(0,0,"M",.27)
    elif symbol == "main_earthing_connection":
        # Hovedjordforbindelse efter jordingsprincippet: tilslutningspunkt,
        # leder og tre aftagende jordstreger. Øverste punkt kan kabelsnappes.
        circle(0,s*.62,s*.07); line(0,s*.55,0,0)
        line(-s*.42,0,s*.42,0)
        line(-s*.28,-s*.15,s*.28,-s*.15)
        line(-s*.14,-s*.30,s*.14,-s*.30)
    elif symbol == "water_heater":
        circle(0,0,s*.42); mark(0,0,"VV",.25)
    elif symbol == "heater":
        q=s*.42; line(-q,-q,q,-q); line(q,-q,q,q); line(q,q,-q,q); line(-q,q,-q,-q)
        poly([(-s*.27,-s*.12),(-s*.14,s*.12),(0,-s*.12),(s*.14,s*.12),(s*.27,-s*.12)])
    elif symbol == "electric_lock":
        q=s*.40; line(-q,-q,q,-q); line(q,-q,q,q); line(q,q,-q,q); line(-q,q,-q,-q); mark(0,0,"L",.34)
    elif symbol == "connection":
        line(-s*.45,-s*.45,s*.45,s*.45); line(-s*.45,s*.45,s*.45,-s*.45); circle(0,0,s*.08)
    elif symbol == "pir":
        circle(-s*.22,0,s*.12); arc(-s*.10,0,s*.28,-55,55); arc(-s*.10,0,s*.45,-45,45)
    elif symbol == "smoke":
        circle(0,0,s*.42); mark(0,0,"R",.34)
    else:
        circle(0,0,s*.30)
    return p


def symbol_connection_points(symbol: str, size: float) -> list[tuple[float, float]]:
    """Lokale kabel-/ledningstilslutningspunkter for et symbol.

    Alle placerbare el-symboler har mindst ét punkt. Det gør kabelsnap ensartet:
    brugeren behøver ikke kende præcis hvilke symboler der tidligere havde fået
    et særskilt connection point. Vægudstyr bruger sit installationspunkt,
    mens frie symboler som lamper/spot/tavler bruger centrum.
    """
    s = max(float(size), 1e-9)
    if is_combo_row_symbol(symbol):
        kinds=combo_modules(symbol); socket_kind=combo_socket_kind(symbol)
        multi=len(kinds)>1; step=s*(.70 if multi else .82)
        ys=[(len(kinds)-1-i)*step for i in range(len(kinds))]
        top_stem=s*(.72 if multi else 1.02)
        pts=[(0.0,(ys[0] if ys else 0.0)+top_stem)]
        for cy in ys:pts.append((0.0,cy))
        if socket_kind in {"socket","socket_earth"}:
            socket_top=(ys[-1] if ys else 0.0)-s*(.62 if multi else .82)
            pts.append((0.0,socket_top))
        return pts
    if is_combo_symbol(symbol):
        # Port 0: væg/montage, port 1: afbryderdel, port 2: stikkontaktdel.
        return [(0.0,s*1.02),(0.0,0.0),(0.0,-s*.82)]
    if symbol in {"socket", "socket_earth", "socket_childsafe", "socket_double_box", "socket_triple_box", "socket_double_box_earth", "socket_triple_box_earth"}:
        # Port 0 bevares ved vægenden af stammen af hensyn til ældre projekter.
        # Port 1 ligger ved selve symbolknudepunktet og gør kabelsnap intuitivt,
        # når brugeren peger på stikkontaktsymbolet i stedet for væggen.
        return [(0.0, s), (0.0, 0.0)]
    if symbol in {"socket_double", "socket_double_earth"}:
        # Første tre porte er de historiske vægporte; de to sidste er de synlige
        # symbolknudepunkter, så kabelenden lander dér hvor brugeren peger.
        return [(0.0, s * .72), (-s*.34, s*.72), (s*.34, s*.72), (-s*.34,0.0), (s*.34,0.0)]
    if symbol in {"socket_triple", "socket_triple_earth"}:
        return [(0.0, s * .72), (-s*.58, s*.72), (s*.58, s*.72), (-s*.58,0.0), (0.0,0.0), (s*.58,0.0)]
    if symbol == "socket_switch":
        return [(0.0, s * EXTENDED_SOCKET_MOUNT_FACTOR), (0.0,0.0)]
    if symbol == "socket_3fn":
        return [
            (0.0, s * EXTENDED_SOCKET_MOUNT_FACTOR),
            (0.0, s * SOCKET_3FN_BODY_OFFSET_FACTOR),
        ]
    if symbol == "socket_shaver":
        return [(0.0, s * 0.82), (0.0,0.0)]
    if symbol == "patch_panel":
        xs=[-s*.68,-s*.41,-s*.14,s*.14,s*.41,s*.68]
        return [(x,y) for y in (s*.14,-s*.14) for x in xs]
    if symbol == "socket_tele":
        return [(0.0, s), (0.0,0.0)]
    if symbol == "wall_light_outlet":
        # Port 0 er dåsen i væggen; port 1 er det synlige lampestedskryds.
        return [(0.0,s*.92),(0.0,0.0)]
    if symbol == "meter_board":
        return [(0.0,s*.34),(0.0,-s*.34),(0.0,0.0)]
    if symbol == "main_earthing_connection":
        return [(0.0,s*.62),(0.0,0.0)]
    if symbol == "solar_panel":
        return [(-s*.55,0.0),(s*.55,0.0),(0.0,0.0)]
    if symbol == "solar_inverter":
        return [(-s*.46,0.0),(s*.46,0.0),(0.0,s*.44),(0.0,-s*.44)]
    if symbol == "solar_battery":
        return [(-s*.25,s*.55),(s*.25,s*.55),(0.0,-s*.44)]
    # Kontakter og alle øvrige komponenter kan tilsluttes i deres logiske centrum.
    if symbol in SYMBOL_NAMES_BY_CODE:
        return [(0.0, 0.0)]
    return []


def symbol_mount_points(symbol: str, size: float) -> list[tuple[float, float]]:
    """Lokale punkter der fysisk skal ramme en væg ved symbolplacering.

    Dette er bevidst adskilt fra kabelporte. Ellers kan en ny kabelport ændre
    vægsnap-adfærden ved et uheld. Kun symboler der normalt vægmonteres får et
    mount point; loft-/gulvsymboler som spot og lampe snapper derfor ikke
    aggressivt til en væg.
    """
    s=max(float(size),1e-9)
    if is_combo_row_symbol(symbol):
        kinds=combo_modules(symbol); multi=len(kinds)>1; step=s*(.70 if multi else .82)
        top_y=((len(kinds)-1)*step) if kinds else 0.0
        return [(0.0,top_y+s*(.72 if multi else 1.02))]
    if is_combo_symbol(symbol):
        return [(0.0,s*1.02)]
    if symbol in {"socket", "socket_earth", "socket_childsafe", "socket_double_box", "socket_triple_box", "socket_double_box_earth", "socket_triple_box_earth"}:
        return [(0.0,s)]
    if symbol in {"socket_double", "socket_double_earth", "socket_triple", "socket_triple_earth"}:
        return [(0.0,s*.72)]
    if symbol in {"socket_switch","socket_3fn"}:
        return [(0.0,s*EXTENDED_SOCKET_MOUNT_FACTOR)]
    if symbol in {"socket_shaver"}:
        return [(0.0,s*.82)]
    if symbol in {"socket_tele"}:
        return [(0.0,s)]
    if symbol == "wall_light_outlet":
        return [(0.0,s*.92)]
    if symbol == "patch_panel":
        return [(0.0,0.0)]
    if symbol.startswith("switch_") or symbol.startswith("pushbutton"):
        return [(0.0,0.0)]
    if symbol in {"ev_charger","solar_inverter","solar_battery","distribution_board","group_board","meter_board","main_earthing_connection","heater","electric_lock"}:
        return [(0.0,0.0)]
    return []


def placement_connection_points(placement: Placement) -> list[tuple[float, float]]:
    return [(x,y) for x,y,_port in placement_connection_ports(placement)]


def placement_connection_ports(placement: Placement) -> list[tuple[float, float, int]]:
    out=[]
    for port,(x,y) in enumerate(symbol_connection_points(placement.symbol, placement.size)):
        x,y=rotate_point(x,y,placement.rotation)
        out.append((placement.x+x,placement.y+y,port))
    return out


def placement_mount_points(placement: Placement) -> list[tuple[float,float]]:
    out=[]
    for x,y in symbol_mount_points(placement.symbol,placement.size):
        x,y=rotate_point(x,y,placement.rotation)
        out.append((placement.x+x,placement.y+y))
    return out


@lru_cache(maxsize=2048)
def symbol_local_bbox(symbol: str, size: float) -> tuple[float,float,float,float]:
    """Konservativ bbox af selve symbolvektorerne, uden mærkningstekst."""
    xs=[]; ys=[]
    for prim in symbol_primitives(symbol,size):
        typ=prim[0]
        if typ=="line":
            xs.extend((prim[1],prim[3])); ys.extend((prim[2],prim[4]))
        elif typ in ("circle","arc"):
            _,cx,cy,r,*_=prim; xs.extend((cx-r,cx+r)); ys.extend((cy-r,cy+r))
        elif typ=="polyline":
            xs.extend(q[0] for q in prim[1]); ys.extend(q[1] for q in prim[1])
        elif typ in {"text","upright_text"}:
            _,x,y,t,h=prim
            # Intern tekst er centreret i både Qt, PDF, DXF og print.
            w=max(float(h)*0.55*len(str(t)),float(h)*0.6)
            xs.extend((x-w*.5,x+w*.5)); ys.extend((y-h*.5,y+h*.5))
    if not xs:return (-size*.5,-size*.5,size*.5,size*.5)
    return min(xs),min(ys),max(xs),max(ys)


def symbol_mating_sites(symbol: str, size: float) -> dict[str,tuple[float,float]]:
    """Snap-sites på symbolkanten. Modstående sider kan kobles direkte sammen."""
    x1,y1,x2,y2=symbol_local_bbox(symbol,size); cx=(x1+x2)/2; cy=(y1+y2)/2
    return {"left":(x1,cy),"right":(x2,cy),"top":(cx,y2),"bottom":(cx,y1),"center":(cx,cy)}


def placement_mating_sites(placement: Placement) -> dict[str,tuple[float,float]]:
    out={}
    for name,(x,y) in symbol_mating_sites(placement.symbol,placement.size).items():
        x,y=rotate_point(x,y,placement.rotation); out[name]=(placement.x+x,placement.y+y)
    return out


def _is_wall_device(symbol: str) -> bool:
    """Stikkontakter og betjeningskontakter, som ofte monteres i samme ramme."""
    return symbol=="wall_light_outlet" or is_combo_symbol(symbol) or symbol.startswith("socket") or symbol.startswith("switch_") or symbol.startswith("pushbutton")


def wall_device_snap_origins(moving_symbol: str, moving_size: float, fixed: Placement, moving_rotation: float = 0.0) -> list[tuple[float,float,str]]:
    """Stabile samlingspositioner for vægudstyr.

    I stedet for den tidligere faste afstand (1,08 x symbolstørrelse) bruges
    symbolernes faktiske vektor-bounding boxes. Montagepunkterne holdes på
    samme væglinje, mens symbolerne lægges lige ved siden af hinanden.
    """
    if not (_is_wall_device(moving_symbol) and _is_wall_device(fixed.symbol)):
        return []
    fm=symbol_mount_points(fixed.symbol,fixed.size); mm=symbol_mount_points(moving_symbol,moving_size)
    if not fm or not mm:return []
    fmx_l,fmy_l=rotate_point(fm[0][0],fm[0][1],fixed.rotation)
    mmx_l,mmy_l=rotate_point(mm[0][0],mm[0][1],moving_rotation)
    fmx,fmy=fixed.x+fmx_l,fixed.y+fmy_l
    # Lokal X-akse følger væggen for et vægmonteret symbol.
    tx,ty=rotate_point(1.0,0.0,fixed.rotation)

    def projection_range(symbol,size,rotation,mount_rot):
        x1,y1,x2,y2=symbol_local_bbox(symbol,size)
        vals=[]
        for x,y in ((x1,y1),(x1,y2),(x2,y1),(x2,y2)):
            rx,ry=rotate_point(x,y,rotation)
            dx,dy=rx-mount_rot[0],ry-mount_rot[1]
            vals.append(dx*tx+dy*ty)
        return min(vals),max(vals)

    fmin,fmax=projection_range(fixed.symbol,fixed.size,fixed.rotation,(fmx_l,fmy_l))
    mmin,mmax=projection_range(moving_symbol,moving_size,moving_rotation,(mmx_l,mmy_l))
    gap=max(min(float(fixed.size),float(moving_size))*0.035,0.0)
    deltas=(fmax+gap-mmin, fmin-gap-mmax)
    out=[]
    for delta in deltas:
        target_mount=(fmx+tx*delta,fmy+ty*delta)
        out.append((target_mount[0]-mmx_l,target_mount[1]-mmy_l,"symbol-sammen"))
    return out


def _angular_distance_deg(a: float, b: float) -> float:
    return abs(((float(a)-float(b)+180.0)%360.0)-180.0)


def wall_device_rotation_for_wall(symbol: str, current_rotation: float, wall_angle: float) -> float:
    """Orientér vægudstyr så lokal X-akse følger væggen.

    Dermed står stikkontaktens stamme vinkelret på væggen. Vi vælger den af
    de to 180°-ækvivalente retninger, der ligger tættest på brugerens aktuelle
    rotation, så manuel orientering stadig respekteres.
    """
    if not _is_wall_device(symbol):return float(current_rotation)%360.0
    base=float(wall_angle)%180.0
    candidates=[base,(base+180.0)%360.0]
    cur=float(current_rotation)%360.0
    return min(candidates,key=lambda q:_angular_distance_deg(q,cur))

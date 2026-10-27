import core_logic as core


def _room():
    return core.RoomPlacement(name="Køkken", code="R01", points=[(0,0),(100,0),(100,100),(0,100)], uid="room-k")


def test_source_breakdown_separates_assembly_and_manual_sources_without_changing_bom():
    room=_room()
    p1=core.Placement("socket",20,20,uid="p1",label="S1")
    p2=core.Placement("socket",40,20,uid="p2",label="S2")
    catalog=[{"article_no":"A1","description":"Indsats","unit":"stk","unit_price":10.0},
             {"article_no":"A2","description":"Ramme","unit":"stk","unit_price":2.0}]
    assemblies=[{"id":"asm1","name":"FUGA stikkontakt AIR","items":[{"article_no":"A1","qty":1},{"article_no":"A2","qty":1}]}]
    assembly_bindings={"p1":{"symbol":"asm1"}}
    bindings={"p2":{"symbol":[{"article_no":"A1","qty":2}]}}

    rows,missing=core.build_bom([p1,p2],catalog,bindings,assemblies=assemblies,assembly_bindings=assembly_bindings,rooms=[room])
    by_no={r["article_no"]:r for r in rows}
    assert by_no["A1"]["qty"]==3
    assert by_no["A2"]["qty"]==1
    assert not missing

    sources=core.bom_source_breakdown([p1,p2],catalog,bindings,[room],assemblies=assemblies,assembly_bindings=assembly_bindings)
    a1=[r for r in sources if r["article_no"]=="A1"]
    assert {r["source_type"] for r in a1}=={"assembly","manual"}
    assert next(r for r in a1 if r["source_type"]=="assembly")["assembly_name"]=="FUGA stikkontakt AIR"
    assert sum(r["qty"] for r in a1)==3


def test_assembly_usage_is_room_filtered_and_prices_children():
    kitchen=_room()
    hall=core.RoomPlacement(name="Gang",code="R02",points=[(100,0),(200,0),(200,100),(100,100)],uid="room-g")
    p1=core.Placement("socket",20,20,uid="p1")
    p2=core.Placement("socket",120,20,uid="p2")
    catalog=[{"article_no":"A1","description":"Indsats","unit":"stk","unit_price":10.0},
             {"article_no":"A2","description":"Ramme","unit":"stk","unit_price":2.0}]
    assemblies=[{"id":"asm1","name":"Montage","items":[{"article_no":"A1","qty":1},{"article_no":"A2","qty":2}]}]
    assembly_bindings={"p1":{"symbol":"asm1"},"p2":{"symbol":"asm1"}}

    all_rows=core.bom_assembly_usage([p1,p2],catalog,{},[kitchen,hall],assemblies,assembly_bindings)
    assert len(all_rows)==1
    assert all_rows[0]["uses"]==2
    assert set(all_rows[0]["rooms"])=={"R01 · Køkken","R02 · Gang"}
    assert all_rows[0]["totals_by_currency"]["DKK"]==28.0

    kitchen_rows=core.bom_assembly_usage([p1,p2],catalog,{},[kitchen,hall],assemblies,assembly_bindings,room_filter_uid="room-k")
    assert kitchen_rows[0]["uses"]==1
    assert kitchen_rows[0]["totals_by_currency"]["DKK"]==14.0

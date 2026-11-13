from pathlib import Path


def test_version_05910():
    import core_logic as core
    from project_model import APP_VERSION
    assert APP_VERSION == core.APP_VERSION == "0.59.75"


def test_primary_ui_exposes_loop_only_wago_as_first_class_action():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert 'QPushButton("+ Samlemuffe / sløjfe")' in source
    assert 'def _new_loop_wago_for_selected_function' in source
    assert 'default_connects=False' in source
    assert '+ Opret samlemuffe / sløjfe · ingen udtag' in source


def test_terminal_context_has_explicit_connected_and_loop_only_choices():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert '+ Opret Wago for {caption} → lampeudtag' in source
    assert '+ Opret samlemuffe for {caption} · ingen forbindelse til udtag' in source
    assert 'functionAction.emit(fid,"new_loop")' in source


def test_loop_only_wago_is_visually_unambiguous():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert 'f"SAMLEMUFFE · {info[\'label\']}"' in source
    assert 'f"{member_count} ledere · til {destination_short}"' in source
    assert 'samlemuffe · ingen udtag' in source


def test_existing_loop_data_model_remains_rollback_compatible():
    import core_logic as core
    raw=[{
        "id":"loop","function":"n","members":[],
        "article_no":"221-412","connects_to_outlet":False,
    }]
    got=core.normalize_pl_box_splices(raw)[0]
    assert got["connects_to_outlet"] is False
    assert got["article_no"] == "221-412"

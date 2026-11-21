import json
from pathlib import Path

from elplan_core import settings as app_settings
from elplan_project import portability
from elplan_catalog import user_library


ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_synced_article_data_is_separate_from_local_machine_data(tmp_path, monkeypatch):
    local = tmp_path / "local-settings"
    synced = tmp_path / "OneDrive" / "Elplan" / "Artikeldata"
    settings = {"core_data_storage_mode": "synced", "core_data_root": str(synced)}
    monkeypatch.delenv("ELPLAN_USER_DATA_DIR", raising=False)
    monkeypatch.setattr(user_library, "user_data_dir", lambda: local)
    monkeypatch.setattr(app_settings, "load_app_settings", lambda: settings)

    assert user_library.core_data_dir() == synced
    assert user_library.article_catalog_path() == synced / "articles.json"
    assert user_library.article_prices_path() == synced / "article_prices.json"
    assert user_library.bom_assemblies_path() == synced / "bom_assemblies.json"
    assert user_library.settings_path() == local / "settings.json"


def test_environment_override_keeps_test_and_admin_data_isolated(tmp_path, monkeypatch):
    override = tmp_path / "override"
    monkeypatch.setenv("ELPLAN_USER_DATA_DIR", str(override))
    mode, directory = user_library.configured_core_data({
        "core_data_storage_mode": "synced",
        "core_data_root": str(tmp_path / "OneDrive"),
    })
    assert mode == user_library.CORE_DATA_MODE_LOCAL
    assert directory == override


def test_migration_merges_into_onedrive_with_target_priority_and_backup(tmp_path):
    source = tmp_path / "local"
    target = tmp_path / "OneDrive" / "Elplan" / "Artikeldata"
    _write(source / "articles.json", {"version": 2, "articles": [
        {"article_no": "A", "description": "Lokal gammel", "unit": "stk"},
        {"article_no": "B", "description": "Kun lokal", "unit": "stk"},
    ]})
    _write(source / "article_prices.json", {"version": 4, "prices": {
        "A": {"manual_price": 10, "price_currency": "DKK"},
        "B": {"manual_price": 11, "price_currency": "DKK"},
    }})
    _write(source / "bom_assemblies.json", {"version": 4, "assemblies": [
        {"id": "same", "name": "Lokal gammel", "items": [{"article_no": "A", "qty": 1}]},
        {"id": "local", "name": "Kun lokal", "items": [{"article_no": "B", "qty": 1}]},
    ], "articles": []})

    _write(target / "articles.json", {"version": 2, "articles": [
        {"article_no": "A", "description": "OneDrive ny", "unit": "stk"},
        {"article_no": "C", "description": "Kun OneDrive", "unit": "stk"},
    ]})
    _write(target / "article_prices.json", {"version": 4, "prices": {
        "A": {"manual_price": 20, "price_currency": "DKK"},
    }})
    _write(target / "bom_assemblies.json", {"version": 4, "assemblies": [
        {"id": "same", "name": "OneDrive ny", "items": [{"article_no": "A", "qty": 2}]},
    ], "articles": []})

    result = user_library.migrate_core_data_directory(source, target)
    articles = {row["article_no"]: row for row in json.loads((target / "articles.json").read_text(encoding="utf-8"))["articles"]}
    prices = json.loads((target / "article_prices.json").read_text(encoding="utf-8"))["prices"]
    assemblies = {row["id"]: row for row in json.loads((target / "bom_assemblies.json").read_text(encoding="utf-8"))["assemblies"]}

    assert set(articles) == {"A", "B", "C"}
    assert articles["A"]["description"] == "OneDrive ny"
    assert prices["A"]["manual_price"] == 20
    assert prices["B"]["manual_price"] == 11
    assert assemblies["same"]["name"] == "OneDrive ny"
    assert assemblies["local"]["name"] == "Kun lokal"
    assert result["backup"] and (Path(result["backup"]) / "articles.json").is_file()
    backed_up = json.loads((Path(result["backup"]) / "articles.json").read_text(encoding="utf-8"))
    assert backed_up["articles"][0]["description"] == "OneDrive ny"
    assert json.loads((source / "articles.json").read_text(encoding="utf-8"))["articles"][0]["description"] == "Lokal gammel"


def test_storage_ui_keeps_article_data_outside_projects_and_settings_portable():
    dialog = (ROOT / "elplan_qt/qt_project_storage.py").read_text(encoding="utf-8")
    app = (ROOT / "elplan_qt/qt_app.py").read_text(encoding="utf-8")
    assert '"Elplan"/"Artikeldata"' in dialog
    assert "Artikelmappen skal ligge uden for projektlageret" in dialog
    assert "Projektfiler ændres ikke" in dialog
    assert 'QAction("Artikeldata…"' in app
    assert 'addMenu("Lager og synkronisering")' in app
    assert {"core_data_storage_mode", "core_data_root"} <= portability._MACHINE_LOCAL_SETTINGS


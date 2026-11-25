from pathlib import Path

from lead_assistant.config import get_setting, resolve_database_path


def test_database_url_can_be_read_from_environment(monkeypatch):
    database_url = "postgresql://user:password@db.example.test/app"
    monkeypatch.setenv("DATABASE_URL", database_url)

    assert get_setting("DATABASE_URL") == database_url


def test_relative_database_path_is_anchored_to_project_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    database_path = Path(resolve_database_path("data/lead_assistant.db"))

    assert database_path == Path(__file__).resolve().parents[1] / "data" / "lead_assistant.db"


def test_absolute_database_path_is_preserved(tmp_path):
    database_path = tmp_path / "custom.db"

    assert resolve_database_path(str(database_path)) == str(database_path)

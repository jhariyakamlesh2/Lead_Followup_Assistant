import lead_assistant.config as config
from streamlit.errors import StreamlitSecretNotFoundError


def test_environment_setting_takes_precedence_over_streamlit_secrets(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "environment-key")
    monkeypatch.setattr(config.st, "secrets", {"ANTHROPIC_API_KEY": "streamlit-key"})

    assert config.get_setting("ANTHROPIC_API_KEY") == "environment-key"


def test_setting_falls_back_to_streamlit_secrets(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(config.st, "secrets", {"ANTHROPIC_API_KEY": "streamlit-key"})

    assert config.get_setting("ANTHROPIC_API_KEY") == "streamlit-key"


def test_setting_uses_default_when_no_streamlit_secrets_file_exists(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    class MissingSecrets:
        def get(self, name, default):
            raise StreamlitSecretNotFoundError("No secrets file found")

    monkeypatch.setattr(config.st, "secrets", MissingSecrets())

    assert config.get_setting("ANTHROPIC_API_KEY", "fallback") == "fallback"

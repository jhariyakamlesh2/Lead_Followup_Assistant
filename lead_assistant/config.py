from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

load_dotenv()


def get_setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value

    try:
        return st.secrets.get(name, default)
    except StreamlitSecretNotFoundError:
        return default


def resolve_database_path(path: str) -> str:
    database_path = Path(path).expanduser()
    if not database_path.is_absolute():
        database_path = Path(__file__).resolve().parent.parent / database_path
    return str(database_path.resolve())


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = get_setting("ANTHROPIC_API_KEY")
    anthropic_model: str = get_setting("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    database_url: str = get_setting("DATABASE_URL")
    database_path: str = resolve_database_path(
        get_setting("DATABASE_PATH", "data/lead_assistant.db")
    )
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: str = os.getenv("SMTP_PORT", "587")
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL", "")
    smtp_security: str = os.getenv("SMTP_SECURITY", "starttls")

settings = Settings()

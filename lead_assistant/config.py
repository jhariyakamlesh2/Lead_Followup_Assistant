from dataclasses import dataclass
import os
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


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = get_setting("ANTHROPIC_API_KEY")
    anthropic_model: str = get_setting("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    database_path: str = os.getenv("DATABASE_PATH", "data/lead_assistant.db")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: str = os.getenv("SMTP_PORT", "587")
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL", "")
    smtp_security: str = os.getenv("SMTP_SECURITY", "starttls")

settings = Settings()

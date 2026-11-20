from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    database_path: str = os.getenv("DATABASE_PATH", "data/lead_assistant.db")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: str = os.getenv("SMTP_PORT", "587")
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL", "")
    smtp_security: str = os.getenv("SMTP_SECURITY", "starttls")

settings = Settings()

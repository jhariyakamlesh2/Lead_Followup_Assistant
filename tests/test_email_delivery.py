import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from lead_assistant.database import Database
from lead_assistant.email_sender import EmailSender, validate_recipient_address


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout, context=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.context = context
        self.events = []
        self.message = None
        self.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def ehlo(self):
        self.events.append("ehlo")

    def starttls(self, context):
        self.events.append("starttls")

    def login(self, username, password):
        self.events.append(("login", username, password))

    def send_message(self, message):
        self.message = message
        self.events.append("send")
        return {}


class FakeEmailSender:
    calls = []

    def __init__(self, _settings):
        pass

    def configuration_error(self):
        return None

    def send_email(self, recipient, subject, body):
        self.calls.append((recipient, subject, body))


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def sender_settings(**overrides):
    values = {
        "smtp_host": "smtp.provider.invalid",
        "smtp_port": "587",
        "smtp_username": "smtp-user",
        "smtp_password": "test-only-password",
        "smtp_from_email": "team@leadpilot.example",
        "smtp_security": "starttls",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def create_draft(db, email, channel="Email", approve=True):
    lead_id = db.add_lead(
        "Taylor Example",
        email,
        "",
        "Data Analytics Career Programme",
        source="Manual",
    )
    draft_id = db.save_draft(
        lead_id,
        channel,
        "A quick follow-up",
        "Hello Taylor,\n\nHere are the details we discussed.",
        {"stage": "Interested"},
        [],
        "Test",
        "mock",
        "1.0",
    )
    if approve:
        db.review_draft(draft_id, "Approved")
    return lead_id, draft_id


def test_smtp_sender_uses_starttls_authentication_and_sends_plain_text(monkeypatch):
    FakeSMTP.instances.clear()
    monkeypatch.setattr("lead_assistant.email_sender.smtplib.SMTP", FakeSMTP)
    sender = EmailSender(sender_settings())

    sender.send_email(
        "taylor@contoso.org",
        "A quick follow-up",
        "Hello Taylor,\n\nHere are the details.",
    )

    client = FakeSMTP.instances[0]
    assert (client.host, client.port, client.timeout) == (
        "smtp.provider.invalid",
        587,
        20,
    )
    assert client.events == [
        "ehlo",
        "starttls",
        "ehlo",
        ("login", "smtp-user", "test-only-password"),
        "send",
    ]
    assert client.message["To"] == "taylor@contoso.org"
    assert client.message["Subject"] == "A quick follow-up"
    assert client.message.get_content() == "Hello Taylor,\n\nHere are the details.\n"


def test_smtp_sender_supports_implicit_tls_without_authentication(monkeypatch):
    FakeSMTP.instances.clear()
    monkeypatch.setattr("lead_assistant.email_sender.smtplib.SMTP_SSL", FakeSMTP)
    sender = EmailSender(
        sender_settings(
            smtp_security="ssl",
            smtp_username="",
            smtp_password="",
        )
    )

    sender.send_email("taylor@contoso.org", "A quick follow-up", "Hello Taylor.")

    client = FakeSMTP.instances[0]
    assert client.context is not None
    assert client.events == ["send"]


def test_demo_email_addresses_are_rejected_before_smtp_connect(monkeypatch):
    def unexpected_connection(*_args, **_kwargs):
        raise AssertionError("SMTP must not be opened for demo addresses.")

    monkeypatch.setattr(
        "lead_assistant.email_sender.smtplib.SMTP", unexpected_connection
    )
    sender = EmailSender(sender_settings())

    with pytest.raises(ValueError, match="demo/test"):
        sender.send_email(
            "aarav.example@email.test",
            "A quick follow-up",
            "Hello there.",
        )
    with pytest.raises(ValueError, match="demo/test"):
        validate_recipient_address("person@example.com")


def test_missing_smtp_configuration_blocks_sending(monkeypatch):
    def unexpected_connection(*_args, **_kwargs):
        raise AssertionError("SMTP must not be opened without configuration.")

    monkeypatch.setattr(
        "lead_assistant.email_sender.smtplib.SMTP", unexpected_connection
    )
    sender = EmailSender(sender_settings(smtp_host="", smtp_from_email=""))

    assert "SMTP_HOST" in sender.configuration_error()
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        sender.send_email("taylor@contoso.org", "Subject", "Body")


def test_legacy_settings_object_reports_restart_instead_of_crashing():
    legacy_settings = SimpleNamespace(
        anthropic_api_key="",
        anthropic_model="",
        database_path="",
    )

    sender = EmailSender(legacy_settings)

    assert "Restart Streamlit" in sender.configuration_error()


def test_existing_database_gets_sent_at_migration(tmp_path):
    database_path = tmp_path / "legacy.sqlite"
    schema_path = Path(__file__).resolve().parents[1] / "schema.sql"
    legacy_schema = schema_path.read_text(encoding="utf-8").replace(
        ", sent_at TEXT", ""
    )
    with sqlite3.connect(database_path) as connection:
        connection.executescript(legacy_schema)

    Database(database_path)

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(draft_messages)")
        }
    assert "sent_at" in columns


def test_database_email_send_lifecycle_and_retry_confirmation(tmp_path):
    db = Database(tmp_path / "email.db")
    lead_id, draft_id = create_draft(
        db, "taylor@contoso.org", approve=False
    )

    with pytest.raises(ValueError, match="approved"):
        db.claim_email_draft_for_sending(draft_id)
    db.review_draft(draft_id, "Approved")

    claimed = db.claim_email_draft_for_sending(draft_id)
    assert claimed["email"] == "taylor@contoso.org"
    with pytest.raises(ValueError, match="approved"):
        db.claim_email_draft_for_sending(draft_id)

    db.mark_email_send_failed(draft_id, "SMTPConnectError")
    with pytest.raises(ValueError, match="Confirm"):
        db.claim_email_draft_for_sending(draft_id)

    db.claim_email_draft_for_sending(draft_id, retry_confirmed=True)
    db.mark_email_draft_sent(draft_id)

    saved = db.get_drafts().iloc[0]
    assert saved["status"] == "Sent"
    assert saved["sent_at"]
    history = db.get_history(lead_id)
    assert history.iloc[-1]["direction"] == "Outbound"
    assert history.iloc[-1]["message"] == (
        "Hello Taylor,\n\nHere are the details we discussed."
    )


def test_interrupted_send_requires_delivery_check_before_retry(tmp_path):
    db = Database(tmp_path / "recovery.db")
    _, draft_id = create_draft(db, "taylor@contoso.org")
    db.claim_email_draft_for_sending(draft_id)

    with pytest.raises(ValueError, match="Verify non-delivery"):
        db.reconcile_email_send(draft_id, confirmed_not_delivered=False)

    db.reconcile_email_send(draft_id, confirmed_not_delivered=True)
    retry = db.claim_email_draft_for_sending(draft_id, retry_confirmed=True)
    assert retry["status"] == "Send Failed"


def test_database_blocks_demo_recipient_and_non_email_channel(tmp_path):
    db = Database(tmp_path / "blocked.db")
    _, demo_draft_id = create_draft(db, "aarav.example@email.test")
    _, whatsapp_draft_id = create_draft(
        db, "taylor@contoso.org", channel="WhatsApp"
    )

    with pytest.raises(ValueError, match="demo/test"):
        db.claim_email_draft_for_sending(demo_draft_id)
    with pytest.raises(ValueError, match="Only Email"):
        db.claim_email_draft_for_sending(whatsapp_draft_id)


def test_review_drafts_ui_sends_only_after_approval_with_mock_sender(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "ui.sqlite"
    db = Database(database_path)
    _, draft_id = create_draft(db, "taylor@contoso.org", approve=False)
    FakeEmailSender.calls.clear()
    monkeypatch.setattr(
        "lead_assistant.config.settings",
        sender_settings(
            database_path=str(database_path),
        ),
    )
    monkeypatch.setattr(
        "lead_assistant.email_sender.EmailSender", FakeEmailSender
    )
    import streamlit as st

    st.cache_resource.clear()
    app = AppTest.from_file(str(APP_PATH)).run()
    app.text_input[0].set_value("admin")
    app.text_input[1].set_value("admin@123")
    app.form_submit_button[0].click().run()
    app.radio[0].set_value("Review Drafts").run()

    assert not app.exception
    assert not any(button.label == "Send email" for button in app.button)
    next(button for button in app.button if button.label == "Approve").click().run()
    assert not app.exception
    assert any(button.label == "Send email" for button in app.button)
    next(button for button in app.button if button.label == "Send email").click().run()

    assert not app.exception
    assert FakeEmailSender.calls == [
        (
            "taylor@contoso.org",
            "A quick follow-up",
            "Hello Taylor,\n\nHere are the details we discussed.",
        )
    ]
    assert Database(database_path).get_drafts().iloc[0]["status"] == "Sent"
    assert not any(button.label == "Send email" for button in app.button)


def test_review_drafts_ui_disables_sending_without_smtp_configuration(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "unconfigured-ui.sqlite"
    db = Database(database_path)
    create_draft(db, "taylor@contoso.org")
    monkeypatch.setattr(
        "lead_assistant.config.settings",
        sender_settings(
            database_path=str(database_path),
            smtp_host="",
            smtp_from_email="",
            smtp_username="",
            smtp_password="",
        ),
    )
    import streamlit as st

    st.cache_resource.clear()
    app = AppTest.from_file(str(APP_PATH)).run()
    app.text_input[0].set_value("admin")
    app.text_input[1].set_value("admin@123")
    app.form_submit_button[0].click().run()
    app.radio[0].set_value("Review Drafts").run()

    assert not app.exception
    assert any("Email sending is disabled" in element.value for element in app.info)
    assert not any(button.label == "Send email" for button in app.button)

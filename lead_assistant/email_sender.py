from email.headerregistry import Address
from email.message import EmailMessage
import smtplib
import ssl


_RESERVED_DOMAINS = {
    "example.com",
    "example.net",
    "example.org",
    "localhost",
    "test",
}
_RESERVED_SUFFIXES = (
    ".example",
    ".example.com",
    ".example.net",
    ".example.org",
    ".invalid",
    ".localhost",
    ".test",
)


def validate_recipient_address(value):
    address = str(value or "").strip()
    if not address or "\r" in address or "\n" in address:
        raise ValueError("Enter a valid recipient email address.")
    try:
        parsed = Address(addr_spec=address)
    except ValueError as exc:
        raise ValueError("Enter a valid recipient email address.") from exc

    domain = parsed.domain.lower()
    if domain in _RESERVED_DOMAINS or domain.endswith(_RESERVED_SUFFIXES):
        raise ValueError(
            "This is a demo/test email address. Add a real lead email before sending."
        )
    return parsed.addr_spec


class EmailSender:
    def __init__(self, settings):
        smtp_fields = (
            "smtp_host",
            "smtp_port",
            "smtp_username",
            "smtp_password",
            "smtp_from_email",
            "smtp_security",
            
        )
        self.settings_error = None
        if any(not hasattr(settings, field) for field in smtp_fields):
            self.settings_error = (
                "SMTP settings are not loaded in this app process. "
                "Restart Streamlit to load the updated configuration."
            )
        self.host = str(getattr(settings, "smtp_host", "") or "").strip()
        self.port = str(getattr(settings, "smtp_port", "587") or "").strip()
        self.username = str(getattr(settings, "smtp_username", "") or "").strip()
        self.password = str(getattr(settings, "smtp_password", "") or "")
        self.from_email = str(getattr(settings, "smtp_from_email", "") or "").strip()
        self.security = str(getattr(settings, "smtp_security", "starttls") or "").strip().lower()

    def configuration_error(self):
        if self.settings_error:
            return self.settings_error
        if not self.host or not self.from_email:
            return "Set SMTP_HOST and SMTP_FROM_EMAIL in your local .env file."
        try:
            port = int(self.port)
        except ValueError:
            return "SMTP_PORT must be a number between 1 and 65535."
        if not 1 <= port <= 65535:
            return "SMTP_PORT must be a number between 1 and 65535."
        if self.security not in {"starttls", "ssl"}:
            return "SMTP_SECURITY must be either 'starttls' or 'ssl'."
        if bool(self.username) != bool(self.password):
            return "Set both SMTP_USERNAME and SMTP_PASSWORD, or leave both blank."
        if "\r" in self.from_email or "\n" in self.from_email:
            return "SMTP_FROM_EMAIL must be a valid email address."
        try:
            Address(addr_spec=self.from_email)
        except ValueError:
            return "SMTP_FROM_EMAIL must be a valid email address."
        return None

    def send_email(self, recipient, subject, body):
        error = self.configuration_error()
        if error:
            raise RuntimeError(error)
        recipient = validate_recipient_address(recipient)
        subject = str(subject or "").strip()
        body = str(body or "")
        if not subject or "\r" in subject or "\n" in subject:
            raise ValueError("The approved email must have a valid subject.")
        if not body.strip():
            raise ValueError("The approved email body cannot be empty.")

        message = EmailMessage()
        message["From"] = self.from_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        port = int(self.port)
        context = ssl.create_default_context()

        if self.security == "ssl":
            with smtplib.SMTP_SSL(
                self.host, port, timeout=20, context=context
            ) as client:
                self._send(client, message)
        else:
            with smtplib.SMTP(self.host, port, timeout=20) as client:
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
                self._send(client, message)

    def _send(self, client, message):
        if self.username:
            client.login(self.username, self.password)
        refused = client.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)

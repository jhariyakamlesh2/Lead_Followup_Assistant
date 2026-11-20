# Sending approved emails

LeadPilot sends email through your SMTP provider only after a reviewer approves
an Email draft and then selects **Send email**. Approval alone never sends a
message. WhatsApp drafts remain draft-only.

## Configure SMTP

Copy the SMTP settings from `.env.example` into your local `.env` and fill them
in using the values supplied by your email provider:

```env
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_SECURITY=starttls
```

Use `starttls` for a STARTTLS endpoint (commonly port 587) or `ssl` for an
implicit-TLS endpoint (commonly port 465). The app requires encrypted SMTP.
If your provider does not require authentication, leave both username and
password blank; otherwise set both. Keep `.env` private and restart Streamlit
after changing it. Never add provider credentials to source control or chat.

## Send a message

1. Add a lead with a real, deliverable email address.
2. Generate an Email draft and review its recipient, subject, and body.
3. In **Review Drafts**, approve the draft.
4. In **Approved email drafts**, verify the recipient and exact message, then
   select **Send email**.

Synthetic/reserved addresses such as the seeded `@email.test` address cannot
be sent to. The app records the send status, sent time, audit event, and
outbound interaction. If a send fails or is interrupted, check the provider's
delivery status before confirming a retry; this avoids accidental duplicates.

Automated tests use a mocked SMTP transport and never send a real email. The
included demo login is not production authentication, so do not expose this
prototype publicly or use it for sensitive data.

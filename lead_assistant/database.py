import sqlite3, json
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
import pandas as pd
from .email_sender import validate_recipient_address

def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

class Database:
    def __init__(self, db_path="data/lead_assistant.db"):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
        schema = schema_path.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(schema)
            draft_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(draft_messages)")
            }
            if "sent_at" not in draft_columns:
                conn.execute("ALTER TABLE draft_messages ADD COLUMN sent_at TEXT")

    def add_lead(self, full_name, email, phone, programme_interest, source="Sample"):
        name, programme = (full_name or "").strip(), (programme_interest or "").strip()
        if not name or not programme:
            raise ValueError("Lead name and programme interest are required.")
        if email and "@" not in email:
            raise ValueError("Please enter a valid email address.")
        stamp = now_iso()
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO leads(full_name,email,phone,programme_interest,source,status,created_at,updated_at)
                   VALUES(?,?,?,?,?,'New',?,?)""",
                (name, email.strip() if email else None, phone.strip() if phone else None,
                 programme, source, stamp, stamp))
            lead_id = cur.lastrowid
            self.audit(lead_id, None, "LEAD_CREATED", {"programme": programme}, conn)
            return lead_id

    def add_interaction(self, lead_id, channel, message, direction="Inbound", occurred_at=None):
        if not str(message or "").strip():
            raise ValueError("Interaction message cannot be empty.")
        if channel not in {"Email", "WhatsApp", "Call", "Web"}:
            raise ValueError("Unsupported channel.")
        if direction not in {"Inbound", "Outbound"}:
            raise ValueError("Direction must be Inbound or Outbound.")
        stamp = now_iso()
        with self.connect() as conn:
            if not conn.execute("SELECT 1 FROM leads WHERE lead_id=?", (lead_id,)).fetchone():
                raise LookupError("Lead not found.")
            cur = conn.execute(
                """INSERT INTO interactions(lead_id,channel,direction,message,occurred_at,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (lead_id, channel, direction, message.strip(), occurred_at or stamp, stamp))
            self.audit(lead_id, None, "INTERACTION_ADDED",
                       {"interaction_id": cur.lastrowid, "channel": channel}, conn)
            return cur.lastrowid

    def add_fact(self, programme_name, category, fact_text, approved=True):
        if not all(str(x or "").strip() for x in (programme_name, category, fact_text)):
            raise ValueError("Programme, category and fact text are required.")
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO programme_facts(programme_name,fact_category,fact_text,is_approved,created_at)
                   VALUES(?,?,?,?,?)""",
                (programme_name.strip(), category.strip(), fact_text.strip(), int(approved), now_iso()))
            fact_id = cur.lastrowid
            self.audit(
                None,
                None,
                "PROGRAMME_FACT_ADDED",
                {
                    "fact_id": fact_id,
                    "programme": programme_name.strip(),
                    "category": category.strip(),
                    "approved": bool(approved),
                },
                conn,
            )
            return fact_id

    def get_leads(self):
        with self.connect() as conn:
            return pd.read_sql_query("SELECT * FROM leads ORDER BY updated_at DESC", conn)

    def get_lead(self, lead_id):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM leads WHERE lead_id=?", (lead_id,)).fetchone()
            return dict(row) if row else None

    def get_history(self, lead_id):
        with self.connect() as conn:
            return pd.read_sql_query(
                "SELECT * FROM interactions WHERE lead_id=? ORDER BY occurred_at",
                conn, params=(lead_id,))

    def get_approved_facts(self, programme_name):
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT fact_id,programme_name,fact_category,fact_text FROM programme_facts
                   WHERE is_approved=1 AND lower(programme_name)=lower(?) ORDER BY fact_id""",
                (programme_name,)).fetchall()
            return [dict(r) for r in rows]

    def save_draft(self, lead_id, channel, subject, body, nlp_result, fact_ids,
                   provider, model, prompt_version):
        if channel not in {"Email", "WhatsApp"} or not body.strip():
            raise ValueError("A valid channel and non-empty draft body are required.")
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO draft_messages
                (lead_id,channel,subject,message_body,nlp_stage,nlp_result_json,fact_ids_json,
                 provider,model,prompt_version,status,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,'Pending Approval',?)""",
                (lead_id, channel, subject, body, nlp_result.get("stage"),
                 json.dumps(nlp_result), json.dumps(fact_ids), provider, model,
                 prompt_version, now_iso()))
            draft_id = cur.lastrowid
            self.audit(lead_id, draft_id, "DRAFT_CREATED",
                       {"channel": channel, "provider": provider, "model": model}, conn)
            return draft_id

    def review_draft(self, draft_id, decision, feedback=""):
        if decision not in {"Approved", "Rejected", "Needs Changes"}:
            raise ValueError("Invalid review decision.")
        with self.connect() as conn:
            cur = conn.execute(
                """UPDATE draft_messages
                   SET status=?,reviewer_feedback=?,reviewed_at=?
                   WHERE draft_id=? AND status='Pending Approval'""",
                (decision, feedback, now_iso(), draft_id))
            if cur.rowcount == 0:
                exists = conn.execute(
                    "SELECT 1 FROM draft_messages WHERE draft_id=?", (draft_id,)
                ).fetchone()
                if not exists:
                    raise LookupError("Draft not found.")
                raise ValueError("Only pending drafts can be reviewed.")
            row = conn.execute("SELECT lead_id FROM draft_messages WHERE draft_id=?",
                               (draft_id,)).fetchone()
            self.audit(row["lead_id"], draft_id, "DRAFT_REVIEWED",
                       {"decision": decision, "feedback": feedback}, conn)

    def claim_email_draft_for_sending(self, draft_id, retry_confirmed=False):
        with self.connect() as conn:
            row = conn.execute(
                """SELECT d.draft_id,d.lead_id,d.channel,d.subject,d.message_body,d.status,
                          l.full_name,l.email
                   FROM draft_messages d JOIN leads l ON l.lead_id=d.lead_id
                   WHERE d.draft_id=?""",
                (draft_id,),
            ).fetchone()
            if not row:
                raise LookupError("Draft not found.")
            if row["channel"] != "Email":
                raise ValueError("Only Email drafts can be sent through SMTP.")
            if row["status"] == "Send Failed":
                if not retry_confirmed:
                    raise ValueError("Confirm the previous email was not delivered before retrying.")
            elif row["status"] != "Approved":
                raise ValueError("Only approved email drafts can be sent.")
            if not row["email"]:
                raise ValueError("This lead does not have an email address.")
            subject = str(row["subject"] or "").strip()
            if not subject:
                raise ValueError("The approved email must have a subject.")
            if "\r" in subject or "\n" in subject:
                raise ValueError("The email subject cannot contain line breaks.")
            if not str(row["message_body"] or "").strip():
                raise ValueError("The approved email body cannot be empty.")
            validate_recipient_address(row["email"])

            cur = conn.execute(
                """UPDATE draft_messages SET status='Sending'
                   WHERE draft_id=? AND status=? AND channel='Email'""",
                (draft_id, row["status"]),
            )
            if cur.rowcount != 1:
                raise ValueError("This draft's send status changed. Refresh and review it again.")
            self.audit(
                row["lead_id"],
                draft_id,
                "EMAIL_SEND_STARTED",
                {"retry": row["status"] == "Send Failed"},
                conn,
            )
            return dict(row)

    def mark_email_send_failed(self, draft_id, error_type):
        with self.connect() as conn:
            cur = conn.execute(
                """UPDATE draft_messages SET status='Send Failed'
                   WHERE draft_id=? AND status='Sending'""",
                (draft_id,),
            )
            if cur.rowcount != 1:
                raise ValueError("No email send is in progress for this draft.")
            row = conn.execute(
                "SELECT lead_id FROM draft_messages WHERE draft_id=?",
                (draft_id,),
            ).fetchone()
            self.audit(
                row["lead_id"],
                draft_id,
                "EMAIL_SEND_FAILED",
                {"error_type": error_type},
                conn,
            )

    def reconcile_email_send(self, draft_id, confirmed_not_delivered):
        if not confirmed_not_delivered:
            raise ValueError("Verify non-delivery with your SMTP provider before recovery.")
        with self.connect() as conn:
            cur = conn.execute(
                """UPDATE draft_messages SET status='Send Failed'
                   WHERE draft_id=? AND status='Sending'""",
                (draft_id,),
            )
            if cur.rowcount != 1:
                raise ValueError("This draft is not awaiting send reconciliation.")
            row = conn.execute(
                "SELECT lead_id FROM draft_messages WHERE draft_id=?",
                (draft_id,),
            ).fetchone()
            self.audit(
                row["lead_id"],
                draft_id,
                "EMAIL_SEND_RECONCILED",
                {"confirmed_not_delivered": True},
                conn,
            )

    def mark_email_draft_sent(self, draft_id):
        stamp = now_iso()
        with self.connect() as conn:
            row = conn.execute(
                """SELECT lead_id,message_body FROM draft_messages
                   WHERE draft_id=? AND channel='Email' AND status='Sending'""",
                (draft_id,),
            ).fetchone()
            if not row:
                raise ValueError("This draft is not in the sending state.")
            cur = conn.execute(
                """UPDATE draft_messages SET status='Sent',sent_at=?
                   WHERE draft_id=? AND status='Sending'""",
                (stamp, draft_id),
            )
            if cur.rowcount != 1:
                raise ValueError("This draft's send status changed.")
            conn.execute(
                """INSERT INTO interactions
                   (lead_id,channel,direction,message,occurred_at,created_at)
                   VALUES(?,'Email','Outbound',?,?,?)""",
                (row["lead_id"], row["message_body"], stamp, stamp),
            )
            self.audit(
                row["lead_id"],
                draft_id,
                "EMAIL_SENT",
                {"channel": "Email"},
                conn,
            )

    def get_drafts(self):
        with self.connect() as conn:
            return pd.read_sql_query(
                """SELECT d.*,l.full_name,l.email,l.source,l.programme_interest
                   FROM draft_messages d
                   JOIN leads l ON d.lead_id=l.lead_id ORDER BY d.created_at DESC""", conn)

    def audit(self, lead_id, draft_id, action, details, conn):
        conn.execute(
            "INSERT INTO audit_logs(lead_id,draft_id,action,details_json,created_at) VALUES(?,?,?,?,?)",
            (lead_id, draft_id, action, json.dumps(details), now_iso()))

    def seed_sample_data(self):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT lead_id FROM leads WHERE email=?",
                ("aarav.example@email.test",),
            ).fetchone()
            lid = row["lead_id"] if row else None
        if lid is None:
            lid = self.add_lead(
                "Aarav Sharma",
                "aarav.example@email.test",
                "+91-9000000001",
                "Data Analytics Career Programme",
            )
        with self.connect() as conn:
            has_history = conn.execute(
                "SELECT 1 FROM interactions WHERE lead_id=? LIMIT 1", (lid,)
            ).fetchone()
            has_facts = conn.execute(
                "SELECT 1 FROM programme_facts WHERE programme_name=? LIMIT 1",
                ("Data Analytics Career Programme",),
            ).fetchone()
        if has_history:
            history = self.get_history(lid)
        else:
            history = None
        if history is None or history.empty:
            self.add_interaction(lid, "WhatsApp",
                "I am interested in the Data Analytics Career Programme. Is it suitable for a beginner?")
            self.add_interaction(lid, "Call",
                "I prefer weekend sessions. Please share details about fees and placement support.")
            self.add_interaction(lid, "Email",
                "Are classes recorded? I still need to know the exact fee.")
        if not has_facts:
            for category, fact in [
                ("Audience", "The programme is designed for beginners and career changers."),
                ("Schedule", "Live online sessions are available on weekends."),
                ("Learning support", "Learners receive guided practice exercises and mentor-led doubt sessions."),
                ("Recording", "Recording availability must be confirmed by the programme team before promising access."),
                ("Fees", "The current fee is not present in the approved sample knowledge base; ask the programme team to confirm.")
            ]:
                self.add_fact("Data Analytics Career Programme", category, fact)

        with self.connect() as conn:
            has_ai_facts = conn.execute(
                "SELECT 1 FROM programme_facts WHERE programme_name=? LIMIT 1",
                ("AI Engineering",),
            ).fetchone()
        if has_ai_facts:
            return
        for category, fact in [
            ("Audience", "The AI Engineering programme is suitable for learners who want to build practical AI engineering foundations."),
            ("Schedule", "The exact live-session schedule must be confirmed by the programme team."),
            ("Learning support", "Learners receive guided practice and mentor-led doubt sessions."),
            ("Recording", "Recording availability must be confirmed by the programme team before promising access."),
            ("Fees", "The current fee is not present in the approved sample knowledge base; ask the programme team to confirm."),
        ]:
            self.add_fact("AI Engineering", category, fact)

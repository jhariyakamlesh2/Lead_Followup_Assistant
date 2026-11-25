import sqlite3, json
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
from email.headerregistry import Address
from email.errors import HeaderParseError
import warnings
import pandas as pd
from .email_sender import validate_recipient_address


class _ConnectionAdapter:
    def __init__(self, connection, is_postgres):
        self._connection = connection
        self._is_postgres = is_postgres

    def execute(self, query, parameters=()):
        if self._is_postgres:
            query = query.replace("?", "%s")
        return self._connection.execute(query, parameters)

    def executescript(self, script):
        return self._connection.executescript(script)

    def __getattr__(self, name):
        return getattr(self._connection, name)


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Database:
    def __init__(self, db_path="data/lead_assistant.db"):
        self.db_path = str(db_path)
        self.is_postgres = self.db_path.startswith(("postgres://", "postgresql://"))
        if self.db_path.startswith("postgres://"):
            self.db_path = "postgresql://" + self.db_path[len("postgres://"):]
        self.duplicate_warnings = []
        if not self.is_postgres:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self):
        if self.is_postgres:
            import psycopg
            from psycopg.rows import dict_row

            raw_conn = psycopg.connect(
                self.db_path,
                row_factory=dict_row,
                prepare_threshold=None,
            )
        else:
            raw_conn = sqlite3.connect(self.db_path)
            raw_conn.row_factory = sqlite3.Row
            raw_conn.execute("PRAGMA foreign_keys=ON")
        conn = _ConnectionAdapter(raw_conn, self.is_postgres)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        schema_name = "schema_postgres.sql" if self.is_postgres else "schema.sql"
        schema_path = Path(__file__).resolve().parent.parent / schema_name
        schema = schema_path.read_text(encoding="utf-8")
        with self.connect() as conn:
            if self.is_postgres:
                for statement in schema.split(";"):
                    if statement.strip():
                        conn.execute(statement)
                draft_columns = {
                    row["column_name"]
                    for row in conn.execute(
                        """SELECT column_name FROM information_schema.columns
                           WHERE table_schema=current_schema()
                             AND table_name='draft_messages'"""
                    )
                }
                if "sent_at" not in draft_columns:
                    conn.execute(
                        "ALTER TABLE draft_messages ADD COLUMN sent_at TEXT"
                    )
                if "response_id" not in draft_columns:
                    conn.execute(
                        "ALTER TABLE draft_messages ADD COLUMN response_id TEXT"
                    )
            else:
                conn.executescript(schema)
                draft_columns = {
                    row["name"] for row in conn.execute("PRAGMA table_info(draft_messages)")
                }
                if "sent_at" not in draft_columns:
                    conn.execute("ALTER TABLE draft_messages ADD COLUMN sent_at TEXT")
                if "response_id" not in draft_columns:
                    conn.execute("ALTER TABLE draft_messages ADD COLUMN response_id TEXT")
        self.remove_duplicate_entries()
        self._create_duplicate_prevention_indexes()

    def _insert_id(self, conn, query, parameters, id_column):
        if self.is_postgres:
            row = conn.execute(
                f"{query} RETURNING {id_column}", parameters
            ).fetchone()
            return row[id_column]
        return conn.execute(query, parameters).lastrowid

    @staticmethod
    def _read_dataframe(conn, query, parameters=()):
        cursor = conn.execute(query, parameters)
        columns = [description[0] for description in cursor.description]
        return pd.DataFrame.from_records(
            [dict(row) for row in cursor.fetchall()],
            columns=columns,
        )

    def _warn_duplicate(self, entity, kept_id, removed_id=None):
        if removed_id is None:
            message = f"Duplicate {entity} detected. Existing record #{kept_id} was reused; no duplicate was inserted."
        else:
            message = f"Duplicate {entity} entries detected. Record #{removed_id} was removed; record #{kept_id} was kept."
        self.duplicate_warnings.append(message)
        warnings.warn(message, UserWarning)

    def consume_duplicate_warnings(self):
        warnings_list = list(self.duplicate_warnings)
        self.duplicate_warnings.clear()
        return warnings_list

    def remove_duplicate_entries(self):
        removed = {
            "leads": 0,
            "interactions": 0,
            "programme_facts": 0,
            "message_templates": 0,
            "draft_messages": 0,
            "audit_logs": 0,
        }
        with self.connect() as conn:
            lead_groups = {}
            for row in conn.execute(
                "SELECT lead_id,full_name,email,programme_interest FROM leads ORDER BY lead_id"
            ):
                key = (
                    str(row["full_name"] or "").strip().lower(),
                    str(row["programme_interest"] or "").strip().lower(),
                    str(row["email"] or "").strip().lower(),
                )
                lead_groups.setdefault(key, []).append(row["lead_id"])
            for ids in lead_groups.values():
                if len(ids) > 1:
                    kept = ids[0]
                    for duplicate_id in ids[1:]:
                        conn.execute("UPDATE interactions SET lead_id=? WHERE lead_id=?", (kept, duplicate_id))
                        conn.execute("UPDATE draft_messages SET lead_id=? WHERE lead_id=?", (kept, duplicate_id))
                        conn.execute("UPDATE audit_logs SET lead_id=? WHERE lead_id=?", (kept, duplicate_id))
                        conn.execute("DELETE FROM leads WHERE lead_id=?", (duplicate_id,))
                        removed["leads"] += 1
                        self._warn_duplicate("lead", kept, duplicate_id)

            def remove_duplicate_rows(table, id_column, columns, name):
                groups = {}
                for row in conn.execute(
                    f"SELECT {id_column},{','.join(columns)} FROM {table} ORDER BY {id_column}"
                ):
                    key = tuple(str(row[column] or "").strip().lower() for column in columns)
                    groups.setdefault(key, []).append(row[id_column])
                for ids in groups.values():
                    if len(ids) > 1:
                        kept = ids[0]
                        for duplicate_id in ids[1:]:
                            conn.execute(
                                f"DELETE FROM {table} WHERE {id_column}=?",
                                (duplicate_id,),
                            )
                            removed[name] += 1
                            self._warn_duplicate(name.replace("_", " "), kept, duplicate_id)

            remove_duplicate_rows(
                "interactions", "interaction_id",
                ["lead_id", "channel", "direction", "message", "occurred_at"],
                "interactions",
            )
            remove_duplicate_rows(
                "programme_facts", "fact_id",
                ["programme_name", "fact_category", "fact_text", "is_approved"],
                "programme_facts",
            )
            remove_duplicate_rows(
                "message_templates", "template_id",
                ["channel", "template_name", "template_text", "version"],
                "message_templates",
            )
            remove_duplicate_rows(
                "draft_messages", "draft_id",
                ["lead_id", "channel", "subject", "message_body", "nlp_result_json",
                 "fact_ids_json", "provider", "model", "prompt_version", "response_id"],
                "draft_messages",
            )
            remove_duplicate_rows(
                "audit_logs", "audit_id",
                ["lead_id", "draft_id", "action", "details_json", "created_at"],
                "audit_logs",
            )
        return removed

    def _create_duplicate_prevention_indexes(self):
        with self.connect() as conn:
            conn.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS uq_leads_identity
                   ON leads(lower(trim(full_name)),lower(trim(programme_interest)),
                           lower(trim(COALESCE(email,''))))"""
            )
            conn.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS uq_interactions_identity
                   ON interactions(lead_id,lower(trim(channel)),
                           lower(trim(direction)),lower(trim(message)),trim(occurred_at))"""
            )
            conn.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS uq_programme_facts_identity
                   ON programme_facts(lower(trim(programme_name)),
                           lower(trim(fact_category)),lower(trim(fact_text)),is_approved)"""
            )
            conn.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS uq_message_templates_identity
                   ON message_templates(lower(trim(channel)),lower(trim(template_name)),
                           trim(template_text),trim(version))"""
            )
            conn.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS uq_draft_messages_response
                   ON draft_messages(response_id) WHERE response_id IS NOT NULL"""
            )

    def add_lead(self, full_name, email, phone, programme_interest, source="Sample"):
        name, programme = (full_name or "").strip(), (programme_interest or "").strip()
        if not name or not programme:
            raise ValueError("Lead name and programme interest are required.")
        normalized_email = str(email or "").strip().lower()
        if email:
            try:
                parsed_email = Address(addr_spec=email.strip())
                if not parsed_email.username or not parsed_email.domain:
                    raise ValueError
            except (ValueError, HeaderParseError) as exc:
                raise ValueError("Please enter a valid email address.") from exc
        stamp = now_iso()
        with self.connect() as conn:
            existing = conn.execute(
                """SELECT lead_id FROM leads
                   WHERE lower(trim(full_name))=?
                     AND lower(trim(programme_interest))=?
                     AND lower(trim(COALESCE(email,'')))=?""",
                (name.lower(), programme.lower(), normalized_email),
            ).fetchone()
            if existing:
                lead_id = existing["lead_id"]
                self._warn_duplicate("lead", lead_id)
                return lead_id
            lead_id = self._insert_id(
                conn,
                """INSERT INTO leads(full_name,email,phone,programme_interest,source,status,created_at,updated_at)
                   VALUES(?,?,?,?,?,'New',?,?)""",
                (name, email.strip() if email else None, phone.strip() if phone else None,
                 programme, source, stamp, stamp),
                "lead_id",
            )
            self.audit(lead_id, None, "LEAD_CREATED", {"programme": programme}, conn)
            return lead_id

    def add_interaction(self, lead_id, channel, message, direction="Inbound", occurred_at=None):
        if not str(message or "").strip():
            raise ValueError("Interaction message cannot be empty.")
        channel_map = {
            "email": "Email",
            "whatsapp": "WhatsApp",
            "call": "Call",
            "web": "Web",
        }
        normalized_channel = channel_map.get(str(channel).strip().lower())
        if normalized_channel is None:
            raise ValueError("Unsupported channel.")
        normalized_direction = str(direction).strip().title()
        if normalized_channel not in {"Email", "WhatsApp", "Call", "Web"}:
            raise ValueError("Unsupported channel.")
        if normalized_direction not in {"Inbound", "Outbound"}:
            raise ValueError("Direction must be Inbound or Outbound.")
        stamp = now_iso()
        normalized_message = str(message or "").strip()
        normalized_occurred_at = occurred_at or stamp
        with self.connect() as conn:
            if not conn.execute("SELECT 1 FROM leads WHERE lead_id=?", (lead_id,)).fetchone():
                raise LookupError("Lead not found.")
            existing = conn.execute(
                """SELECT interaction_id FROM interactions
                   WHERE lead_id=? AND lower(trim(channel))=?
                     AND lower(trim(direction))=? AND lower(trim(message))=?
                     AND trim(occurred_at)=?""",
                (lead_id, normalized_channel.lower(), normalized_direction.lower(),
                 normalized_message.lower(), normalized_occurred_at),
            ).fetchone()
            if existing:
                interaction_id = existing["interaction_id"]
                self._warn_duplicate("interaction", interaction_id)
                return interaction_id
            interaction_id = self._insert_id(
                conn,
                """INSERT INTO interactions(lead_id,channel,direction,message,occurred_at,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (lead_id, normalized_channel, normalized_direction, normalized_message, normalized_occurred_at, stamp),
                "interaction_id",
            )
            self.audit(lead_id, None, "INTERACTION_ADDED",
                       {"interaction_id": interaction_id, "channel": channel}, conn)
            return interaction_id

    def add_fact(self, programme_name, category, fact_text, approved=True):
        if not all(str(x or "").strip() for x in (programme_name, category, fact_text)):
            raise ValueError("Programme, category and fact text are required.")
        normalized_programme = str(programme_name).strip()
        normalized_category = str(category).strip()
        normalized_fact = str(fact_text).strip()
        with self.connect() as conn:
            existing = conn.execute(
                """SELECT fact_id FROM programme_facts
                   WHERE lower(trim(programme_name))=?
                     AND lower(trim(fact_category))=?
                     AND lower(trim(fact_text))=?
                     AND is_approved=?""",
                (normalized_programme.lower(), normalized_category.lower(),
                 normalized_fact.lower(), int(approved)),
            ).fetchone()
            if existing:
                fact_id = existing["fact_id"]
                self._warn_duplicate("programme fact", fact_id)
                return fact_id
            fact_id = self._insert_id(
                conn,
                """INSERT INTO programme_facts(programme_name,fact_category,fact_text,is_approved,created_at)
                   VALUES(?,?,?,?,?)""",
                (normalized_programme, normalized_category, normalized_fact, int(approved), now_iso()),
                "fact_id",
            )
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
            return self._read_dataframe(
                conn, "SELECT * FROM leads ORDER BY updated_at DESC"
            )

    def get_lead(self, lead_id):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM leads WHERE lead_id=?", (lead_id,)).fetchone()
            return dict(row) if row else None

    def get_history(self, lead_id):
        with self.connect() as conn:
            return self._read_dataframe(
                conn,
                "SELECT * FROM interactions WHERE lead_id=? ORDER BY occurred_at",
                (lead_id,),
            )

    def get_approved_facts(self, programme_name):
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT fact_id,programme_name,fact_category,fact_text FROM programme_facts
                   WHERE is_approved=1 AND lower(programme_name)=lower(?) ORDER BY fact_id""",
                (programme_name,)).fetchall()
            return [dict(r) for r in rows]

    def get_programme_facts(self):
        with self.connect() as conn:
            return self._read_dataframe(
                conn,
                "SELECT * FROM programme_facts ORDER BY programme_name,fact_id",
            )

    def save_draft(self, lead_id, channel, subject, body, nlp_result, fact_ids,
                   provider, model, prompt_version, response_id=None):
        if channel not in {"Email", "WhatsApp"} or not body.strip():
            raise ValueError("A valid channel and non-empty draft body are required.")
        if channel == "WhatsApp" and str(subject or "").strip():
            raise ValueError("A WhatsApp draft subject must be empty.")
        if channel == "Email" and ("\r" in str(subject or "") or "\n" in str(subject or "")):
            raise ValueError("The email subject cannot contain line breaks.")
        with self.connect() as conn:
            draft_id = self._insert_id(
                conn,
                """INSERT INTO draft_messages
                (lead_id,channel,subject,message_body,nlp_stage,nlp_result_json,fact_ids_json,
                 provider,model,prompt_version,response_id,status,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,'Pending Approval',?)""",
                (lead_id, channel, subject, body, nlp_result.get("stage"),
                 json.dumps(nlp_result), json.dumps(fact_ids), provider, model,
                 prompt_version, response_id, now_iso()),
                "draft_id",
            )
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
            return self._read_dataframe(
                conn,
                """SELECT d.*,l.full_name,l.email,l.source,l.programme_interest
                   FROM draft_messages d
                   JOIN leads l ON d.lead_id=l.lead_id ORDER BY d.created_at DESC""")

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
        if not has_ai_facts:
            for category, fact in [
                ("Audience", "The AI Engineering programme is suitable for learners who want to build practical AI engineering foundations."),
                ("Schedule", "The exact live-session schedule must be confirmed by the programme team."),
                ("Learning support", "Learners receive guided practice and mentor-led doubt sessions."),
                ("Recording", "Recording availability must be confirmed by the programme team before promising access."),
                ("Fees", "The current fee is not present in the approved sample knowledge base; ask the programme team to confirm."),
            ]:
                self.add_fact("AI Engineering", category, fact)

        additional_programmes = {
            "Artificial Intelligence & Machine Learning": "The course covers Artificial Intelligence and Machine Learning.",
            "Data Science & Analytics": "The course covers Data Science and Analytics.",
            "Cybersecurity & Cloud/DevOps": "The course covers Cybersecurity, Cloud and DevOps.",
        }
        for programme, focus_fact in additional_programmes.items():
            with self.connect() as conn:
                has_facts = conn.execute(
                    "SELECT 1 FROM programme_facts WHERE programme_name=? LIMIT 1",
                    (programme,),
                ).fetchone()
            if has_facts:
                continue
            for category, fact in [
                ("Course focus", focus_fact),
                ("Schedule", "The course schedule must be confirmed by the programme team."),
                ("Learning support", "Course support details must be confirmed by the programme team."),
                ("Recording", "Recording availability must be confirmed by the programme team before promising access."),
                ("Fees", "The current course fee must be confirmed by the programme team."),
            ]:
                self.add_fact(programme, category, fact)

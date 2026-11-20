PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS leads (
 lead_id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, email TEXT,
 phone TEXT, programme_interest TEXT NOT NULL, source TEXT DEFAULT 'Sample',
 status TEXT NOT NULL DEFAULT 'New', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS interactions (
 interaction_id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER NOT NULL,
 channel TEXT NOT NULL, direction TEXT NOT NULL DEFAULT 'Inbound', message TEXT NOT NULL,
 occurred_at TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS programme_facts (
 fact_id INTEGER PRIMARY KEY AUTOINCREMENT, programme_name TEXT NOT NULL,
 fact_category TEXT NOT NULL, fact_text TEXT NOT NULL, is_approved INTEGER NOT NULL DEFAULT 1,
 source_note TEXT DEFAULT 'Trainer-approved synthetic sample', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS message_templates (
 template_id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT NOT NULL,
 template_name TEXT NOT NULL, template_text TEXT NOT NULL, version TEXT NOT NULL DEFAULT '1.0',
 is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS draft_messages (
 draft_id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER NOT NULL, channel TEXT NOT NULL,
 subject TEXT, message_body TEXT NOT NULL, nlp_stage TEXT, nlp_result_json TEXT NOT NULL,
 fact_ids_json TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
 prompt_version TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending Approval',
 reviewer_feedback TEXT, created_at TEXT NOT NULL, reviewed_at TEXT, sent_at TEXT,
 FOREIGN KEY(lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS audit_logs (
 audit_id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, draft_id INTEGER,
 action TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(lead_id) REFERENCES leads(lead_id) ON DELETE SET NULL,
 FOREIGN KEY(draft_id) REFERENCES draft_messages(draft_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_interactions_lead_date ON interactions(lead_id,occurred_at);
CREATE INDEX IF NOT EXISTS idx_drafts_status ON draft_messages(status);

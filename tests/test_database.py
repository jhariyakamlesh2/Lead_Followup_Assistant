import sqlite3

import pytest
from lead_assistant.database import Database, _ConnectionAdapter


def test_postgres_connection_adapter_translates_placeholders():
    class FakeConnection:
        def execute(self, query, parameters):
            return query, parameters

    adapter = _ConnectionAdapter(FakeConnection(), is_postgres=True)

    assert adapter.execute(
        "SELECT * FROM leads WHERE lead_id=? AND status=?", (3, "New")
    ) == ("SELECT * FROM leads WHERE lead_id=%s AND status=%s", (3, "New"))


def test_crud_and_review(tmp_path):
    db=Database(tmp_path/"test.db")
    lid=db.add_lead("Test Lead","test@example.test","","Demo Programme")
    db.add_interaction(lid,"WhatsApp","Please share details.")
    assert db.get_lead(lid)["full_name"]=="Test Lead"
    assert len(db.get_history(lid))==1
    fid=db.add_fact("Demo Programme","Schedule","Weekend classes.")
    did=db.save_draft(lid,"WhatsApp","","Hello there.",{"stage":"Interested"},[fid],"Test","mock","1.0","msg_test")
    db.review_draft(did,"Approved","Checked.")
    draft = db.get_drafts().iloc[0]
    assert draft["status"]=="Approved"
    assert draft["response_id"]=="msg_test"


def test_whatsapp_subject_and_email_subject_are_validated(tmp_path):
    db = Database(tmp_path / "test.db")
    lid = db.add_lead("Test Lead", "", "", "Demo Programme")
    fid = db.add_fact("Demo Programme", "Schedule", "Weekend classes.")

    with pytest.raises(ValueError, match="subject must be empty"):
        db.save_draft(lid, "WhatsApp", "Not allowed", "Hello", {"stage": "Interested"}, [fid], "Test", "mock", "1.0")
    with pytest.raises(ValueError, match="line breaks"):
        db.save_draft(lid, "Email", "Subject\nBcc: test@example.test", "Hello", {"stage": "Interested"}, [fid], "Test", "mock", "1.0")
def test_missing_required_lead_fields(tmp_path):
    db=Database(tmp_path/"test.db")
    with pytest.raises(ValueError): db.add_lead("","","","")

def test_invalid_email_is_rejected(tmp_path):
    db=Database(tmp_path/"test.db")
    with pytest.raises(ValueError,match="valid email"):
        db.add_lead("Test Lead","not-an-email","","Demo Programme")


def test_malformed_address_with_extra_separator_is_rejected(tmp_path):
    db = Database(tmp_path / "test.db")
    with pytest.raises(ValueError, match="valid email"):
        db.add_lead("Test Lead", "bad@@example.test", "", "Demo Programme")

def test_empty_interaction_is_rejected(tmp_path):
    db=Database(tmp_path/"test.db")
    lid=db.add_lead("Test Lead","","","Demo Programme")
    with pytest.raises(ValueError,match="cannot be empty"):
        db.add_interaction(lid,"Email","  ")

def test_interaction_for_missing_lead_is_rejected(tmp_path):
    db=Database(tmp_path/"test.db")
    with pytest.raises(LookupError,match="Lead not found"):
        db.add_interaction(999,"Email","Hello")

def test_invalid_interaction_direction_is_rejected(tmp_path):
    db=Database(tmp_path/"test.db")
    lid=db.add_lead("Test Lead","","","Demo Programme")
    with pytest.raises(ValueError,match="Direction"):
        db.add_interaction(lid,"Email","Hello","Sideways")

def test_demo_seed_is_idempotent_and_complete(tmp_path):
    db=Database(tmp_path/"test.db")
    db.seed_sample_data()
    db.seed_sample_data()
    leads=db.get_leads()
    demo=leads[leads.email=="aarav.example@email.test"]
    assert len(demo)==1
    lead_id=int(demo.iloc[0].lead_id)
    assert len(db.get_history(lead_id))==3
    assert len(db.get_approved_facts("Data Analytics Career Programme"))==5


def test_database_connection_closes_after_context_exit(tmp_path):
    db = Database(tmp_path / "test.db")
    with db.connect() as connection:
        connection.execute("SELECT 1")

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")


def test_demo_seed_adds_approved_ai_engineering_facts(tmp_path):
    db = Database(tmp_path / "test.db")
    db.seed_sample_data()

    facts = db.get_approved_facts("AI Engineering")

    assert len(facts) == 5
    assert all(fact["fact_text"].strip() for fact in facts)


def test_demo_seed_adds_new_course_facts_idempotently(tmp_path):
    db = Database(tmp_path / "test.db")
    programmes = [
        "Artificial Intelligence & Machine Learning",
        "Data Science & Analytics",
        "Cybersecurity & Cloud/DevOps",
    ]

    db.seed_sample_data()
    initial_facts = {
        programme: db.get_approved_facts(programme) for programme in programmes
    }
    db.seed_sample_data()

    for programme in programmes:
        facts = db.get_approved_facts(programme)
        assert len(facts) == 5
        assert len(facts) == len(initial_facts[programme])
        assert all(fact["fact_text"].strip() for fact in facts)


def test_duplicate_lead_is_reused_and_warned(tmp_path):
    db = Database(tmp_path / "test.db")
    first_id = db.add_lead("Duplicate Lead", "lead@example.test", "", "Demo Programme")
    db.consume_duplicate_warnings()

    second_id = db.add_lead(" duplicate lead ", "LEAD@example.test", "", "demo programme")

    assert second_id == first_id
    assert len(db.get_leads()) == 1
    assert db.consume_duplicate_warnings()


def test_duplicate_interaction_is_reused_and_warned(tmp_path):
    db = Database(tmp_path / "test.db")
    lead_id = db.add_lead("Test Lead", "", "", "Demo Programme")
    first_id = db.add_interaction(
        lead_id, "Email", "Please share details.", "Inbound", "2026-11-24T10:00:00"
    )
    db.consume_duplicate_warnings()

    second_id = db.add_interaction(
        lead_id, "email", "  please share details.  ", "inbound", "2026-11-24T10:00:00"
    )

    assert second_id == first_id
    assert len(db.get_history(lead_id)) == 1
    assert db.consume_duplicate_warnings()


def test_duplicate_fact_is_reused_and_warned(tmp_path):
    db = Database(tmp_path / "test.db")
    first_id = db.add_fact("Demo Programme", "Schedule", "Weekend classes.")
    db.consume_duplicate_warnings()

    second_id = db.add_fact(" demo programme ", " schedule ", " weekend classes.")

    assert second_id == first_id
    assert len(db.get_approved_facts("Demo Programme")) == 1
    assert db.consume_duplicate_warnings()


def test_existing_duplicate_rows_are_removed_during_initialize(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    db = Database(db_path)
    lead_id = db.add_lead("Cleanup Lead", "", "", "Demo Programme")
    db.consume_duplicate_warnings()

    with db.connect() as conn:
        conn.execute("DROP INDEX IF EXISTS uq_leads_identity")
        conn.execute("DROP INDEX IF EXISTS uq_interactions_identity")
        conn.execute(
            """INSERT INTO leads(full_name,email,phone,programme_interest,source,status,created_at,updated_at)
               VALUES(?,?,?,?,?,'New',?,?)""",
            ("cleanup lead", "", "", "demo programme", "Manual",
             "2026-11-24T10:00:00", "2026-11-24T10:00:00"),
        )
        conn.execute(
            """INSERT INTO interactions(lead_id,channel,direction,message,occurred_at,created_at)
               VALUES(?,?,?,?,?,?)""",
            (lead_id, "Email", "Inbound", "Same message", "2026-11-24T10:00:00",
             "2026-11-24T10:00:00"),
        )
        conn.execute(
            """INSERT INTO interactions(lead_id,channel,direction,message,occurred_at,created_at)
               VALUES(?,?,?,?,?,?)""",
            (lead_id, "email", "inbound", "Same message", "2026-11-24T10:00:00",
             "2026-11-24T10:00:00"),
        )

    reloaded = Database(db_path)
    warnings_list = reloaded.consume_duplicate_warnings()

    assert len(reloaded.get_leads()) == 1
    assert len(reloaded.get_history(lead_id)) == 1
    assert any("Duplicate" in warning for warning in warnings_list)

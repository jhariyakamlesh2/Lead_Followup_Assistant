import sqlite3

import pytest
from lead_assistant.database import Database


def test_crud_and_review(tmp_path):
    db=Database(tmp_path/"test.db")
    lid=db.add_lead("Test Lead","test@example.test","","Demo Programme")
    db.add_interaction(lid,"WhatsApp","Please share details.")
    assert db.get_lead(lid)["full_name"]=="Test Lead"
    assert len(db.get_history(lid))==1
    fid=db.add_fact("Demo Programme","Schedule","Weekend classes.")
    did=db.save_draft(lid,"WhatsApp","","Hello there.",{"stage":"Interested"},[fid],"Test","mock","1.0")
    db.review_draft(did,"Approved","Checked.")
    assert db.get_drafts().iloc[0]["status"]=="Approved"
def test_missing_required_lead_fields(tmp_path):
    db=Database(tmp_path/"test.db")
    with pytest.raises(ValueError): db.add_lead("","","","")

def test_invalid_email_is_rejected(tmp_path):
    db=Database(tmp_path/"test.db")
    with pytest.raises(ValueError,match="valid email"):
        db.add_lead("Test Lead","not-an-email","","Demo Programme")

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

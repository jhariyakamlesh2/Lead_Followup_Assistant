import pytest

from lead_assistant.database import Database
from lead_assistant.workflow import generate_and_save_draft


class FakeGenerator:
    def __init__(self, fact_id):
        self.fact_id = fact_id
        self.received_history = None

    def generate(self, lead, history, nlp_result, facts, channel):
        self.received_history = history
        return {
            "subject": "Following up on your enquiry" if channel == "Email" else "",
            "message": "The programme is designed for beginners.",
            "fact_ids_used": [self.fact_id],
            "claims": [{
                "claim": "The programme is designed for beginners.",
                "fact_ids": [self.fact_id],
            }],
            "review_notes": ["Confirm the current fee with the programme team."],
        }, {"provider": "Anthropic", "model": "claude-sonnet-4-5", "response_id": "test-id"}


def test_end_to_end_saves_grounded_pending_draft_and_nlp(tmp_path):
    db = Database(tmp_path / "test.db")
    lead_id = db.add_lead("Demo Lead", "", "", "Demo Programme")
    db.add_interaction(lead_id, "WhatsApp", "I am a beginner. What are the fees?")
    fact_id = db.add_fact("Demo Programme", "Audience", "The programme is designed for beginners.")
    generator = FakeGenerator(fact_id)

    result = generate_and_save_draft(db, lead_id, "Email", generator)

    assert result["nlp"]["stage"] == "Considering"
    assert result["nlp"]["unanswered_topics"] == ["fees"]
    assert generator.received_history[0]["direction"] == "Inbound"
    draft = db.get_drafts().iloc[0]
    assert draft.status == "Pending Approval"
    assert draft.provider == "Anthropic"
    assert draft.model == "claude-sonnet-4-5"
    assert int(draft.draft_id) == result["draft_id"]


def test_unsupported_channel_fails_before_generation(tmp_path):
    db = Database(tmp_path / "test.db")
    generator = FakeGenerator(1)
    with pytest.raises(ValueError, match="channel"):
        generate_and_save_draft(db, 1, "SMS", generator)
    assert generator.received_history is None


def test_generator_failure_does_not_persist_a_draft(tmp_path):
    db = Database(tmp_path / "test.db")
    lead_id = db.add_lead("Demo Lead", "", "", "Demo Programme")
    db.add_interaction(lead_id, "Email", "What are the fees?")
    db.add_fact("Demo Programme", "Audience", "The programme is designed for beginners.")

    class FailingGenerator:
        def generate(self, *_args):
            raise RuntimeError("simulated provider failure")

    with pytest.raises(RuntimeError, match="simulated provider failure"):
        generate_and_save_draft(db, lead_id, "Email", FailingGenerator())

    assert db.get_drafts().empty


def test_missing_approved_facts_blocks_draft_before_generation(tmp_path):
    db = Database(tmp_path / "test.db")
    lead_id = db.add_lead("Demo Lead", "", "", "Unknown Programme")
    db.add_interaction(lead_id, "Email", "Tell me about this programme.")
    generator = FakeGenerator(1)

    with pytest.raises(ValueError, match="No approved programme facts"):
        generate_and_save_draft(db, lead_id, "Email", generator)

    assert generator.received_history is None
    assert db.get_drafts().empty

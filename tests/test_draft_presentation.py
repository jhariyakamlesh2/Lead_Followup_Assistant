from pathlib import Path
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest


class DraftDatabase:
    def __init__(self, _db_path):
        pass

    def seed_sample_data(self):
        pass

    def get_leads(self):
        return pd.DataFrame(
            [{
                "lead_id": 1,
                "full_name": "Test Lead",
                "programme_interest": "Data Analytics",
                "status": "New",
            }]
        )

    def get_drafts(self):
        return pd.DataFrame(columns=["status"])

    def get_history(self, _lead_id):
        return pd.DataFrame(
            columns=["channel", "direction", "message", "occurred_at"]
        )


def test_generated_draft_presents_empty_metadata_clearly():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    with patch("lead_assistant.database.Database", DraftDatabase):
        st.cache_resource.clear()
        app = AppTest.from_file(str(app_path))
        app.session_state["authenticated"] = True
        app.session_state["latest"] = {
            "draft": {
                "subject": "Following up",
                "message": "Thanks for your enquiry.",
                "fact_ids_used": [],
                "review_notes": [],
            },
            "metadata": {
                "provider": "Anthropic",
                "model": "claude-test-model",
            },
        }
        app.session_state["latest_context"] = (1, "Email", ())
        app.run()
        app.radio[0].set_value("Generate Draft").run()

    assert not app.exception
    assert app.subheader[-1].value == "Generated draft"
    assert app.text_area[-1].label == "Message for review"
    assert app.text_area[-1].value == "Thanks for your enquiry."
    captions = {caption.value for caption in app.caption}
    assert "No approved programme facts were cited." in captions
    assert "No additional review notes." in captions


def test_previous_draft_is_cleared_when_channel_changes():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    with patch("lead_assistant.database.Database", DraftDatabase):
        st.cache_resource.clear()
        app = AppTest.from_file(str(app_path))
        app.session_state["authenticated"] = True
        app.session_state["latest"] = {
            "draft": {
                "subject": "Following up",
                "message": "Thanks for your enquiry.",
                "fact_ids_used": [],
                "review_notes": [],
            },
            "metadata": {
                "provider": "Anthropic",
                "model": "claude-test-model",
            },
        }
        app.session_state["latest_context"] = (1, "Email", ())
        app.run()
        app.radio[0].set_value("Generate Draft").run()
        next(radio for radio in app.radio if radio.label == "Draft channel").set_value(
            "WhatsApp"
        ).run()

    assert not app.exception
    assert "latest" not in app.session_state
    assert all(heading.value != "Generated draft" for heading in app.subheader)

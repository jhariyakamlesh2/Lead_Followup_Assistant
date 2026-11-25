from pathlib import Path
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest


class ConversationDatabase:
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
            [{
                "channel": "Call",
                "direction": "Inbound",
                "message": "test call",
                "occurred_at": "2026-01-01",
            }]
        )

    def get_approved_facts(self, _programme):
        return []


def test_conversation_insights_show_readable_signals():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    with patch("lead_assistant.database.Database", ConversationDatabase):
        st.cache_resource.clear()
        app = AppTest.from_file(str(app_path))
        app.session_state["authenticated"] = True
        app.run()
        app.radio[0].set_value("Generate Draft").run()

    assert not app.exception
    assert not any(
        "Using local SQLite storage" in warning.value for warning in app.warning
    )
    assert app.subheader[-1].value == "Conversation insights"
    assert next(metric.value for metric in app.metric if metric.label == "Stage") == "New Enquiry"
    captions = {caption.value for caption in app.caption}
    assert {
        "No preferences detected yet.",
        "No follow-up topics detected yet.",
        "2 words analyzed",
        "No direct questions detected.",
    } <= captions
    assert app.expander[-1].label == "Questions and topic details"
    assert not app.get("json")

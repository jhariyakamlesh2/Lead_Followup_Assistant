from pathlib import Path
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest


class EmptyDatabase:
    def __init__(self, _db_path):
        pass

    def seed_sample_data(self):
        pass

    def get_leads(self):
        return pd.DataFrame(
            columns=["lead_id", "full_name", "programme_interest", "status"]
        )

    def get_drafts(self):
        return pd.DataFrame(columns=["status"])


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_login_is_required_before_dashboard():
    with patch("lead_assistant.database.Database", EmptyDatabase):
        st.cache_resource.clear()
        app = AppTest.from_file(str(APP_PATH)).run()

        assert not app.exception
        assert app.session_state["authenticated"] is False
        assert app.text_input[0].label == "User ID"
        assert app.text_input[1].label == "Password"
        assert not app.metric


def test_invalid_login_stays_on_login_page():
    with patch("lead_assistant.database.Database", EmptyDatabase):
        st.cache_resource.clear()
        app = AppTest.from_file(str(APP_PATH)).run()
        app.text_input[0].set_value("admin")
        app.text_input[1].set_value("incorrect")
        app.form_submit_button[0].click().run()

        assert not app.exception
        assert app.session_state["authenticated"] is False
        assert app.error[0].value == "Invalid user ID or password."
        assert not app.metric


def test_demo_credentials_open_dashboard():
    with patch("lead_assistant.database.Database", EmptyDatabase):
        st.cache_resource.clear()
        app = AppTest.from_file(str(APP_PATH)).run()
        app.text_input[0].set_value("admin")
        app.text_input[1].set_value("admin@123")
        app.form_submit_button[0].click().run()

        assert not app.exception
        assert app.session_state["authenticated"] is True
        assert len(app.metric) == 4
        assert any(
            heading.value == "How each draft is prepared"
            for heading in app.subheader
        )
        assert {
            f"STEP {number:02}" for number in range(1, 8)
        } <= {caption.value for caption in app.caption}

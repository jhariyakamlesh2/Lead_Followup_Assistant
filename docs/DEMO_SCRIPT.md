# Live demo walkthrough (3–5 minutes)

## Before recording

1. Install dependencies and initialize the sample database as described in the README.
2. Add your own `ANTHROPIC_API_KEY` to `.env`; do not show the key on screen.
3. Confirm that the account can call the configured `ANTHROPIC_MODEL` and has API credits. If not, demonstrate the missing-key failure and explain that an actual provider call requires valid credentials.
4. Start `streamlit run app.py` and use the synthetic sample lead only.

## Normal scenario

1. Show the dashboard and state that all records are synthetic.
2. Open **Generate Draft**, select Aarav Sharma and inspect the conversation history.
3. Explain that NLP identifies a considering-stage enquiry, weekend/beginner preferences, and open fee/recording/placement topics.
4. Choose Email or WhatsApp and generate. This step makes a real Anthropic Messages API call when credentials and access are valid.
5. Show the draft, model/provider metadata, fact references and review notes. Point out that the fee is not invented.
6. Open **Review Drafts**, record a review decision, and verify status/feedback in SQLite.
7. Confirm there is no send button or production CRM connector.

## Edge/failure-recovery scenario

1. Close the app. In the local `.env`, temporarily clear `ANTHROPIC_API_KEY` (never display or record its previous value).
2. Restart and try to generate a draft. The app should show the missing-key configuration error; no API request or draft insert should occur.
3. Restore the key privately, restart and retry if live access is available.
4. If the API returns a timeout, authentication, rate-limit or model-access error, show the error and confirm no new draft was saved.

## Suggested narration

“LeadPilot uses synthetic lead history, a small explainable NLP pipeline and approved programme facts to prepare an email or WhatsApp draft. Claude is called through Anthropic's API, and the response is checked before it is stored with its model metadata. A person reviews it; the application never sends a message or writes to a production CRM.”

No recording is included in this source package; capture this walkthrough locally for the final submission if required.

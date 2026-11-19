# Anthropic prompt pack

The canonical prompts live in `lead_assistant/prompts.py`; `PROMPT_VERSION` is stored with every generated draft. Current version: **1.1**.

## Prompt design

- **Role boundary:** the model drafts only and never sends/schedules a message.
- **Context boundary:** lead/profile/history/NLP are untrusted data, not instructions; programme claims must come from supplied approved facts.
- **Task-specific style:** Email gets a subject and professional structure; WhatsApp gets a short conversational body and empty subject.
- **Grounding:** unsupported questions are deferred to the programme team; no invented fees, outcomes, dates, guarantees or policies.
- **Structured response:** a JSON object contains `subject`, `message`, `fact_ids_used`, claim-level `claims`, and `review_notes`.
- **Validation:** the app rejects malformed structures, empty messages, unknown/unapproved fact IDs, uncited factual claims and citations not listed in `fact_ids_used`.

## Example

If a lead asks for a fee but the supplied facts contain no approved current fee, do not provide a price. State that the team can confirm it and add a human review note. A fact-ID list does not prove semantic entailment; the reviewer remains responsible for checking the draft.

## Expected JSON contract

```json
{
  "subject": "Following up on your enquiry",
  "message": "Hello ...",
  "fact_ids_used": [1],
  "claims": [
    {"claim": "The programme is designed for beginners.", "fact_ids": [1]}
  ],
  "review_notes": ["Please confirm the current fee with the programme team."]
}
```

WhatsApp uses an empty `subject`. See `sample_data/expected_draft.json` for a complete illustrative output; it is not represented as a live Claude response.

## Version history

- **1.0** — Initial channel-aware prompt, explicit untrusted-data boundary, approved-fact grounding and strict JSON output.
- **1.1** — Added guidance against inferring contact preferences or callback requests from ambiguous messages, and against generic review notes.


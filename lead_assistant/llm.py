import json
from .prompts import SYSTEM_PROMPT, TASK_PROMPT

DRAFT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "message": {"type": "string"},
        "fact_ids_used": {"type": "array", "items": {"type": "integer"}},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "fact_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["claim", "fact_ids"],
                "additionalProperties": False,
            },
        },
        "review_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["subject", "message", "fact_ids_used", "claims", "review_notes"],
    "additionalProperties": False,
}

class LLMError(RuntimeError):
    pass

class AnthropicDraftGenerator:
    def __init__(self, api_key, model="claude-sonnet-4-5", timeout=30):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is missing. Add it to your .env file.")
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError("Anthropic SDK is not installed. Run: pip install -r requirements.txt") from exc
        self.client = Anthropic(api_key=api_key, timeout=timeout, max_retries=1)
        self.model, self.provider = model, "Anthropic"

    def generate(self, lead, history, nlp_result, facts, channel):
        prompt = TASK_PROMPT.format(
            lead_json=json.dumps(lead, ensure_ascii=False),
            history_json=json.dumps(history, ensure_ascii=False),
            nlp_json=json.dumps(nlp_result, ensure_ascii=False),
            facts_json=json.dumps(facts, ensure_ascii=False), channel=channel)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1200,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": DRAFT_RESPONSE_SCHEMA,
                    }
                },
            )
            text = "\n".join(
                block.text for block in response.content
                if getattr(block, "type", None) == "text"
            )
            stop_reason = getattr(response, "stop_reason", None)
            if stop_reason == "max_tokens":
                raise ValueError(
                    "Anthropic reached the response token limit before completing the draft. "
                    "Increase max_tokens or reduce the prompt size."
                )
            if not text.strip():
                content_types = [
                    getattr(block, "type", "unknown") for block in response.content
                ]
                raise ValueError(
                    "Anthropic returned no text content for the draft "
                    f"(stop_reason={stop_reason!r}, content_types={content_types!r})."
                )
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Anthropic returned text that was not valid JSON "
                    f"(stop_reason={stop_reason!r}, line={exc.lineno}, column={exc.colno})."
                ) from exc
            result = validate_llm_result(parsed, facts)
            return result, {
                "provider": self.provider,
                "model": response.model,
                "response_id": response.id,
            }
        except Exception as exc:
            raise LLMError(f"Anthropic draft generation failed: {exc}") from exc

def validate_llm_result(result, facts):
    required = {"subject","message","fact_ids_used","claims","review_notes"}
    if not isinstance(result, dict) or not required.issubset(result):
        raise ValueError("LLM response is missing required JSON fields.")
    if not isinstance(result["subject"], str):
        raise ValueError("LLM subject must be a string.")
    if not isinstance(result["message"], str) or not result["message"].strip():
        raise ValueError("LLM returned an empty message.")
    valid = {int(f["fact_id"]) for f in facts}
    if not isinstance(result["fact_ids_used"], list) or any(type(x) is not int or x not in valid for x in result["fact_ids_used"]):
        raise ValueError("LLM referenced an unknown or unapproved fact ID.")
    if not isinstance(result["claims"], list) or not isinstance(result["review_notes"], list):
        raise ValueError("Malformed claims or review notes.")
    if any(not isinstance(note, str) for note in result["review_notes"]):
        raise ValueError("Review notes must be strings.")
    cited_ids = set(result["fact_ids_used"])
    for claim in result["claims"]:
        if (
            not isinstance(claim, dict)
            or not isinstance(claim.get("claim"), str)
            or not isinstance(claim.get("fact_ids"), list)
        ):
            raise ValueError("Malformed factual claim.")
        if any(
            type(x) is not int or x not in valid or x not in cited_ids
            for x in claim["fact_ids"]
        ):
            raise ValueError("A claim references an unknown fact ID.")
        if claim["claim"].strip() and not claim["fact_ids"]:
            raise ValueError("Every factual claim must cite an approved fact ID.")
    return result

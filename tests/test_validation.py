import json
import pytest
from types import SimpleNamespace

from lead_assistant.llm import AnthropicDraftGenerator, LLMError, validate_llm_result
FACTS=[{"fact_id":1,"fact_text":"Weekend sessions are available."}]
def sample():
    return {"subject":"Follow-up","message":"Weekend sessions are available.",
      "fact_ids_used":[1],"claims":[{"claim":"Weekend sessions are available.","fact_ids":[1]}],
      "review_notes":[]}
def test_valid(): assert validate_llm_result(sample(),FACTS)["fact_ids_used"]==[1]
def test_unknown_fact():
    x=sample(); x["fact_ids_used"]=[999]
    with pytest.raises(ValueError): validate_llm_result(x,FACTS)
def test_empty_message():
    x=sample(); x["message"]=" "
    with pytest.raises(ValueError): validate_llm_result(x,FACTS)
def test_uncited_claim():
    x=sample(); x["claims"]=[{"claim":"Guaranteed job","fact_ids":[]}]
    with pytest.raises(ValueError): validate_llm_result(x,FACTS)

def test_claim_must_be_in_used_fact_ids():
    x=sample(); x["fact_ids_used"]=[]
    with pytest.raises(ValueError): validate_llm_result(x,FACTS)

def test_malformed_review_notes_are_rejected():
    x=sample(); x["review_notes"]=[{"note":"Check this"}]
    with pytest.raises(ValueError): validate_llm_result(x,FACTS)

def test_missing_anthropic_key_fails_before_network_call():
    with pytest.raises(ValueError,match="ANTHROPIC_API_KEY"):
        AnthropicDraftGenerator("")

def test_anthropic_response_is_parsed_and_metadata_is_recorded():
    response=SimpleNamespace(
        content=[SimpleNamespace(type="text",text=json.dumps(sample()))],
        model="claude-test-model",
        id="msg_test",
    )
    calls={}
    def create(**kwargs):
        calls.update(kwargs)
        return response
    generator=object.__new__(AnthropicDraftGenerator)
    generator.client=SimpleNamespace(messages=SimpleNamespace(create=create))
    generator.model="configured-model"
    generator.provider="Anthropic"

    result,metadata=generator.generate({},[],{},FACTS,"Email")

    assert result["fact_ids_used"]==[1]
    assert metadata=={
        "provider":"Anthropic",
        "model":"claude-test-model",
        "response_id":"msg_test",
    }
    assert calls["model"]=="configured-model"
    assert calls["max_tokens"]==1200
    assert calls["messages"][0]["role"]=="user"
    assert calls["output_config"]["format"]["type"]=="json_schema"
    assert set(calls["output_config"]["format"]["schema"]["required"])=={
        "subject","message","fact_ids_used","claims","review_notes"
    }

def test_anthropic_api_failure_is_reported():
    def fail(**kwargs):
        raise RuntimeError("simulated network failure")
    generator=object.__new__(AnthropicDraftGenerator)
    generator.client=SimpleNamespace(messages=SimpleNamespace(create=fail))
    generator.model="configured-model"
    generator.provider="Anthropic"
    with pytest.raises(LLMError,match="simulated network failure"):
        generator.generate({},[],{},FACTS,"Email")

def test_anthropic_empty_response_reports_missing_text():
    response=SimpleNamespace(content=[],model="claude-test-model",id="msg_empty",stop_reason="end_turn")
    generator=object.__new__(AnthropicDraftGenerator)
    generator.client=SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
    generator.model="configured-model"
    generator.provider="Anthropic"

    with pytest.raises(LLMError,match="returned no text content.*end_turn"):
        generator.generate({},[],{},FACTS,"Email")

def test_anthropic_token_limit_reports_truncated_response():
    response=SimpleNamespace(
        content=[SimpleNamespace(type="text",text='{"message":')],
        model="claude-test-model",
        id="msg_truncated",
        stop_reason="max_tokens",
    )
    generator=object.__new__(AnthropicDraftGenerator)
    generator.client=SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
    generator.model="configured-model"
    generator.provider="Anthropic"

    with pytest.raises(LLMError,match="response token limit"):
        generator.generate({},[],{},FACTS,"Email")

def test_anthropic_invalid_json_reports_parse_location():
    response=SimpleNamespace(
        content=[SimpleNamespace(type="text",text="not JSON")],
        model="claude-test-model",
        id="msg_invalid",
        stop_reason="end_turn",
    )
    generator=object.__new__(AnthropicDraftGenerator)
    generator.client=SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
    generator.model="configured-model"
    generator.provider="Anthropic"

    with pytest.raises(LLMError,match="not valid JSON.*line=1, column=1"):
        generator.generate({},[],{},FACTS,"Email")

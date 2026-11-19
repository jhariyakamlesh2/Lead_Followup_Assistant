from lead_assistant.nlp import analyze_conversation, tokenize

def test_clean_tokenize():
    assert "hello" in tokenize("Hello!!! https://example.com")

def test_tokenizer_strips_urls_and_punctuation():
    assert tokenize("Fees? See https://example.com") == ["fees", "see"]

def test_preferences_and_stage():
    r=analyze_conversation(["I am interested. I prefer weekend sessions as I am a beginner."])
    assert r["stage"]=="Interested"
    assert "weekend_sessions" in r["preferences"]
    assert "beginner_friendly" in r["preferences"]
def test_question_topics():
    r=analyze_conversation(["What are the fees? Are classes recorded?"])
    assert "fees" in r["unanswered_topics"] and "recordings" in r["unanswered_topics"]
def test_empty_input():
    r=analyze_conversation([])
    assert r["stage"]=="New Enquiry" and r["token_count"]==0

def test_outbound_history_marks_only_referenced_question_topic_as_addressed():
    r=analyze_conversation([
        {"direction":"Inbound","message":"What are the fees? Are classes recorded?"},
        {"direction":"Outbound","message":"The current fee is not confirmed yet."},
    ])
    assert r["answered_topics"]==["fees"]
    assert r["unanswered_topics"]==["recordings"]

def test_plain_string_messages_are_treated_as_inbound():
    r=analyze_conversation(["Please share details about weekend sessions."])
    assert r["unanswered_topics"]==["schedule"]

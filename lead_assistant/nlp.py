import re
from collections import Counter

QUESTION_PATTERNS = {
 "fees": [r"\bfee(s)?\b", r"\bcost\b", r"\bprice\b", r"\bpayment\b"],
 "schedule": [r"\btime\b", r"\bschedule\b", r"\bweekend(s)?\b", r"\bweekday(s)?\b"],
 "recordings": [r"\brecord(ed|ing|ings)?\b", r"\breplay(s)?\b"],
 "placement": [r"\bplacement\b", r"\bjob support\b", r"\bcareer support\b"],
 "eligibility": [r"\beligib(le|ility)\b", r"\bbeginner\b", r"\bexperience\b"]
}
PREFERENCE_PATTERNS = {
 "weekend_sessions": [r"\bweekends?\b", r"\bsaturday\b", r"\bsunday\b"],
 "beginner_friendly": [r"\bbeginner\b", r"\bno experience\b", r"\bnew to\b"],
 "online_learning": [r"\bonline\b", r"\bremote\b", r"\bvirtual\b"],
 "career_change": [r"\bcareer change\b", r"\bswitch careers\b", r"\bchange my career\b"],
 "ai_engineering": [r"\bai engineering\b", r"\bartificial intelligence\b", r"\bmachine learning\b", r"\blearn ai\b"]
}
REQUEST_PATTERN = re.compile(
    r"\b(please share|share details|tell me|need to know|still need|"
    r"let me know|could you|can you|is there|do you|what|when|where|how|which)\b",
    re.I,
)

def clean_text(text):
    text = (text or "").lower()
    text = re.sub(r"https?://\S+|\S+@\S+", " ", text)
    text = re.sub(r"[^a-z0-9? ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def tokenize(text):
    return re.findall(r"[a-z0-9]+", clean_text(text))

def _matches(text, patterns):
    return [label for label, regexes in patterns.items()
            if any(re.search(p, text, re.I) for p in regexes)]

def analyze_conversation(messages):
    inbound, outbound = [], []
    for item in messages:
        if isinstance(item, dict):
            message = str(item.get("message", "") or "").strip()
            direction = str(item.get("direction", "Inbound")).strip().lower()
            target = outbound if direction == "outbound" else inbound
        else:
            message = str(item or "").strip()
            target = inbound
        if message:
            target.append(message)

    inbound_text = " ".join(inbound)
    outbound_text = " ".join(outbound)
    text, tokens = clean_text(inbound_text), tokenize(inbound_text)
    preferences = _matches(text, PREFERENCE_PATTERNS)
    topics = _matches(text, QUESTION_PATTERNS)
    questions = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", inbound_text)
        if "?" in sentence or REQUEST_PATTERN.search(sentence)
    ]
    requested_topics = _matches(clean_text(" ".join(questions)), QUESTION_PATTERNS)
    answered_topics = _matches(clean_text(outbound_text), QUESTION_PATTERNS)
    unanswered_topics = sorted(set(requested_topics) - set(answered_topics))
    if any(x in text for x in ["ready to enroll", "register now", "sign me up", "enroll me"]):
        stage = "Ready to Enroll"
    elif requested_topics or any(x in text for x in ["fee", "fees", "cost", "payment", "placement", "recording"]):
        stage = "Considering"
    elif any(
        x in text
        for x in [
            "interested",
            "want to learn",
            "wants to learn",
            "looking to learn",
            "tell me",
            "more information",
            "details",
        ]
    ):
        stage = "Interested"
    else:
        stage = "New Enquiry"
    return {
        "stage": stage,
        "preferences": sorted(set(preferences)),
        "mentioned_topics": sorted(set(topics)),
        "answered_topics": sorted(set(answered_topics)),
        "unanswered_topics": unanswered_topics,
        "questions_detected": questions,
        "keywords": [w for w, _ in Counter(tokens).most_common(12)],
        "token_count": len(tokens)
    }

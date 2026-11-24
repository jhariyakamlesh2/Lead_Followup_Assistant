from .nlp import analyze_conversation
from .prompts import PROMPT_VERSION

def generate_and_save_draft(db, lead_id, channel, generator):
    if channel not in {"Email", "WhatsApp"}:
        raise ValueError("Draft channel must be Email or WhatsApp.")
    lead = db.get_lead(lead_id)
    if not lead:
        raise LookupError("Lead not found.")
    history = db.get_history(lead_id).to_dict(orient="records")
    nlp = analyze_conversation(history)
    facts = db.get_approved_facts(lead["programme_interest"])
    if not facts:
        raise ValueError("No approved programme facts found.")
    result, metadata = generator.generate(lead, history, nlp, facts, channel)
    allowed = {f["fact_id"] for f in facts}
    if not set(result["fact_ids_used"]).issubset(allowed):
        raise ValueError("Unsupported fact reference.")
    draft_id = db.save_draft(lead_id, channel, result.get("subject",""),
        result["message"], nlp, result["fact_ids_used"], metadata["provider"],
        metadata["model"], PROMPT_VERSION, metadata.get("response_id"))
    return {"draft_id":draft_id,"nlp":nlp,"draft":result,"metadata":metadata}

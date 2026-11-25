from pathlib import Path
import smtplib

import pandas as pd
import streamlit as st
from lead_assistant.database import Database
from lead_assistant.config import settings
from lead_assistant.email_sender import EmailSender, validate_recipient_address
from lead_assistant.llm import AnthropicDraftGenerator
from lead_assistant.workflow import generate_and_save_draft
from lead_assistant.nlp import analyze_conversation

st.set_page_config(page_title="LeadPilot AI", page_icon="✉️", layout="wide")
st.logo(
    str(Path(__file__).resolve().parent / "assets" / "leadpilot-logo.svg"),
    size="large",
    icon_image=str(Path(__file__).resolve().parent / "assets" / "leadpilot-mark.svg"),
)

DEMO_USER_ID = "admin"
DEMO_PASSWORD = "admin@123"

st.session_state.setdefault("authenticated", False)
if not st.session_state["authenticated"]:
    with st.container(horizontal=True, horizontal_alignment="center"):
        with st.container(width=560, border=True):
            st.title(":rainbow[LeadPilot AI]", icon=":material/mark_email_unread:")
            st.caption("Sign in to manage lead follow-ups and draft reviews.")
            with st.form("login"):
                user_id = st.text_input("User ID", value="admin")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in", type="primary")
            st.caption("Demo access only. Do not use these credentials for sensitive data.")
            if submitted:
                if user_id == DEMO_USER_ID and password == DEMO_PASSWORD:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Invalid user ID or password.")
    st.stop()


@st.cache_resource
def get_db():
    database_url = getattr(settings, "database_url", "")
    db = Database(database_url or settings.database_path)
    db.seed_sample_data()
    return db


db = get_db()
PROGRAMME_OPTIONS = [
    "Data Analytics Career Programme",
    "Artificial Intelligence & Machine Learning",
    "Data Science & Analytics",
    "Cybersecurity & Cloud/DevOps",
]
if hasattr(db, "consume_duplicate_warnings"):
    for duplicate_warning in db.consume_duplicate_warnings():
        st.warning(duplicate_warning)
email_sender = EmailSender(settings)
st.title(":rainbow[LeadPilot AI]", icon=":material/mark_email_unread:")
tagline_animation = ""
if not st.session_state.get("leadpilot_tagline_animation_played", False):
    tagline_animation = " leadpilot-tagline--enter"
    st.session_state["leadpilot_tagline_animation_played"] = True
st.html(
    f"""
    <style>
    .leadpilot-tagline {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.65rem;
        margin: 0.35rem 0 1.25rem;
    }}

    .leadpilot-tagline__phrase {{
        position: relative;
        isolation: isolate;
        display: inline-flex;
        align-items: center;
        gap: 0.55rem;
        max-width: 100%;
        padding: 0.55rem 0.95rem 0.55rem 0.62rem;
        border: 1px solid #CFDBFF;
        border-radius: 999px;
        background: linear-gradient(135deg, #FFFFFF 8%, #EDF3FF 100%);
        box-shadow: 0 7px 18px rgba(37, 75, 145, 0.1);
        color: #172A49;
        font-size: 0.94rem;
        font-weight: 600;
        line-height: 1.25;
        transition: transform 180ms ease, box-shadow 180ms ease;
    }}

    .leadpilot-tagline__phrase:hover {{
        transform: translateY(-2px);
        box-shadow: 0 11px 24px rgba(37, 75, 145, 0.16);
    }}

    .leadpilot-tagline__icon {{
        display: inline-grid;
        width: 1.85rem;
        height: 1.85rem;
        flex: none;
        place-items: center;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.9);
        box-shadow: inset 0 0 0 1px rgba(37, 75, 145, 0.1);
        color: #315CEB;
        font-size: 1.05rem;
        font-weight: 700;
    }}

    .leadpilot-tagline__insights {{
        border-color: #DED4FF;
        background: linear-gradient(135deg, #FFFFFF 8%, #F4F0FF 100%);
        box-shadow: 0 7px 18px rgba(92, 63, 168, 0.1);
    }}

    .leadpilot-tagline__insights .leadpilot-tagline__icon {{
        color: #7450D8;
        box-shadow: inset 0 0 0 1px rgba(116, 80, 216, 0.16);
    }}

    .leadpilot-tagline__approved {{
        border-color: #C6E9DD;
        background: linear-gradient(135deg, #FFFFFF 8%, #EAF8F2 100%);
        box-shadow: 0 7px 18px rgba(31, 119, 94, 0.1);
    }}

    .leadpilot-tagline__approved .leadpilot-tagline__icon {{
        color: #16866A;
        box-shadow: inset 0 0 0 1px rgba(22, 134, 106, 0.16);
    }}

    .leadpilot-tagline--enter .leadpilot-tagline__intelligent {{
        animation: leadpilot-feature-glide 760ms cubic-bezier(0.2, 0.8, 0.2, 1) 80ms both;
    }}

    .leadpilot-tagline--enter .leadpilot-tagline__insights {{
        animation: leadpilot-feature-pop 760ms cubic-bezier(0.2, 0.8, 0.2, 1) 260ms both;
    }}

    .leadpilot-tagline--enter .leadpilot-tagline__approved {{
        animation: leadpilot-feature-confirm 800ms cubic-bezier(0.2, 0.8, 0.2, 1) 440ms both;
    }}

    .leadpilot-tagline--enter .leadpilot-tagline__approved .leadpilot-tagline__icon {{
        animation: leadpilot-check-pop 650ms ease-out 900ms both;
    }}

    @keyframes leadpilot-feature-glide {{
        0% {{ opacity: 0; filter: blur(5px); transform: translate(-16px, 9px) scale(0.95); }}
        70% {{ opacity: 1; filter: blur(0); transform: translate(0, -2px) scale(1.03); }}
        100% {{ opacity: 1; filter: blur(0); transform: translate(0) scale(1); }}
    }}

    @keyframes leadpilot-feature-pop {{
        0% {{ opacity: 0; filter: blur(4px); transform: translateY(12px) scale(0.82) rotate(-4deg); }}
        68% {{ opacity: 1; filter: blur(0); transform: translateY(-2px) scale(1.06) rotate(1deg); }}
        100% {{ opacity: 1; filter: blur(0); transform: translateY(0) scale(1) rotate(0); }}
    }}

    @keyframes leadpilot-feature-confirm {{
        0% {{ opacity: 0; transform: translateY(14px) scale(0.92); }}
        72% {{ opacity: 1; transform: translateY(-2px) scale(1.03); }}
        100% {{ opacity: 1; transform: translateY(0) scale(1); }}
    }}

    @keyframes leadpilot-check-pop {{
        0% {{ transform: scale(0.7) rotate(-30deg); }}
        70% {{ transform: scale(1.14) rotate(8deg); }}
        100% {{ transform: scale(1) rotate(0); }}
    }}

    @media (max-width: 640px) {{
        .leadpilot-tagline {{ gap: 0.5rem; }}
        .leadpilot-tagline__phrase {{ padding: 0.5rem 0.75rem 0.5rem 0.52rem; font-size: 0.87rem; }}
        .leadpilot-tagline__icon {{ width: 1.75rem; height: 1.75rem; }}
    }}

    @media (prefers-reduced-motion: reduce) {{
        .leadpilot-tagline__phrase,
        .leadpilot-tagline__phrase:hover {{
            transition: none;
            transform: none;
        }}

        .leadpilot-tagline--enter .leadpilot-tagline__phrase,
        .leadpilot-tagline--enter .leadpilot-tagline__icon {{
            animation: none;
        }}
    }}
    </style>
    <p class="leadpilot-tagline{tagline_animation}">
        <span class="leadpilot-tagline__phrase leadpilot-tagline__intelligent">
            <span class="leadpilot-tagline__icon" aria-hidden="true">✦</span>
            Intelligent lead follow-ups
        </span>
        <span class="leadpilot-tagline__phrase leadpilot-tagline__insights">
            <span class="leadpilot-tagline__icon" aria-hidden="true">∿</span>
            NLP insights
        </span>
        <span class="leadpilot-tagline__phrase leadpilot-tagline__approved">
            <span class="leadpilot-tagline__icon" aria-hidden="true">✓</span>
            Human-approved messaging
        </span>
    </p>
    """
)
leads, drafts = db.get_leads(), db.get_drafts()
a,b,c,d = st.columns(4)
a.metric("Total leads",len(leads))
b.metric("History",sum(len(db.get_history(int(x))) for x in leads["lead_id"]) if not leads.empty else 0)
c.metric("Drafts",len(drafts))
d.metric("Queue",int((drafts.status=="Pending Approval").sum()) if not drafts.empty else 0)
with st.sidebar:
    st.markdown("### :material/space_dashboard: Workspace")
    st.caption("Your lead follow-up workspace")
    st.html(
        """
        <style>
        .st-key-workspace-nav [role="radiogroup"] {
            display: flex;
            flex-direction: column;
            gap: 0.3rem;
        }

        .st-key-workspace-nav label:has(input[type="radio"]) {
            display: flex;
            align-items: center;
            width: 100%;
            padding: 0.52rem 0.65rem;
            border: 1px solid transparent;
            border-radius: 0.8rem;
            background: transparent;
            transition: background 160ms ease, border-color 160ms ease, transform 160ms ease;
        }

        .st-key-workspace-nav label:has(input[type="radio"]):hover {
            transform: translateX(2px);
            border-color: rgba(174, 197, 255, 0.26);
            background: rgba(130, 166, 255, 0.1);
        }

        .st-key-workspace-nav label:has(input[type="radio"]:checked) {
            border-color: rgba(143, 171, 255, 0.55);
            background: linear-gradient(110deg, rgba(54, 92, 219, 0.38), rgba(54, 92, 219, 0.12));
            box-shadow: inset 3px 0 0 #83A7FF, 0 6px 16px rgba(0, 0, 0, 0.13);
        }

        .st-key-workspace-nav input[type="radio"] {
            accent-color: #AFC2FF;
        }

        @media (prefers-reduced-motion: reduce) {
            .st-key-workspace-nav label:has(input[type="radio"]) {
                transition: none;
            }

            .st-key-workspace-nav label:has(input[type="radio"]):hover {
                transform: none;
            }
        }
        </style>
        """
    )
    page = st.radio(
        "Workspace",
        ["Dashboard", "Lead Management", "Generate Draft", "Review Drafts", "Programme Facts"],
        label_visibility="collapsed",
        key="workspace-nav",
    )
    with st.container(border=True):
        st.badge("Demo mode", icon=":material/science:", color="blue")
        st.caption("Demo addresses are blocked; approved emails can be sent after review.")
        if st.button("Sign out", icon=":material/logout:", width="stretch"):
            st.session_state["authenticated"] = False
            st.rerun()
if page=="Dashboard":
    st.subheader("Workspace overview")
    x,y=st.columns([1.2,1])
    x.markdown("#### Recent leads")
    x.dataframe(leads[["lead_id","full_name","programme_interest","status"]] if not leads.empty else leads,width="stretch",hide_index=True)
    y.markdown("#### Draft approval status")
    if not drafts.empty:
        y.bar_chart(
            drafts.status.value_counts(),
            alt="Draft count by approval status",
        )
    else:
        y.info("No drafts yet.")
    st.subheader("How each draft is prepared", icon=":material/account_tree:")
    st.caption("AI drafts are saved for human review; nothing is sent automatically.")
    workflow_steps = [
        ("history", "Lead history"),
        ("psychology", "NLP insights"),
        ("verified", "Approved facts"),
        ("smart_toy", "Anthropic Claude"),
        ("fact_check", "Validation"),
        ("database", "SQLite"),
        ("rate_review", "Human review"),
    ]
    with st.container(horizontal=True, gap="small"):
        for step_number, (icon, label) in enumerate(workflow_steps, start=1):
            with st.container(width=160, border=True):
                st.caption(f"STEP {step_number:02}")
                st.markdown(f":material/{icon}:")
                st.markdown(f"**{label}**")
elif page=="Lead Management":
    st.subheader("Add a new lead")
    with st.form("lead"):
        x,y=st.columns(2)
        name=x.text_input("Full name *"); email=y.text_input("Email")
        phone=x.text_input("Phone"); programme=y.selectbox("Programme interest *",PROGRAMME_OPTIONS)
        if st.form_submit_button("Save lead",type="primary"):
            try:
                lead_id = db.add_lead(name,email,phone,programme)
                if hasattr(db, "consume_duplicate_warnings"):
                    for duplicate_warning in db.consume_duplicate_warnings():
                        st.warning(duplicate_warning)
                st.success(f"Lead #{lead_id} saved.")
                st.rerun()
            except Exception as e: st.error(str(e))
    st.divider(); st.markdown("#### Add interaction")
    if not leads.empty:
        with st.form("interaction"):
            lid=st.selectbox("Lead",leads.lead_id.tolist(),format_func=lambda z:f"#{z} — {leads.loc[leads.lead_id==z,'full_name'].iloc[0]}")
            channel=st.selectbox("Channel",["WhatsApp","Email","Call","Web"])
            direction=st.selectbox("Direction",["Inbound","Outbound"])
            msg=st.text_area("Message / call notes")
            if st.form_submit_button("Save interaction"):
                try:
                    interaction_id = db.add_interaction(int(lid),channel,msg,direction)
                    if hasattr(db, "consume_duplicate_warnings"):
                        for duplicate_warning in db.consume_duplicate_warnings():
                            st.warning(duplicate_warning)
                    st.success(f"Interaction #{interaction_id} saved.")
                    st.rerun()
                except Exception as e: st.error(str(e))
    st.markdown("#### Lead directory"); st.dataframe(leads,width="stretch",hide_index=True)
elif page=="Generate Draft":
    st.subheader("Create a personalized follow-up")
    if leads.empty: st.warning("Add a lead first.")
    else:
        lid=st.selectbox("Select lead",leads.lead_id.tolist(),format_func=lambda z:f"#{z} — {leads.loc[leads.lead_id==z,'full_name'].iloc[0]}")
        channel=st.radio("Draft channel",["Email","WhatsApp"],horizontal=True)
        hist=db.get_history(int(lid))
        history_signature = tuple(
            (str(row.direction), str(row.message), str(row.occurred_at))
            for row in hist.itertuples(index=False)
        )
        draft_context = (int(lid), channel, history_signature)
        if st.session_state.get("latest_context") != draft_context:
            st.session_state.pop("latest", None)
            st.session_state.pop("latest_context", None)
        with st.expander("Conversation history",expanded=True):
            st.dataframe(hist[["channel","direction","message","occurred_at"]],width="stretch",hide_index=True)
        nlp=analyze_conversation(hist.to_dict(orient="records"))
        p,q,r=st.columns(3); p.metric("Stage",nlp["stage"]); q.metric("Preferences",len(nlp["preferences"])); r.metric("Open questions",len(nlp["unanswered_topics"]))
        st.subheader("Conversation insights", icon=":material/insights:")
        preference_column, topic_column, keyword_column = st.columns([1, 1.3, 1])
        with preference_column.container(border=True):
            st.markdown("**Preferences**")
            if nlp["preferences"]:
                with st.container(horizontal=True, gap="small"):
                    for preference in nlp["preferences"]:
                        st.badge(preference.replace("_", " ").title(), color="blue")
            else:
                st.caption("No preferences detected yet.")
        with topic_column.container(border=True):
            st.markdown("**Follow-up topics**")
            mentioned_topics = set(nlp["mentioned_topics"])
            answered_topics = set(nlp["answered_topics"])
            unanswered_topics = set(nlp["unanswered_topics"])
            with st.container(horizontal=True, gap="small"):
                for topic in sorted(mentioned_topics | answered_topics | unanswered_topics):
                    if topic in unanswered_topics:
                        st.badge(f"{topic.title()} to follow up", color="orange")
                    elif topic in answered_topics:
                        st.badge(f"{topic.title()} answered", color="green")
                    else:
                        st.badge(f"{topic.title()} mentioned", color="blue")
            if not mentioned_topics and not answered_topics and not unanswered_topics:
                st.caption("No follow-up topics detected yet.")
        with keyword_column.container(border=True):
            st.markdown("**Conversation signals**")
            if nlp["keywords"]:
                with st.container(horizontal=True, gap="small"):
                    for keyword in nlp["keywords"]:
                        st.badge(keyword, color="gray")
            else:
                st.caption("No keywords detected yet.")
            st.caption(f'{nlp["token_count"]} words analyzed')
        with st.expander("Questions and topic details"):
            if nlp["questions_detected"]:
                st.markdown("**Questions detected**")
                for question in nlp["questions_detected"]:
                    st.write(question)
            else:
                st.caption("No direct questions detected.")
            for label, topics, color in (
                ("Mentioned topics", nlp["mentioned_topics"], "blue"),
                ("Answered topics", nlp["answered_topics"], "green"),
                ("Topics to follow up", nlp["unanswered_topics"], "orange"),
            ):
                st.markdown(f"**{label}**")
                if topics:
                    with st.container(horizontal=True, gap="small"):
                        for topic in topics:
                            st.badge(topic.title(), color=color)
                else:
                    st.caption(f"No {label.lower()} detected.")
        approved_facts = (
            db.get_approved_facts(
                str(leads.loc[leads.lead_id == lid, "programme_interest"].iloc[0])
            )
            if hasattr(db, "get_approved_facts")
            else []
        )
        if not approved_facts:
            st.warning(
                "No approved facts are configured for this programme. "
                "Add trainer-approved facts under **Programme Facts** before generating a draft."
            )
        if st.button(
            "Generate AI draft",
            type="primary",
            disabled=not approved_facts,
            help=None if approved_facts else "Add approved programme facts before generating.",
        ):
            st.session_state.pop("latest", None)
            st.session_state.pop("latest_context", None)
            try:
                generator=AnthropicDraftGenerator(settings.anthropic_api_key,settings.anthropic_model)
                with st.spinner("Calling Anthropic Claude..."):
                    st.session_state["latest"]=generate_and_save_draft(db,int(lid),channel,generator)
                    st.session_state["latest_context"] = draft_context
                st.success("Draft saved as Pending Approval.")
            except Exception as e: st.error(str(e))
        output=st.session_state.get("latest")
        if output:
            draft = output["draft"]
            metadata = output["metadata"]
            st.subheader("Generated draft", icon=":material/draft:")
            with st.container(border=True):
                if draft.get("subject"):
                    st.markdown("**Subject**")
                    st.write(draft["subject"])
                st.text_area(
                    "Message for review",
                    draft["message"],
                    height=220,
                    disabled=True,
                )
                provider_column, model_column = st.columns(2)
                provider_column.caption("Provider")
                provider_column.write(metadata["provider"])
                model_column.caption("Model")
                model_column.write(metadata["model"])
                st.markdown("**Approved fact references**")
                if draft["fact_ids_used"]:
                    for fact_id in draft["fact_ids_used"]:
                        st.badge(f"Fact #{fact_id}", color="blue")
                else:
                    st.caption("No approved programme facts were cited.")
                st.markdown("**Reviewer notes**")
                if draft["review_notes"]:
                    for note in draft["review_notes"]:
                        st.write(note)
                else:
                    st.caption("No additional review notes.")
            st.warning(
                "Saved draft only. Human approval and a separate email send action are required."
            )
elif page=="Review Drafts":
    st.subheader("Human review queue"); drafts=db.get_drafts()
    send_notice = st.session_state.pop("email_send_notice", None)
    if send_notice:
        if send_notice[0] == "success":
            st.success(send_notice[1])
        else:
            st.error(send_notice[1])
    if drafts.empty: st.info("No drafts available.")
    else:
        st.dataframe(drafts[["draft_id","full_name","channel","status","provider","model","created_at"]],width="stretch",hide_index=True)
        pending=drafts[drafts.status=="Pending Approval"]
        if not pending.empty:
            did=st.selectbox("Pending draft",pending.draft_id.tolist())
            row=drafts[drafts.draft_id==did].iloc[0]
            st.text_area("Draft content",row.message_body,height=200,disabled=True)
            feedback=st.text_area("Reviewer feedback")
            x,y,z=st.columns(3)
            if x.button("Approve",type="primary"): db.review_draft(int(did),"Approved",feedback); st.success("Approved."); st.rerun()
            if y.button("Needs changes"): db.review_draft(int(did),"Needs Changes",feedback); st.rerun()
            if z.button("Reject"): db.review_draft(int(did),"Rejected",feedback); st.rerun()
        else: st.info("No pending drafts.")

    st.subheader("Approved email drafts")
    if drafts.empty or not {"channel", "status"}.issubset(drafts.columns):
        st.info("Approve an email draft to make it available here.")
    else:
        approved_emails = drafts[
            (drafts["channel"] == "Email")
            & drafts["status"].isin(["Approved", "Send Failed", "Sending"])
        ]
        if approved_emails.empty:
            st.info("Approve an email draft to make it available here.")
        else:
            email_draft_id = st.selectbox(
                "Email draft",
                approved_emails["draft_id"].tolist(),
                format_func=lambda draft_id: (
                    f"#{draft_id} — "
                    f"{approved_emails.loc[approved_emails.draft_id == draft_id, 'full_name'].iloc[0]}"
                ),
                key="approved-email-draft",
            )
            email_draft = approved_emails[
                approved_emails["draft_id"] == email_draft_id
            ].iloc[0]
            recipient = "" if pd.isna(email_draft["email"]) else str(email_draft["email"]).strip()
            subject = "" if pd.isna(email_draft["subject"]) else str(email_draft["subject"]).strip()
            st.caption(
                f"To: {email_draft['full_name']} <{recipient or 'email missing'}>"
            )
            st.write(f"Subject: {subject or 'Missing subject'}")
            st.text_area(
                "Approved email preview",
                email_draft["message_body"],
                height=180,
                disabled=True,
                key=f"email-preview-{email_draft_id}",
            )

            recipient_error = None
            try:
                validate_recipient_address(recipient)
            except ValueError as error:
                recipient_error = str(error)
            smtp_configuration_error = email_sender.configuration_error()

            if email_draft["status"] == "Sending":
                st.warning(
                    "A send attempt may still be active or may have been interrupted. Wait for it to stop and check your SMTP provider before retrying."
                )
                delivery_checked = st.checkbox(
                    "I verified no send is active and this email was not delivered.",
                    key=f"email-recovery-confirm-{email_draft_id}",
                )
                if st.button(
                    "Allow retry after verification",
                    disabled=not delivery_checked,
                    key=f"email-recover-{email_draft_id}",
                ):
                    db.reconcile_email_send(email_draft_id, delivery_checked)
                    st.session_state["email_send_notice"] = (
                        "success",
                        "Send status updated. You can now retry this email.",
                    )
                    st.rerun()
            elif recipient_error:
                st.warning(recipient_error)
            elif "\r" in subject or "\n" in subject:
                st.warning("The email subject contains unsupported line breaks.")
            elif not subject:
                st.warning("This email draft has no subject. Request changes before sending.")
            elif smtp_configuration_error:
                st.info(
                    "Email sending is disabled. "
                    + smtp_configuration_error
                )
            else:
                is_retry = email_draft["status"] == "Send Failed"
                retry_confirmed = False
                if is_retry:
                    st.warning(
                        "The previous attempt failed. Check your provider before retrying."
                    )
                    retry_confirmed = st.checkbox(
                        "I confirmed the previous email was not delivered.",
                        key=f"email-retry-confirm-{email_draft_id}",
                    )
                send_clicked = st.button(
                    "Retry email send" if is_retry else "Send email",
                    type="primary",
                    disabled=is_retry and not retry_confirmed,
                    icon=":material/send:",
                    key=f"send-email-{email_draft_id}",
                )
                if send_clicked:
                    try:
                        sending_draft = db.claim_email_draft_for_sending(
                            int(email_draft_id),
                            retry_confirmed=retry_confirmed,
                        )
                    except (LookupError, ValueError) as error:
                        st.error(str(error))
                    else:
                        try:
                            with st.spinner("Sending email..."):
                                email_sender.send_email(
                                    sending_draft["email"],
                                    sending_draft["subject"],
                                    sending_draft["message_body"],
                                )
                        except (OSError, RuntimeError, ValueError, smtplib.SMTPException) as error:
                            db.mark_email_send_failed(
                                int(email_draft_id), type(error).__name__
                            )
                            st.session_state["email_send_notice"] = (
                                "error",
                                f"Email send failed: {error}. Check provider delivery status before retrying.",
                            )
                        else:
                            db.mark_email_draft_sent(int(email_draft_id))
                            st.session_state["email_send_notice"] = (
                                "success",
                                f"Email sent to {sending_draft['email']}.",
                            )
                        st.rerun()
elif page=="Programme Facts":
    st.subheader("Approved programme knowledge base")
    st.caption("Only approved facts are passed to the LLM. Use verified, trainer-approved information.")
    with st.form("fact"):
        prog=st.selectbox("Programme",PROGRAMME_OPTIONS)
        cat=st.selectbox("Category",["Audience","Schedule","Fees","Duration","Eligibility","Learning support","Placement","Recording","Other"])
        fact=st.text_area("Approved fact")
        if st.form_submit_button("Add approved fact"):
            try:
                fact_id = db.add_fact(prog,cat,fact,True)
                if hasattr(db, "consume_duplicate_warnings"):
                    for duplicate_warning in db.consume_duplicate_warnings():
                        st.warning(duplicate_warning)
                st.success(f"Approved fact #{fact_id} saved.")
                st.rerun()
            except Exception as e: st.error(str(e))
    facts = db.get_programme_facts()
    st.dataframe(facts,width="stretch",hide_index=True)

"""Margin Leak Scorecard — Streamlit entrypoint.

Voice: BMT v1.1 (contractor, no "tool", no em dashes, no hedges).
Look: BMT Design System v3.0 (dark everywhere, Streamlit default font,
      blue active, orange #ff6b35 brand accent, RAG for status).

Privacy: ZERO data capture. No email, no name, no CSV writes. Nothing
         leaves the browser beyond the Claude API call, and even that
         only sees the anonymous answers.

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from scoring import (
    ACTIVE_PROJECT_OPTIONS,
    QUESTIONS,
    REVENUE_TIERS,
    SCALE_1_5_LABELS,
    SCHEDULE_OVERLAP_OPTIONS,
    call_claude,
    compute_score,
)


# ---------------------------------------------------------------------------
# Environment + constants
# ---------------------------------------------------------------------------

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")

# Bridge Streamlit Cloud / Render secrets into os.environ so scoring.py sees them.
try:
    for key, value in st.secrets.items():
        if key not in os.environ:
            os.environ[key] = str(value)
except Exception:
    pass

CONTACT_EMAIL = "michael@blackmountaintechnologies.ca"
CONTACT_PHONE = os.environ.get("CONTACT_PHONE", "250-254-2377").strip()
FORMSPREE_ENDPOINT = os.environ.get(
    "FORMSPREE_ENDPOINT",
    "https://formspree.io/f/mvzledqa",
).strip()
CALENDAR_URL = os.environ.get(
    "CALENDAR_URL",
    "https://calendly.com/michael-blackmountaintechnologies/30min",
).strip()


def _no_math(text: str) -> str:
    """Streamlit's markdown renderer treats `$...$` as LaTeX math and
    italicizes the content. Escape every dollar sign so dollar amounts
    render as literal text."""
    if not isinstance(text, str):
        return text
    return text.replace("$", "\\$")


# ---------------------------------------------------------------------------
# Page + styles (BMT Design System v3.0 — dark, Streamlit default font,
# orange #ff6b35 brand, blue #3b82f6 active, RAG for status)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Margin Leak Scorecard · Black Mountain Technologies",
    page_icon="◆",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Load theme + scorecard extensions from styles/.
for css_file in ("styles/theme.css", "styles/scorecard.css"):
    path = HERE / css_file
    if path.exists():
        st.markdown(f"<style>{path.read_text()}</style>", unsafe_allow_html=True)

# Hide the collapsed sidebar — this is a single-page public app.
st.markdown(
    """
    <style>
      [data-testid="stSidebar"] { display: none !important; }
      [data-testid="stSidebarCollapsedControl"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# UI building blocks
# ---------------------------------------------------------------------------

def question_block(number: int, text: str) -> None:
    st.markdown(
        f"<div class='bmt-q-num'>Q{number:02d}</div>"
        f"<div class='bmt-q-text'>{text}</div>",
        unsafe_allow_html=True,
    )


def scale_radio(qid: str) -> int:
    labels = SCALE_1_5_LABELS[qid]
    options = [1, 2, 3, 4, 5]

    def fmt(n: int) -> str:
        return f"{n}. {labels[n]}"

    return int(st.radio(
        label=qid,
        options=options,
        index=2,
        format_func=fmt,
        horizontal=False,
        key=f"radio_{qid}",
        label_visibility="collapsed",
    ))


def render_landing() -> None:
    st.markdown(
        "<div class='bmt-tagline'>Black Mountain Technologies</div>",
        unsafe_allow_html=True,
    )
    st.markdown("# Margin Leak Scorecard")
    st.markdown("<hr class='bmt-hero-rule'/>", unsafe_allow_html=True)
    st.markdown(
        "<div class='bmt-subhead'>10 questions about your company. A free "
        "audit from artificial intelligence.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='bmt-privacy-note'><strong>Completely free.</strong> "
        "No email, no signup, no annoying emails after the fact.</div>",
        unsafe_allow_html=True,
    )
    st.write("")


def render_details_expander() -> None:
    with st.expander("More about this scorecard"):
        st.markdown(
            "Most Canadian GCs in the \\$5M to \\$40M range are losing "
            "**2% to 4% of annual revenue** to margin leak. Industry math "
            "for what that looks like:"
        )
        st.markdown(
            "- **\\$5M-\\$10M shop:** \\$100K to \\$400K a year\n"
            "- **\\$10M-\\$15M shop:** \\$200K to \\$600K a year\n"
            "- **\\$15M-\\$25M shop:** \\$300K to \\$1M a year\n"
            "- **\\$25M-\\$40M shop:** \\$500K to \\$1.6M a year"
        )
        st.markdown(
            "This matters most for companies somewhere between \\$10M and "
            "\\$30M. That is the stage where the owner stops making every "
            "call personally and new executives start stepping in. More "
            "projects are running at once than ever. The simple systems "
            "that worked at \\$5M start cracking. That is when margin "
            "leak gets expensive and when a read like this pays for itself."
        )
        st.markdown(
            "Procore will not flag it. Your PMs tell you every job is on "
            "track. Then Q4 closes, your margin is down two points, and "
            "nobody can tell you where the money went. **This scorecard "
            "tells you where.**"
        )

        st.markdown(
            "<div class='bmt-section-heading' style='margin-top:1.2rem;'>What margin leak actually means</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "Margin leak is money you should have kept on your jobs. You "
            "lose it through small gaps in how the work runs. Each gap is "
            "small on its own. Add them up across a year of jobs and the "
            "total is **six figures or more**. A few you will recognize:"
        )
        st.markdown(
            "- **Change orders approved and never invoiced.** Signed off "
            "on site. Never made it to the pay app.\n"
            "- **Field extras done as a favor.** Your PM said \"no problem, "
            "we'll take care of it.\" Now you're eating the cost.\n"
            "- **Labor blowouts found at close-out.** Crew was 40% over "
            "estimate by week 2. Nobody flagged it until the job closed.\n"
            "- **Subcontractor backcharges you never pushed.** You ate "
            "someone else's screw-up because the paperwork was annoying.\n"
            "- **Schedule slips that compound.** Same wall opened three "
            "times because trades weren't sequenced.\n"
            "- **Rental equipment rolling past the need-by date.** "
            "Excavator's been on site two weeks longer than the schedule. "
            "Nobody called it in.\n"
            "- **Material waste nobody logs.** Damaged, stolen, miscounted, "
            "double-paid.\n"
            "- **Holdback released and never invoiced back.** Job closed, "
            "retention paid out, final invoice never issued.\n"
            "- **Procurement price drift.** Supplier quoted one price, "
            "billed another, nobody audited."
        )

        st.markdown(
            "<div class='bmt-section-heading' style='margin-top:1.2rem;'>The honest truth about leaks</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "You will always lose some margin. Construction has too many "
            "variables. Weather changes. Subs do not show up. Material "
            "prices move in the middle of a job. Bids miss the mark. That "
            "is the reality of the work. Anyone who tells you different "
            "is selling you something."
        )
        st.markdown(
            "**Aim for zero leak. Nobody actually gets there.** Make your "
            "process as tight as you can so when something goes wrong, "
            "the leak is easy to find and small to fix. Not buried at "
            "close-out."
        )
        st.markdown(
            "That is what modern construction AI does. It does not stop "
            "the thing from going wrong. It catches the dollar impact "
            "while you can still fix it, before close-out hides it. "
            "**Shops that grow do not chase perfect jobs. They build a "
            "tight process.**"
        )

        st.markdown(
            "<div class='bmt-section-heading' style='margin-top:1.2rem;'>What you get in 60 seconds</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "- A **score out of 100**, color-coded green to red, that "
            "shows how tight or leaky your operation is\n"
            "- A **plain-English read** from Claude Opus 4.7 on what your "
            "answers mean for your margin\n"
            "- A **rough estimate of your annual dollar leak**, based on "
            "your revenue tier and industry benchmarks (not your actual "
            "jobs)\n"
            "- **3 to 5 specific leaks** tied to your answers, each with a "
            "**3-step plan you can start this week**\n"
            "- A **clear next step** if you want the real number on your "
            "actual closed jobs, not an industry estimate"
        )

        st.markdown(
            "<div class='bmt-section-heading' style='margin-top:1.2rem;'>Why this isn't a waste of your time</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "- **Built by contractors for contractors.** The AI knows what "
            "close-out, change orders, and labor tracking actually look "
            "like because it was built by people who run jobs. Not by a "
            "SaaS team that read a book about construction.\n"
            "- **If it doesn't name a real leak, book a call anyway.** If "
            "the output doesn't flag one specific leak you could fix this "
            "week, book a 15-minute autopsy walkthrough. We'll find one "
            "live or we'll tell you straight there is nothing to find. No "
            "pitch deck.\n"
            "- **This is the preview. The full thing is the Company "
            "Autopsy.** 60 seconds here gives you a score and a short "
            "read. The Cost Overrun Solution software runs the full "
            "autopsy on your actual closed jobs and shows you the real "
            "dollar leak in six figures or more."
        )

        st.markdown(
            "<div class='bmt-section-heading' style='margin-top:1.2rem;'>Rather just talk?</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "Skip the scorecard. Book a 15-minute autopsy walkthrough. "
            "We'll pull one of your closed jobs live and show you where "
            "the margin went."
        )
        top_subject = quote("Autopsy walkthrough request · Cost Overrun Solution")
        top_body = quote(
            "Hi Michael,\n\n"
            "I'd like to book a 15-minute autopsy walkthrough for the "
            "Cost Overrun Solution software.\n\n"
            "Thanks."
        )
        st.link_button(
            "Book a 15-minute autopsy walkthrough",
            f"mailto:{CONTACT_EMAIL}?subject={top_subject}&body={top_body}",
            use_container_width=True,
        )


def render_form() -> tuple[bool, dict]:
    with st.form("scorecard_form", clear_on_submit=False):
        st.markdown(
            "<div class='bmt-section-heading'>10 questions</div>",
            unsafe_allow_html=True,
        )

        answers: dict = {}

        for idx, q in enumerate(QUESTIONS, start=1):
            question_block(idx, q["text"])

            if q["kind"] == "scale_1_5":
                answers[q["id"]] = scale_radio(q["id"])

            elif q["kind"] == "yes_no_sometimes":
                answers[q["id"]] = st.radio(
                    label=q["id"],
                    options=SCHEDULE_OVERLAP_OPTIONS,
                    index=1,
                    horizontal=True,
                    key=f"radio_{q['id']}",
                    label_visibility="collapsed",
                )

            elif q["kind"] == "active_projects":
                answers[q["id"]] = st.radio(
                    label=q["id"],
                    options=ACTIVE_PROJECT_OPTIONS,
                    index=1,
                    horizontal=True,
                    key=f"radio_{q['id']}",
                    label_visibility="collapsed",
                )

            elif q["kind"] == "revenue_tier":
                answers[q["id"]] = st.radio(
                    label=q["id"],
                    options=REVENUE_TIERS,
                    index=1,
                    horizontal=False,
                    key=f"radio_{q['id']}",
                    label_visibility="collapsed",
                    # Escape $ so Streamlit does not parse them as LaTeX math.
                    format_func=_no_math,
                )

            elif q["kind"] == "free_text":
                answers[q["id"]] = st.text_area(
                    label=q["id"],
                    max_chars=200,
                    height=80,
                    placeholder="One or two sentences is fine.",
                    label_visibility="collapsed",
                )

        st.markdown("")
        submitted = st.form_submit_button("See my margin leak breakdown")

    return submitted, {"answers": answers}


def validate(answers: dict) -> list[str]:
    errs: list[str] = []
    for q in QUESTIONS:
        if q["id"] == "q10":
            continue
        if answers.get(q["id"]) in (None, ""):
            errs.append(f"Please answer: {q['text']}")
    return errs


def render_result(score: dict, ai: dict) -> None:
    tier = score["tier"]
    color = tier["color"]

    # Scroll the parent window to the top so users land on the score,
    # not wherever they were scrolled when they hit submit.
    components.html(
        "<script>setTimeout(() => window.parent.scrollTo({top:0, behavior:'instant'}), 0);</script>",
        height=0,
    )

    st.markdown(
        "<div class='bmt-tagline'>Your scorecard</div>",
        unsafe_allow_html=True,
    )
    st.markdown("# Your Margin Leak Results")

    st.markdown(
        f"""
        <div class="bmt-score-wrap">
            <div style="flex:0 0 auto;">
                <div class="bmt-score-label">Overall Score</div>
                <div style="display:flex;align-items:baseline;gap:2px;">
                    <span class="bmt-score-number">{score['normalized']}</span>
                    <span class="bmt-score-slash">/100</span>
                </div>
            </div>
            <div style="flex:1 1 auto;">
                <div class="bmt-tier-pill" style="
                    background:{color}1f;
                    color:{color};
                    border:1px solid {color}66;
                ">{_no_math(tier['name'])}</div>
                <div class="bmt-score-blurb">{_no_math(tier['blurb'])}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    headline = ai.get("headline", "")
    if headline:
        st.markdown(
            f"<div class='bmt-headline'>{_no_math(headline)}</div>",
            unsafe_allow_html=True,
        )

    summary = ai.get("score_summary", "")
    if summary:
        st.markdown(_no_math(summary))

    est = ai.get("estimated_dollar_range", "")
    if est:
        st.markdown(
            f"""
            <div class="bmt-callout">
                <div class="label">Estimated margin leak</div>
                <div class="amount">{_no_math(est)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Plain-English action plan (grade-6, DO / WHY / 3-step playbook)
    plan = ai.get("plain_english_plan") or []
    if isinstance(plan, list) and plan:
        item_blocks = []
        for i, step in enumerate(plan[:5], start=1):
            if isinstance(step, dict):
                do = _no_math(str(step.get("do", "")))
                why = _no_math(str(step.get("why", "")))
                how = step.get("how", [])
                if isinstance(how, str):
                    how = [how]
            else:
                do = _no_math(str(step))
                why = ""
                how = []

            why_html = f"<div class='bmt-plan-why'>{why}</div>" if why else ""

            how_html = ""
            if isinstance(how, list) and how:
                steps_html = "".join(
                    f"<li>{_no_math(str(h))}</li>" for h in how[:3]
                )
                how_html = (
                    f"<div class='bmt-plan-how'>"
                    f"  <div class='bmt-plan-how-label'>3-step plan</div>"
                    f"  <ol class='bmt-plan-how-list'>{steps_html}</ol>"
                    f"</div>"
                )

            item_blocks.append(
                f"<div class='bmt-plan-item'>"
                f"  <div class='bmt-plan-num'>{i}</div>"
                f"  <div class='bmt-plan-body'>"
                f"    <div class='bmt-plan-do'>{do}</div>"
                f"    {why_html}"
                f"    {how_html}"
                f"  </div>"
                f"</div>"
            )
        items_html = "".join(item_blocks)
        st.markdown(
            f"""
            <div class="bmt-plan-block">
                <div class="bmt-plan-label">WHAT TO DO THIS WEEK</div>
                <div class="bmt-plan-heading">Here is how to stop the leak. Start this week.</div>
                {items_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="bmt-cta-block">
            <div class="bmt-cta-label">Want the full autopsy?</div>
            <div class="bmt-cta-body">
                What you just read is a quick overview based on 10 answers.
                The full Company Autopsy from our Cost Overrun Solution
                software runs on your actual closed jobs. We take a real
                job, go through the numbers with you, and show you exactly
                where the margin went and how to get it back. 15 minutes
                on video. No pitch deck. No pressure.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("lead_submitted"):
        lead_name = st.session_state.get("lead_name", "").strip()
        thanks_name = lead_name.split()[0] if lead_name else "Got it"
        st.markdown(
            f"""
            <div class="bmt-cta-block" style="border-left-color:#10b981;background:linear-gradient(135deg,#eafbf2 0%,#f5fdfa 100%);border-color:#bfeed8;">
                <div class="bmt-cta-label" style="color:#10b981;">Thanks {thanks_name}</div>
                <div class="bmt-cta-body">
                    Your details are on their way to Michael. He will reach
                    out within 24 hours to set up the video walkthrough.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if CALENDAR_URL:
            st.markdown(
                "Or skip the back-and-forth and pick a time directly:"
            )
            st.link_button(
                "Pick a time for the video walkthrough",
                CALENDAR_URL,
                use_container_width=True,
            )
    else:
        form_col, contact_col = st.columns([2, 1])

        with form_col:
            with st.form("lead_form", clear_on_submit=False):
                st.markdown("**Get in touch**")
                lead_name_in = st.text_input("Your name")
                lead_phone_in = st.text_input("Phone")
                lead_email_in = st.text_input("Email")
                lead_size_in = st.selectbox(
                    "Approximate company size",
                    REVENUE_TIERS,
                    index=1,
                )
                lead_issue_in = st.text_area(
                    "Biggest cost problem you are dealing with right now",
                    placeholder="One or two sentences is fine.",
                    height=80,
                )
                submit_lead = st.form_submit_button("Send", use_container_width=True)

            if submit_lead:
                errs: list[str] = []
                if not lead_name_in.strip():
                    errs.append("Add your name.")
                if not lead_phone_in.strip():
                    errs.append("Add your phone.")
                if not lead_email_in.strip() or "@" not in lead_email_in:
                    errs.append("Add a valid email.")

                if errs:
                    for e in errs:
                        st.error(e)
                elif not FORMSPREE_ENDPOINT:
                    st.error(
                        "The contact form is not wired up yet. "
                        f"Email {CONTACT_EMAIL} directly."
                    )
                else:
                    try:
                        response = requests.post(
                            FORMSPREE_ENDPOINT,
                            data={
                                "name": lead_name_in,
                                "phone": lead_phone_in,
                                "email": lead_email_in,
                                "company_size": lead_size_in,
                                "issue": lead_issue_in,
                                "scorecard_score": f"{score['normalized']}/100",
                                "scorecard_tier": tier["name"],
                            },
                            headers={"Accept": "application/json"},
                            timeout=10,
                        )
                        if response.ok:
                            st.session_state["lead_submitted"] = True
                            st.session_state["lead_name"] = lead_name_in
                            st.rerun()
                        else:
                            st.error(
                                "Something went wrong sending the form. "
                                f"Email {CONTACT_EMAIL} directly."
                            )
                    except Exception as e:
                        st.error(
                            "Could not send the form. "
                            f"Email {CONTACT_EMAIL} directly. ({e})"
                        )

        with contact_col:
            tel_digits = "".join(c for c in CONTACT_PHONE if c.isdigit())
            phone_html = (
                f"<div class='bmt-contact-row'>Or call:<br/>"
                f"<a href='tel:{tel_digits}'><strong>{CONTACT_PHONE}</strong></a></div>"
                if CONTACT_PHONE else ""
            )
            st.markdown(
                f"""
                <div class="bmt-contact-card">
                    <div class="bmt-contact-label">Reach me directly</div>
                    <div class="bmt-contact-row">
                        Email:<br/>
                        <a href="mailto:{CONTACT_EMAIL}"><strong>{CONTACT_EMAIL}</strong></a>
                    </div>
                    {phone_html}
                    <div class="bmt-contact-row" style="margin-top:14px;font-style:italic;color:var(--text-secondary);font-size:13px;">
                        First meeting is 15 minutes on video so I can show
                        you the software running on a real closed job.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if ai.get("_error"):
        st.info(
            "Heads up. The AI breakdown could not run, so this page is "
            f"showing a generic version. `{ai['_error']}`."
        )

    st.write("")
    if st.button("Start over", key="restart"):
        for key in ("result", "lead_submitted", "lead_name"):
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

if "result" in st.session_state:
    render_result(
        st.session_state["result"]["score"],
        st.session_state["result"]["ai"],
    )
else:
    render_landing()
    render_details_expander()
    submitted, payload = render_form()

    if submitted:
        errs = validate(payload["answers"])
        if errs:
            for e in errs:
                st.error(e)
        else:
            with st.spinner("Crunching your answers..."):
                score = compute_score(payload["answers"])
                ai = call_claude(payload["answers"], score, company_name="")

            # NOTE: no write_lead_row, no CSV, no session state beyond result.
            # Nothing leaves the browser except the Claude API call.
            st.session_state["result"] = {"score": score, "ai": ai}
            st.rerun()

st.markdown(
    f"""
    <div class="bmt-footer">
        Black Mountain Technologies &nbsp;·&nbsp;
        <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>
    </div>
    """,
    unsafe_allow_html=True,
)

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

import streamlit as st
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
            "Most Canadian GCs, from \\$5M to \\$500M+, are bleeding "
            "**3% to 8% of annual revenue** before close-out even hits. "
            "That number scales with you:"
        )
        st.markdown(
            "- **\\$15M shop:** \\$300K to \\$900K a year\n"
            "- **\\$50M shop:** \\$1.5M to \\$4M a year\n"
            "- **\\$150M shop:** \\$3M to \\$15M a year\n"
            "- **\\$500M+:** seven to eight figures annually"
        )
        st.markdown(
            "Procore won't flag it. Your PMs say everything's green. Then "
            "Q4 closes, margin's down two points, and nobody can point to "
            "where it went. **This scorecard tells you where.**"
        )

        st.markdown(
            "<div class='bmt-section-heading' style='margin-top:1.2rem;'>What margin leak actually means</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "Profit you should have kept that walks out through small "
            "cracks in how you run your jobs. Each one's small on its own. "
            "Stack them across a year of jobs and those small holes total "
            "**six or seven figures**. A few you'll recognize:"
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
            "You'll never hit zero. Construction has variables. Weather "
            "hits. Subs no-show. Material prices move mid-job. Bids break. "
            "That's the reality of the trades, and anyone telling you "
            "otherwise is selling you something."
        )
        st.markdown(
            "**The aim is airtight. Nobody actually hits it.** Make your "
            "process as tight as you can so when things go sideways, the "
            "leak is easy to spot and small to contain, not buried in "
            "close-out."
        )
        st.markdown(
            "That's what modern construction AI does. It doesn't stop the "
            "thing that went sideways. It catches the margin hit before it "
            "buries itself in close-out. **Shops that grow don't chase "
            "perfect jobs. They chase tight process.**"
        )

        st.markdown(
            "<div class='bmt-section-heading' style='margin-top:1.2rem;'>What you get in 60 seconds</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "- A **score out of 100**, color-coded green to red, showing "
            "how tight or leaky you run\n"
            "- A **plain-English read** from Claude Opus 4.7 on what your "
            "answers actually mean for your margin\n"
            "- A **ballpark annual dollar leak**, sized to your revenue "
            "tier (industry benchmark math, not your actual jobs)\n"
            "- **3 to 5 specific leaks** tied to YOUR answers, each with a "
            "**3-step Monday playbook** on how to close it\n"
            "- A **clear next step** if you want the real number on your "
            "actual closed jobs, not an industry benchmark"
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
            "week, book a 15-minute discovery call. We'll find one live, "
            "or we'll tell you straight there's nothing to find. No pitch "
            "deck.\n"
            "- **This is a preview of the paid software.** 60 seconds gets "
            "you a score and three leaks. The paid software digs through "
            "your actual closed jobs and typically finds **six to seven "
            "figures in recoverable margin** on portfolios your size."
        )

        st.markdown(
            "<div class='bmt-section-heading' style='margin-top:1.2rem;'>Rather just talk?</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "Skip the scorecard. Book a 15-minute discovery call. I'll "
            "walk you through what the paid software does on your actual "
            "closed jobs, live, no form."
        )
        top_subject = quote("Discovery call request · Margin Leak Scorecard")
        top_body = quote(
            "Hi Michael,\n\n"
            "I'd like to book a 15-minute discovery call to see the Black "
            "Mountain Technologies software.\n\n"
            "Thanks."
        )
        st.link_button(
            "Book a 15-minute discovery call",
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

    st.markdown(
        "<div class='bmt-tagline'>Your scorecard</div>",
        unsafe_allow_html=True,
    )
    st.markdown("# Your Margin Leak Read")

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
                    f"  <div class='bmt-plan-how-label'>Playbook</div>"
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
                <div class="bmt-plan-label">IN PLAIN ENGLISH · WHAT TO DO MONDAY</div>
                <div class="bmt-plan-heading">Here's how to stop the leak. Start this week.</div>
                {items_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    subject = quote(f"Discovery call · Scorecard result · {score['normalized']}/100 {tier['name']}")
    body = quote(
        f"Hi Michael,\n\n"
        f"I just ran the Margin Leak Scorecard. My score was "
        f"{score['normalized']}/100 ({tier['name']}).\n\n"
        f"I'd like to book a 15-minute discovery call to see the full "
        f"software.\n\n"
        f"Thanks."
    )
    mailto = f"mailto:{CONTACT_EMAIL}?subject={subject}&body={body}"

    st.link_button(
        "Book a 15-minute discovery call",
        mailto,
        use_container_width=True,
    )

    if ai.get("_error"):
        st.info(
            "Heads up. The AI breakdown fell back to a generic version because of "
            f"an error. `{ai['_error']}`."
        )

    st.write("")
    if st.button("Start over", key="restart"):
        if "result" in st.session_state:
            del st.session_state["result"]
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
    submitted, payload = render_form()
    render_details_expander()

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

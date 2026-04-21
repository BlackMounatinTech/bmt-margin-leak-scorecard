"""Margin Leak Scorecard — Streamlit entrypoint.

Voice: BMT v1.1 (contractor, no "tool", no em dashes, no hedges).
Look: BMT Design System v3.0 (dark everywhere, Streamlit default font,
      blue active, orange #ff6b35 brand accent, RAG for status).

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime
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

DATA_DIR = HERE / ".tmp"
CSV_PATH = DATA_DIR / "scorecard_leads.csv"
CSV_FIELDS = [
    "timestamp",
    "company_name",
    "email",
    "score",
    "tier",
    "revenue_tier",
    "active_projects",
    "biggest_pain",
    "all_answers_json",
]

CONTACT_EMAIL = "michael@blackmountaintechnologies.ca"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
# Lead capture
# ---------------------------------------------------------------------------

def write_lead_row(company_name: str, email: str, score: dict, answers: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = CSV_PATH.exists()
    row = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "company_name": company_name,
        "email": email,
        "score": score["normalized"],
        "tier": score["tier"]["name"],
        "revenue_tier": answers.get("q9", ""),
        "active_projects": answers.get("q8", ""),
        "biggest_pain": answers.get("q10", ""),
        "all_answers_json": json.dumps(answers, ensure_ascii=False),
    }
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


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
        "<div class='bmt-subhead'>Find out in 60 seconds how much money is "
        "walking out the door on every job you close. Sized to your company.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "Most Canadian GCs, from \\$5M to \\$500M+, are bleeding **3% to 8% of "
        "annual revenue** before close-out even hits. That number scales with "
        "you:"
    )
    st.markdown(
        "- **\\$15M shop:** \\$300K to \\$900K a year\n"
        "- **\\$50M shop:** \\$1.5M to \\$4M a year\n"
        "- **\\$150M shop:** \\$3M to \\$15M a year\n"
        "- **\\$500M+:** seven to eight figures annually"
    )
    st.markdown(
        "Procore won't flag it. Your PMs say everything's green. Then Q4 closes, "
        "margin's down two points, and nobody can point to where it went. "
        "**This scorecard tells you where.**"
    )

    st.markdown(
        "<div class='bmt-section-heading' style='margin-top:1.5rem;'>What this actually is</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "A free AI-powered self-assessment we built for Canadian GC owners and "
        "operators who are thinking about working with us. The scoring is "
        "deterministic math. The breakdown is Claude Opus 4.7 reading your "
        "answers and telling you what they actually mean for your margin. No "
        "demo dressed up to make us look good. You answer honest, you get an "
        "honest read."
    )
    st.markdown(
        "The value you walk away with is proportional to how tight or sloppy "
        "you run. A small shop with okay process might see **\\$50K** worth "
        "of fixable leaks. A \\$100M shop with blind spots might see "
        "**\\$500K to \\$2M**. Either way, you leave with a number you "
        "didn't have when you showed up. That's why it exists."
    )

    st.markdown(
        "<div class='bmt-section-heading' style='margin-top:1.5rem;'>What margin leak actually means</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "Profit you should have kept that walks out through small cracks in "
        "how you run your jobs. Each one's small on its own. Stack them "
        "across a year of jobs and those small holes total **six or seven "
        "figures**. A few you'll recognize:"
    )
    st.markdown(
        "- **Change orders approved and never invoiced.** Signed off on site. "
        "Never made it to the pay app.\n"
        "- **Field extras done as a favor.** Your PM said \"no problem, we'll "
        "take care of it.\" Now you're eating the cost.\n"
        "- **Labor blowouts found at close-out.** Crew was 40% over estimate "
        "by week 2. Nobody flagged it until the job closed.\n"
        "- **Subcontractor backcharges you never pushed.** You ate someone "
        "else's screw-up because the paperwork was annoying.\n"
        "- **Schedule slips that compound.** Same wall opened three times "
        "because trades weren't sequenced.\n"
        "- **Rental equipment rolling past the need-by date.** Excavator's "
        "been on site two weeks longer than the schedule. Nobody called it in.\n"
        "- **Material waste nobody logs.** Damaged, stolen, miscounted, "
        "double-paid.\n"
        "- **Holdback released and never invoiced back.** Job closed, "
        "retention paid out, final invoice never issued.\n"
        "- **Procurement price drift.** Supplier quoted one price, billed "
        "another, nobody audited."
    )

    st.markdown(
        "<div class='bmt-section-heading' style='margin-top:1.5rem;'>The honest truth about leaks</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "You will never hit zero. Construction has variables. Weather hits. "
        "Subs no-show. Material prices move mid-job. Bid assumptions break. "
        "That is the reality of the trades, and anyone who tells you "
        "otherwise is selling you something."
    )
    st.markdown(
        "**The aim is airtight. Nobody actually hits it. The shops that "
        "grow just get closer than everyone else on the bid list.** Make "
        "the process as watertight as you can so when the variables hit, "
        "the leak is measurable and containable, not mysterious and "
        "compounding into the next job."
    )
    st.markdown(
        "That's what modern construction AI does. It doesn't stop the "
        "weather. It catches the leak the weather caused before it hides "
        "in close-out. **The contractors who actually grow don't chase "
        "perfect jobs. They chase tight process.**"
    )

    st.markdown(
        "<div class='bmt-section-heading' style='margin-top:1.5rem;'>What you get in 60 seconds</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "- A **score out of 100** showing how bad the leak is, color-coded\n"
        "- **3 specific leaks** tied to YOUR actual answers, not generic bullshit\n"
        "- A **dollar range** sized to your revenue. What this costs you per year.\n"
        "- A **one-line fix** for each leak you can start Monday"
    )

    st.markdown(
        "<div class='bmt-section-heading' style='margin-top:1.5rem;'>Why this isn't a waste of your time</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "- **Built by contractors for contractors.** The AI knows what "
        "close-out, change orders, and labor tracking actually look like "
        "because it was built by people who run jobs. Not by a SaaS team "
        "that read a book about construction.\n"
        "- **Private by design.** No login. No data upload. No account. No "
        "calendar invite. No export. Your P&L never leaves your server. "
        "You don't even need to give your real name to see your number. "
        "Screenshot the result if you want to keep it.\n"
        "- **Risk reversal built in.** If the output doesn't name at least "
        "one specific leak you could fix this week, book a free 15-minute "
        "discovery call. We'll find it live, or we'll tell you straight "
        "there's nothing to find. No pitch deck. No pressure.\n"
        "- **The free preview of the paid software.** 60 seconds gets you a "
        "score and three leaks. The paid software digs through your actual "
        "closed jobs and typically finds **six to seven figures in "
        "recoverable margin** on portfolios your size. The discovery call "
        "shows you exactly how."
    )

    # CTA block: skip-ahead to discovery call
    st.markdown(
        "<div class='bmt-section-heading' style='margin-top:1.6rem;'>"
        "Already know you want to talk?</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "Skip the scorecard. Book a 15-minute discovery call. I'll walk you "
        "through what the paid software does on your actual closed jobs, "
        "live, no form."
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

    st.markdown(
        "<div class='bmt-subhead' style='margin-top:1.8rem;'>Or start "
        "the scorecard below. You're 60 seconds from knowing a number "
        "that could be worth seven figures to you this year.</div>",
        unsafe_allow_html=True,
    )
    st.write("")


def render_form() -> tuple[bool, dict]:
    with st.form("scorecard_form", clear_on_submit=False):
        st.markdown(
            "<div class='bmt-section-heading'>Your info (optional)</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Both fields are optional. Fill them in if you want follow-up. "
            "Skip them and your result still renders. No gate."
        )
        col_a, col_b = st.columns(2)
        with col_a:
            company_name = st.text_input(
                "Company name (optional)",
                max_chars=50,
                placeholder="e.g. Northshore Construction Ltd.",
            )
        with col_b:
            email = st.text_input(
                "Work email (optional)",
                placeholder="you@yourcompany.com",
            )

        st.markdown(
            "<div class='bmt-section-heading' style='margin-top:1.4rem;'>10 questions</div>",
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

    return submitted, {
        "company_name": company_name.strip() if company_name else "",
        "email": email.strip() if email else "",
        "answers": answers,
    }


def validate(company_name: str, email: str, answers: dict) -> list[str]:
    """Company name and email are both optional. Only validate format if provided."""
    errs: list[str] = []
    if company_name and len(company_name) > 50:
        errs.append("Company name must be 50 characters or fewer.")
    if email and not EMAIL_RE.match(email):
        errs.append("That email doesn't look right. Double-check, or leave it blank.")
    for q in QUESTIONS:
        if q["id"] == "q10":
            continue
        if answers.get(q["id"]) in (None, ""):
            errs.append(f"Please answer: {q['text']}")
    return errs


def render_result(
    company_name: str,
    score: dict,
    ai: dict,
) -> None:
    tier = score["tier"]
    color = tier["color"]
    display_name = (company_name or "").strip() or "Your Scorecard"
    safe_company = _no_math(display_name)

    st.markdown(
        "<div class='bmt-tagline'>Your scorecard</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"# {safe_company}")

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

    # Plain-English action plan (grade-6, DO / WHY / HOW playbook / RECOVERY)
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

    mailto_company = company_name or "(company name not provided)"
    subject = quote(f"Discovery call · Scorecard result · {mailto_company}")
    body = quote(
        f"Hi Michael,\n\n"
        f"I just ran the Margin Leak Scorecard for {mailto_company}.\n"
        f"My score was {score['normalized']}/100 ({tier['name']}).\n\n"
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
            f"an error. `{ai['_error']}`. Your results are still saved for follow-up."
        )

    st.write("")
    if st.button("Start over", key="restart"):
        for k in ("result", "company_name", "email"):
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

if "result" in st.session_state:
    render_result(
        st.session_state["company_name"],
        st.session_state["result"]["score"],
        st.session_state["result"]["ai"],
    )
else:
    render_landing()
    submitted, payload = render_form()

    if submitted:
        errs = validate(payload["company_name"], payload["email"], payload["answers"])
        if errs:
            for e in errs:
                st.error(e)
        else:
            with st.spinner("Crunching your answers..."):
                score = compute_score(payload["answers"])
                ai = call_claude(payload["answers"], score, payload["company_name"])

            try:
                write_lead_row(
                    payload["company_name"],
                    payload["email"],
                    score,
                    payload["answers"],
                )
            except Exception as e:
                st.warning(f"Couldn't save lead row. {e}")

            st.session_state["company_name"] = payload["company_name"]
            st.session_state["email"] = payload["email"]
            st.session_state["result"] = {
                "score": score,
                "ai": ai,
                "answers": payload["answers"],
            }
            # Rerun switches to results-only view (clears form/landing cleanly).
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

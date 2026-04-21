"""Scoring algorithm, question definitions, and Claude Opus call for the Margin Leak Scorecard."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from anthropic import Anthropic


# ---------------------------------------------------------------------------
# Question definitions — keep wording identical to the build brief.
# ---------------------------------------------------------------------------

SCALE_1_5_LABELS = {
    "q1": {
        1: "Never",
        2: "After close-out only",
        3: "Monthly",
        4: "Weekly",
        5: "Daily",
    },
    "q2": {
        1: "Almost never. I trust the team",
        2: "Rarely",
        3: "About half the time",
        4: "Most of them",
        5: "Every single one",
    },
    "q3": {
        1: "Don't track",
        2: "Spreadsheets after the fact",
        3: "Timesheets reviewed monthly",
        4: "Real-time digital tracking",
        5: "Integrated software with alerts",
    },
    "q4": {
        1: "Never",
        2: "More than a year ago",
        3: "6-12 months ago",
        4: "Within the last 6 months",
        5: "After every job",
    },
    "q5": {
        1: "Every job",
        2: "Most jobs",
        3: "Sometimes",
        4: "Rarely",
        5: "Never. We catch them early",
    },
    "q7": {
        1: "Not confident at all",
        2: "Somewhat unsure",
        3: "Mostly confident",
        4: "Very confident",
        5: "100% confident",
    },
}

QUESTIONS = [
    {
        "id": "q1",
        "text": "How often do you review budget vs actual on active projects?",
        "kind": "scale_1_5",
    },
    {
        "id": "q2",
        "text": "When change orders get approved, how consistently do you personally review them before sign-off?",
        "kind": "scale_1_5",
    },
    {
        "id": "q3",
        "text": "How do you currently track field labor hours against estimate?",
        "kind": "scale_1_5",
    },
    {
        "id": "q4",
        "text": "When was the last time you ran a full post-mortem on a closed job?",
        "kind": "scale_1_5",
    },
    {
        "id": "q5",
        "text": "How often do you discover cost overruns only at close-out?",
        "kind": "scale_1_5",
    },
    {
        "id": "q6",
        "text": "Do schedule overlaps or double-bookings cost you money on most jobs?",
        "kind": "yes_no_sometimes",
    },
    {
        "id": "q7",
        "text": "How confident are you that every approved scope change made it into the final invoice?",
        "kind": "scale_1_5",
    },
    {
        "id": "q8",
        "text": "Roughly how many active projects does your company run simultaneously?",
        "kind": "active_projects",
    },
    {
        "id": "q9",
        "text": "Estimated annual revenue range?",
        "kind": "revenue_tier",
    },
    {
        "id": "q10",
        "text": "What's your biggest cost pain right now?",
        "kind": "free_text",
    },
]

ACTIVE_PROJECT_OPTIONS = ["1-3", "4-7", "8-15", "16+"]
REVENUE_TIERS = ["$5M-$15M", "$15M-$50M", "$50M-$150M", "$150M-$500M", "$500M+"]
SCHEDULE_OVERLAP_OPTIONS = ["Yes", "Sometimes", "No"]

REVENUE_DOLLAR_HINTS = {
    "$5M-$15M": "$50K-$200K annually",
    "$15M-$50M": "$200K-$800K annually",
    "$50M-$150M": "$800K-$3M annually",
    "$150M-$500M": "$3M-$15M annually",
    "$500M+": "seven to eight figures annually",
}

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

TIERS = [
    {
        "min": 80,
        "max": 100,
        "name": "Tight Ship",
        "color": "#10b981",
        "emoji_label": "GREEN",
        "blurb": "You're running lean. There's still money to find, but you're already ahead of most.",
    },
    {
        "min": 60,
        "max": 79,
        "name": "Some Leakage",
        "color": "#eab308",
        "emoji_label": "YELLOW",
        "blurb": "You've got the basics, but there are specific places margin is walking out the door.",
    },
    {
        "min": 40,
        "max": 59,
        "name": "Significant Leakage",
        "color": "#f97316",
        "emoji_label": "ORANGE",
        "blurb": "You're bleeding margin in multiple areas. The good news: it's recoverable.",
    },
    {
        "min": 0,
        "max": 39,
        "name": "Critical Leakage",
        "color": "#ef4444",
        "emoji_label": "RED",
        "blurb": "This is serious. You're losing six figures or more annually and don't have visibility into where.",
    },
]

MAX_RAW_SCORE = 35


def _score_q6(answer: str) -> int:
    mapping = {"Yes": 1, "Sometimes": 3, "No": 5}
    return mapping.get(answer, 3)


def compute_score(answers: dict[str, Any]) -> dict[str, Any]:
    """Return raw, normalized, and tier info for a full answer set.

    Scoring (per brief):
      - q1, q3, q4, q5, q7 scored directly as 1-5
      - q2 is inverted: (6 - raw) — heavy personal review on every CO flags a
        systems gap, not a tight operation
      - q6: Yes=1, Sometimes=3, No=5
      - q8, q9, q10 do not score — they inform AI output only
    """
    direct = ["q1", "q3", "q4", "q5", "q7"]
    raw = sum(int(answers.get(q, 3)) for q in direct)
    raw += 6 - int(answers.get("q2", 3))  # inverted
    raw += _score_q6(answers.get("q6", "Sometimes"))

    raw = max(0, min(MAX_RAW_SCORE, raw))
    normalized = round((raw / MAX_RAW_SCORE) * 100)
    tier = tier_for_score(normalized)

    return {
        "raw": raw,
        "normalized": normalized,
        "tier": tier,
    }


def tier_for_score(score: int) -> dict[str, Any]:
    for t in TIERS:
        if t["min"] <= score <= t["max"]:
            return t
    return TIERS[-1]


# ---------------------------------------------------------------------------
# Claude prompt + call
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a senior construction cost recovery analyst at Black Mountain Technologies. You review a contractor's self-assessment answers and produce a personalized margin leak breakdown.

VOICE: Direct, contractor-to-contractor, no corporate jargon. Write like a GC owner talking to another GC owner. Use "you" not "your organization." Swearing is fine if it fits.

DO NOT:
- RESTATE OR SUMMARIZE THE CONTRACTOR'S ANSWERS BACK TO THEM. They already know what they answered. They wrote the answers 10 seconds ago. Any line that could be replaced with "here's what you told me" must be rewritten as insight, not recap. This is the #1 failure mode of this type of output.
- Use the word "tool" anywhere in your output. Call it "AI" or "software" instead. A tool is an accessory. The AI is infrastructure.
- Use vendor words: "platform", "system", "engine", "solution" (as a generic noun). These read as SaaS.
- Use buzzwords: "synergy", "leverage", "unlock value", "game-changing", "robust", "scalable", "seamless"
- Use em dashes (—) anywhere in your output. Use periods or colons instead. Humans do not write em dashes.
- Use hedges: "may", "might", "could potentially", "is designed to"
- Recommend the paid software explicitly. The CTA handles that separately.

DO:
- Call out specific answer patterns they gave. Example: "You answered 2 on post-mortems. That's where the money hides."
- Reference Canadian construction market realities (weather, subcontractor shortages, material escalation)
- Use their revenue tier to estimate a realistic dollar-range leak (industry benchmarks: 3-8% margin leak on typical multi-trade ICI GC portfolios)
- For every leak, tie it to a specific question number AND include a concrete "if this keeps up, here's what happens on your jobs" outcome.
- Adjust tone and dollar claim by revenue tier:
  - $5M-$15M: "a few thousand here and there adds up to $50K-$200K annually"
  - $15M-$50M: "$200K-$800K annually in recoverable margin"
  - $50M-$150M: "$800K-$3M annually"
  - $150M-$500M: "$3M-$15M annually"
  - $500M+: "seven to eight figures annually"

OUTPUT: Return ONLY valid JSON. No markdown fences, no prose before or after. The JSON schema:
{
  "headline": "ONE sentence, 12 words or fewer. A provocative hook that names the single biggest weakness their answers reveal, or the pattern that typically compounds worst on shops their size. Not a restatement of their answers. Think of it as the subject line of an email they'd actually open.",
  "score_summary": "2 short sentences MAX. DO NOT summarize their answers back to them. Give them ONE diagnostic insight they did not already have: where the weakest link in their operation is, what typically breaks first on shops like theirs, how their answer pattern stacks against peers their size, or which leak compounds worst given their specific mix. Read like a veteran GC telling another GC what they see that the other GC is too close to notice. Diagnostic, not descriptive.",
  "estimated_dollar_range": "a specific dollar range based on revenue tier, for example '$200K-$800K annually'",
  "plain_english_plan": [
    {
      "do": "One short sentence. Verb-first action they can start THIS WEEK.",
      "why": "ONE short sentence. Tie to their specific answer. Plain English. No more than 20 words.",
      "how": ["exactly 3 concrete execution steps", "each step is a short grade-6 sentence", "Monday / week 2 / how they measure it worked"]
    }
  ]
}

Rules for plain_english_plan specifically:
- 3 to 5 items total.
- Grade-6 reading level. If a 12-year-old wouldn't follow it, rewrite it.
- No jargon. Say "look at every job's budget every week" not "weekly cost variance review". Say "write down what went wrong and what went right" not "post-mortem". Say "money you should have kept" not "margin erosion".
- Each "do" starts with a verb: Track, Write, Check, Set, Call, Schedule, Reconcile, Stop, Start.
- Each "why" is ONE sentence, max 20 words, must reference a specific answer they gave.
- "how" is exactly 3 steps. Concrete. Action-oriented. DO NOT include "talk to us", "book a call with us", "reach out", or any pitch language. The HOW is pure execution advice. The separate discovery-call CTA button on the page handles the pitch.
- No "recovery" field. The top-level estimated_dollar_range covers the dollar anchor for the whole scorecard. Do not estimate per-item dollar recovery.

Remember: zero em dashes. Zero uses of "tool", "platform", "system", "engine", or "solution" as generic nouns.
"""


def _human_readable_answers(answers: dict[str, Any]) -> str:
    lines: list[str] = []
    for q in QUESTIONS:
        qid = q["id"]
        val = answers.get(qid)
        if val is None or val == "":
            continue
        if q["kind"] == "scale_1_5":
            label = SCALE_1_5_LABELS.get(qid, {}).get(int(val), str(val))
            lines.append(f"- {q['text']}\n  Answer: {val}/5 ({label})")
        elif q["kind"] == "yes_no_sometimes":
            lines.append(f"- {q['text']}\n  Answer: {val}")
        elif q["kind"] == "active_projects":
            lines.append(f"- {q['text']}\n  Answer: {val} simultaneous projects")
        elif q["kind"] == "revenue_tier":
            lines.append(f"- {q['text']}\n  Answer: {val}")
        elif q["kind"] == "free_text":
            lines.append(f"- {q['text']}\n  Answer: {val or '(not provided)'}")
    return "\n".join(lines)


def build_user_message(answers: dict[str, Any], score: dict[str, Any], company_name: str) -> str:
    tier = score["tier"]
    dollar_hint = REVENUE_DOLLAR_HINTS.get(answers.get("q9", ""), "")
    return f"""Company: {company_name}
Overall Score: {score['normalized']}/100
Tier: {tier['name']} ({tier['emoji_label']}). {tier['blurb']}
Revenue dollar-range hint for this tier: {dollar_hint}

Their answers:
{_human_readable_answers(answers)}

Write the personalized breakdown as valid JSON per the schema. Tie every leak directly to specific answers above. Be specific, punchy, and Canadian-construction-aware. Zero em dashes."""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    # ```json ... ``` or ``` ... ```
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return text


def _fallback_result(tier: dict[str, Any], raw_text: str | None = None) -> dict[str, Any]:
    return {
        "headline": tier["blurb"],
        "score_summary": (
            "We couldn't render the full AI breakdown this time. The short version: "
            + tier["blurb"]
            + " Book a 15-minute discovery call for a proper forensic read."
        ),
        "estimated_dollar_range": "",
        "plain_english_plan": [
            {
                "do": "Track labor hours every single day on every active job.",
                "why": "You log hours in a spreadsheet after the week is done, so you find out about a budget blow a week too late to fix it.",
                "how": [
                    "Pick your 2 biggest active jobs to start.",
                    "Give each foreman a phone or tablet to log hours at the end of every shift.",
                    "Have the PM review the daily totals every morning by 9 AM.",
                ],
            },
            {
                "do": "Sit down for 30 minutes after every closed job and write what cost more than planned.",
                "why": "You have not done this in over a year, so the same leak keeps showing up on the next job.",
                "how": [
                    "Block 30 minutes on your calendar the day after every substantial completion.",
                    "Pull the final budget vs actual from your accountant before the meeting.",
                    "Write down the top 3 overruns, the root cause of each, and share with PMs before the next bid.",
                ],
            },
            {
                "do": "Before you sign any change order, write down which invoice it will go on.",
                "why": "Change orders get approved on site and forgotten. Scope built, invoice never raised. Pure margin, gone.",
                "how": [
                    "Add one line to your CO form: 'Invoice number for billing.'",
                    "Require the PM to fill it in before signing.",
                    "Have accounting reconcile every CO to its invoice monthly.",
                ],
            },
        ],
        "_raw_fallback": raw_text or "",
    }


def call_claude(answers: dict[str, Any], score: dict[str, Any], company_name: str) -> dict[str, Any]:
    """Call Claude Opus 4.7 and return a parsed result dict.

    Returns a fallback dict if the API key is missing or the call/parse fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        result = _fallback_result(score["tier"], raw_text="ANTHROPIC_API_KEY not set.")
        result["_error"] = "ANTHROPIC_API_KEY not set in environment."
        return result

    model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7").strip()
    client = Anthropic(api_key=api_key)
    user_msg = build_user_message(answers, score, company_name)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=3500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = response.content[0].text if response.content else ""
    except Exception as e:
        result = _fallback_result(score["tier"], raw_text=str(e))
        result["_error"] = f"Anthropic API error: {e}"
        return result

    cleaned = _strip_code_fences(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        result = _fallback_result(score["tier"], raw_text=text)
        result["_error"] = f"JSON parse error: {e}"
        return result

    # Sanity-check required keys; fill missing ones rather than blowing up.
    required = ["headline", "score_summary", "estimated_dollar_range", "plain_english_plan"]
    for key in required:
        if key not in parsed:
            parsed[key] = _fallback_result(score["tier"])[key]
    if not isinstance(parsed.get("plain_english_plan"), list):
        parsed["plain_english_plan"] = _fallback_result(score["tier"])["plain_english_plan"]
    return parsed

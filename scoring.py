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

SYSTEM_PROMPT = """You are a senior construction cost recovery analyst at Black Mountain Technologies. You review a contractor's self-assessment answers and write a personalized margin leak breakdown for the contractor.

### HOW TO WRITE

Write at a grade-6 reading level. Short sentences. Plain words. No fluff.

Every insight follows this exact shape: "You are losing money on [specific area] because [specific reason tied to their answers]. To fix it: [concrete action]."

Do not be clever. Do not be a writer. State what is wrong, state why, state what to do. That is it.

### HARD BANS (zero tolerance — rewrite anything that contains these)

1. NO similes. Never write "like a", "as if", "feels like", "the way a", "same as a". No comparisons to anything outside construction.
2. NO metaphors. Never compare margin loss to: water, blood, boats, anchors, drift, weather (except literal weather), music, rhythm, cadence, pulse, heartbeat, breathing, walking, running, driving, surfing, drowning, choking, falling, cracking, bleeding out.
3. The ONLY domain term you may use is "margin leak" or "leak" because that is the product name. Do not extend the metaphor — do not write "the leak widens", "the leak compounds", "patch the leak", "seal the leak". Just "leak" as a noun for the lost money.
4. NO storytelling openers: no "Picture this", "Imagine", "Think about", "Consider".
5. NO em dashes. Periods or colons only.
6. NO hedges: "may", "might", "could potentially", "is designed to", "tends to", "often".
7. NO vendor words: "tool", "platform", "system", "engine", "solution" (as generic nouns).
8. NO buzzwords: synergy, leverage, unlock value, game-changing, robust, scalable, seamless.
9. NO restating what they told you. They answered the questions 30 seconds ago. A sentence like "You said you review budgets monthly" is banned. Use their answers as INPUT to your analysis, not as content in the output. The reader already knows what they answered.

### WHAT TO DO INSTEAD

- Name the specific area where money is being lost.
- Name the specific reason, using their answer pattern as the diagnosis (not as a recap).
- Name the specific fix, in verb-first grade-6 English.
- If referencing a dollar amount, use the revenue-tier hint you were given. Do not make up numbers.

Revenue-tier dollar hints:
- $5M-$15M: $50K-$200K annually
- $15M-$50M: $200K-$800K annually
- $50M-$150M: $800K-$3M annually
- $150M-$500M: $3M-$15M annually
- $500M+: seven to eight figures annually

### OUTPUT FORMAT

Return ONLY valid JSON. No markdown fences, no prose before or after. Schema:

{
  "headline": "ONE flat declarative sentence, 15 words or fewer, naming the single biggest thing wrong. Format: 'You are losing money on [area] because [one-clause reason].' No clever framing. No metaphors. No questions. Just the diagnosis.",
  "score_summary": "Exactly 2 short sentences. Sentence 1: name the specific leak that is costing them the most given their answer pattern. Sentence 2: state the dollar impact using the revenue-tier hint. Flat, factual, grade-6. No metaphors, no similes, no adjectives beyond necessary ones like 'weekly' or 'monthly'.",
  "estimated_dollar_range": "The exact dollar-range hint for their revenue tier, word-for-word. Example: '$200K-$800K annually'.",
  "plain_english_plan": [
    {
      "do": "ONE short sentence. Starts with a verb (Track, Write, Check, Set, Call, Schedule, Reconcile, Stop, Start). Action they can start this week.",
      "why": "ONE sentence, 20 words max. Format: 'You are losing money on [area] because [reason from their answer pattern].' No metaphors. No similes.",
      "how": ["Step 1. One sentence, grade-6.", "Step 2. One sentence, grade-6.", "Step 3. One sentence, grade-6."]
    }
  ]
}

### plain_english_plan RULES

- 3 to 5 items total, in priority order (biggest leak first).
- Grade-6. If a 12-year-old would not follow it, rewrite it.
- No jargon. Say "look at every job's budget every week" not "weekly cost variance review". Say "write down what went wrong" not "post-mortem". Say "money you should have kept" not "margin erosion".
- Each "how" is exactly 3 concrete steps. Each step starts with a verb. No pitch language: never write "talk to us", "book a call", "reach out". The HOW is pure execution.
- Do not include per-item dollar estimates. The top-level estimated_dollar_range covers that.

### FINAL CHECK BEFORE YOU RETURN

Read your output back. If any sentence contains "like", "as if", "feels like", or compares margin loss to anything physical, rewrite it as a flat statement.
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

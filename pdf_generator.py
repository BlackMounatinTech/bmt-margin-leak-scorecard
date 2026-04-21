"""PDF export for the Margin Leak Scorecard result.

Palette matches BMT Design System v3.0 (canonical: BMT_Shared/DESIGN_SYSTEM.md):
  - Dark navy cover band (matches --bg-sidebar #0d1321)
  - Light body pages for print readability
  - Orange #ff6b35 brand accent throughout
  - Blue #3b82f6 for info/active, RAG for status (tier color)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos


# BMT v3.0 palette — see /Users/michaelmackrell/BMT_Shared/DESIGN_SYSTEM.md
NAVY_DEEP = (13, 19, 33)       # #0d1321 — --bg-sidebar
NAVY_MID = (26, 31, 46)        # #1a1f2e — --bg-card-alt
ORANGE = (255, 107, 53)        # #ff6b35 — --brand-accent
ORANGE_DARK = (204, 72, 0)     # darker orange for text-on-tint
ORANGE_BG = (255, 243, 237)    # soft orange tint for print callout bg
BLUE = (59, 130, 246)          # #3b82f6 — --active-border
RAG_GREEN = (34, 197, 94)      # #22c55e
RAG_YELLOW = (245, 158, 11)    # #f59e0b
RAG_RED = (239, 68, 68)        # #ef4444
WHITE = (255, 255, 255)
TEXT_PRIMARY = (15, 23, 42)    # dark heading on light body
TEXT_BODY = (71, 85, 105)      # body on light
TEXT_SECONDARY = (100, 116, 139)
TEXT_TERTIARY = (148, 163, 184)
BORDER = (226, 232, 240)
BG_ALT = (248, 250, 252)


def _tier_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


class ScorecardPDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_fill_color(*NAVY_DEEP)
        self.rect(0, 0, 210, 12, "F")
        self.set_fill_color(*ORANGE)
        self.rect(0, 12, 210, 0.6, "F")
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*WHITE)
        self.set_xy(12, 3.5)
        self.cell(0, 6, "MARGIN LEAK SCORECARD   BLACK MOUNTAIN TECHNOLOGIES",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(6)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*TEXT_TERTIARY)
        self.cell(0, 8,
                  f"Page {self.page_no()}/{{nb}}    Confidential. Prepared for internal review.",
                  align="C")


def _safe(text: str) -> str:
    """fpdf2 core fonts are latin-1. Replace common unicode with ASCII-ish."""
    if not isinstance(text, str):
        text = str(text)
    replacements = {
        "–": "-", "—": "-",
        "‘": "'", "’": "'", "“": '"', "”": '"',
        "…": "...", "•": "*",
        " ": " ",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def generate_scorecard_pdf(
    company_name: str,
    email: str,
    score: dict[str, Any],
    ai_result: dict[str, Any],
    answers: dict[str, Any],
) -> bytes:
    pdf = ScorecardPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    tier = score["tier"]
    tier_rgb = _tier_rgb(tier["color"])

    # ----- Cover band (dark navy with emerald accent) -----
    pdf.set_fill_color(*NAVY_DEEP)
    pdf.rect(0, 0, 210, 70, "F")
    pdf.set_fill_color(*ORANGE)
    pdf.rect(0, 70, 210, 1.5, "F")

    pdf.set_text_color(*ORANGE)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(14, 14)
    pdf.cell(0, 5, _safe("BLACK MOUNTAIN TECHNOLOGIES"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_xy(14, 22)
    pdf.cell(0, 12, _safe("Margin Leak Scorecard"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(226, 232, 240)
    pdf.set_xy(14, 40)
    pdf.cell(0, 6, _safe(f"Prepared for: {company_name}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_xy(14, 47)
    pdf.cell(0, 6, _safe(f"Contact: {email}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_xy(14, 54)
    pdf.cell(0, 6, _safe(f"Date: {datetime.now().strftime('%B %d, %Y')}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ----- Score block (light body) -----
    pdf.set_y(80)
    pdf.set_text_color(*TEXT_SECONDARY)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 5, _safe("OVERALL SCORE"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 48)
    pdf.set_text_color(*TEXT_PRIMARY)
    pdf.cell(60, 18, f"{score['normalized']}", new_x=XPos.END, new_y=YPos.TOP)

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*tier_rgb)
    pdf.set_xy(pdf.get_x(), pdf.get_y() + 4)
    pdf.cell(0, 7, _safe(tier["name"].upper()),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXT_BODY)
    pdf.set_x(74)
    pdf.multi_cell(120, 5.2, _safe(tier["blurb"]))
    pdf.ln(5)

    # ----- Headline -----
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*TEXT_PRIMARY)
    pdf.multi_cell(0, 7, _safe(ai_result.get("headline", "")))
    pdf.ln(1)

    # ----- Score summary -----
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*TEXT_BODY)
    pdf.multi_cell(0, 6, _safe(ai_result.get("score_summary", "")))
    pdf.ln(4)

    # ----- Top 3 Leaks -----
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*TEXT_SECONDARY)
    pdf.cell(0, 5, _safe("TOP 3 LEAK AREAS"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)

    leaks = ai_result.get("top_3_leaks", []) or []
    for i, leak in enumerate(leaks[:3], start=1):
        y_start = pdf.get_y()

        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*ORANGE)
        pdf.set_x(20)
        pdf.cell(0, 5, _safe(f"LEAK  {i:02d}"),
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_text_color(*TEXT_PRIMARY)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(20)
        pdf.multi_cell(0, 6, _safe(leak.get("title", "")))

        pdf.set_x(20)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*TEXT_BODY)
        pdf.multi_cell(0, 5.3, _safe(leak.get("what_it_means", "")))

        pdf.set_x(20)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*ORANGE_DARK)
        pdf.cell(12, 5.3, _safe("FIX  "),
                 new_x=XPos.END, new_y=YPos.TOP)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5.3, _safe(leak.get("fix_hint", "")))
        pdf.ln(3)

        y_end = pdf.get_y()
        pdf.set_draw_color(*ORANGE)
        pdf.set_line_width(1.2)
        pdf.line(14, y_start + 0.5, 14, y_end - 2)
        pdf.set_line_width(0.2)

    # ----- Estimated dollar range callout (amber) -----
    est = ai_result.get("estimated_dollar_range", "")
    if est:
        pdf.ln(2)
        y_start = pdf.get_y()
        pdf.set_fill_color(*ORANGE_BG)
        pdf.rect(14, y_start, 182, 22, "F")
        pdf.set_fill_color(*ORANGE)
        pdf.rect(14, y_start, 3, 22, "F")

        pdf.set_xy(22, y_start + 3)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*ORANGE_DARK)
        pdf.cell(0, 5, _safe("ESTIMATED MARGIN LEAK"),
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(22, y_start + 10)
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(*TEXT_PRIMARY)
        pdf.cell(0, 8, _safe(est), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_y(y_start + 24)

    # ----- One-line closer -----
    closer = ai_result.get("one_line_closer", "")
    if closer:
        pdf.ln(2)
        pdf.set_font("Helvetica", "BI", 12)
        pdf.set_text_color(*TEXT_PRIMARY)
        pdf.multi_cell(0, 6, _safe(closer))
        pdf.ln(2)

    # ----- CTA -----
    pdf.ln(2)
    pdf.set_draw_color(*ORANGE)
    pdf.set_line_width(0.4)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ORANGE)
    pdf.cell(0, 6, _safe("BOOK A 15-MINUTE WALKTHROUGH"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXT_BODY)
    pdf.multi_cell(0, 5.5, _safe(
        "Michael Mackrell, Black Mountain Technologies.\n"
        "Email: michael@blackmountaintechnologies.ca"
    ))

    # ----- Appendix: answers -----
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*TEXT_PRIMARY)
    pdf.cell(0, 8, _safe("Your Answers"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXT_BODY)
    for key, label in [
        ("q1", "Budget vs actual review cadence"),
        ("q2", "Personal review of change orders"),
        ("q3", "Field labor hour tracking"),
        ("q4", "Last job post-mortem"),
        ("q5", "Discovering overruns at close-out"),
        ("q6", "Schedule overlaps cost money"),
        ("q7", "Confidence scope changes hit invoice"),
        ("q8", "Simultaneous active jobs"),
        ("q9", "Estimated annual revenue"),
        ("q10", "Biggest cost pain right now"),
    ]:
        val = answers.get(key, "")
        if val == "" or val is None:
            continue
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*TEXT_PRIMARY)
        pdf.multi_cell(0, 5.5, _safe(label))
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*TEXT_BODY)
        pdf.set_x(18)
        pdf.multi_cell(0, 5.5, _safe(f"- {val}"))
        pdf.ln(1)

    # Export
    output = pdf.output(dest="S")
    if isinstance(output, (bytes, bytearray)):
        return bytes(output)
    return bytes(output, "latin-1") if isinstance(output, str) else bytes(output)

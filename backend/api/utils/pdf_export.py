"""PDF export utility for trend reports."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))

_CJK_FONT = "HYSMyeongJo-Medium"


def generate_trends_pdf(rows: list[dict[str, Any]]) -> bytes:
    """Generate a PDF report from trend data rows.

    Args:
        rows: List of trend dicts with keys: title, category, score,
              early_trend_score, keywords, created_at.

    Returns:
        PDF file content as bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "KoreanTitle",
        parent=styles["Title"],
        fontName=_CJK_FONT,
        fontSize=16,
        leading=20,
    )
    cell_style = ParagraphStyle(
        "KoreanCell",
        fontName=_CJK_FONT,
        fontSize=8,
        leading=10,
        wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "HeaderCell",
        fontName=_CJK_FONT,
        fontSize=9,
        leading=11,
        textColor=colors.white,
    )

    elements: list[Any] = []

    now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    elements.append(Paragraph("TrendScope Trend Report", title_style))
    elements.append(Spacer(1, 3 * mm))
    elements.append(
        Paragraph(
            f"Generated: {now_str} &nbsp; | &nbsp; Total: {len(rows)} trends",
            ParagraphStyle("Meta", fontName=_CJK_FONT, fontSize=9, textColor=colors.grey),
        )
    )
    elements.append(Spacer(1, 6 * mm))

    headers = ["#", "Title", "Category", "Score", "Keywords", "Date"]
    header_row = [Paragraph(h, header_style) for h in headers]

    data = [header_row]
    for idx, row in enumerate(rows, 1):
        kw_list = row["keywords"] if row["keywords"] else []
        keywords = "|".join(kw_list)
        created_at = row["created_at"]
        created = created_at.strftime("%Y-%m-%d") if created_at else ""
        score = float(row["score"])
        data.append(
            [
                str(idx),
                Paragraph(str(row["title"]), cell_style),
                Paragraph(str(row["category"]), cell_style),
                f"{score:.1f}",
                Paragraph(keywords[:80], cell_style),
                created,
            ]
        )

    col_widths = [8 * mm, 70 * mm, 22 * mm, 16 * mm, 40 * mm, 22 * mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), _CJK_FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (3, 0), (3, -1), "CENTER"),
                ("ALIGN", (5, 0), (5, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    return buf.getvalue()

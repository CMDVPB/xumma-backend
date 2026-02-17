import os
import shutil
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    Spacer,
)
import re
from html import unescape
import pdfkit
from django.template.loader import render_to_string

from axx.translations import TRANSLATIONS, VALID_DOC_TYPES
from axx.utils import resolve_inv_type_title


def get_pdfkit_config():
    wkhtmltopdf_path = os.getenv("WKHTMLTOPDF_PATH")

    # 1️⃣ If ENV is set, trust it
    if wkhtmltopdf_path:
        if not os.path.exists(wkhtmltopdf_path):
            raise RuntimeError(
                f"wkhtmltopdf not found at '{wkhtmltopdf_path}'."
            )
        return pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

    # 2️⃣ Otherwise, resolve from PATH (Docker/Linux)
    resolved = shutil.which("wkhtmltopdf")
    if resolved:
        return pdfkit.configuration(wkhtmltopdf=resolved)

    # 3️⃣ Nothing worked
    raise RuntimeError(
        "wkhtmltopdf not found. Install it or set WKHTMLTOPDF_PATH."
    )


def html_to_rl_paragraphs(html: str):
    """
    Convert rich HTML into a list of ReportLab-safe paragraph strings.
    """
    if not html:
        return ["-"]

    text = unescape(html)

    # Normalize line breaks
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)

    # Headings -> bold text
    text = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>",
                  r"\n<b>\1</b>\n", text, flags=re.IGNORECASE | re.DOTALL)

    # Strong -> b
    text = re.sub(r"<strong[^>]*>", "<b>", text, flags=re.IGNORECASE)
    text = re.sub(r"</strong>", "</b>", text, flags=re.IGNORECASE)

    # Lists -> dash lines
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?ul[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Horizontal rules -> separator
    text = re.sub(r"<hr[^>]*>", "\n----------------------\n",
                  text, flags=re.IGNORECASE)

    # Remove all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text.split("\n\n")

###### START PDF GENERATORS ######


def generate_order_pdf(order_data: dict, lang: str, doc_type: str) -> bytes:

    print('GENERATE ORDER PDF', lang, doc_type)

    html = render_to_string(
        "pdf/order_contract.html",
        {
        "order": order_data,
        "signatures": order_data.get("signatures"),
    },
    )

    pdf = pdfkit.from_string(
        html,
        False,
        configuration=get_pdfkit_config(),
        options={
            "page-size": "A4",
            "margin-top": "20mm",
            "margin-bottom": "20mm",
            "margin-left": "20mm",
            "margin-right": "20mm",
            "encoding": "UTF-8",
        },
    )

    return pdf


def generate_proforma_pdf(proforma_data: dict, lang: str, inv_type: str) -> bytes:
    buffer = BytesIO()

    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])

    if inv_type not in VALID_DOC_TYPES:
        inv_type = "proforma"

    print('DOC TYPE TITLE', proforma_data.get("title"))

    title = (t["titles"].get(proforma_data.get("title"), t["titles"]["proforma"])
             )

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12,
        leftMargin=28,
        topMargin=28,
        bottomMargin=28,
    )

    GRID = [
        doc.width * 0.35,
        doc.width * 0.10,
        doc.width * 0.18,
        doc.width * 0.30,
    ]

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="InvoiceTitle",
        fontSize=16,
        fontName="Helvetica-Bold",
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceSectionTitle",
        fontSize=10,
        fontName="Helvetica-Bold",
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceTitleNumber",
        fontSize=14,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceText",
        fontSize=10,
        spaceAfter=2,
    ))

    elements = []

    # ======================
    # TITLE
    # ======================
    elements.append(
        Paragraph(title,
                  styles["InvoiceTitle"])
    )

    elements.append(Spacer(1, 12))

    # ======================
    # FROM + META
    # ======================
    from_block = [
        Paragraph(f"<b>{t['seller']}:</b>", styles["InvoiceSectionTitle"]),
        Paragraph(proforma_data["from"]["name"], styles["InvoiceText"]),
    ]
    for line in proforma_data["from"]["address"]:
        from_block.append(Paragraph(line, styles["InvoiceText"]))

    from_block.append(Paragraph(
        f"<b>{t['iban']}:</b> {proforma_data['from']['iban']}", styles["InvoiceText"])),

    meta = proforma_data["meta"]
    meta_block = [
        Paragraph(
            f"<b>{t['invoice_number']}</b> {meta['number']}", styles["InvoiceTitleNumber"]),
        Paragraph(f"<b>{t['date']}:</b> {meta['date']}",
                  styles["InvoiceText"]),
        Paragraph(f"<b>{t['due_date']}:</b> {meta['due_date']}",
                  styles["InvoiceText"]),
        Paragraph(
            f"<b>{t['customer_ref']}:</b> {meta['customer_ref']}", styles["InvoiceText"]),
        Paragraph(f"<b>{t['currency']}:</b> {meta['currency']}",
                  styles["InvoiceText"]),
    ]

    header_table = Table(
        [[from_block, meta_block]],
        colWidths=[doc.width * 0.60, doc.width * 0.40],
        hAlign="LEFT",
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 12))

    # ======================
    # TO
    # ======================
    elements.append(
        Paragraph(f"<b>{t['buyer']}:</b>", styles["InvoiceSectionTitle"]))
    elements.append(
        Paragraph(proforma_data["to"]["name"], styles["InvoiceText"]))
    for line in proforma_data["to"]["address"]:
        elements.append(Paragraph(line, styles["InvoiceText"]))
    elements.append(Spacer(1, 12))

    # ======================
    # ITEMS TABLE
    # ======================
    table_data = [[
        t["service"],
        t["quantity"],
        t["unit_price"],
        t["amount"]
    ]]

    for row in proforma_data["rows"]:
        table_data.append([
            row["description"],
            row["quantity"],
            row["rate"],
            row["amount"],
        ])

    items_table = Table(table_data, colWidths=GRID, hAlign="LEFT")
    items_table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(items_table)
    elements.append(Spacer(1, 24))

    # ======================
    # TOTALS
    # ======================
    totals_data = []
    for total in proforma_data["totals"]:
        totals_data.append([
            "",
            "",
            total["label"],
            total["amount"],
        ])

    totals_table = Table(totals_data, colWidths=GRID, hAlign="LEFT")
    totals_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("FONT", (2, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (2, -1), (-1, -1), 0.5, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    elements.append(totals_table)
    elements.append(Spacer(1, 16))

    # ======================
    # NOTES
    # ======================
    elements.append(Spacer(1, 24))
    line_width = GRID[0] + GRID[1] + GRID[2] + GRID[3]

    line = Table([[""]], colWidths=[line_width], hAlign="LEFT")
    line.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, -1), 0.25, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(line)

    elements.append(Paragraph(t["notes"], styles["InvoiceSectionTitle"]))
    elements.append(
        Paragraph(proforma_data.get("notes") or "-", styles["InvoiceText"])
    )

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def generate_act_pdf(proforma_data: dict, lang: str, inv_type: str) -> bytes:
    buffer = BytesIO()

    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])

    print('def generate_act_pdf:', inv_type)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12,
        leftMargin=28,
        topMargin=28,
        bottomMargin=28,
    )

    GRID = [
        doc.width * 0.35,
        doc.width * 0.10,
        doc.width * 0.18,
        doc.width * 0.32,
    ]

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ActTitleCentered",
        fontSize=16,
        fontName="Helvetica-Bold",
        spaceAfter=12,
        alignment=1,
    ))
    styles.add(ParagraphStyle(
        name="ActSubtitleCentered",
        fontSize=12,
        fontName="Helvetica-Bold",
        spaceAfter=8,
        alignment=1,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceSectionTitle",
        fontSize=10,
        fontName="Helvetica-Bold",
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceTitleNumber",
        fontSize=14,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceText",
        fontSize=10,
        spaceAfter=2,
    ))

    elements = []

    # ======================
    # TITLE
    # ======================
    elements.append(
        Paragraph(t["act_title"],
                  styles["ActTitleCentered"])
    )

    elements.append(Spacer(1, 6))

    # ======================
    # META
    # ======================

    meta = proforma_data["meta"]

    meta_text = (
        f"<b>{t['nr']}:</b> {meta['number']} "
        f"<b>{t['from']}:</b> {meta['date']}"
    )

    meta_block = [
        Paragraph(meta_text, styles["ActSubtitleCentered"])
    ]

    meta_table = Table([[meta_block]], colWidths=[doc.width], hAlign="CENTER")
    meta_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    elements.append(meta_table)
    elements.append(Spacer(1, 18))

    # ======================
    # FROM + TO
    # ======================

    from_block = [
        Paragraph(f"<b>{t['seller']}:</b>", styles["InvoiceSectionTitle"]),
        Paragraph(proforma_data["from"]["name"], styles["InvoiceText"]),
    ]
    for line in proforma_data["from"]["address"]:
        from_block.append(Paragraph(line, styles["InvoiceText"]))

    from_block.append(Paragraph(
        f"<b>{t['iban']}:</b> {proforma_data['from']['iban']}", styles["InvoiceText"])),

    to_block = [
        Paragraph(f"<b>{t['buyer']}:</b>", styles["InvoiceSectionTitle"]),
        Paragraph(proforma_data["to"]["name"], styles["InvoiceText"]),
    ]

    for line in proforma_data["to"]["address"]:
        to_block.append(Paragraph(line, styles["InvoiceText"]))

    header_table = Table(
        [[from_block, to_block]],
        colWidths=[doc.width * 0.50, doc.width * 0.50],
        hAlign="LEFT",
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 14))

    # ======================
    # TO
    # ======================
    # elements.append(
    #     Paragraph(f"<b>{t['buyer']}:</b>", styles["InvoiceSectionTitle"]))
    # elements.append(
    #     Paragraph(proforma_data["to"]["name"], styles["InvoiceText"]))
    # for line in proforma_data["to"]["address"]:
    #     elements.append(Paragraph(line, styles["InvoiceText"]))
    # elements.append(Spacer(1, 12))

    # ======================
    # ITEMS TABLE
    # ======================
    table_data = [[
        t["service"],
        t["quantity"],
        t["unit_price"],
        t["amount"]
    ]]

    for row in proforma_data["rows"]:
        table_data.append([
            row["description"],
            row["quantity"],
            row["rate"],
            row["amount"],
        ])

    items_table = Table(table_data, colWidths=GRID, hAlign="LEFT")
    items_table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(items_table)
    elements.append(Spacer(1, 24))

    # ======================
    # TOTALS
    # ======================
    totals_data = []
    for total in proforma_data["totals"]:
        totals_data.append([
            "",
            "",
            total["label"],
            total["amount"],
        ])

    totals_table = Table(totals_data, colWidths=GRID, hAlign="LEFT")
    totals_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("FONT", (2, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (2, -1), (-1, -1), 0.5, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    elements.append(totals_table)
    elements.append(Spacer(1, 16))

    # ======================
    # NOTES
    # ======================
    elements.append(Spacer(1, 24))
    line_width = GRID[0] + GRID[1] + GRID[2] + GRID[3]

    line = Table([[""]], colWidths=[line_width], hAlign="LEFT")
    line.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, -1), 0.25, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(line)

    elements.append(Paragraph(t["notes"], styles["InvoiceSectionTitle"]))
    elements.append(
        Paragraph(proforma_data.get("notes") or "-", styles["InvoiceText"])
    )

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()
    return pdf

###### END PDF GENERATORS ######

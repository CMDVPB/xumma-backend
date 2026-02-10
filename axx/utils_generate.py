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


def generate_proforma_pdf(proforma_data: dict) -> bytes:
    buffer = BytesIO()

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
        name="InvoiceText",
        fontSize=10,
        spaceAfter=2,
    ))

    elements = []

    # ======================
    # TITLE
    # ======================
    elements.append(
        Paragraph(proforma_data.get("title", "Invoice"),
                  styles["InvoiceTitle"])
    )

    # ======================
    # FROM + META
    # ======================
    from_block = [
        Paragraph("<b>Vanzator:</b>", styles["InvoiceSectionTitle"]),
        Paragraph(proforma_data["from"]["name"], styles["InvoiceText"]),
    ]
    for line in proforma_data["from"]["address"]:
        from_block.append(Paragraph(line, styles["InvoiceText"]))

    from_block.append(Paragraph(
        f"<b>IBAN #:</b> {proforma_data['from']['iban']}", styles["InvoiceText"])),

    meta = proforma_data["meta"]
    meta_block = [
        Paragraph(
            f"<b>Cont de plata #</b> {meta['number']}", styles["InvoiceText"]),
        Paragraph(f"<b>Data:</b> {meta['date']}", styles["InvoiceText"]),
        Paragraph(
            f"<b>Scadenta:</b> {meta['due_date']}", styles["InvoiceText"]),
        Paragraph(
            f"<b>Ref. client:</b> {meta['customer_ref']}", styles["InvoiceText"]),
        Paragraph(
            f"<b>Valuta:</b> {meta['currency']}", styles["InvoiceText"]),
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
    elements.append(Paragraph("<b>Cumparator:</b>",
                    styles["InvoiceSectionTitle"]))
    elements.append(
        Paragraph(proforma_data["to"]["name"], styles["InvoiceText"]))
    for line in proforma_data["to"]["address"]:
        elements.append(Paragraph(line, styles["InvoiceText"]))
    elements.append(Spacer(1, 12))

    # ======================
    # ITEMS TABLE
    # ======================
    table_data = [["Serviciu", "Cantitatea", "Pret unitar", "Valoarea"]]

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
    elements.append(Paragraph("Nota", styles["InvoiceSectionTitle"]))
    elements.append(
        Paragraph(proforma_data.get("notes") or "-", styles["InvoiceText"])
    )

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# def generate_order_pdf(order_data: dict) -> bytes:
#     buffer = BytesIO()

#     doc = SimpleDocTemplate(
#         buffer,
#         pagesize=A4,
#         rightMargin=28,
#         leftMargin=28,
#         topMargin=28,
#         bottomMargin=28,
#     )

#     styles = getSampleStyleSheet()
#     styles.add(ParagraphStyle(
#         name="OrderTitle",
#         fontSize=16,
#         fontName="Helvetica-Bold",
#         spaceAfter=14,
#     ))
#     styles.add(ParagraphStyle(
#         name="OrderSection",
#         fontSize=10,
#         fontName="Helvetica-Bold",
#         spaceAfter=6,
#     ))
#     styles.add(ParagraphStyle(
#         name="OrderText",
#         fontSize=10,
#         spaceAfter=6,
#         leading=14,
#     ))

#     elements = []

#     # ======================
#     # TITLE
#     # ======================
#     elements.append(Paragraph(order_data["title"], styles["OrderTitle"]))

#     # ======================
#     # FROM + META
#     # ======================
#     from_block = [
#         Paragraph("<b>Transportator:</b>", styles["OrderSection"]),
#         Paragraph(order_data["from"]["name"], styles["OrderText"]),
#     ]
#     for line in order_data["from"]["address"]:
#         from_block.append(Paragraph(line, styles["OrderText"]))

#     meta_block = [
#         Paragraph(
#             f"<b>Nr. comanda:</b> {order_data['meta']['number']}", styles["OrderText"]),
#         Paragraph(
#             f"<b>Data:</b> {order_data['meta']['date']}", styles["OrderText"]),
#     ]

#     header_table = Table(
#         [[from_block, meta_block]],
#         colWidths=[doc.width * 0.65, doc.width * 0.35],
#     )
#     header_table.setStyle(TableStyle([
#         ("VALIGN", (0, 0), (-1, -1), "TOP"),
#         ("LEFTPADDING", (0, 0), (-1, -1), 0),
#         ("RIGHTPADDING", (0, 0), (-1, -1), 0),
#         ("TOPPADDING", (0, 0), (-1, -1), 0),
#         ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
#     ]))

#     elements.append(header_table)
#     elements.append(Spacer(1, 16))

#     # ======================
#     # TO
#     # ======================
#     elements.append(Paragraph("<b>Beneficiar:</b>", styles["OrderSection"]))
#     elements.append(Paragraph(order_data["to"]["name"], styles["OrderText"]))
#     for line in order_data["to"]["address"]:
#         elements.append(Paragraph(line, styles["OrderText"]))

#     elements.append(Spacer(1, 20))

#     # ======================
#     # CONTRACT CONTENT
#     # ======================
#     elements.append(
#         Paragraph("<b>Conditii contractuale</b>", styles["OrderSection"]))

#     paragraphs = html_to_rl_paragraphs(order_data["content"])

#     for p in paragraphs:
#         elements.append(
#             Paragraph(p.replace("\n", "<br/>"), styles["OrderText"]))
#         elements.append(Spacer(1, 6))

#     doc.build(elements)

#     pdf = buffer.getvalue()
#     buffer.close()
#     return pdf


def generate_order_pdf(order_data: dict) -> bytes:
    html = render_to_string(
        "pdf/order_contract.html",
        {"order": order_data},
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

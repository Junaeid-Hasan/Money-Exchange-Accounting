import io
import csv
from decimal import Decimal
from datetime import date, datetime
from typing import List, Dict, Any, Optional

# ReportLab imports for PDF
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

# OpenPyXL imports for Excel
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


def generate_receipt_pdf(
    company_info: dict,
    receipt_data: dict,
) -> io.BytesIO:
    """
    Generates a professional financial receipt PDF using ReportLab.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    elements = []
    styles = getSampleStyleSheet()

    # Title style
    title_style = ParagraphStyle(
        "CompanyTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        alignment=1,  # Centered
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "CompanySubTitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569"),
        alignment=1,
    )
    receipt_badge_style = ParagraphStyle(
        "ReceiptBadge",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1e40af"),
        alignment=1,
        fontName="Helvetica-Bold",
    )

    # 1. Company Header
    elements.append(Paragraph(company_info.get("company_name", "Money Exchange Ltd."), title_style))
    elements.append(Paragraph(company_info.get("address", "Dhaka, Bangladesh"), subtitle_style))
    elements.append(Paragraph(f"Phone: {company_info.get('phone', '')} | Email: {company_info.get('email', '')}", subtitle_style))
    if company_info.get("trade_license_number"):
        elements.append(Paragraph(f"Trade License: {company_info.get('trade_license_number')}", subtitle_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#cbd5e1"), spaceBefore=5, spaceAfter=15))

    # 2. Receipt Title
    receipt_title = receipt_data.get("receipt_title", "OFFICIAL FINANCIAL RECEIPT")
    elements.append(Paragraph(receipt_title, receipt_badge_style))
    elements.append(Spacer(1, 10))

    # 3. Meta Information (Two-column key-value)
    meta_table_data = [
        [
            Paragraph(f"<b>Receipt No:</b> {receipt_data.get('receipt_number', 'N/A')}", styles["Normal"]),
            Paragraph(f"<b>Date:</b> {receipt_data.get('date', datetime.now().strftime('%Y-%m-%d %H:%M'))}", styles["Normal"]),
        ],
        [
            Paragraph(f"<b>Reference Tx:</b> {receipt_data.get('transaction_number', 'N/A')}", styles["Normal"]),
            Paragraph(f"<b>Counter Staff:</b> {receipt_data.get('staff_name', 'Authorized Teller')}", styles["Normal"]),
        ],
        [
            Paragraph(f"<b>Customer Name:</b> {receipt_data.get('customer_name', 'N/A')}", styles["Normal"]),
            Paragraph(f"<b>Customer Phone:</b> {receipt_data.get('customer_phone', 'N/A')}", styles["Normal"]),
        ],
    ]
    t_meta = Table(meta_table_data, colWidths=[270, 270])
    t_meta.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    elements.append(t_meta)
    elements.append(Spacer(1, 15))

    # 4. Financial Breakdown Table
    items_data = [["Description", "Details / Rate", "Amount (BDT)"]]
    for item in receipt_data.get("items", []):
        items_data.append([
            item.get("description", ""),
            item.get("detail", ""),
            f"৳{Decimal(str(item.get('amount', 0))):,.2f}",
        ])

    # Summary rows
    if "total_bdt" in receipt_data:
        items_data.append(["Total Transaction Value", "", f"৳{Decimal(str(receipt_data['total_bdt'])):,.2f}"])
    if "paid_bdt" in receipt_data:
        items_data.append(["Amount Paid / Received", receipt_data.get("payment_method", "Cash"), f"৳{Decimal(str(receipt_data['paid_bdt'])):,.2f}"])
    if "outstanding_bdt" in receipt_data:
        items_data.append(["Remaining Outstanding Balance", "", f"৳{Decimal(str(receipt_data['outstanding_bdt'])):,.2f}"])

    t_items = Table(items_data, colWidths=[260, 140, 140])
    t_items.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            # Bold summary rows
            ("FONTNAME", (0, -3), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -3), (-1, -1), colors.HexColor("#f8fafc")),
        ])
    )
    elements.append(t_items)
    elements.append(Spacer(1, 20))

    # 5. Important note & Signatures
    footer_note = company_info.get("receipt_footer_note", "Please verify your cash and foreign currency before leaving.")
    elements.append(Paragraph(f"<b>Note:</b> {footer_note}", subtitle_style))
    elements.append(Spacer(1, 40))

    sig_data = [
        ["_________________________", "_________________________"],
        ["Customer Signature", "Authorized Officer Signature"],
    ]
    t_sig = Table(sig_data, colWidths=[270, 270])
    t_sig.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, 1), 9),
            ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#475569")),
        ])
    )
    elements.append(t_sig)

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_balance_sheet_pdf(
    company_info: dict,
    balance_sheet: dict,
) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    elements = []
    styles = getSampleStyleSheet()

    # Company Header
    elements.append(Paragraph(company_info.get("company_name", "Money Exchange Ltd."), styles["Heading1"]))
    elements.append(Paragraph("BALANCE SHEET (STATEMENT OF FINANCIAL POSITION)", styles["Heading2"]))
    elements.append(Paragraph(f"As of: {balance_sheet['as_of_date'].strftime('%d %B %Y')}", styles["Normal"]))
    elements.append(Spacer(1, 15))

    table_data = [["Account Code", "Account Description", "Amount (BDT)"]]

    # Assets
    table_data.append(["", "--- ASSETS ---", ""])
    for a in balance_sheet["assets"]:
        table_data.append([a["code"], a["name"], f"৳{a['amount']:,.2f}"])
    table_data.append(["", "TOTAL ASSETS", f"৳{balance_sheet['total_assets']:,.2f}"])

    # Liabilities
    table_data.append(["", "--- LIABILITIES ---", ""])
    for l in balance_sheet["liabilities"]:
        table_data.append([l["code"], l["name"], f"৳{l['amount']:,.2f}"])
    table_data.append(["", "TOTAL LIABILITIES", f"৳{balance_sheet['total_liabilities']:,.2f}"])

    # Equity
    table_data.append(["", "--- EQUITY ---", ""])
    for e in balance_sheet["equity"]:
        table_data.append([e["code"], e["name"], f"৳{e['amount']:,.2f}"])
    table_data.append(["", "TOTAL EQUITY", f"৳{balance_sheet['total_equity']:,.2f}"])

    # Total Liabilities & Equity
    table_data.append(["", "TOTAL LIABILITIES & EQUITY", f"৳{balance_sheet['total_liabilities_and_equity']:,.2f}"])

    t = Table(table_data, colWidths=[100, 300, 140])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(t)
    elements.append(Spacer(1, 20))
    status_msg = "BALANCE SHEET BALANCED (Total Assets = Total Liabilities + Total Equity)" if balance_sheet["is_balanced"] else "UNBALANCED WARNING"
    elements.append(Paragraph(f"<b>Status:</b> {status_msg}", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_transactions_excel(transactions: list) -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Transactions"

    headers = [
        "Tx Number", "Date", "Type", "Customer", "MYR Qty", "Rate (BDT)",
        "Total BDT", "Paid BDT", "Outstanding BDT", "Payment Status", "Tx Status"
    ]
    ws.append(headers)

    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for tx in transactions:
        ws.append([
            tx.transaction_number,
            tx.transaction_date.strftime("%Y-%m-%d %H:%M") if hasattr(tx.transaction_date, "strftime") else str(tx.transaction_date),
            tx.transaction_type,
            tx.customer.full_name if tx.customer else "N/A",
            float(tx.myr_quantity),
            float(tx.exchange_rate),
            float(tx.total_amount_bdt),
            float(tx.paid_amount_bdt),
            float(tx.outstanding_amount_bdt),
            tx.payment_status,
            tx.status,
        ])

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generate_customer_statement_pdf(company_info: dict, summary: dict) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()

    customer = summary["customer"]

    # Header
    elements.append(Paragraph(company_info.get("company_name", "Money Exchange Ltd."), styles["Heading1"]))
    elements.append(Paragraph("CUSTOMER ACCOUNT STATEMENT & RUNNING LEDGER", styles["Heading2"]))
    elements.append(Paragraph(f"Customer: <b>{customer.full_name}</b> ({customer.customer_code})", styles["Normal"]))
    elements.append(Paragraph(f"Phone: {customer.phone_number} | NID/Passport: {customer.national_id or 'N/A'}", styles["Normal"]))
    elements.append(Paragraph(f"Current Receivables: ৳{summary['receivable_bdt']:,.2f} | Current Payables: ৳{summary['payable_bdt']:,.2f}", styles["Normal"]))
    elements.append(Spacer(1, 15))

    ledger_data = [["Date", "Reference", "Type / Description", "Debit (BDT)", "Credit (BDT)", "Status"]]
    for e in summary["ledger_entries"]:
        ledger_data.append([
            e["date"].strftime("%Y-%m-%d") if hasattr(e["date"], "strftime") else str(e["date"]),
            e["ref"],
            e["description"],
            f"৳{e['debit_bdt']:,.2f}" if e["debit_bdt"] > 0 else "-",
            f"৳{e['credit_bdt']:,.2f}" if e["credit_bdt"] > 0 else "-",
            e["status"],
        ])

    t = Table(ledger_data, colWidths=[75, 100, 185, 60, 60, 60])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (3, 0), (4, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

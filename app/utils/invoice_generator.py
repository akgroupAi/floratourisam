"""PDF invoice generator for bookings paid via Razorpay."""

import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)


# Brand colours
PRIMARY = colors.HexColor("#1A3C5E")
ACCENT = colors.HexColor("#2E86C1")
LIGHT_BG = colors.HexColor("#F0F4F8")
GREY = colors.HexColor("#7F8C8D")
WHITE = colors.white
BLACK = colors.black


def _fmt_currency(amount: float, currency: str) -> str:
    symbols = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}
    sym = symbols.get(currency.upper(), currency + " ")
    return f"{sym}{amount:,.2f}"


def _fmt_date(d) -> str:
    if d is None:
        return "—"
    if isinstance(d, datetime):
        return d.strftime("%d %b %Y, %I:%M %p")
    return d.strftime("%d %b %Y")


def generate_invoice_pdf(
    *,
    # Payment info
    payment_reference: str,
    razorpay_payment_id: Optional[str],
    payment_status: str,
    payment_method: str,
    paid_at: Optional[datetime],
    # Booking info
    booking_reference: str,
    booking_type: str,
    entity_name: Optional[str],
    check_in_date=None,
    check_out_date=None,
    guest_count: int,
    base_price: float,
    taxes: float,
    discount: float,
    total_price: float,
    currency: str,
    # User info
    user_name: str,
    user_email: str,
    user_phone: Optional[str] = None,
) -> bytes:
    """Return a PDF invoice as bytes."""

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Header ──────────────────────────────────────────────────────────
    header_data = [
        [
            Paragraph(
                "<font color='#FFFFFF' size='18'><b>Flora Tourism</b></font><br/>"
                "<font color='#BDC3C7' size='9'>Your Wellness Travel Partner</font>",
                ParagraphStyle("hdr", fontName="Helvetica", leading=20),
            ),
            Paragraph(
                "<font color='#FFFFFF' size='22'><b>INVOICE</b></font>",
                ParagraphStyle("inv", fontName="Helvetica", alignment=2),
            ),
        ]
    ]
    header_table = Table(header_data, colWidths=[100 * mm, 75 * mm])
    header_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
            ("PADDING", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 6 * mm))

    # ── Meta row (invoice # / date) ──────────────────────────────────────
    invoice_no = f"INV-{payment_reference}"
    issued_on = _fmt_date(paid_at or datetime.utcnow())

    meta_data = [
        [
            Paragraph(f"<b>Invoice No:</b> {invoice_no}", styles["Normal"]),
            Paragraph(f"<b>Issue Date:</b> {issued_on}", styles["Normal"]),
            Paragraph(f"<b>Status:</b> {payment_status.upper()}", styles["Normal"]),
        ]
    ]
    meta_table = Table(meta_data, colWidths=[65 * mm, 65 * mm, 45 * mm])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOX", (0, 0), (-1, -1), 0.5, ACCENT),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 6 * mm))

    # ── Bill-to / Payment-via ────────────────────────────────────────────
    phone_line = f"<br/>Phone: {user_phone}" if user_phone else ""
    rzp_line = (
        f"<br/>Razorpay ID: <font color='#2E86C1'>{razorpay_payment_id}</font>"
        if razorpay_payment_id
        else ""
    )

    bill_data = [
        [
            Paragraph(
                f"<b><font color='#1A3C5E'>Bill To</font></b><br/>"
                f"{user_name}<br/>{user_email}{phone_line}",
                ParagraphStyle("bt", fontName="Helvetica", fontSize=9, leading=14),
            ),
            Paragraph(
                f"<b><font color='#1A3C5E'>Payment Via</font></b><br/>"
                f"Method: {payment_method.replace('_', ' ').title()}<br/>"
                f"Gateway: Razorpay{rzp_line}",
                ParagraphStyle("pv", fontName="Helvetica", fontSize=9, leading=14),
            ),
        ]
    ]
    bill_table = Table(bill_data, colWidths=[87 * mm, 88 * mm])
    bill_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("BOX", (0, 0), (0, 0), 0.5, colors.HexColor("#D5D8DC")),
            ("BOX", (1, 0), (1, 0), 0.5, colors.HexColor("#D5D8DC")),
        ])
    )
    story.append(bill_table)
    story.append(Spacer(1, 6 * mm))

    # ── Booking Details ──────────────────────────────────────────────────
    story.append(
        Paragraph(
            "<font color='#1A3C5E' size='11'><b>Booking Details</b></font>",
            styles["Normal"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=4))

    booking_rows = [
        ["Booking Reference", booking_reference],
        ["Booking Type", booking_type.replace("_", " ").title()],
        ["Property / Service", entity_name or "—"],
    ]
    if check_in_date:
        booking_rows.append(["Check-in Date", _fmt_date(check_in_date)])
    if check_out_date:
        booking_rows.append(["Check-out Date", _fmt_date(check_out_date)])
        if check_in_date:
            nights = (check_out_date - check_in_date).days
            booking_rows.append(["Duration", f"{nights} night{'s' if nights != 1 else ''}"])
    booking_rows.append(["Guests", str(guest_count)])

    bk_table = Table(
        [[Paragraph(f"<b>{r[0]}</b>", styles["Normal"]), r[1]] for r in booking_rows],
        colWidths=[60 * mm, 115 * mm],
    )
    bk_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, LIGHT_BG]),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D5D8DC")),
        ])
    )
    story.append(bk_table)
    story.append(Spacer(1, 6 * mm))

    # ── Pricing Breakdown ────────────────────────────────────────────────
    story.append(
        Paragraph(
            "<font color='#1A3C5E' size='11'><b>Price Summary</b></font>",
            styles["Normal"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=4))

    price_rows = [
        ["Description", "Amount"],
        ["Base Price", _fmt_currency(base_price, currency)],
        ["Taxes & Fees", _fmt_currency(taxes, currency)],
    ]
    if discount > 0:
        price_rows.append(["Discount", f"- {_fmt_currency(discount, currency)}"])

    price_rows.append(["", ""])  # spacer row
    price_rows.append(["TOTAL PAID", _fmt_currency(total_price, currency)])

    pr_table = Table(price_rows, colWidths=[130 * mm, 45 * mm])
    pr_table.setStyle(
        TableStyle([
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("PADDING", (0, 0), (-1, 0), 6),
            # Body rows
            ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -2), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, LIGHT_BG]),
            ("PADDING", (0, 1), (-1, -2), 5),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            # Total row
            ("BACKGROUND", (0, -1), (-1, -1), ACCENT),
            ("TEXTCOLOR", (0, -1), (-1, -1), WHITE),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, -1), (-1, -1), 11),
            ("PADDING", (0, -1), (-1, -1), 8),
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D5D8DC")),
            # Spacer row
            ("BACKGROUND", (0, -2), (-1, -2), WHITE),
            ("LINEABOVE", (0, -1), (-1, -1), 1, ACCENT),
        ])
    )
    story.append(pr_table)
    story.append(Spacer(1, 10 * mm))

    # ── Footer ───────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY))
    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(
            "<font color='#7F8C8D' size='8'>"
            "This is a system-generated invoice and does not require a physical signature. "
            "For support, contact support@floratourism.com | www.floratourism.com"
            "</font>",
            ParagraphStyle("footer", fontName="Helvetica", alignment=1, fontSize=8),
        )
    )

    doc.build(story)
    return buffer.getvalue()

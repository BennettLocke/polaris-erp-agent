"""Customer and customer-balance business services."""

from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any

from src.engine.exceptions import DBError

from .base import BusinessService
from .identity import IdentityLinkService


class CustomerService(BusinessService):
    def list(self, keyword: str = "", limit: int = 100) -> list[dict]:
        return self.db.customer_list(keyword, limit=limit)

    def list_page(
        self,
        keyword: str = "",
        *,
        page: int = 1,
        page_size: int = 20,
        filter_value: str = "all",
    ) -> tuple[list[dict], int, dict]:
        return self.db.customer_list_page(
            keyword=keyword,
            page=page,
            page_size=page_size,
            filter_value=filter_value,
        )

    def create(self, *, name: str, contacts_name: str = "", contacts_tel: str = "") -> dict:
        result = self.db.customer_create(name=name, contacts_name=contacts_name, contacts_tel=contacts_tel)
        data = result.get("data") if isinstance(result, dict) else {}
        customer_id = data.get("id") if isinstance(data, dict) else None
        if customer_id and contacts_tel:
            link_result = IdentityLinkService(db=self.db).sync_customer_phone(customer_id, contacts_tel)
            if isinstance(result, dict):
                result.setdefault("data", {})["identity_link"] = link_result.get("data") if isinstance(link_result, dict) else link_result
        return result

    def update_monthly(self, customer_id: int, is_monthly_customer: Any) -> dict:
        return self.db.update_customer_monthly(customer_id, is_monthly_customer)

    def update_profile(
        self,
        customer_id: int,
        *,
        name: Any = None,
        contacts_name: Any = None,
        address: Any = None,
    ) -> dict:
        return self.db.update_customer_profile(
            customer_id,
            name=name,
            contacts_name=contacts_name,
            address=address,
        )

    def sync_phone(self, customer_id: int, phone: str, *, operator_user_id: Any = None) -> dict:
        return IdentityLinkService(db=self.db).sync_customer_phone(
            customer_id,
            phone,
            operator_user_id=operator_user_id,
        )

    def sales(
        self,
        customer_id: int,
        *,
        page: int = 1,
        page_size: int = 50,
        period: str = "",
        month: str = "",
        pay_status: str = "",
    ) -> tuple[list[dict], int, dict]:
        return self.db.customer_sales(
            customer_id,
            page=page,
            page_size=page_size,
            period=period,
            month=month,
            pay_status=pay_status,
        )

    def statement(
        self,
        customer_id: int,
        *,
        month: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> dict:
        return self.db.customer_statement(
            customer_id,
            month=month,
            date_from=date_from,
            date_to=date_to,
        )


class CustomerBalanceService(BusinessService):
    def ledger(self, customer_id: int, *, page: int = 1, page_size: int = 100) -> tuple[list[dict], int, dict]:
        return self.db.customer_balance_ledger(customer_id, page=page, page_size=page_size)

    def _amount_decimal(self, amount: Any) -> Decimal:
        try:
            return Decimal(str(amount).replace(",", "").strip())
        except (InvalidOperation, AttributeError):
            raise DBError("amount is required")

    def apply_action(
        self,
        customer_id: int,
        *,
        action: str,
        amount: Any,
        pay_type: str = "",
        note: str = "",
        month: str = "",
        operator_user_id: Any = None,
    ) -> dict:
        clean_action = str(action or "").strip()
        amount_value = self._amount_decimal(amount)
        if clean_action == "settlement":
            if amount_value <= 0:
                raise DBError("amount must be greater than 0")
            return self.db.customer_month_settlement(
                customer_id,
                month=month,
                amount=amount,
                pay_type=pay_type or "wechat",
                note=note,
                operator_user_id=operator_user_id,
            )
        if clean_action in ("receipt", "recharge"):
            if amount_value <= 0:
                raise DBError("amount must be greater than 0")
            return self.db.customer_balance_entry(
                customer_id,
                entry_type=clean_action,
                amount=amount,
                pay_type=pay_type or clean_action,
                note=note,
                operator_user_id=operator_user_id,
            )
        if clean_action == "adjust":
            if amount_value == 0:
                raise DBError("amount cannot be 0")
            if not str(note or "").strip():
                raise DBError("adjust note is required")
            return self.db.customer_balance_adjust(
                customer_id,
                amount=amount,
                note=note,
                operator_user_id=operator_user_id,
            )
        raise DBError("action is required")


def get_customer_service() -> CustomerService:
    return CustomerService()


def get_customer_balance_service() -> CustomerBalanceService:
    return CustomerBalanceService()


def _statement_pdf_font_name() -> str:
    """Register the statement PDF font, preferring Microsoft YaHei."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        os.environ.get("SJAGENT_PDF_FONT_PATH"),
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        str(Path(__file__).resolve().parents[3] / "assets" / "fonts" / "msyh.ttc"),
        str(Path(__file__).resolve().parents[3] / "assets" / "fonts" / "MicrosoftYaHei.ttf"),
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/Deng.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/source-han-sans/SourceHanSansSC-Regular.otf",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont("SjStatementFont", str(path)))
            return "SjStatementFont"
        except Exception:
            continue

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light"


def build_customer_statement_pdf(statement: dict) -> bytes:
    """Build a customer statement PDF with a fixed first-version template."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:  # pragma: no cover - depends on optional runtime package
        raise DBError("PDF组件未安装，请先安装 reportlab") from exc

    font_name = _statement_pdf_font_name()
    styles = getSampleStyleSheet()
    base_style = ParagraphStyle(
        "SjBase",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        leading=13,
    )
    cell_style = ParagraphStyle(
        "SjCell",
        parent=base_style,
        fontSize=7.8,
        leading=10,
    )
    title_style = ParagraphStyle(
        "SjTitle",
        parent=base_style,
        fontSize=17,
        leading=22,
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "SjSection",
        parent=base_style,
        fontSize=11,
        leading=15,
        spaceBefore=8,
        spaceAfter=6,
    )

    def text(value: Any) -> str:
        return str(value if value not in (None, "") else "-")

    def money(value: Any) -> str:
        if value in (None, ""):
            return "-"
        return f"¥{text(value)}"

    customer = statement.get("customer") or {}
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    story: list[Any] = [
        Paragraph("肆计包装设计对账单", title_style),
        Paragraph(
            f"客户：{text(customer.get('name'))}　周期：{text(statement.get('period_label'))}　"
            f"生成时间：{text(statement.get('generated_at'))}",
            base_style,
        ),
        Spacer(1, 8),
        Paragraph("销售明细", section_style),
    ]

    sales_rows = [["日期", "单号", "商品", "颜色/规格", "数量", "单价", "金额", "付款"]]
    for order in statement.get("sales") or []:
        items = order.get("items") or []
        if not items:
            sales_rows.append([
                text(order.get("sales_at"))[:10],
                text(order.get("sales_no")),
                "销售单明细",
                "-",
                text(order.get("total_quantity")),
                "-",
                money(order.get("receivable_amount")),
                text(order.get("pay_status_text")),
            ])
            continue
        for item in items:
            sales_rows.append([
                text(order.get("sales_at"))[:10],
                Paragraph(text(order.get("sales_no")), cell_style),
                Paragraph(text(item.get("title")), cell_style),
                Paragraph(text(item.get("color")), cell_style),
                text(item.get("quantity")),
                money(item.get("unit_price")),
                money(item.get("amount")),
                " / ".join(part for part in [text(order.get("pay_status_text")), text(order.get("pay_type_text"))] if part != "-"),
            ])
    total_row_index = None
    if len(sales_rows) == 1:
        sales_rows.append(["-", "-", "无销售明细", "-", "-", "-", "-", "-"])
    else:
        total_row_index = len(sales_rows)
        sales_rows.append([
            Paragraph(f"共计：{text(statement.get('sales_count'))} 单", cell_style),
            "",
            "",
            "",
            f"{text(statement.get('sales_quantity'))} 套",
            "",
            money(statement.get('sales_amount')),
            "",
        ])

    sales_table = Table(sales_rows, repeatRows=1, colWidths=[18 * mm, 25 * mm, 36 * mm, 22 * mm, 15 * mm, 20 * mm, 22 * mm, 20 * mm])
    table_style = [
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 7.6),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F4F4F5")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E4E4E7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 3),
    ]
    if total_row_index is not None:
        table_style.extend([
            ("SPAN", (0, total_row_index), (3, total_row_index)),
            ("BACKGROUND", (0, total_row_index), (-1, total_row_index), colors.HexColor("#FAFAFA")),
            ("LINEABOVE", (0, total_row_index), (-1, total_row_index), 0.5, colors.HexColor("#A1A1AA")),
            ("ALIGN", (4, total_row_index), (6, total_row_index), "RIGHT"),
        ])
    sales_table.setStyle(TableStyle(table_style))
    story.append(sales_table)
    doc.build(story)
    return buffer.getvalue()

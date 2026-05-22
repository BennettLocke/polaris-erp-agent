"""Sales flow regression checks against sjagent_core.

This script creates temporary REGRESSION-* customers/products, verifies sales
inventory/balance behavior, then removes only those temporary rows.
"""
from __future__ import annotations

import os
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

from src.engine.native_db import (  # noqa: E402
    get_native_db_client,
    reset_native_operator_user_id,
    set_native_operator_user_id,
)


def dec(value) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.001"))


class SalesFlowRegression:
    def __init__(self) -> None:
        self.db = get_native_db_client()
        self.stamp = str(int(time.time() * 1000))
        self.party_ids: list[int] = []
        self.spu_ids: list[int] = []
        self.sku_ids: list[int] = []
        self.sales_ids: list[int] = []
        self.stock_doc_ids: list[int] = []
        self.transfer_ids: list[int] = []
        self.stocktake_ids: list[int] = []
        self.operator_token = None
        self.party_counter = 0

    def query_one(self, sql: str, params=()):
        rows = self.db.query(sql, params)
        return rows[0] if rows else {}

    def assert_equal(self, actual, expected, label: str) -> None:
        if actual != expected:
            raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")

    def unit_id(self) -> int:
        row = self.query_one("SELECT id FROM product_unit WHERE name='套' OR code='set' ORDER BY id ASC LIMIT 1")
        if not row:
            row = self.query_one("SELECT id FROM product_unit ORDER BY id ASC LIMIT 1")
        if not row:
            raise AssertionError("product_unit is empty")
        return int(row["id"])

    def customer(self, name_suffix: str) -> int:
        self.party_counter += 1
        name = f"REGRESSION-{name_suffix}-{self.stamp}"
        phone = f"199{self.stamp[-7:]}{self.party_counter}"
        affected = self.db.execute(
            """
            INSERT INTO party
                (name, kind, phone, phone_normalized, source, status, created_at, updated_at)
            VALUES (%s, 'customer', %s, %s, 'regression', 'active', NOW(), NOW())
            """,
            (name, phone, phone),
        )
        row = self.query_one("SELECT id FROM party WHERE name=%s LIMIT 1", (name,))
        if not affected or not row:
            raise AssertionError("failed to create regression customer")
        party_id = int(row["id"])
        self.party_ids.append(party_id)
        return party_id

    def sku(self, title: str, product_type: str, is_stock_item: int, price: str) -> int:
        self.db.execute(
            """
            INSERT INTO product_spu
                (title, product_type, inventory_policy, purchase_policy, status, source, created_at, updated_at)
            VALUES (%s, %s, 'strict', 'order_qty', 'active', 'regression', NOW(), NOW())
            """,
            (f"REGRESSION-{title}-{self.stamp}", product_type),
        )
        spu = self.query_one(
            "SELECT id FROM product_spu WHERE source='regression' AND title=%s ORDER BY id DESC LIMIT 1",
            (f"REGRESSION-{title}-{self.stamp}",),
        )
        spu_id = int(spu["id"])
        self.spu_ids.append(spu_id)
        sku_no = f"REG{self.stamp[-8:]}{len(self.sku_ids) + 1}"
        self.db.execute(
            """
            INSERT INTO product_sku
                (spu_id, sku_no, color, unit_id, inventory_policy, purchase_policy, retail_price,
                 cost_price, is_stock_item, is_sellable, is_listed, status, source, created_at, updated_at, search_text)
            VALUES (%s, %s, %s, %s, 'strict', 'order_qty', %s, 0, %s, 1, 0, 'active',
                    'regression', NOW(), NOW(), %s)
            """,
            (spu_id, sku_no, "红色", self.unit_id(), price, int(is_stock_item), title),
        )
        row = self.query_one("SELECT id FROM product_sku WHERE sku_no=%s LIMIT 1", (sku_no,))
        sku_id = int(row["id"])
        self.sku_ids.append(sku_id)
        return sku_id

    def set_inventory(self, sku_id: int, quantity: str) -> None:
        unit_id = self.unit_id()
        self.db.execute(
            """
            INSERT INTO inventory_balance
                (sku_id, warehouse_id, unit_id, quantity, reserved_qty, available_qty, version, updated_at)
            VALUES (%s, 1, %s, %s, 0, %s, 1, NOW())
            ON DUPLICATE KEY UPDATE quantity=VALUES(quantity), available_qty=VALUES(available_qty), updated_at=NOW()
            """,
            (sku_id, unit_id, quantity, quantity),
        )

    def inventory_qty(self, sku_id: int) -> Decimal:
        row = self.query_one(
            "SELECT quantity FROM inventory_balance WHERE sku_id=%s AND warehouse_id=1 AND unit_id=%s",
            (sku_id, self.unit_id()),
        )
        return dec(row.get("quantity"))

    def balance_amount(self, customer_id: int) -> Decimal:
        row = self.query_one(
            """
            SELECT
              COALESCE((SELECT SUM(balance_delta) FROM customer_balance_ledger WHERE customer_id=%s), 0)
              - COALESCE((
                  SELECT SUM(receivable_amount)
                  FROM sales_order
                  WHERE customer_id=%s
                    AND status NOT IN ('canceled', 'deleted')
                    AND pay_status IN ('unpaid', 'monthly', 'partial')
                ), 0) AS balance_amount
            """,
            (customer_id, customer_id),
        )
        return Decimal(str(row.get("balance_amount") or "0")).quantize(Decimal("0.01"))

    def ledger_count(self, sales_id: int, sku_id: int, biz_type: str) -> int:
        row = self.query_one(
            "SELECT COUNT(*) AS total FROM inventory_ledger WHERE biz_id=%s AND sku_id=%s AND biz_type=%s",
            (sales_id, sku_id, biz_type),
        )
        return int(row.get("total") or 0)

    def biz_ledger_count(self, biz_id: int, sku_id: int, biz_type: str) -> int:
        row = self.query_one(
            "SELECT COUNT(*) AS total FROM inventory_ledger WHERE biz_id=%s AND sku_id=%s AND biz_type=%s",
            (biz_id, sku_id, biz_type),
        )
        return int(row.get("total") or 0)

    def run(self) -> None:
        self.operator_token = set_native_operator_user_id(1)
        unit_id = self.unit_id()
        stock_sku = self.sku("库存礼盒", "gift_box", 1, "10.00")
        bag_sku = self.sku("泡袋不扣库存", "bag", 0, "2.00")
        label_sku = self.sku("标签不扣库存", "accessory", 0, "1.00")
        self.set_inventory(stock_sku, "50")

        balance_customer = self.customer("余额")
        self.db.customer_balance_entry(
            balance_customer,
            entry_type="recharge",
            amount="1000.00",
            pay_type="wechat",
            note="regression recharge",
        )
        sale = self.db.create_sales_order(
            customer_id=balance_customer,
            warehouse_id=1,
            pay_status="paid",
            pay_type="balance",
            products=[
                {"product_id": stock_sku, "unit_id": unit_id, "buy_number": 10, "price": "10.00", "warehouse_id": 1},
                {"product_id": bag_sku, "unit_id": unit_id, "buy_number": 5, "price": "2.00", "warehouse_id": 1},
                {"product_id": label_sku, "unit_id": unit_id, "buy_number": 3, "price": "1.00", "warehouse_id": 1},
            ],
        )
        sales_id = int(sale["data"]["id"])
        self.sales_ids.append(sales_id)
        self.assert_equal(self.inventory_qty(stock_sku), Decimal("40.000"), "balance sale stock deduct")
        self.assert_equal(self.ledger_count(sales_id, stock_sku, "sales_out"), 1, "stock sales_out ledger")
        self.assert_equal(self.ledger_count(sales_id, bag_sku, "sales_out"), 0, "bag no sales_out ledger")
        self.assert_equal(self.ledger_count(sales_id, label_sku, "sales_out"), 0, "label no sales_out ledger")
        self.assert_equal(self.balance_amount(balance_customer), Decimal("887.00"), "balance payment deduct")
        detail = self.db.sales_detail(sales_id)["data"]
        if not detail.get("created_by_name"):
            raise AssertionError("sales order creator is not recorded")
        self.db.delete_sales_order(sales_id)
        self.assert_equal(self.inventory_qty(stock_sku), Decimal("50.000"), "delete restores stock")
        self.assert_equal(self.ledger_count(sales_id, stock_sku, "sales_delete"), 1, "stock delete ledger")
        self.assert_equal(self.ledger_count(sales_id, bag_sku, "sales_delete"), 0, "bag no delete ledger")
        self.assert_equal(self.balance_amount(balance_customer), Decimal("1000.00"), "delete refunds balance payment")
        deleted_detail = self.db.sales_detail(sales_id)["data"]
        if not deleted_detail.get("deleted_by_name"):
            raise AssertionError("sales order deleter is not recorded")

        stock_in = self.db.create_stock_in(
            1,
            [{"product_id": bag_sku, "unit_id": unit_id, "buy_number": 7}],
            note="regression non-stock stock-in",
        )
        stock_doc_id = int(stock_in["data"]["id"])
        self.stock_doc_ids.append(stock_doc_id)
        self.assert_equal(self.inventory_qty(bag_sku), Decimal("0.000"), "bag stock-in does not create inventory balance")
        self.assert_equal(self.biz_ledger_count(stock_doc_id, bag_sku, "stock_in"), 0, "bag no stock-in ledger")

        transfer = self.db.create_transfer(
            1,
            2,
            [{"product_id": bag_sku, "unit_id": unit_id, "transfer_number": 3}],
            note="regression non-stock transfer",
        )
        transfer_id = int(transfer["data"]["id"])
        self.transfer_ids.append(transfer_id)
        self.assert_equal(self.inventory_qty(bag_sku), Decimal("0.000"), "bag transfer does not create inventory balance")
        self.assert_equal(self.biz_ledger_count(transfer_id, bag_sku, "transfer_out"), 0, "bag no transfer-out ledger")
        self.assert_equal(self.biz_ledger_count(transfer_id, bag_sku, "transfer_in"), 0, "bag no transfer-in ledger")

        stocktake = self.db.create_stocktake(
            1,
            [{"product_id": bag_sku, "unit_id": unit_id, "number": 99}],
            note="regression non-stock stocktake",
        )
        stocktake_id = int(stocktake["data"]["id"])
        self.stocktake_ids.append(stocktake_id)
        self.assert_equal(self.inventory_qty(bag_sku), Decimal("0.000"), "bag stocktake does not create inventory balance")
        self.assert_equal(self.biz_ledger_count(stocktake_id, bag_sku, "stocktake"), 0, "bag no stocktake ledger")

        monthly_customer = self.customer("月结")
        monthly = self.db.create_sales_order(
            customer_id=monthly_customer,
            warehouse_id=1,
            pay_status="monthly",
            pay_type="monthly",
            products=[{"product_id": stock_sku, "unit_id": unit_id, "buy_number": 4, "price": "10.00", "warehouse_id": 1}],
        )
        monthly_id = int(monthly["data"]["id"])
        self.sales_ids.append(monthly_id)
        self.assert_equal(self.inventory_qty(stock_sku), Decimal("46.000"), "monthly sale stock deduct")
        self.assert_equal(self.balance_amount(monthly_customer), Decimal("-40.00"), "monthly debt is negative balance")
        self.db.delete_sales_order(monthly_id)
        self.assert_equal(self.inventory_qty(stock_sku), Decimal("50.000"), "monthly delete restores stock")
        self.assert_equal(self.balance_amount(monthly_customer), Decimal("0.00"), "monthly delete removes debt")

        settled_customer = self.customer("已结月结")
        settled = self.db.create_sales_order(
            customer_id=settled_customer,
            warehouse_id=1,
            pay_status="monthly",
            pay_type="monthly",
            create_time="2026-05-22 10:00:00",
            products=[{"product_id": stock_sku, "unit_id": unit_id, "buy_number": 2, "price": "10.00", "warehouse_id": 1}],
        )
        settled_id = int(settled["data"]["id"])
        self.sales_ids.append(settled_id)
        self.db.customer_month_settlement(
            settled_customer,
            month="2026-05",
            amount="20.00",
            pay_type="wechat",
            note="regression settlement",
        )
        self.assert_equal(self.balance_amount(settled_customer), Decimal("0.00"), "settled monthly clears debt")
        self.db.delete_sales_order(settled_id)
        self.assert_equal(self.inventory_qty(stock_sku), Decimal("50.000"), "settled monthly delete restores stock")
        self.assert_equal(self.balance_amount(settled_customer), Decimal("20.00"), "settled monthly delete becomes customer credit")

    def cleanup(self) -> None:
        def placeholders(values: list[int]) -> str:
            return ",".join(["%s"] * len(values))

        try:
            if self.stock_doc_ids:
                ph = placeholders(self.stock_doc_ids)
                self.db.execute(f"DELETE FROM inventory_ledger WHERE biz_id IN ({ph}) AND biz_type='stock_in'", self.stock_doc_ids)
                self.db.execute(f"DELETE FROM stock_document_item WHERE stock_document_id IN ({ph})", self.stock_doc_ids)
                self.db.execute(f"DELETE FROM stock_document WHERE id IN ({ph})", self.stock_doc_ids)
            if self.transfer_ids:
                ph = placeholders(self.transfer_ids)
                self.db.execute(f"DELETE FROM inventory_ledger WHERE biz_id IN ({ph}) AND biz_type IN ('transfer_out','transfer_in')", self.transfer_ids)
                self.db.execute(f"DELETE FROM transfer_order_item WHERE transfer_order_id IN ({ph})", self.transfer_ids)
                self.db.execute(f"DELETE FROM transfer_order WHERE id IN ({ph})", self.transfer_ids)
            if self.stocktake_ids:
                ph = placeholders(self.stocktake_ids)
                self.db.execute(f"DELETE FROM inventory_ledger WHERE biz_id IN ({ph}) AND biz_type='stocktake'", self.stocktake_ids)
                self.db.execute(f"DELETE FROM stocktake_item WHERE stocktake_order_id IN ({ph})", self.stocktake_ids)
                self.db.execute(f"DELETE FROM stocktake_order WHERE id IN ({ph})", self.stocktake_ids)
            if self.sales_ids:
                ph = placeholders(self.sales_ids)
                self.db.execute(f"DELETE FROM inventory_ledger WHERE biz_id IN ({ph}) AND biz_type IN ('sales_out','sales_delete','sales_cancel')", self.sales_ids)
                self.db.execute(f"DELETE FROM sales_order_item WHERE sales_order_id IN ({ph})", self.sales_ids)
                self.db.execute(f"DELETE FROM sales_order WHERE id IN ({ph})", self.sales_ids)
            if self.party_ids:
                ph = placeholders(self.party_ids)
                self.db.execute(f"DELETE FROM customer_balance_ledger WHERE customer_id IN ({ph})", self.party_ids)
                self.db.execute(f"DELETE FROM party WHERE id IN ({ph})", self.party_ids)
            if self.sku_ids:
                ph = placeholders(self.sku_ids)
                self.db.execute(f"DELETE FROM inventory_ledger WHERE sku_id IN ({ph})", self.sku_ids)
                self.db.execute(f"DELETE FROM inventory_balance WHERE sku_id IN ({ph})", self.sku_ids)
                self.db.execute(f"DELETE FROM product_sku WHERE id IN ({ph})", self.sku_ids)
            if self.spu_ids:
                ph = placeholders(self.spu_ids)
                self.db.execute(f"DELETE FROM product_spu WHERE id IN ({ph})", self.spu_ids)
        finally:
            if self.operator_token is not None:
                reset_native_operator_user_id(self.operator_token)


def main() -> int:
    runner = SalesFlowRegression()
    try:
        runner.run()
        print("sales flow regression ok")
        return 0
    finally:
        runner.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())

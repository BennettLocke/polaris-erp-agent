"""Inventory business service."""

from __future__ import annotations

from typing import Any

from .base import BusinessService


class InventoryService(BusinessService):
    def product_inventory(self, product_id: int) -> list[dict]:
        return self.db.get_product_inventory(product_id)

    def warehouse_inventory(self, warehouse_id: int) -> list[dict]:
        return self.db.get_warehouse_inventory(warehouse_id)

    def search(
        self,
        *,
        keyword: str = "",
        color: str = "",
        warehouse_id: int | None = None,
        only_in_stock: bool = False,
        limit: int = 100,
    ) -> list[dict]:
        return self.db.search_inventory(
            keyword=keyword,
            color=color,
            warehouse_id=warehouse_id,
            only_in_stock=only_in_stock,
            limit=limit,
        )

    def balances(
        self,
        *,
        keyword: str = "",
        color: str = "",
        warehouse_id: int | None = None,
        stock_status: str = "",
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        return self.db.inventory_balances(
            keyword=keyword,
            color=color,
            warehouse_id=warehouse_id,
            stock_status=stock_status,
            page=page,
            page_size=page_size,
        )

    def ledger(
        self,
        *,
        keyword: str = "",
        sku_id: int | None = None,
        warehouse_id: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        return self.db.inventory_ledger(
            keyword=keyword,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            page=page,
            page_size=page_size,
        )

    def stock_documents(self, *, keyword: str = "", page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        return self.db.stock_documents(keyword=keyword, page=page, page_size=page_size)

    def stocktakes(self, *, keyword: str = "", page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        return self.db.stocktakes(keyword=keyword, page=page, page_size=page_size)

    def transfers(self, *, keyword: str = "", page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        return self.db.transfers(keyword=keyword, page=page, page_size=page_size)

    def warehouse_list(self) -> list[dict]:
        return self.db.warehouse_list()

    def create_stock_in(
        self,
        *,
        warehouse_id: int,
        products: list[dict],
        note: str = "",
        operator_user_id: Any = None,
    ) -> dict:
        return self.db.create_stock_in(
            warehouse_id=warehouse_id,
            products=products,
            note=note,
            operator_user_id=operator_user_id,
        )

    def create_transfer(
        self,
        *,
        out_warehouse_id: int,
        enter_warehouse_id: int,
        products: list[dict],
        note: str = "",
        operator_user_id: Any = None,
    ) -> dict:
        return self.db.create_transfer(
            out_warehouse_id=out_warehouse_id,
            enter_warehouse_id=enter_warehouse_id,
            products=products,
            note=note,
            operator_user_id=operator_user_id,
        )

    def create_stocktake(
        self,
        *,
        warehouse_id: int,
        products: list[dict],
        note: str = "",
        operator_user_id: Any = None,
    ) -> dict:
        return self.db.create_stocktake(
            warehouse_id=warehouse_id,
            products=products,
            note=note,
            operator_user_id=operator_user_id,
        )


def get_inventory_service() -> InventoryService:
    return InventoryService()

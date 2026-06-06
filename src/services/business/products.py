"""Product business service."""

from __future__ import annotations

from typing import Any, Iterable

from .base import BusinessService


class ProductService(BusinessService):
    def search(self, keyword: str, *, limit: int = 80, listed_only: bool = False) -> list[dict]:
        return self.db.product_search(keyword, limit=limit, listed_only=listed_only)

    def list(
        self,
        *,
        keyword: str = "",
        page: int = 1,
        page_size: int = 20,
        status: Any = None,
        category_id: int | None = None,
        group: bool = False,
        category_ids: Iterable[Any] | None = None,
        product_type: str = "",
        listed_only: bool = False,
        sort: str = "",
        listed_state: str = "",
        stock_mode: str = "",
        quality: str = "",
    ) -> tuple[list[dict], int]:
        if str(product_type or "").strip():
            return self.db.product_list(
                keyword=keyword,
                page=page,
                page_size=page_size,
                status=status,
                category_id=category_id,
                group=group,
                category_ids=category_ids,
                product_type=product_type,
                listed_only=listed_only,
                sort=sort,
                listed_state=listed_state,
                stock_mode=stock_mode,
                quality=quality,
            )
        return self.db.product_list(
            keyword=keyword,
            page=page,
            page_size=page_size,
            status=status,
            category_id=category_id,
            group=group,
            category_ids=category_ids,
            listed_only=listed_only,
            sort=sort,
            listed_state=listed_state,
            stock_mode=stock_mode,
            quality=quality,
        )

    def categories(self, *, listed_only: bool = False, exclude_names: Iterable[str] | None = None) -> list[dict]:
        return self.db.product_categories(listed_only=listed_only, exclude_names=exclude_names)

    def save_category(self, payload: dict, *, operator_user_id: Any = None) -> dict:
        return self.db.save_product_category(payload, operator_user_id=operator_user_id)

    def info(self, product_id: int, *, listed_only: bool = False) -> dict | None:
        return self.db.product_info(product_id, listed_only=listed_only)

    def options(self, product_id: int | None = None) -> dict:
        return self.db.product_options(product_id)

    def save(self, payload: dict) -> dict:
        return self.db.save_product(payload)

    def delete(self, ids: str | list[int]) -> dict:
        return self.db.delete_product(ids)

    def update_shelves(
        self,
        product_id: int,
        state: int,
        *,
        spu_id: Any | None = None,
        sku_ids: Iterable[Any] | None = None,
    ) -> dict:
        return self.db.update_product_shelves(product_id, state, spu_id=spu_id, sku_ids=sku_ids)

    def price(self, product_id: int) -> float | None:
        return self.db.get_product_price(product_id)

    def record_upload(self, url: str, *, storage: str = "oss") -> None:
        self.db.record_product_upload(url, storage=storage)

    def media_assets(
        self,
        *,
        spu_id: int | None = None,
        sku_ids: list[int] | None = None,
        media_type: str = "",
        include_pending: bool = True,
        limit: int = 120,
    ) -> list[dict]:
        return self.db.product_media_assets(
            spu_id=spu_id,
            sku_ids=sku_ids,
            media_type=media_type,
            include_pending=include_pending,
            limit=limit,
        )

    def media_assets_page(
        self,
        *,
        spu_id: int | None = None,
        sku_ids: list[int] | None = None,
        media_type: str = "",
        include_pending: bool = True,
        page: int = 1,
        page_size: int = 80,
    ) -> tuple[list[dict], int]:
        return self.db.product_media_assets_page(
            spu_id=spu_id,
            sku_ids=sku_ids,
            media_type=media_type,
            include_pending=include_pending,
            page=page,
            page_size=page_size,
        )

    def delete_media(self, media_id: int) -> dict:
        return self.db.delete_product_media(media_id)

    def delete_pending_media(self, media_ids: Iterable[Any]) -> dict:
        return self.db.delete_pending_product_media(media_ids)

    def update_purchase_policy_by_series(self, series: list[str] | str, purchase_policy: str) -> dict:
        return self.db.update_purchase_policy_by_series(series, purchase_policy)

    def next_sku_no(self, *, start_number: Any = 1001, compact_from_start: bool = True) -> str:
        try:
            start = int(start_number or 1001)
        except (TypeError, ValueError):
            start = 1001
        with self.db.cursor() as cursor:
            return self.db._next_sku_no(
                cursor,
                start_number=max(start, 1001),
                compact_from_start=compact_from_start,
            )


def get_product_service() -> ProductService:
    return ProductService()

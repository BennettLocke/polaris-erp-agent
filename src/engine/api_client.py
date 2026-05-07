"""统一 API 请求引擎 - 完整 ERP 接口封装"""
import json
import httpx
from urllib.parse import quote
from typing import Any, Optional
from src.core.config import get_config
from src.engine.exceptions import APIError
from src.engine.retry import retry_on_api_error
from src.utils import get_logger

logger = get_logger("sjagent.api_client")


class ERPSystemClient:
    """
    ERP 系统 API 客户端
    统一封装所有 Agent API 调用，包含参数校验、异常捕获、失败重试、操作日志

    API 基础格式：
    https://shop.513sjbz.com/api.php?s=plugins/index&pluginsname=erp&pluginscontrol=Agent&pluginsaction={action}&api_key={key}
    """

    def __init__(self):
        self.config = get_config()
        self.base_url = self.config.erp_api_base
        self.api_key = self.config.erp_api_key
        self.timeout = 30.0
        self._client = httpx.Client(timeout=self.timeout)

    def _build_url(self, action: str) -> str:
        """构建 API URL"""
        return (
            f"{self.base_url}"
            f"?s=plugins/index"
            f"&pluginsname=erp"
            f"&pluginscontrol=Agent"
            f"&pluginsaction={action}"
            f"&api_key={self.api_key}"
        )

    def _post(self, action: str, data: dict) -> dict:
        """POST 请求"""
        url = self._build_url(action)
        logger.info(f"API POST: {action}")

        try:
            response = self._client.post(url, data=data)
            try:
                result = response.json()
            except ValueError:
                logger.error(f"API 返回非 JSON: status={response.status_code}, body={response.text[:200]}")
                raise APIError(f"API 返回非 JSON 响应: status={response.status_code}")

            if result.get("code") != 0:
                raise APIError(
                    message=result.get("msg", "API调用失败"),
                    code=result.get("code"),
                    response=result,
                )

            return result
        except httpx.HTTPError as e:
            logger.error(f"HTTP 请求异常: {e}")
            raise APIError(f"网络请求失败: {e}")

    def _upload(self, action: str, files: dict, data: dict | None = None) -> dict:
        """multipart upload request"""
        url = self._build_url(action)
        logger.info(f"API UPLOAD: {action}")

        try:
            response = self._client.post(url, data=data or {}, files=files)
            try:
                result = response.json()
            except ValueError:
                logger.error(f"API returned non-JSON: status={response.status_code}, body={response.text[:200]}")
                raise APIError(f"API returned non-JSON response: status={response.status_code}")

            if result.get("code") != 0:
                raise APIError(
                    message=result.get("msg", "API call failed"),
                    code=result.get("code"),
                    response=result,
                )
            return result
        except httpx.HTTPError as e:
            logger.error(f"HTTP upload error: {e}")
            raise APIError(f"Upload request failed: {e}")

    def _get(self, action: str, params: dict = None) -> dict:
        """GET 请求"""
        url = self._build_url(action)
        if params:
            for k, v in params.items():
                url += f"&{quote(str(k))}={quote(str(v))}"

        logger.info(f"API GET: {action}")

        try:
            response = self._client.get(url)
            try:
                result = response.json()
            except ValueError:
                logger.error(f"API 返回非 JSON: status={response.status_code}, body={response.text[:200]}")
                raise APIError(f"API 返回非 JSON 响应: status={response.status_code}")

            if result.get("code") != 0:
                raise APIError(
                    message=result.get("msg", "API调用失败"),
                    code=result.get("code"),
                    response=result,
                )

            return result
        except httpx.HTTPError as e:
            logger.error(f"HTTP 请求异常: {e}")
            raise APIError(f"网络请求失败: {e}")

    # ==================== 库存操作（4个）====================

    @retry_on_api_error(max_retries=3)
    def inventory_list(
        self,
        warehouse_id: Optional[int] = None,
        product_id: Optional[int] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """查询库存列表"""
        params = {"page": page, "page_size": page_size}
        if warehouse_id:
            params["warehouse_id"] = warehouse_id
        if product_id:
            params["product_id"] = product_id
        if keyword:
            params["keyword"] = keyword
        return self._get("InventoryList", params)

    @retry_on_api_error(max_retries=3)
    def inventory_detail(self, product_id: int) -> dict:
        """查询单产品库存（各仓库分布）"""
        return self._get("InventoryDetail", {"product_id": product_id})

    @retry_on_api_error(max_retries=3)
    def inventory_sync(
        self,
        warehouse_id: int,
        products: list[dict],
        note: str = "盘点同步",
    ) -> dict:
        """
        盘点同步（推荐）
        设置目标库存数（绝对值，非增量），自动创建status=3已盘点单，立即生效

        products: [{"product_id": X, "unit_id": 1, "number": 目标库存数}]
        """
        data = {
            "warehouse_id": warehouse_id,
            "note": note,
        }
        for i, p in enumerate(products):
            data[f"products[{i}][product_id]"] = p["product_id"]
            data[f"products[{i}][unit_id]"] = p.get("unit_id", 1)
            data[f"products[{i}][number]"] = p["number"]
        return self._post("InventorySync", data)

    @retry_on_api_error(max_retries=3)
    def inventory_check_add(
        self,
        warehouse_id: int,
        products: list[dict],
        note: str = "",
        status: int = 0,
    ) -> dict:
        """
        创建盘点单（不推荐，状态为0待审核不自动生效）
        请使用 inventory_sync 代替

        products: [{"product_id": X, "unit_id": 1, "check_number": Y}]
        """
        data = {
            "warehouse_id": warehouse_id,
            "status": status,
            "note": note,
        }
        for i, p in enumerate(products):
            data[f"products[{i}][product_id]"] = p["product_id"]
            data[f"products[{i}][unit_id]"] = p.get("unit_id", 1)
            data[f"products[{i}][check_number]"] = p["check_number"]
        return self._post("InventoryCheckAdd", data)

    # ==================== 产品管理（1个）====================

    @retry_on_api_error(max_retries=3)
    def product_list(
        self,
        keyword: Optional[str] = None,
        brand_name: Optional[str] = None,
        status: Optional[int] = None,
        category_id: Optional[int] = None,
        group: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """
        查询产品列表（支持模糊搜索）
        keyword 支持中文字符正则拆分
        """
        params = {"page": page, "page_size": page_size}
        if keyword:
            params["keyword"] = keyword
        if brand_name:
            params["brand_name"] = brand_name
        if status is not None:
            params["status"] = status
        if category_id:
            params["category_id"] = category_id
        if group:
            params["group"] = 1
        return self._get("ProductList", params)

    @retry_on_api_error(max_retries=3)
    def product_add(
        self,
        title: str,
        spec: str = "",
        unit_id: int = 1,
        simple_desc: str = "",
        brand_name: str = "",
    ) -> dict:
        """
        添加产品
        产品已存在返回已有ID，不重复创建
        """
        data = {"title": title}
        if spec:
            data["spec"] = spec
        if unit_id:
            data["unit_id"] = unit_id
        if simple_desc:
            data["simple_desc"] = simple_desc
        if brand_name:
            data["brand_name"] = brand_name
        return self._post("ProductAdd", data)

    @retry_on_api_error(max_retries=3)
    def product_detail(self, product_id: int) -> dict:
        """商品详情"""
        return self._get("ProductDetail", {"id": product_id})

    @retry_on_api_error(max_retries=3)
    def product_save_info(self, product_id: int | None = None) -> dict:
        """商品编辑基础数据"""
        params = {}
        if product_id:
            params["id"] = product_id
        return self._get("ProductSaveInfo", params)

    @retry_on_api_error(max_retries=3)
    def product_save(self, data: dict) -> dict:
        """创建/编辑商品"""
        form: dict[str, Any] = {}
        for key, value in (data or {}).items():
            if value is None:
                continue
            if isinstance(value, (list, dict)):
                form[key] = json.dumps(value, ensure_ascii=False)
            else:
                form[key] = value
        return self._post("ProductSave", form)

    @retry_on_api_error(max_retries=3)
    def product_upload(self, filename: str, content: bytes, content_type: str = "image/jpeg") -> dict:
        """上传商品图片"""
        return self._upload("ProductUpload", {
            "image": (filename or "product.jpg", content, content_type or "application/octet-stream")
        })

    @retry_on_api_error(max_retries=3)
    def product_shelves_update(self, product_id: int, state: int) -> dict:
        """同步商城商品上下架"""
        return self._post("ProductShelvesUpdate", {"id": product_id, "state": state})

    # ==================== 客户管理（2个）====================

    @retry_on_api_error(max_retries=3)
    def company_list(self, keyword: Optional[str] = None) -> dict:
        """查询客户列表"""
        params = {}
        if keyword:
            params["keyword"] = keyword
        return self._get("CompanyList", params if params else None)

    @retry_on_api_error(max_retries=3)
    def company_add(
        self,
        name: str,
        contacts_name: str = "",
        contacts_tel: str = "",
        address: str = "",
    ) -> dict:
        """添加客户"""
        data = {"name": name}
        if contacts_name:
            data["contacts_name"] = contacts_name
        if contacts_tel:
            data["contacts_tel"] = contacts_tel
        if address:
            data["address"] = address
        return self._post("CompanyAdd", data)

    # ==================== 销售管理（7个）====================

    @retry_on_api_error(max_retries=3)
    def sales_add(
        self,
        customer_id: int,
        warehouse_id: int,
        products: list[dict],
        pay_type: int = 1,
        note: str = "",
    ) -> dict:
        """
        开销售单（自动扣库存）
        开单即完成(status=5)，自动扣减仓库库存

        products: [{"product_id": X, "unit_id": 1, "warehouse_id": 2, "buy_number": Y, "price": Z}]
        """
        data = {
            "customer_id": customer_id,
            "warehouse_id": warehouse_id,
            "pay_type": pay_type,
            "note": note,
        }
        for i, p in enumerate(products):
            data[f"products[{i}][product_id]"] = p["product_id"]
            data[f"products[{i}][unit_id]"] = p.get("unit_id", 1)
            data[f"products[{i}][warehouse_id]"] = p.get("warehouse_id", warehouse_id)
            data[f"products[{i}][buy_number]"] = p["buy_number"]
            if "price" in p and p["price"]:
                data[f"products[{i}][price]"] = p["price"]
        return self._post("SalesAdd", data)

    @retry_on_api_error(max_retries=3)
    def sales_delete(self, ids: str) -> dict:
        """
        删除销售单（自动回滚库存）
        删除时自动退回库存到对应仓库
        """
        return self._post("SalesDelete", {"ids": ids})

    @retry_on_api_error(max_retries=3)
    def sales_list(
        self,
        keyword: Optional[str] = None,
        customer_id: Optional[int] = None,
        status: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """查询销售单列表"""
        params = {"page": page, "page_size": page_size}
        if keyword:
            params["keyword"] = keyword
        if customer_id:
            params["customer_id"] = customer_id
        if status is not None:
            params["status"] = status
        return self._get("SalesList", params)

    @retry_on_api_error(max_retries=3)
    def sales_detail(self, sales_id: int) -> dict:
        """销售单详情（含产品明细）"""
        return self._get("SalesDetail", {"id": sales_id})

    @retry_on_api_error(max_retries=3)
    def sales_print(self, sales_id: int) -> dict:
        """销售单打印数据"""
        return self._get("SalesPrint", {"id": sales_id})

    @retry_on_api_error(max_retries=3)
    def sales_print_html(self, sales_id: int) -> dict:
        """销售单打印页面（HTML）"""
        return self._get("SalesPrintHtml", {"id": sales_id})

    @retry_on_api_error(max_retries=3)
    def sales_print_task(self, sales_id: int) -> dict:
        """创建打印任务"""
        return self._post("SalesPrintTask", {"sales_id": sales_id})

    @retry_on_api_error(max_retries=3)
    def sales_print_task_list(self) -> dict:
        """待打印任务列表"""
        return self._get("SalesPrintTaskList")

    @retry_on_api_error(max_retries=3)
    def sales_print_task_done(self, task_id: int) -> dict:
        """标记打印完成"""
        return self._post("SalesPrintTaskDone", {"task_id": task_id})

    # ==================== 采购管理（1个）====================

    @retry_on_api_error(max_retries=3)
    def purchase_add(
        self,
        company_id: int,
        products: list[dict],
        note: str = "",
    ) -> dict:
        """
        创建采购单

        products: [{"product_id": X, "unit_id": 1, "buy_number": Y, "price": Z}]
        """
        data = {"company_id": company_id, "note": note}
        for i, p in enumerate(products):
            data[f"products[{i}][product_id]"] = p["product_id"]
            data[f"products[{i}][unit_id]"] = p.get("unit_id", 1)
            data[f"products[{i}][buy_number]"] = p["buy_number"]
            if "price" in p:
                data[f"products[{i}][price]"] = p["price"]
        return self._post("PurchaseAdd", data)

    # ==================== 其他出入库（2个）====================

    @retry_on_api_error(max_retries=3)
    def other_enter_add(
        self,
        warehouse_id: int,
        products: list[dict],
        note: str = "",
        status: int = 5,
    ) -> dict:
        """
        其他入库（采购入库/退货入库/进货入库）
        status=5 直接完成并入库

        products: [{"product_id": X, "unit_id": 1, "buy_number": Y}]
        """
        data = {
            "warehouse_id": warehouse_id,
            "status": status,
            "note": note,
        }
        for i, p in enumerate(products):
            data[f"products[{i}][product_id]"] = p["product_id"]
            data[f"products[{i}][unit_id]"] = p.get("unit_id", 1)
            data[f"products[{i}][buy_number]"] = p["buy_number"]
        return self._post("OtherEnterAdd", data)

    @retry_on_api_error(max_retries=3)
    def other_out_add(
        self,
        warehouse_id: int,
        products: list[dict],
        note: str = "",
        status: int = 5,
    ) -> dict:
        """
        其他出库（销售出库/报损出库/撤回错误入库）
        出库自动扣减库存，库存不足会报错回滚
        """
        data = {
            "warehouse_id": warehouse_id,
            "status": status,
            "note": note,
        }
        for i, p in enumerate(products):
            data[f"products[{i}][product_id]"] = p["product_id"]
            data[f"products[{i}][unit_id]"] = p.get("unit_id", 1)
            data[f"products[{i}][buy_number]"] = p["buy_number"]
        return self._post("OtherOutAdd", data)

    # ==================== 库存调拨（1个）====================

    @retry_on_api_error(max_retries=3)
    def inventory_transfer(
        self,
        out_warehouse_id: int,
        enter_warehouse_id: int,
        products: list[dict],
        note: str = "",
    ) -> dict:
        """
        仓库间调拨
        调出仓库扣库存，调入仓库加库存
        status=3 已调拨，立即生效
        """
        data = {
            "out_warehouse_id": out_warehouse_id,
            "enter_warehouse_id": enter_warehouse_id,
            "note": note,
        }
        for i, p in enumerate(products):
            data[f"products[{i}][product_id]"] = p["product_id"]
            data[f"products[{i}][unit_id]"] = p.get("unit_id", 1)
            data[f"products[{i}][transfer_number]"] = p["transfer_number"]
        return self._post("InventoryTransfer", data)

    # ==================== 仓库管理（1个）====================

    @retry_on_api_error(max_retries=3)
    def warehouse_list(self) -> dict:
        """
        查询仓库列表

        返回: [{"id": 1, "name": "自己店里"}, {"id": 2, "name": "百鑫仓库"}]
        """
        return self._get("WarehouseList")

    # ==================== 工作流订单（4个）====================

    @retry_on_api_error(max_retries=3)
    def workflow_order_list(
        self,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """工作流订单列表"""
        params = {"page": page, "page_size": page_size}
        if keyword:
            params["keyword"] = keyword
        return self._get("WorkflowOrderList", params)

    @retry_on_api_error(max_retries=3)
    def workflow_order_detail(self, order_id: int) -> dict:
        """工作流订单详情"""
        return self._get("WorkflowOrderDetail", {"id": order_id})

    @retry_on_api_error(max_retries=3)
    def workflow_order_save(
        self,
        customer_name: str,
        goods_name: str,
        order_quantity: int,
        order_id: Optional[int] = None,
        customer_phone: str = "",
        goods_color: str = "",
        order_images: list = None,
        is_screen_print: int = 0,
        order_type: int = 0,
        remark: str = "",
    ) -> dict:
        """
        保存工作流订单

        order_images: 图片URL列表 ["url1", "url2"]
        """
        data = {
            "customer_name": customer_name,
            "goods_name": goods_name,
            "order_quantity": order_quantity,
            "order_type": order_type,
        }
        if order_id:
            data["id"] = order_id
        if customer_phone:
            data["customer_phone"] = customer_phone
        if goods_color:
            data["goods_color"] = goods_color
        if order_images:
            for i, url in enumerate(order_images):
                data[f"order_images[{i}]"] = url
        if is_screen_print:
            data["is_screen_print"] = is_screen_print
        if remark:
            data["remark"] = remark
        return self._post("WorkflowOrderSave", data)

    @retry_on_api_error(max_retries=3)
    def workflow_order_status_update(self, order_id: int, field: str, value: int) -> dict:
        """更新工作流订单状态"""
        return self._post("WorkflowOrderStatusUpdate", {"id": order_id, "field": field, "value": value})

    @retry_on_api_error(max_retries=3)
    def workflow_order_delete(self, ids: str) -> dict:
        """删除工作流订单"""
        return self._post("WorkflowOrderDelete", {"ids": ids})

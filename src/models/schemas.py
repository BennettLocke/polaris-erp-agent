"""Pydantic 数据模型"""
from pydantic import BaseModel, Field
from typing import Optional


class OrderItem(BaseModel):
    """订单商品项"""
    product_id: int
    product_name: str
    color: Optional[str] = None
    quantity: int
    unit: str = "套"  # 套/个/张/捆
    unit_id: int = 1
    price: Optional[float] = None
    warehouse_id: int = 2  # 默认百鑫


class Customer(BaseModel):
    """客户信息"""
    customer_id: int
    name: str
    contacts_name: Optional[str] = None
    contacts_tel: Optional[str] = None
    address: Optional[str] = None


class InventoryRecord(BaseModel):
    """库存记录"""
    product_id: int
    product_name: str
    spec: str  # 颜色
    warehouse_id: int
    warehouse_name: str
    inventory: int  # 库存数量
    unit_id: int = 1


class SalesOrder(BaseModel):
    """销售单"""
    sales_id: int
    sales_no: str
    customer_id: int
    warehouse_id: int
    total_price: float
    status: int
    products: list[OrderItem] = Field(default_factory=list)


class WorkflowOrder(BaseModel):
    """工作流订单"""
    order_id: int
    customer_name: str
    goods_name: str
    color: Optional[str] = None
    quantity: int
    images: list[str] = Field(default_factory=list)
    status: str = "pending"

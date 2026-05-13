from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class OrderStatus(str, Enum):
    pending = "beklemede"
    processing = "işlemde"
    shipped = "kargoda"
    delivered = "teslim_edildi"
    cancelled = "iptal"


class ChatMessage(BaseModel):
    role: str  # "user" | "model"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []


class ChatResponse(BaseModel):
    reply: str
    tools_used: Optional[List[str]] = []


class Order(BaseModel):
    id: str
    customer_name: str
    customer_phone: str
    product: str
    quantity: int
    status: OrderStatus
    created_at: datetime
    tracking_code: Optional[str] = None


class OrderCreate(BaseModel):
    customer_name: str
    customer_phone: str
    product: str
    quantity: int
    unit_price: Optional[float] = None
    customer_address: Optional[str] = None
    notes: Optional[str] = None


class InventoryItem(BaseModel):
    product_name: str
    quantity: int
    unit: str
    low_stock_threshold: int
    supplier_email: Optional[str] = None


class InventoryItemCreate(BaseModel):
    product_name: str
    quantity: int
    unit: str
    low_stock_threshold: int
    supplier_email: Optional[str] = None
    unit_price: Optional[float] = 0.0
    cost_price: Optional[float] = 0.0
    warehouse: Optional[str] = "Ana Depo"
    supplier_name: Optional[str] = None


class CargoUpdate(BaseModel):
    order_id: str
    tracking_code: str
    status: str


class CargoCreate(BaseModel):
    tracking_code: str
    status: str
    location: str
    estimated_delivery: str
    delay_reason: Optional[str] = None


class OrderStatusUpdate(BaseModel):
    status: str
    tracking_code: Optional[str] = None


class PaymentStatusUpdate(BaseModel):
    payment_status: str          # ödenmedi | ödendi | kısmi
    payment_method: Optional[str] = None  # nakit | kredi_karti | havale | eft


class SupplierCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    product_categories: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    rating: Optional[float] = 5.0


class SupplierUpdate(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    product_categories: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    rating: Optional[float] = None

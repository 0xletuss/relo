from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

# Enums for order statuses
class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"

class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    BANK_TRANSFER = "bank_transfer"
    CASH_ON_DELIVERY = "cod"

# Request Models
class CreateOrderRequest(BaseModel):
    shipping_address: str = Field(..., min_length=10, max_length=500)
    billing_address: Optional[str] = Field(None, max_length=500)
    payment_method: PaymentMethod
    notes: Optional[str] = Field(None, max_length=1000)

    @validator('shipping_address')
    def validate_shipping_address(cls, v):
        if not v or not v.strip():
            raise ValueError('Shipping address is required')
        return v.strip()

    @validator('billing_address')
    def validate_billing_address(cls, v):
        if v:
            return v.strip()
        return v

class UpdateOrderStatusRequest(BaseModel):
    status: OrderStatus

class UpdatePaymentStatusRequest(BaseModel):
    payment_status: PaymentStatus

# Response Models
class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    product_name: str
    product_reference: Optional[str]
    quantity: int
    price: float
    subtotal: float
    created_at: datetime

    class Config:
        from_attributes = True

class OrderResponse(BaseModel):
    id: int
    customer_id: int
    order_number: str
    total_amount: float
    status: OrderStatus
    payment_status: PaymentStatus
    payment_method: str
    shipping_address: str
    billing_address: Optional[str]
    shipping_fee: float
    tax_amount: float
    discount_amount: float
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]

    class Config:
        from_attributes = True

class OrderSummaryResponse(BaseModel):
    id: int
    order_number: str
    total_amount: float
    status: OrderStatus
    payment_status: PaymentStatus
    items_count: int
    created_at: datetime

    class Config:
        from_attributes = True

class OrderListResponse(BaseModel):
    orders: List[OrderSummaryResponse]
    total_orders: int
    page: int
    page_size: int

class OrderActionResponse(BaseModel):
    message: str
    order: OrderResponse

# Order statistics
class OrderStatsResponse(BaseModel):
    total_orders: int
    pending_orders: int
    processing_orders: int
    shipped_orders: int
    delivered_orders: int
    cancelled_orders: int
    total_revenue: float
    average_order_value: float
"""
Order Models - SQLAlchemy and Pydantic
Consolidated to prevent duplicate class definitions
"""
from sqlalchemy import Column, Integer, String, DECIMAL, Text, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from models.database import Base
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, validator, Field
from typing import Optional, List

# =====================================================
# Enums - Define ONCE and use for both SQLAlchemy and Pydantic
# =====================================================

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

# =====================================================
# SQLAlchemy Models (Database Tables)
# =====================================================

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    total_amount = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    status = Column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING, index=True)
    payment_status = Column(SQLEnum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    payment_method = Column(String(50))
    shipping_address = Column(Text, nullable=False)
    billing_address = Column(Text)
    shipping_fee = Column(DECIMAL(10, 2), default=0.00)
    tax_amount = Column(DECIMAL(10, 2), default=0.00)
    discount_amount = Column(DECIMAL(10, 2), default=0.00)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - FIXED: Use back_populates consistently
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    customer = relationship("User", back_populates="orders")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    price = Column(DECIMAL(10, 2), nullable=False)
    subtotal = Column(DECIMAL(10, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product")

# =====================================================
# Pydantic Models (Request/Response)
# =====================================================

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

class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
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
    payment_method: Optional[str]
    shipping_address: str
    billing_address: Optional[str]
    shipping_fee: float
    tax_amount: float
    discount_amount: float
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse] = []

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

class OrderStatsResponse(BaseModel):
    total_orders: int
    pending_orders: int
    processing_orders: int
    shipped_orders: int
    delivered_orders: int
    cancelled_orders: int
    total_revenue: float
    average_order_value: float
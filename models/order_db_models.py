from sqlalchemy import Column, Integer, String, DECIMAL, Text, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from models.database import Base
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
    
    # Relationships
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    customer = relationship("User", backref="orders")

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
# =====================================================
# models/product_model.py - COMPLETE FIX
# =====================================================

from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models.database import Base

# Simple string constants for validation
class StockStatus:
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    PRE_ORDER = "pre_order"

class Product(Base):
    __tablename__ = "products"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, nullable=True, index=True)  # ADD THIS LINE
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    reference_number = Column(String(50), nullable=True, index=True)
    category = Column(String(100), nullable=True, index=True)
    material = Column(String(100), nullable=True)
    case_size = Column(String(20), nullable=True)
    image_url = Column(String(500), nullable=True)
    stock_status = Column(String(20), nullable=True, default="in_stock")
    stock = Column(Integer, nullable=False, default=0)  # ADD THIS LINE
    featured = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    cart_items = relationship("Cart", back_populates="product", cascade="all, delete-orphan")
    wishlist_items = relationship("Wishlist", back_populates="product", cascade="all, delete-orphan")
    # OrderItem relationship is defined in models/order.py

    def to_dict(self):
        return {
            "id": self.id,
            "seller_id": self.seller_id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "reference_number": self.reference_number,
            "category": self.category,
            "material": self.material,
            "case_size": self.case_size,
            "image_url": self.image_url,
            "stock_status": self.stock_status,
            "featured": self.featured,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class Category(Base):
    __tablename__ = "categories"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    slug = Column(String(100), nullable=False, unique=True)
    image_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "slug": self.slug,
            "image_url": self.image_url,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Cart(Base):
    __tablename__ = "cart"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    product = relationship("Product", back_populates="cart_items")

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "product": self.product.to_dict() if self.product else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class Wishlist(Base):
    __tablename__ = "wishlist"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    product = relationship("Product", back_populates="wishlist_items")

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "product_id": self.product_id,
            "product": self.product.to_dict() if self.product else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

# NOTE: Order and OrderItem are now defined in models/order.py
# Do NOT define them here to avoid duplicate class errors
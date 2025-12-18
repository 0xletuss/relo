from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, MetaData, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# Build DATABASE_URL from environment variables
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "railway")

# Validate required environment variables
if not DB_PASSWORD:
    raise ValueError("DB_PASSWORD environment variable is required")
if not DB_HOST:
    raise ValueError("DB_HOST environment variable is required")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"Connecting to database at {DB_HOST}:{DB_PORT}/{DB_NAME}")

# Create engine with MySQL specific settings
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=5,
        max_overflow=10,
        echo=False,
        connect_args={
            "connect_timeout": 10,
        }
    )
    # Test the connection
    with engine.connect() as conn:
        print("✓ Database connection successful!")
except Exception as e:
    print(f"✗ Database connection failed: {e}")
    raise

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FIXED: Clear metadata to prevent enum caching issues
metadata = MetaData()
Base = declarative_base(metadata=metadata)

# Database models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default='customer', nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True, index=True)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships - using back_populates for bidirectional relationships
    # FIXED: Removed 'orders' relationship - orders link to Seller/Customer, not User directly
    seller = relationship("Seller", back_populates="user", uselist=False, lazy="select")
    customer = relationship("Customer", back_populates="user", uselist=False, lazy="select")

class Seller(Base):
    __tablename__ = "sellers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    business_name = Column(String(255), nullable=True)
    business_description = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    verified = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="seller")
    # Note: Add orders relationship when Order model is imported:
    # orders = relationship("Order", back_populates="seller")

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="customer")
    # Note: Add relationships when models are imported:
    # orders = relationship("Order", back_populates="customer")
    # cart_items = relationship("Cart", back_populates="customer")
    # wishlist_items = relationship("Wishlist", back_populates="customer")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    token = Column(String(500), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_revoked = Column(Boolean, default=False)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create tables - FIXED import path
def create_tables():
    """Create all database tables including order tables"""
    print("📦 Importing models...")
    
    # Import all models to ensure they're registered with Base
    try:
        # FIXED: Import from order.py (not order_db_models)
        from models.order import Order, OrderItem
        print("✓ Order models imported successfully")
    except ImportError as e:
        print(f"⚠ Warning: Could not import order models: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        from models.product_model import Product, Cart
        print("✓ Product models imported successfully")
    except ImportError as e:
        print(f"⚠ Warning: Could not import product models: {e}")
        import traceback
        traceback.print_exc()
    
    # Create all tables
    print("🔨 Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created/verified")

# Export for use in other modules
SQLALCHEMY_DATABASE_URL = DATABASE_URL
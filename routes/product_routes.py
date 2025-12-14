# =====================================================
# routes/product_routes.py
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from models.database import get_db
from models.product_model import Product, Category, Cart, Wishlist, Order, OrderItem, StockStatus, OrderStatus
from routes.auth_routes import get_current_user  # Import from auth_routes instead
import random
import string
from datetime import datetime

router = APIRouter()

# =====================================================
# Pydantic Schemas
# =====================================================

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    reference_number: Optional[str] = None
    category: Optional[str] = None
    material: Optional[str] = None
    case_size: Optional[str] = None
    image_url: Optional[str] = None
    stock_status: Optional[StockStatus] = StockStatus.IN_STOCK
    featured: bool = False

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    reference_number: Optional[str] = None
    category: Optional[str] = None
    material: Optional[str] = None
    case_size: Optional[str] = None
    image_url: Optional[str] = None
    stock_status: Optional[StockStatus] = None
    featured: Optional[bool] = None

class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    reference_number: Optional[str]
    category: Optional[str]
    material: Optional[str]
    case_size: Optional[str]
    image_url: Optional[str]
    stock_status: str
    featured: bool
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        from_attributes = True

class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)

class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1)

class WishlistItemCreate(BaseModel):
    product_id: int

class OrderCreate(BaseModel):
    shipping_address: str
    billing_address: Optional[str] = None
    payment_method: str
    notes: Optional[str] = None

# =====================================================
# Product Endpoints
# =====================================================

@router.get("/products", response_model=List[ProductResponse])
async def get_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    category: Optional[str] = None,
    featured: Optional[bool] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort_by: Optional[str] = Query(None, regex="^(price_asc|price_desc|name_asc|name_desc|newest)$"),
    db: Session = Depends(get_db)
):
    """Get all products with optional filtering and sorting"""
    query = db.query(Product)

    # Apply filters
    if category:
        query = query.filter(Product.category == category)
    if featured is not None:
        query = query.filter(Product.featured == featured)
    if search:
        query = query.filter(
            (Product.name.ilike(f"%{search}%")) | 
            (Product.description.ilike(f"%{search}%"))
        )
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    # Apply sorting
    if sort_by == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort_by == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort_by == "name_asc":
        query = query.order_by(Product.name.asc())
    elif sort_by == "name_desc":
        query = query.order_by(Product.name.desc())
    elif sort_by == "newest":
        query = query.order_by(Product.created_at.desc())
    else:
        query = query.order_by(Product.id.desc())

    products = query.offset(skip).limit(limit).all()
    return [ProductResponse(**product.to_dict()) for product in products]

@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """Get a specific product by ID"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse(**product.to_dict())

@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new product (Admin only)"""
    # You can add admin check here if needed
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Not authorized")
    
    new_product = Product(**product.dict())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return ProductResponse(**new_product.to_dict())

@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update a product (Admin only)"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    for key, value in product_update.dict(exclude_unset=True).items():
        setattr(product, key, value)
    
    db.commit()
    db.refresh(product)
    return ProductResponse(**product.to_dict())

@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete a product (Admin only)"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db.delete(product)
    db.commit()
    return None

@router.get("/products/category/{category}")
async def get_products_by_category(
    category: str,
    db: Session = Depends(get_db)
):
    """Get products by category"""
    products = db.query(Product).filter(Product.category == category).all()
    return [ProductResponse(**product.to_dict()) for product in products]

@router.get("/categories")
async def get_categories(db: Session = Depends(get_db)):
    """Get all unique categories"""
    categories = db.query(Category).all()
    return [cat.to_dict() for cat in categories]

# =====================================================
# Cart Endpoints
# =====================================================

@router.get("/cart")
async def get_cart(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's cart"""
    cart_items = db.query(Cart).filter(Cart.customer_id == current_user.id).all()
    
    total = sum(item.product.price * item.quantity for item in cart_items)
    
    return {
        "items": [item.to_dict() for item in cart_items],
        "total": total,
        "item_count": sum(item.quantity for item in cart_items)
    }

@router.post("/cart", status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    cart_item: CartItemCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add item to cart"""
    # Check if product exists
    product = db.query(Product).filter(Product.id == cart_item.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check if item already in cart
    existing_item = db.query(Cart).filter(
        Cart.customer_id == current_user.id,
        Cart.product_id == cart_item.product_id
    ).first()
    
    if existing_item:
        # Update quantity
        existing_item.quantity += cart_item.quantity
        db.commit()
        db.refresh(existing_item)
        return {"message": "Cart updated", "item": existing_item.to_dict()}
    else:
        # Add new item
        new_cart_item = Cart(
            customer_id=current_user.id,
            product_id=cart_item.product_id,
            quantity=cart_item.quantity
        )
        db.add(new_cart_item)
        db.commit()
        db.refresh(new_cart_item)
        return {"message": "Item added to cart", "item": new_cart_item.to_dict()}

@router.put("/cart/{cart_item_id}")
async def update_cart_item(
    cart_item_id: int,
    cart_update: CartItemUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update cart item quantity"""
    cart_item = db.query(Cart).filter(
        Cart.id == cart_item_id,
        Cart.customer_id == current_user.id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    
    cart_item.quantity = cart_update.quantity
    db.commit()
    db.refresh(cart_item)
    return {"message": "Cart item updated", "item": cart_item.to_dict()}

@router.delete("/cart/{cart_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_cart(
    cart_item_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove item from cart"""
    cart_item = db.query(Cart).filter(
        Cart.id == cart_item_id,
        Cart.customer_id == current_user.id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    
    db.delete(cart_item)
    db.commit()
    return None

@router.delete("/cart", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear all items from cart"""
    db.query(Cart).filter(Cart.customer_id == current_user.id).delete()
    db.commit()
    return None

# =====================================================
# Wishlist Endpoints
# =====================================================

@router.get("/wishlist")
async def get_wishlist(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's wishlist"""
    wishlist_items = db.query(Wishlist).filter(
        Wishlist.customer_id == current_user.id
    ).all()
    
    return {
        "items": [item.to_dict() for item in wishlist_items],
        "count": len(wishlist_items)
    }

@router.post("/wishlist", status_code=status.HTTP_201_CREATED)
async def add_to_wishlist(
    wishlist_item: WishlistItemCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add item to wishlist"""
    # Check if product exists
    product = db.query(Product).filter(Product.id == wishlist_item.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check if already in wishlist
    existing = db.query(Wishlist).filter(
        Wishlist.customer_id == current_user.id,
        Wishlist.product_id == wishlist_item.product_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Item already in wishlist")
    
    new_item = Wishlist(
        customer_id=current_user.id,
        product_id=wishlist_item.product_id
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return {"message": "Item added to wishlist", "item": new_item.to_dict()}

@router.delete("/wishlist/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_wishlist(
    product_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove item from wishlist"""
    wishlist_item = db.query(Wishlist).filter(
        Wishlist.customer_id == current_user.id,
        Wishlist.product_id == product_id
    ).first()
    
    if not wishlist_item:
        raise HTTPException(status_code=404, detail="Wishlist item not found")
    
    db.delete(wishlist_item)
    db.commit()
    return None

# =====================================================
# Order Endpoints
# =====================================================

def generate_order_number():
    """Generate unique order number"""
    timestamp = datetime.now().strftime("%Y%m%d")
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ORD-{timestamp}-{random_str}"

@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create order from cart"""
    # Get cart items
    cart_items = db.query(Cart).filter(Cart.customer_id == current_user.id).all()
    
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Calculate total
    total_amount = sum(item.product.price * item.quantity for item in cart_items)
    
    # Create order
    new_order = Order(
        customer_id=current_user.id,
        order_number=generate_order_number(),
        total_amount=total_amount,
        shipping_address=order_data.shipping_address,
        billing_address=order_data.billing_address or order_data.shipping_address,
        payment_method=order_data.payment_method,
        notes=order_data.notes,
        status=OrderStatus.PENDING
    )
    db.add(new_order)
    db.flush()
    
    # Create order items
    for cart_item in cart_items:
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=cart_item.product_id,
            quantity=cart_item.quantity,
            price=cart_item.product.price,
            subtotal=cart_item.product.price * cart_item.quantity
        )
        db.add(order_item)
    
    # Clear cart
    db.query(Cart).filter(Cart.customer_id == current_user.id).delete()
    
    db.commit()
    db.refresh(new_order)
    
    return {
        "message": "Order created successfully",
        "order": new_order.to_dict()
    }

@router.get("/orders")
async def get_orders(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's orders"""
    orders = db.query(Order).filter(
        Order.customer_id == current_user.id
    ).order_by(Order.created_at.desc()).all()
    
    return {"orders": [order.to_dict() for order in orders]}

@router.get("/orders/{order_id}")
async def get_order(
    order_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific order details"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.customer_id == current_user.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return order.to_dict()
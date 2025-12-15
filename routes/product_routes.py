# =====================================================
# routes/product_routes.py - FIXED PYDANTIC SCHEMAS
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from models.database import get_db
from models.product_model import Product, Category, Cart, Wishlist, Order, OrderItem
from routes.auth_routes import get_current_user
import random
import string
from datetime import datetime

router = APIRouter()

# =====================================================
# Pydantic Schemas - FIXED: Use str instead of Enum
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
    stock_status: Optional[str] = "in_stock"  # Changed from StockStatus enum
    featured: bool = False


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    reference_number: Optional[str] = None
    category: Optional[str] = None
    material: Optional[str] = None
    case_size: Optional[str] = None
    image_url: Optional[str] = None
    stock_status: Optional[str] = None  # Changed from StockStatus enum
    featured: Optional[bool] = None


class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    reference_number: Optional[str] = None
    category: Optional[str] = None
    material: Optional[str] = None
    case_size: Optional[str] = None
    image_url: Optional[str] = None
    stock_status: Optional[str] = None  # Changed from enum to str
    featured: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    slug: str
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1)


class CartItemResponse(BaseModel):
    id: int
    customer_id: int
    product_id: int
    quantity: int
    product: ProductResponse
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CartResponse(BaseModel):
    items: List[CartItemResponse]
    total: float
    item_count: int


class WishlistItemCreate(BaseModel):
    product_id: int


class WishlistItemResponse(BaseModel):
    id: int
    customer_id: int
    product_id: int
    product: ProductResponse
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WishlistResponse(BaseModel):
    items: List[WishlistItemResponse]
    count: int


class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    quantity: int
    price: float
    subtotal: float
    product: ProductResponse

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: int
    customer_id: int
    order_number: str
    total_amount: float
    status: Optional[str] = None  # Changed from enum to str
    shipping_address: Optional[str] = None
    billing_address: Optional[str] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    order_items: List[OrderItemResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    shipping_address: str
    billing_address: Optional[str] = None
    payment_method: str
    notes: Optional[str] = None


class OrdersListResponse(BaseModel):
    orders: List[OrderResponse]


# =====================================================
# Product Endpoints
# =====================================================

@router.get("/products", response_model=List[ProductResponse])
async def get_products(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Max number of items to return"),
    category: Optional[str] = Query(None, description="Filter by category"),
    featured: Optional[bool] = Query(None, description="Filter featured products"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter"),
    sort_by: Optional[str] = Query(
        None, 
        regex="^(price_asc|price_desc|name_asc|name_desc|newest)$",
        description="Sort order: price_asc, price_desc, name_asc, name_desc, newest"
    ),
    db: Session = Depends(get_db)
):
    """
    Get all products with optional filtering and sorting.
    
    - **skip**: Pagination offset
    - **limit**: Number of items per page (max 100)
    - **category**: Filter by product category
    - **featured**: Show only featured products
    - **search**: Search text in product name/description
    - **min_price/max_price**: Price range filter
    - **sort_by**: Sort products
    """
    try:
        query = db.query(Product)

        # Apply filters
        if category:
            query = query.filter(Product.category == category)
        
        if featured is not None:
            query = query.filter(Product.featured == featured)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Product.name.ilike(search_pattern)) | 
                (Product.description.ilike(search_pattern))
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
            # Default sorting by ID descending
            query = query.order_by(Product.id.desc())

        # Execute query with pagination
        products = query.offset(skip).limit(limit).all()
        
        return products
    
    except Exception as e:
        print(f"Error in get_products: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch products: {str(e)}"
        )


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific product by ID"""
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )
    
    return product


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new product (Admin only).
    
    Requires authentication. Add admin check if needed.
    """
    try:
        # Optional: Add admin authorization check
        # if not current_user.is_admin:
        #     raise HTTPException(status_code=403, detail="Admin access required")
        
        new_product = Product(**product.dict())
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        
        return new_product
    
    except Exception as e:
        db.rollback()
        print(f"Error creating product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create product: {str(e)}"
        )


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update a product (Admin only)"""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {product_id} not found"
            )
        
        # Update only provided fields
        update_data = product_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)
        
        db.commit()
        db.refresh(product)
        
        return product
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error updating product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update product: {str(e)}"
        )


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete a product (Admin only)"""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {product_id} not found"
            )
        
        db.delete(product)
        db.commit()
        
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error deleting product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete product: {str(e)}"
        )


@router.get("/products/category/{category}", response_model=List[ProductResponse])
async def get_products_by_category(
    category: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get products by category with pagination"""
    try:
        products = db.query(Product)\
            .filter(Product.category == category)\
            .offset(skip)\
            .limit(limit)\
            .all()
        
        return products
    
    except Exception as e:
        print(f"Error fetching products by category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch products: {str(e)}"
        )


@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(db: Session = Depends(get_db)):
    """Get all unique categories"""
    try:
        categories = db.query(Category).all()
        return categories
    
    except Exception as e:
        print(f"Error fetching categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch categories: {str(e)}"
        )


# =====================================================
# Cart Endpoints
# =====================================================

@router.get("/cart", response_model=CartResponse)
async def get_cart(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's shopping cart"""
    try:
        cart_items = db.query(Cart)\
            .filter(Cart.customer_id == current_user.id)\
            .all()
        
        total = sum(item.product.price * item.quantity for item in cart_items)
        item_count = sum(item.quantity for item in cart_items)
        
        return CartResponse(
            items=cart_items,
            total=total,
            item_count=item_count
        )
    
    except Exception as e:
        print(f"Error fetching cart: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch cart: {str(e)}"
        )


@router.post("/cart", status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    cart_item: CartItemCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add item to cart or update quantity if already exists"""
    try:
        # Verify product exists
        product = db.query(Product).filter(Product.id == cart_item.product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {cart_item.product_id} not found"
            )
        
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
            
            return {
                "message": "Cart updated successfully",
                "item": existing_item
            }
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
            
            return {
                "message": "Item added to cart successfully",
                "item": new_cart_item
            }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error adding to cart: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add item to cart: {str(e)}"
        )


@router.put("/cart/{cart_item_id}")
async def update_cart_item(
    cart_item_id: int,
    cart_update: CartItemUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update cart item quantity"""
    try:
        cart_item = db.query(Cart).filter(
            Cart.id == cart_item_id,
            Cart.customer_id == current_user.id
        ).first()
        
        if not cart_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cart item with ID {cart_item_id} not found"
            )
        
        cart_item.quantity = cart_update.quantity
        db.commit()
        db.refresh(cart_item)
        
        return {
            "message": "Cart item updated successfully",
            "item": cart_item
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error updating cart item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update cart item: {str(e)}"
        )


@router.delete("/cart/{cart_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_cart(
    cart_item_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove item from cart"""
    try:
        cart_item = db.query(Cart).filter(
            Cart.id == cart_item_id,
            Cart.customer_id == current_user.id
        ).first()
        
        if not cart_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cart item with ID {cart_item_id} not found"
            )
        
        db.delete(cart_item)
        db.commit()
        
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error removing cart item: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove cart item: {str(e)}"
        )


@router.delete("/cart", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear all items from cart"""
    try:
        deleted_count = db.query(Cart)\
            .filter(Cart.customer_id == current_user.id)\
            .delete()
        
        db.commit()
        
        return None
    
    except Exception as e:
        db.rollback()
        print(f"Error clearing cart: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cart: {str(e)}"
        )


# =====================================================
# Wishlist Endpoints
# =====================================================

@router.get("/wishlist", response_model=WishlistResponse)
async def get_wishlist(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's wishlist"""
    try:
        wishlist_items = db.query(Wishlist)\
            .filter(Wishlist.customer_id == current_user.id)\
            .all()
        
        return WishlistResponse(
            items=wishlist_items,
            count=len(wishlist_items)
        )
    
    except Exception as e:
        print(f"Error fetching wishlist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch wishlist: {str(e)}"
        )


@router.post("/wishlist", status_code=status.HTTP_201_CREATED)
async def add_to_wishlist(
    wishlist_item: WishlistItemCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add item to wishlist"""
    try:
        # Verify product exists
        product = db.query(Product).filter(Product.id == wishlist_item.product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {wishlist_item.product_id} not found"
            )
        
        # Check if already in wishlist
        existing = db.query(Wishlist).filter(
            Wishlist.customer_id == current_user.id,
            Wishlist.product_id == wishlist_item.product_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item already in wishlist"
            )
        
        # Add to wishlist
        new_item = Wishlist(
            customer_id=current_user.id,
            product_id=wishlist_item.product_id
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        
        return {
            "message": "Item added to wishlist successfully",
            "item": new_item
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error adding to wishlist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add item to wishlist: {str(e)}"
        )


@router.delete("/wishlist/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_wishlist(
    product_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove item from wishlist"""
    try:
        wishlist_item = db.query(Wishlist).filter(
            Wishlist.customer_id == current_user.id,
            Wishlist.product_id == product_id
        ).first()
        
        if not wishlist_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Wishlist item with product ID {product_id} not found"
            )
        
        db.delete(wishlist_item)
        db.commit()
        
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error removing from wishlist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove from wishlist: {str(e)}"
        )


# =====================================================
# Order Endpoints
# =====================================================

def generate_order_number() -> str:
    """Generate unique order number with timestamp and random string"""
    timestamp = datetime.now().strftime("%Y%m%d")
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ORD-{timestamp}-{random_str}"


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create order from cart items.
    
    Requires:
    - Non-empty cart
    - Valid shipping address
    - Payment method
    """
    try:
        # Get cart items
        cart_items = db.query(Cart)\
            .filter(Cart.customer_id == current_user.id)\
            .all()
        
        if not cart_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cart is empty. Cannot create order."
            )
        
        # Calculate total amount
        total_amount = sum(item.product.price * item.quantity for item in cart_items)
        
        # Create order - FIXED: Use string instead of enum
        new_order = Order(
            customer_id=current_user.id,
            order_number=generate_order_number(),
            total_amount=total_amount,
            shipping_address=order_data.shipping_address,
            billing_address=order_data.billing_address or order_data.shipping_address,
            payment_method=order_data.payment_method,
            notes=order_data.notes,
            status="pending"  # Changed from OrderStatus.PENDING
        )
        db.add(new_order)
        db.flush()  # Get order ID without committing
        
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
        
        # Commit transaction
        db.commit()
        db.refresh(new_order)
        
        return new_order
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error creating order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create order: {str(e)}"
        )


@router.get("/orders", response_model=OrdersListResponse)
async def get_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's orders with pagination"""
    try:
        orders = db.query(Order)\
            .filter(Order.customer_id == current_user.id)\
            .order_by(Order.created_at.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
        
        return OrdersListResponse(orders=orders)
    
    except Exception as e:
        print(f"Error fetching orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch orders: {str(e)}"
        )


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific order details"""
    try:
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.customer_id == current_user.id
        ).first()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order with ID {order_id} not found"
            )
        
        return order
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch order: {str(e)}"
        )
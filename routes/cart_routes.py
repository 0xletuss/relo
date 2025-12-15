from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from models.cart_model import (
    AddToCartRequest,
    UpdateCartItemRequest,
    CartItemResponse,
    CartResponse,
    CartActionResponse,
    ProductInCart
)
from models.database import get_db, User, Cart, Product, Customer
from routes.auth_routes import get_current_user
from typing import List

router = APIRouter()

# Helper function to calculate cart totals
def calculate_cart_response(cart_items, db: Session) -> CartResponse:
    """Calculate cart totals and format response"""
    items = []
    total_amount = 0.0
    total_items = 0

    for cart_item in cart_items:
        # Get product details
        product = db.query(Product).filter(Product.id == cart_item.product_id).first()
        if not product:
            continue

        subtotal = float(product.price) * cart_item.quantity
        total_amount += subtotal
        total_items += cart_item.quantity

        # Create product response
        product_response = ProductInCart(
            id=product.id,
            name=product.name,
            price=float(product.price),
            reference_number=product.reference_number,
            category=product.category,
            material=product.material,
            case_size=product.case_size,
            image_url=product.image_url
        )

        # Create cart item response
        cart_item_response = CartItemResponse(
            id=cart_item.id,
            product_id=cart_item.product_id,
            quantity=cart_item.quantity,
            created_at=cart_item.created_at,
            updated_at=cart_item.updated_at,
            product=product_response,
            subtotal=subtotal
        )
        items.append(cart_item_response)

    return CartResponse(
        items=items,
        total_items=total_items,
        total_amount=total_amount
    )

# Helper function to get or create customer
def get_or_create_customer(user: User, db: Session) -> Customer:
    """Get existing customer or create new one for user"""
    # Try to find customer by email
    customer = db.query(Customer).filter(Customer.email == user.email).first()
    
    if not customer:
        # Create new customer
        customer = Customer(
            email=user.email,
            first_name=user.username,
            last_name=""
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
    
    return customer

# Routes
@router.get("/cart", response_model=CartResponse)
async def get_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's cart"""
    # Get or create customer
    customer = get_or_create_customer(current_user, db)
    
    # Get cart items
    cart_items = db.query(Cart).filter(Cart.customer_id == customer.id).all()
    
    return calculate_cart_response(cart_items, db)

@router.post("/cart", response_model=CartActionResponse, status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    request: AddToCartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add product to cart"""
    # Get or create customer
    customer = get_or_create_customer(current_user, db)
    
    # Verify product exists
    product = db.query(Product).filter(Product.id == request.product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check if product is in stock
    if product.stock_status != "in_stock":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product is out of stock"
        )
    
    # Check if item already exists in cart
    existing_cart_item = db.query(Cart).filter(
        Cart.customer_id == customer.id,
        Cart.product_id == request.product_id
    ).first()
    
    if existing_cart_item:
        # Update quantity
        existing_cart_item.quantity += request.quantity
        db.commit()
        db.refresh(existing_cart_item)
        message = "Cart updated successfully"
    else:
        # Create new cart item
        new_cart_item = Cart(
            customer_id=customer.id,
            product_id=request.product_id,
            quantity=request.quantity
        )
        db.add(new_cart_item)
        db.commit()
        db.refresh(new_cart_item)
        message = "Product added to cart successfully"
    
    # Get updated cart
    cart_items = db.query(Cart).filter(Cart.customer_id == customer.id).all()
    cart_response = calculate_cart_response(cart_items, db)
    
    return CartActionResponse(
        message=message,
        cart=cart_response
    )

@router.put("/cart/{cart_item_id}", response_model=CartActionResponse)
async def update_cart_item(
    cart_item_id: int,
    request: UpdateCartItemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update cart item quantity"""
    # Get or create customer
    customer = get_or_create_customer(current_user, db)
    
    # Find cart item
    cart_item = db.query(Cart).filter(
        Cart.id == cart_item_id,
        Cart.customer_id == customer.id
    ).first()
    
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found"
        )
    
    # Update quantity
    cart_item.quantity = request.quantity
    db.commit()
    db.refresh(cart_item)
    
    # Get updated cart
    cart_items = db.query(Cart).filter(Cart.customer_id == customer.id).all()
    cart_response = calculate_cart_response(cart_items, db)
    
    return CartActionResponse(
        message="Cart item updated successfully",
        cart=cart_response
    )

@router.delete("/cart/{cart_item_id}", response_model=CartActionResponse)
async def remove_from_cart(
    cart_item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove item from cart"""
    # Get or create customer
    customer = get_or_create_customer(current_user, db)
    
    # Find cart item
    cart_item = db.query(Cart).filter(
        Cart.id == cart_item_id,
        Cart.customer_id == customer.id
    ).first()
    
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found"
        )
    
    # Delete cart item
    db.delete(cart_item)
    db.commit()
    
    # Get updated cart
    cart_items = db.query(Cart).filter(Cart.customer_id == customer.id).all()
    cart_response = calculate_cart_response(cart_items, db)
    
    return CartActionResponse(
        message="Item removed from cart successfully",
        cart=cart_response
    )

@router.delete("/cart", response_model=CartActionResponse)
async def clear_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear entire cart"""
    # Get or create customer
    customer = get_or_create_customer(current_user, db)
    
    # Delete all cart items
    db.query(Cart).filter(Cart.customer_id == customer.id).delete()
    db.commit()
    
    return CartActionResponse(
        message="Cart cleared successfully",
        cart=CartResponse(items=[], total_items=0, total_amount=0.0)
    )
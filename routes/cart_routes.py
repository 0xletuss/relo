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
from models.database import get_db, User
from models.product_model import Cart, Product
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

# Routes
@router.get("/cart", response_model=CartResponse)
async def get_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's cart"""
    # Cart is linked directly to user via customer_id (which is user.id)
    cart_items = db.query(Cart).filter(Cart.customer_id == current_user.id).all()
    
    return calculate_cart_response(cart_items, db)

@router.post("/cart", response_model=CartActionResponse, status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    request: AddToCartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add product to cart"""
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
        Cart.customer_id == current_user.id,
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
            customer_id=current_user.id,
            product_id=request.product_id,
            quantity=request.quantity
        )
        db.add(new_cart_item)
        db.commit()
        db.refresh(new_cart_item)
        message = "Product added to cart successfully"
    
    # Get updated cart
    cart_items = db.query(Cart).filter(Cart.customer_id == current_user.id).all()
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
    # Find cart item
    cart_item = db.query(Cart).filter(
        Cart.id == cart_item_id,
        Cart.customer_id == current_user.id
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
    cart_items = db.query(Cart).filter(Cart.customer_id == current_user.id).all()
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
    # Find cart item
    cart_item = db.query(Cart).filter(
        Cart.id == cart_item_id,
        Cart.customer_id == current_user.id
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
    cart_items = db.query(Cart).filter(Cart.customer_id == current_user.id).all()
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
    # Delete all cart items
    db.query(Cart).filter(Cart.customer_id == current_user.id).delete()
    db.commit()
    
    return CartActionResponse(
        message="Cart cleared successfully",
        cart=CartResponse(items=[], total_items=0, total_amount=0.0)
    )
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
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            logger.warning(f"Product {cart_item.product_id} not found for cart item {cart_item.id}")
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

# Cart Routes - These will be mounted at /api
@router.get("/cart", response_model=CartResponse)
async def get_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's cart"""
    try:
        logger.info(f"Fetching cart for user {current_user.id}")
        cart_items = db.query(Cart).filter(Cart.user_id == current_user.id).all()
        logger.info(f"Found {len(cart_items)} cart items")
        
        response = calculate_cart_response(cart_items, db)
        logger.info(f"Cart response: {response.total_items} items, total: {response.total_amount}")
        return response
    except Exception as e:
        logger.error(f"Error fetching cart: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch cart: {str(e)}"
        )

@router.post("/cart", response_model=CartActionResponse, status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    request: AddToCartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add product to cart"""
    try:
        logger.info(f"User {current_user.id} adding product {request.product_id} (qty: {request.quantity})")
        
        # Verify product exists
        product = db.query(Product).filter(Product.id == request.product_id).first()
        if not product:
            logger.error(f"Product {request.product_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        
        logger.info(f"Product found: {product.name}, stock: {product.stock_status}")
        
        # Check if product is in stock
        if product.stock_status == "out_of_stock":
            logger.warning(f"Product {request.product_id} is out of stock")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product is out of stock"
            )
        
        # Check if item already exists in cart
        existing_cart_item = db.query(Cart).filter(
            Cart.user_id == current_user.id,
            Cart.product_id == request.product_id
        ).first()
        
        if existing_cart_item:
            # Update quantity
            logger.info(f"Updating existing cart item {existing_cart_item.id}")
            old_qty = existing_cart_item.quantity
            existing_cart_item.quantity += request.quantity
            logger.info(f"Quantity updated: {old_qty} -> {existing_cart_item.quantity}")
            message = "Cart updated successfully"
        else:
            # Create new cart item
            logger.info(f"Creating new cart item")
            new_cart_item = Cart(
                user_id=current_user.id,
                product_id=request.product_id,
                quantity=request.quantity
            )
            db.add(new_cart_item)
            logger.info(f"New cart item added to session")
            message = "Product added to cart successfully"
        
        # Commit changes
        logger.info("Committing to database...")
        db.commit()
        logger.info("Commit successful")
        
        # Refresh if we updated existing item
        if existing_cart_item:
            db.refresh(existing_cart_item)
        
        # Get updated cart
        logger.info("Fetching updated cart...")
        cart_items = db.query(Cart).filter(Cart.user_id == current_user.id).all()
        logger.info(f"Retrieved {len(cart_items)} cart items after add")
        
        cart_response = calculate_cart_response(cart_items, db)
        
        return CartActionResponse(
            message=message,
            cart=cart_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding to cart: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add to cart: {str(e)}"
        )

@router.put("/cart/{cart_item_id}", response_model=CartActionResponse)
async def update_cart_item(
    cart_item_id: int,
    request: UpdateCartItemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update cart item quantity"""
    try:
        logger.info(f"Updating cart item {cart_item_id} to quantity {request.quantity}")
        
        # Find cart item
        cart_item = db.query(Cart).filter(
            Cart.id == cart_item_id,
            Cart.user_id == current_user.id
        ).first()
        
        if not cart_item:
            logger.error(f"Cart item {cart_item_id} not found for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found"
            )
        
        # Update quantity
        cart_item.quantity = request.quantity
        db.commit()
        db.refresh(cart_item)
        logger.info(f"Cart item {cart_item_id} updated successfully")
        
        # Get updated cart
        cart_items = db.query(Cart).filter(Cart.user_id == current_user.id).all()
        cart_response = calculate_cart_response(cart_items, db)
        
        return CartActionResponse(
            message="Cart item updated successfully",
            cart=cart_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating cart item: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update cart item: {str(e)}"
        )

@router.delete("/cart/{cart_item_id}", response_model=CartActionResponse)
async def remove_from_cart(
    cart_item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove item from cart"""
    try:
        logger.info(f"Removing cart item {cart_item_id}")
        
        # Find cart item
        cart_item = db.query(Cart).filter(
            Cart.id == cart_item_id,
            Cart.user_id == current_user.id
        ).first()
        
        if not cart_item:
            logger.error(f"Cart item {cart_item_id} not found for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found"
            )
        
        # Delete cart item
        db.delete(cart_item)
        db.commit()
        logger.info(f"Cart item {cart_item_id} deleted successfully")
        
        # Get updated cart
        cart_items = db.query(Cart).filter(Cart.user_id == current_user.id).all()
        cart_response = calculate_cart_response(cart_items, db)
        
        return CartActionResponse(
            message="Item removed from cart successfully",
            cart=cart_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error removing cart item: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove cart item: {str(e)}"
        )

@router.delete("/cart", response_model=CartActionResponse)
async def clear_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear entire cart"""
    try:
        logger.info(f"Clearing cart for user {current_user.id}")
        
        # Delete all cart items
        deleted_count = db.query(Cart).filter(Cart.user_id == current_user.id).delete()
        db.commit()
        logger.info(f"Cleared {deleted_count} items from cart")
        
        return CartActionResponse(
            message="Cart cleared successfully",
            cart=CartResponse(items=[], total_items=0, total_amount=0.0)
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error clearing cart: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cart: {str(e)}"
        )
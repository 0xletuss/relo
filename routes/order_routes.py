from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
# FIXED: Import everything from order.py (not order_model or order_db_models)
from models.order import (
    Order,
    OrderItem,
    CreateOrderRequest,
    UpdateOrderStatusRequest,
    UpdatePaymentStatusRequest,
    OrderResponse,
    OrderSummaryResponse,
    OrderListResponse,
    OrderActionResponse,
    OrderItemResponse,
    OrderStatsResponse,
    OrderStatus,
    PaymentStatus
)
from models.database import get_db, User
from models.product_model import Cart, Product
from routes.auth_routes import get_current_user
from typing import Optional
import logging
from datetime import datetime
import random
import string

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Helper function to generate order number
def generate_order_number() -> str:
    """Generate unique order number"""
    date_str = datetime.now().strftime("%Y%m%d")
    random_str = ''.join(random.choices(string.digits, k=6))
    return f"ORD-{date_str}-{random_str}"

# Helper function to calculate order totals
def calculate_order_totals(cart_items, db: Session):
    """Calculate subtotal, tax, shipping, and total"""
    subtotal = 0.0
    
    for cart_item in cart_items:
        product = db.query(Product).filter(Product.id == cart_item.product_id).first()
        if product:
            subtotal += float(product.price) * cart_item.quantity
    
    # Calculate additional fees (customize as needed)
    shipping_fee = 10.0 if subtotal < 1000 else 0.0  # Free shipping over $1000
    tax_rate = 0.12  # 12% tax
    tax_amount = subtotal * tax_rate
    discount = 0.0
    
    total = subtotal + shipping_fee + tax_amount - discount
    
    return {
        "subtotal": subtotal,
        "shipping_fee": shipping_fee,
        "tax_amount": tax_amount,
        "discount_amount": discount,
        "total_amount": total
    }

# Helper function to build order response
def build_order_response(order: Order, db: Session) -> OrderResponse:
    """Build complete order response with items"""
    order_items = []
    
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        order_item_response = OrderItemResponse(
            id=item.id,
            order_id=item.order_id,
            product_id=item.product_id,
            quantity=item.quantity,
            price=float(item.price),
            subtotal=float(item.subtotal),
            created_at=item.created_at
        )
        order_items.append(order_item_response)
    
    return OrderResponse(
        id=order.id,
        customer_id=order.customer_id,
        order_number=order.order_number,
        total_amount=float(order.total_amount),
        status=order.status,
        payment_status=order.payment_status,
        payment_method=order.payment_method,
        shipping_address=order.shipping_address,
        billing_address=order.billing_address,
        shipping_fee=float(order.shipping_fee),
        tax_amount=float(order.tax_amount),
        discount_amount=float(order.discount_amount),
        notes=order.notes,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=order_items
    )

# Order Routes
@router.post("/orders", response_model=OrderActionResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create order from cart items"""
    try:
        logger.info(f"User {current_user.id} creating order")
        
        # Get cart items
        cart_items = db.query(Cart).filter(Cart.customer_id == current_user.id).all()
        
        if not cart_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cart is empty. Cannot create order."
            )
        
        logger.info(f"Found {len(cart_items)} items in cart")
        
        # Verify all products are available
        for cart_item in cart_items:
            product = db.query(Product).filter(Product.id == cart_item.product_id).first()
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product {cart_item.product_id} not found"
                )
            if product.stock_status == "out_of_stock":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product '{product.name}' is out of stock"
                )
        
        # Calculate totals
        totals = calculate_order_totals(cart_items, db)
        
        # Generate order number
        order_number = generate_order_number()
        
        # Create order
        new_order = Order(
            customer_id=current_user.id,
            order_number=order_number,
            total_amount=totals["total_amount"],
            status=OrderStatus.PENDING,
            payment_status=PaymentStatus.PENDING,
            payment_method=request.payment_method.value,
            shipping_address=request.shipping_address,
            billing_address=request.billing_address or request.shipping_address,
            shipping_fee=totals["shipping_fee"],
            tax_amount=totals["tax_amount"],
            discount_amount=totals["discount_amount"],
            notes=request.notes
        )
        
        db.add(new_order)
        db.flush()  # Get the order ID
        
        logger.info(f"Order {order_number} created with ID {new_order.id}")
        
        # Create order items from cart
        for cart_item in cart_items:
            product = db.query(Product).filter(Product.id == cart_item.product_id).first()
            subtotal = float(product.price) * cart_item.quantity
            
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=cart_item.product_id,
                quantity=cart_item.quantity,
                price=product.price,
                subtotal=subtotal
            )
            db.add(order_item)
        
        # Clear cart after order creation
        db.query(Cart).filter(Cart.customer_id == current_user.id).delete()
        
        # Commit transaction
        db.commit()
        db.refresh(new_order)
        
        logger.info(f"Order {order_number} completed successfully")
        
        # Build response
        order_response = build_order_response(new_order, db)
        
        return OrderActionResponse(
            message="Order created successfully",
            order=order_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating order: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create order: {str(e)}"
        )

@router.get("/orders", response_model=OrderListResponse)
async def get_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status_filter: Optional[OrderStatus] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's orders with pagination"""
    try:
        logger.info(f"Fetching orders for user {current_user.id}")
        
        # Build query
        query = db.query(Order).filter(Order.customer_id == current_user.id)
        
        # Apply status filter if provided
        if status_filter:
            query = query.filter(Order.status == status_filter)
        
        # Get total count
        total_orders = query.count()
        
        # Apply pagination and ordering
        orders = query.order_by(desc(Order.created_at))\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()
        
        # Build response
        order_summaries = []
        for order in orders:
            items_count = len(order.items)
            summary = OrderSummaryResponse(
                id=order.id,
                order_number=order.order_number,
                total_amount=float(order.total_amount),
                status=order.status,
                payment_status=order.payment_status,
                items_count=items_count,
                created_at=order.created_at
            )
            order_summaries.append(summary)
        
        return OrderListResponse(
            orders=order_summaries,
            total_orders=total_orders,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error fetching orders: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch orders: {str(e)}"
        )

@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific order details"""
    try:
        logger.info(f"Fetching order {order_id} for user {current_user.id}")
        
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.customer_id == current_user.id
        ).first()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        return build_order_response(order, db)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching order: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch order: {str(e)}"
        )

@router.patch("/orders/{order_id}/cancel", response_model=OrderActionResponse)
async def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel an order"""
    try:
        logger.info(f"Cancelling order {order_id} for user {current_user.id}")
        
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.customer_id == current_user.id
        ).first()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Only allow cancellation of pending or processing orders
        if order.status not in [OrderStatus.PENDING, OrderStatus.PROCESSING]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel order with status '{order.status.value}'"
            )
        
        order.status = OrderStatus.CANCELLED
        db.commit()
        db.refresh(order)
        
        logger.info(f"Order {order_id} cancelled successfully")
        
        return OrderActionResponse(
            message="Order cancelled successfully",
            order=build_order_response(order, db)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling order: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel order: {str(e)}"
        )

@router.get("/orders/stats/summary", response_model=OrderStatsResponse)
async def get_order_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get order statistics for current user"""
    try:
        logger.info(f"Fetching order stats for user {current_user.id}")
        
        # Get all orders for user
        orders = db.query(Order).filter(Order.customer_id == current_user.id).all()
        
        # Calculate stats
        total_orders = len(orders)
        pending = sum(1 for o in orders if o.status == OrderStatus.PENDING)
        processing = sum(1 for o in orders if o.status == OrderStatus.PROCESSING)
        shipped = sum(1 for o in orders if o.status == OrderStatus.SHIPPED)
        delivered = sum(1 for o in orders if o.status == OrderStatus.DELIVERED)
        cancelled = sum(1 for o in orders if o.status == OrderStatus.CANCELLED)
        
        # Calculate revenue (only delivered orders)
        total_revenue = sum(float(o.total_amount) for o in orders if o.status == OrderStatus.DELIVERED)
        avg_order_value = total_revenue / delivered if delivered > 0 else 0.0
        
        return OrderStatsResponse(
            total_orders=total_orders,
            pending_orders=pending,
            processing_orders=processing,
            shipped_orders=shipped,
            delivered_orders=delivered,
            cancelled_orders=cancelled,
            total_revenue=total_revenue,
            average_order_value=avg_order_value
        )
        
    except Exception as e:
        logger.error(f"Error fetching order stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch order stats: {str(e)}"
        )
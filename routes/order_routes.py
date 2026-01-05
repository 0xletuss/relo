from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
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

# =====================================================
# Helper Functions
# =====================================================

def generate_order_number() -> str:
    """Generate unique order number"""
    date_str = datetime.now().strftime("%Y%m%d")
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ORD-{date_str}-{random_str}"


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


# =====================================================
# Order Routes
# =====================================================

@router.post("/orders", response_model=OrderActionResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create order from cart items
    
    CRITICAL FIX:
    - Cart.customer_id references users.id (so we use current_user.id)
    - Order.customer_id references customers.id (so we use current_user.customer.id)
    """
    try:
        # STEP 1: Verify user has customer profile
        if not current_user.customer:
            logger.error(f"User {current_user.id} attempted to create order without customer profile")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User does not have a customer profile. Only customers can create orders."
            )
        
        # STEP 2: Get the actual customer_id (this is the fix!)
        customer_id = current_user.customer.id
        logger.info(f"Creating order - User ID: {current_user.id}, Customer ID: {customer_id}")
        
        # STEP 3: Get cart items using current_user.id (because Cart.customer_id = users.id)
        cart_items = db.query(Cart).filter(Cart.user_id == current_user.id).all()
        
        if not cart_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cart is empty. Cannot create order."
            )
        
        logger.info(f"Found {len(cart_items)} items in cart for user {current_user.id}")
        
        # STEP 4: Verify all products are available
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
        
        # STEP 5: Calculate totals
        totals = calculate_order_totals(cart_items, db)
        
        # STEP 6: Generate order number
        order_number = generate_order_number()
        
        # STEP 7: Create order with CUSTOMER_ID (not user_id!)
        new_order = Order(
            customer_id=customer_id,  # THIS IS THE CRITICAL FIX - Use customer.id, not user.id
            order_number=order_number,
            total_amount=totals["total_amount"],
            status=OrderStatus.PENDING,
            payment_status=PaymentStatus.PENDING,
            payment_method=request.payment_method.value if hasattr(request.payment_method, 'value') else request.payment_method,
            shipping_address=request.shipping_address,
            billing_address=request.billing_address or request.shipping_address,
            shipping_fee=totals["shipping_fee"],
            tax_amount=totals["tax_amount"],
            discount_amount=totals["discount_amount"],
            notes=request.notes
        )
        
        db.add(new_order)
        db.flush()  # Get the order ID without committing
        
        logger.info(f"Order {order_number} created with ID {new_order.id} for customer {customer_id}")
        
        # STEP 8: Create order items from cart
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
        
        # STEP 9: Clear cart after order creation (using current_user.id)
        deleted_count = db.query(Cart).filter(Cart.user_id == current_user.id).delete()
        logger.info(f"Cleared {deleted_count} items from cart for user {current_user.id}")
        
        # STEP 10: Commit transaction
        db.commit()
        db.refresh(new_order)
        
        logger.info(f"✅ Order {order_number} completed successfully")
        
        # STEP 11: Build and return response
        order_response = build_order_response(new_order, db)
        
        return OrderActionResponse(
            message="Order created successfully",
            order=order_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error creating order: {str(e)}", exc_info=True)
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
        # Verify user has customer profile
        if not current_user.customer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User does not have a customer profile."
            )
        
        customer_id = current_user.customer.id
        logger.info(f"Fetching orders for customer {customer_id}")
        
        # Build query using customer_id
        query = db.query(Order).filter(Order.customer_id == customer_id)
        
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
        
    except HTTPException:
        raise
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
        # Verify user has customer profile
        if not current_user.customer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User does not have a customer profile."
            )
        
        customer_id = current_user.customer.id
        logger.info(f"Fetching order {order_id} for customer {customer_id}")
        
        # Filter by customer_id
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.customer_id == customer_id
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
        # Verify user has customer profile
        if not current_user.customer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User does not have a customer profile."
            )
        
        customer_id = current_user.customer.id
        logger.info(f"Cancelling order {order_id} for customer {customer_id}")
        
        # Filter by customer_id
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.customer_id == customer_id
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
        # Verify user has customer profile
        if not current_user.customer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User does not have a customer profile."
            )
        
        customer_id = current_user.customer.id
        logger.info(f"Fetching order stats for customer {customer_id}")
        
        # Get all orders for customer
        orders = db.query(Order).filter(Order.customer_id == customer_id).all()
        
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching order stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch order stats: {str(e)}"
        )


# =====================================================
# Checkout Endpoints (Aliases for frontend compatibility)
# =====================================================

@router.post("/checkout/process", response_model=OrderActionResponse, status_code=status.HTTP_201_CREATED)
async def checkout_process(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process checkout - creates order from cart items
    This is an alias for the create_order endpoint to match frontend expectations
    """
    logger.info(f"Checkout process called by user {current_user.id}")
    return await create_order(request, current_user, db)


@router.get("/checkout/summary")
async def checkout_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get checkout summary with cart items and totals"""
    try:
        # Verify user has customer profile
        if not current_user.customer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User does not have a customer profile."
            )
        
        customer_id = current_user.customer.id
        logger.info(f"Fetching checkout summary - User ID: {current_user.id}, Customer ID: {customer_id}")
        
        # Get cart items (Cart.customer_id actually references users.id)
        cart_items = db.query(Cart).filter(Cart.user_id == current_user.id).all()
        
        if not cart_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cart is empty"
            )
        
        # Calculate totals
        items_data = []
        subtotal = 0.0
        
        for cart_item in cart_items:
            product = db.query(Product).filter(Product.id == cart_item.product_id).first()
            if product:
                item_subtotal = float(product.price) * cart_item.quantity
                subtotal += item_subtotal
                
                items_data.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "quantity": cart_item.quantity,
                    "price": float(product.price),
                    "subtotal": item_subtotal,
                    "image_url": product.image_url,
                    "variant_name": None,
                    "variant_value": None
                })
        
        # Calculate fees
        shipping_fee = 10.0 if subtotal < 1000 else 0.0
        tax_rate = 0.12
        tax_amount = subtotal * tax_rate
        marketplace_fee = 0.0
        discount = 0.0
        
        total = subtotal + shipping_fee + tax_amount + marketplace_fee - discount
        
        logger.info(f"Checkout summary: {len(items_data)} items, total: ₱{total}")
        
        return {
            "items": items_data,
            "item_count": len(cart_items),
            "subtotal": subtotal,
            "shipping_fee": shipping_fee,
            "tax": tax_amount,
            "marketplace_fee": marketplace_fee,
            "discount": discount,
            "total": total
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching checkout summary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch checkout summary: {str(e)}"
        )
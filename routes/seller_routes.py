from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from models.database import get_db_connection
from decimal import Decimal
import traceback

router = APIRouter()

# Pydantic Models
class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    category: Optional[str] = None
    stock: int = 0
    material: Optional[str] = None
    case_size: Optional[str] = None
    reference_number: Optional[str] = None
    image_url: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    stock: Optional[int] = None
    stock_status: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: str

# Helper function to get seller_id from user
def get_seller_id(user_id: int):
    # For now, return user_id as seller_id
    # Later, you can join with sellers table
    return user_id

# ==================== DASHBOARD ====================
@router.get("/seller/stats")
async def get_seller_stats(seller_id: int):
    """Get dashboard statistics for seller"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Total Products
        cursor.execute("SELECT COUNT(*) as total FROM products WHERE seller_id = %s", (seller_id,))
        total_products = cursor.fetchone()['total']
        
        # Total Orders
        cursor.execute("SELECT COUNT(*) as total FROM orders WHERE seller_id = %s", (seller_id,))
        total_orders = cursor.fetchone()['total']
        
        # Revenue (only delivered orders)
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as revenue 
            FROM orders 
            WHERE seller_id = %s AND status = 'DELIVERED'
        """, (seller_id,))
        revenue = cursor.fetchone()['revenue']
        
        # Pending Orders
        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM orders 
            WHERE seller_id = %s AND status = 'PENDING'
        """, (seller_id,))
        pending_orders = cursor.fetchone()['total']
        
        cursor.close()
        conn.close()
        
        return {
            "total_products": total_products or 0,
            "total_orders": total_orders or 0,
            "revenue": float(revenue) if revenue else 0.0,
            "pending_orders": pending_orders or 0
        }
    except Exception as e:
        print(f"❌ Error in get_seller_stats: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/seller/recent-orders")
async def get_recent_orders(seller_id: int, limit: int = 5):
    """Get recent orders for seller"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                o.id,
                o.order_number,
                o.customer_name,
                o.customer_phone,
                o.total_amount,
                o.status,
                o.created_at,
                GROUP_CONCAT(CONCAT(p.name, ' x', oi.quantity) SEPARATOR ', ') as items
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            LEFT JOIN products p ON oi.product_id = p.id
            WHERE o.seller_id = %s
            GROUP BY o.id
            ORDER BY o.created_at DESC
            LIMIT %s
        """, (seller_id, limit))
        
        orders = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Convert datetime and Decimal
        for order in orders:
            if order.get('created_at'):
                order['created_at'] = order['created_at'].isoformat()
            if isinstance(order.get('total_amount'), Decimal):
                order['total_amount'] = float(order['total_amount'])
        
        return {"orders": orders}
    except Exception as e:
        print(f"❌ Error in get_recent_orders: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ==================== PRODUCTS / INVENTORY ====================
@router.get("/seller/products")
async def get_seller_products(
    seller_id: int, 
    search: Optional[str] = None,
    category: Optional[str] = None
):
    """Get all products for a seller"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT id, name, description, price, category, stock, 
                   stock_status, image_url, created_at
            FROM products 
            WHERE seller_id = %s
        """
        params = [seller_id]
        
        if search:
            query += " AND (name LIKE %s OR description LIKE %s)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term])
        
        if category:
            query += " AND category = %s"
            params.append(category)
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Convert types
        for product in products:
            if isinstance(product.get('price'), Decimal):
                product['price'] = float(product['price'])
            if product.get('created_at'):
                product['created_at'] = product['created_at'].isoformat()
        
        return {"products": products}
    except Exception as e:
        print(f"❌ Error in get_seller_products: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/seller/products")
async def create_product(product: ProductCreate, seller_id: int):
    """Create a new product"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO products 
            (seller_id, name, description, price, category, stock, 
             material, case_size, reference_number, image_url, stock_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            seller_id, product.name, product.description, product.price,
            product.category, product.stock, product.material, product.case_size,
            product.reference_number, product.image_url,
            'in_stock' if product.stock > 0 else 'out_of_stock'
        ))
        
        conn.commit()
        product_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        return {"message": "Product created successfully", "product_id": product_id}
    except Exception as e:
        print(f"❌ Error in create_product: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/seller/products/{product_id}")
async def update_product(product_id: int, product: ProductUpdate, seller_id: int):
    """Update a product"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build dynamic update query
        update_fields = []
        params = []
        
        if product.name:
            update_fields.append("name = %s")
            params.append(product.name)
        if product.description is not None:
            update_fields.append("description = %s")
            params.append(product.description)
        if product.price:
            update_fields.append("price = %s")
            params.append(product.price)
        if product.category:
            update_fields.append("category = %s")
            params.append(product.category)
        if product.stock is not None:
            update_fields.append("stock = %s")
            params.append(product.stock)
            update_fields.append("stock_status = %s")
            params.append('in_stock' if product.stock > 0 else 'out_of_stock')
        if product.stock_status:
            update_fields.append("stock_status = %s")
            params.append(product.stock_status)
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        params.extend([product_id, seller_id])
        query = f"UPDATE products SET {', '.join(update_fields)} WHERE id = %s AND seller_id = %s"
        
        cursor.execute(query, params)
        conn.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Product not found")
        
        cursor.close()
        conn.close()
        return {"message": "Product updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in update_product: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/seller/products/{product_id}")
async def delete_product(product_id: int, seller_id: int):
    """Delete a product"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM products WHERE id = %s AND seller_id = %s",
            (product_id, seller_id)
        )
        conn.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Product not found")
        
        cursor.close()
        conn.close()
        return {"message": "Product deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in delete_product: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ORDERS ====================
@router.get("/seller/orders")
async def get_seller_orders(
    seller_id: int,
    status: Optional[str] = None,
    limit: int = 50
):
    """Get all orders for a seller"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT 
                o.id,
                o.order_number,
                o.customer_name,
                o.customer_phone,
                o.total_amount,
                o.status,
                o.shipping_address,
                o.payment_status,
                o.payment_method,
                o.notes,
                o.created_at,
                GROUP_CONCAT(
                    CONCAT(p.name, ' x', oi.quantity)
                    SEPARATOR '|'
                ) as items
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            LEFT JOIN products p ON oi.product_id = p.id
            WHERE o.seller_id = %s
        """
        params = [seller_id]
        
        if status:
            query += " AND o.status = %s"
            params.append(status.upper())
        
        query += " GROUP BY o.id ORDER BY o.created_at DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, params)
        orders = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Format response
        for order in orders:
            if order.get('created_at'):
                order['created_at'] = order['created_at'].isoformat()
            if isinstance(order.get('total_amount'), Decimal):
                order['total_amount'] = float(order['total_amount'])
            if order.get('items'):
                order['items'] = order['items'].split('|')
        
        return {"orders": orders}
    except Exception as e:
        print(f"❌ Error in get_seller_orders: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/seller/orders/{order_id}/status")
async def update_order_status(order_id: int, status_update: OrderStatusUpdate, seller_id: int):
    """Update order status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        valid_statuses = ['PENDING', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED']
        if status_update.status.upper() not in valid_statuses:
            raise HTTPException(status_code=400, detail="Invalid status")
        
        cursor.execute("""
            UPDATE orders 
            SET status = %s, updated_at = NOW()
            WHERE id = %s AND seller_id = %s
        """, (status_update.status.upper(), order_id, seller_id))
        
        conn.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Order not found")
        
        cursor.close()
        conn.close()
        return {"message": "Order status updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in update_order_status: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ANALYTICS ====================
@router.get("/seller/analytics/revenue")
async def get_revenue_analytics(seller_id: int, period: str = 'month'):
    """Get revenue analytics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Determine date range
        days = {'week': 7, 'month': 30, 'year': 365}.get(period, 30)
        
        cursor.execute("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as order_count,
                SUM(total_amount) as revenue
            FROM orders
            WHERE seller_id = %s 
                AND status = 'DELIVERED'
                AND created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """, (seller_id, days))
        
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        for row in data:
            if row.get('date'):
                row['date'] = row['date'].isoformat()
            if isinstance(row.get('revenue'), Decimal):
                row['revenue'] = float(row['revenue'])
        
        return {"data": data}
    except Exception as e:
        print(f"❌ Error in get_revenue_analytics: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/seller/analytics/top-products")
async def get_top_products(seller_id: int, limit: int = 5):
    """Get top selling products"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                p.id,
                p.name,
                p.category,
                SUM(oi.quantity) as total_sold,
                SUM(oi.quantity * oi.price) as total_revenue
            FROM products p
            INNER JOIN order_items oi ON p.id = oi.product_id
            INNER JOIN orders o ON oi.order_id = o.id
            WHERE p.seller_id = %s AND o.status = 'DELIVERED'
            GROUP BY p.id
            ORDER BY total_revenue DESC
            LIMIT %s
        """, (seller_id, limit))
        
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        
        for product in products:
            if isinstance(product.get('total_revenue'), Decimal):
                product['total_revenue'] = float(product['total_revenue'])
        
        return {"products": products}
    except Exception as e:
        print(f"❌ Error in get_top_products: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
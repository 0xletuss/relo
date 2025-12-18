from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timedelta
from models.database import get_db
from models.product_model import Product
from models.order import Order, OrderItem
from decimal import Decimal
import traceback
import cloudinary
import cloudinary.uploader
import base64

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

# ==================== IMAGE UPLOAD ====================
@router.post("/seller/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """Upload image to Cloudinary"""
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read file content
        contents = await file.read()
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            contents,
            folder="rolex_products",
            resource_type="image",
            transformation=[
                {'width': 1000, 'height': 1000, 'crop': 'limit'},
                {'quality': 'auto:good'}
            ]
        )
        
        return {
            "message": "Image uploaded successfully",
            "url": upload_result['secure_url'],
            "public_id": upload_result['public_id']
        }
    except Exception as e:
        print(f"❌ Error in upload_image: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")

@router.delete("/seller/delete-image")
async def delete_image(public_id: str):
    """Delete image from Cloudinary"""
    try:
        result = cloudinary.uploader.destroy(public_id)
        return {"message": "Image deleted successfully", "result": result}
    except Exception as e:
        print(f"❌ Error in delete_image: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to delete image: {str(e)}")

# ==================== DASHBOARD ====================
@router.get("/seller/stats")
async def get_seller_stats(seller_id: int, db: Session = Depends(get_db)):
    """Get dashboard statistics for seller"""
    try:
        # Total Products
        total_products = db.query(func.count(Product.id)).filter(
            Product.seller_id == seller_id
        ).scalar() or 0
        
        # Total Orders
        total_orders = db.query(func.count(Order.id)).filter(
            Order.seller_id == seller_id
        ).scalar() or 0
        
        # Revenue (only delivered orders)
        revenue = db.query(func.sum(Order.total_amount)).filter(
            Order.seller_id == seller_id,
            Order.status == 'DELIVERED'
        ).scalar() or 0
        
        # Pending Orders
        pending_orders = db.query(func.count(Order.id)).filter(
            Order.seller_id == seller_id,
            Order.status == 'PENDING'
        ).scalar() or 0
        
        return {
            "total_products": total_products,
            "total_orders": total_orders,
            "revenue": float(revenue),
            "pending_orders": pending_orders
        }
    except Exception as e:
        print(f"❌ Error in get_seller_stats: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/seller/recent-orders")
async def get_recent_orders(
    seller_id: int, 
    limit: int = 5, 
    db: Session = Depends(get_db)
):
    """Get recent orders for seller"""
    try:
        orders = db.query(Order).filter(
            Order.seller_id == seller_id
        ).order_by(desc(Order.created_at)).limit(limit).all()
        
        result = []
        for order in orders:
            # Get order items
            items = db.query(OrderItem).filter(
                OrderItem.order_id == order.id
            ).all()
            
            items_text = ', '.join([
                f"{item.product.name if item.product else 'Unknown'} x{item.quantity}"
                for item in items
            ])
            
            result.append({
                "id": order.id,
                "order_number": order.order_number,
                "customer_name": order.customer_name,
                "customer_phone": order.customer_phone,
                "total_amount": float(order.total_amount),
                "status": order.status,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "items": items_text
            })
        
        return {"orders": result}
    except Exception as e:
        print(f"❌ Error in get_recent_orders: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ==================== PRODUCTS / INVENTORY ====================
@router.get("/seller/products")
async def get_seller_products(
    seller_id: int,
    search: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all products for a seller"""
    try:
        query = db.query(Product).filter(Product.seller_id == seller_id)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Product.name.like(search_term)) | 
                (Product.description.like(search_term))
            )
        
        if category:
            query = query.filter(Product.category == category)
        
        products = query.order_by(desc(Product.created_at)).all()
        
        result = []
        for product in products:
            result.append({
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": float(product.price) if product.price else 0.0,
                "category": product.category,
                "stock": product.stock,
                "stock_status": product.stock_status,
                "image_url": product.image_url,
                "material": product.material,
                "case_size": product.case_size,
                "reference_number": product.reference_number,
                "created_at": product.created_at.isoformat() if product.created_at else None
            })
        
        return {"products": result}
    except Exception as e:
        print(f"❌ Error in get_seller_products: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/seller/products")
async def create_product(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    price: float = Form(...),
    category: Optional[str] = Form(None),
    stock: int = Form(0),
    material: Optional[str] = Form(None),
    case_size: Optional[str] = Form(None),
    reference_number: Optional[str] = Form(None),
    seller_id: int = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Create a new product with image upload"""
    try:
        image_url = None
        
        # Upload image to Cloudinary if provided
        if image and image.filename:
            # Validate file type
            if not image.content_type.startswith('image/'):
                raise HTTPException(status_code=400, detail="File must be an image")
            
            # Read file content
            contents = await image.read()
            
            # Upload to Cloudinary
            upload_result = cloudinary.uploader.upload(
                contents,
                folder="rolex_products",
                resource_type="image",
                transformation=[
                    {'width': 1000, 'height': 1000, 'crop': 'limit'},
                    {'quality': 'auto:good'}
                ]
            )
            
            image_url = upload_result['secure_url']
            print(f"✅ Image uploaded to Cloudinary: {image_url}")
        
        # Create product in database
        new_product = Product(
            seller_id=seller_id,
            name=name,
            description=description,
            price=price,
            category=category,
            stock=stock,
            material=material,
            case_size=case_size,
            reference_number=reference_number,
            image_url=image_url,
            stock_status='in_stock' if stock > 0 else 'out_of_stock'
        )
        
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        
        return {
            "message": "Product created successfully", 
            "product_id": new_product.id,
            "image_url": image_url
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error in create_product: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/seller/products/{product_id}")
async def update_product(
    product_id: int,
    seller_id: int = Form(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    category: Optional[str] = Form(None),
    stock: Optional[int] = Form(None),
    material: Optional[str] = Form(None),
    case_size: Optional[str] = Form(None),
    reference_number: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Update a product with optional new image"""
    try:
        db_product = db.query(Product).filter(
            Product.id == product_id,
            Product.seller_id == seller_id
        ).first()
        
        if not db_product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Upload new image if provided
        if image and image.filename:
            # Validate file type
            if not image.content_type.startswith('image/'):
                raise HTTPException(status_code=400, detail="File must be an image")
            
            # Delete old image from Cloudinary if exists
            if db_product.image_url:
                try:
                    # Extract public_id from URL
                    public_id = db_product.image_url.split('/')[-1].split('.')[0]
                    cloudinary.uploader.destroy(f"rolex_products/{public_id}")
                except:
                    pass  # Continue even if deletion fails
            
            # Upload new image
            contents = await image.read()
            upload_result = cloudinary.uploader.upload(
                contents,
                folder="rolex_products",
                resource_type="image",
                transformation=[
                    {'width': 1000, 'height': 1000, 'crop': 'limit'},
                    {'quality': 'auto:good'}
                ]
            )
            
            db_product.image_url = upload_result['secure_url']
            print(f"✅ New image uploaded: {upload_result['secure_url']}")
        
        # Update other fields
        if name is not None:
            db_product.name = name
        if description is not None:
            db_product.description = description
        if price is not None:
            db_product.price = price
        if category is not None:
            db_product.category = category
        if stock is not None:
            db_product.stock = stock
            db_product.stock_status = 'in_stock' if stock > 0 else 'out_of_stock'
        if material is not None:
            db_product.material = material
        if case_size is not None:
            db_product.case_size = case_size
        if reference_number is not None:
            db_product.reference_number = reference_number
        
        db_product.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "message": "Product updated successfully",
            "image_url": db_product.image_url
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error in update_product: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/seller/products/{product_id}")
async def delete_product(
    product_id: int, 
    seller_id: int, 
    db: Session = Depends(get_db)
):
    """Delete a product and its image from Cloudinary"""
    try:
        db_product = db.query(Product).filter(
            Product.id == product_id,
            Product.seller_id == seller_id
        ).first()
        
        if not db_product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Delete image from Cloudinary if exists
        if db_product.image_url:
            try:
                # Extract public_id from URL
                # Example URL: https://res.cloudinary.com/dwgvlwkyt/image/upload/v1234567890/rolex_products/abc123.jpg
                url_parts = db_product.image_url.split('/')
                filename = url_parts[-1].split('.')[0]  # Get filename without extension
                public_id = f"rolex_products/{filename}"
                
                result = cloudinary.uploader.destroy(public_id)
                print(f"✅ Image deleted from Cloudinary: {public_id}, Result: {result}")
            except Exception as img_error:
                print(f"⚠️ Could not delete image from Cloudinary: {img_error}")
                # Continue with product deletion even if image deletion fails
        
        db.delete(db_product)
        db.commit()
        return {"message": "Product deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error in delete_product: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ORDERS ====================
@router.get("/seller/orders")
async def get_seller_orders(
    seller_id: int,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get all orders for a seller"""
    try:
        query = db.query(Order).filter(Order.seller_id == seller_id)
        
        if status:
            query = query.filter(Order.status == status.upper())
        
        orders = query.order_by(desc(Order.created_at)).limit(limit).all()
        
        result = []
        for order in orders:
            # Get order items
            items = db.query(OrderItem).filter(
                OrderItem.order_id == order.id
            ).all()
            
            items_list = [
                f"{item.product.name if item.product else 'Unknown'} x{item.quantity}"
                for item in items
            ]
            
            result.append({
                "id": order.id,
                "order_number": order.order_number,
                "customer_name": order.customer_name,
                "customer_phone": order.customer_phone,
                "total_amount": float(order.total_amount),
                "status": order.status,
                "shipping_address": order.shipping_address,
                "payment_status": order.payment_status,
                "payment_method": order.payment_method,
                "notes": order.notes,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "items": items_list
            })
        
        return {"orders": result}
    except Exception as e:
        print(f"❌ Error in get_seller_orders: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/seller/orders/{order_id}/status")
async def update_order_status(
    order_id: int, 
    status_update: OrderStatusUpdate, 
    seller_id: int, 
    db: Session = Depends(get_db)
):
    """Update order status"""
    try:
        valid_statuses = ['PENDING', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED']
        if status_update.status.upper() not in valid_statuses:
            raise HTTPException(status_code=400, detail="Invalid status")
        
        order = db.query(Order).filter(
            Order.id == order_id,
            Order.seller_id == seller_id
        ).first()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        order.status = status_update.status.upper()
        order.updated_at = datetime.utcnow()
        
        db.commit()
        return {"message": "Order status updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error in update_order_status: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ANALYTICS ====================
@router.get("/seller/analytics/revenue")
async def get_revenue_analytics(
    seller_id: int, 
    period: str = 'month', 
    db: Session = Depends(get_db)
):
    """Get revenue analytics"""
    try:
        days = {'week': 7, 'month': 30, 'year': 365}.get(period, 30)
        date_threshold = datetime.utcnow() - timedelta(days=days)
        
        # Raw SQL for date grouping (SQLAlchemy way)
        from sqlalchemy import text
        
        result = db.execute(text("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as order_count,
                SUM(total_amount) as revenue
            FROM orders
            WHERE seller_id = :seller_id
                AND status = 'DELIVERED'
                AND created_at >= :date_threshold
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """), {"seller_id": seller_id, "date_threshold": date_threshold})
        
        data = []
        for row in result:
            data.append({
                "date": row[0].isoformat() if row[0] else None,
                "order_count": row[1],
                "revenue": float(row[2]) if row[2] else 0.0
            })
        
        return {"data": data}
    except Exception as e:
        print(f"❌ Error in get_revenue_analytics: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/seller/analytics/top-products")
async def get_top_products(
    seller_id: int, 
    limit: int = 5, 
    db: Session = Depends(get_db)
):
    """Get top selling products"""
    try:
        from sqlalchemy import text
        
        result = db.execute(text("""
            SELECT 
                p.id,
                p.name,
                p.category,
                SUM(oi.quantity) as total_sold,
                SUM(oi.quantity * oi.price) as total_revenue
            FROM products p
            INNER JOIN order_items oi ON p.id = oi.product_id
            INNER JOIN orders o ON oi.order_id = o.id
            WHERE p.seller_id = :seller_id AND o.status = 'DELIVERED'
            GROUP BY p.id, p.name, p.category
            ORDER BY total_revenue DESC
            LIMIT :limit
        """), {"seller_id": seller_id, "limit": limit})
        
        products = []
        for row in result:
            products.append({
                "id": row[0],
                "name": row[1],
                "category": row[2],
                "total_sold": row[3],
                "total_revenue": float(row[4]) if row[4] else 0.0
            })
        
        return {"products": products}
    except Exception as e:
        print(f"❌ Error in get_top_products: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get top products: {str(e)}")
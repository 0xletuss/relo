# =====================================================
# routes/product_routes.py - Products and Wishlist Only
# Orders have been moved to routes/order_routes.py
# =====================================================

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from models.database import get_db
from models.product_model import Product, Category, Wishlist
from routes.auth_routes import get_current_user
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    stock_status: Optional[str] = "in_stock"
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
    stock_status: Optional[str] = None
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
    stock_status: Optional[str] = None
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
    """Get all products with optional filtering and sorting."""
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
            query = query.order_by(Product.id.desc())

        products = query.offset(skip).limit(limit).all()
        logger.info(f"Fetched {len(products)} products")
        return products
    
    except Exception as e:
        logger.error(f"Error in get_products: {e}", exc_info=True)
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
    """Create a new product (Admin only)"""
    try:
        new_product = Product(**product.dict())
        db.add(new_product)
        db.commit()
        db.refresh(new_product)
        logger.info(f"Product created: {new_product.id}")
        return new_product
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating product: {e}", exc_info=True)
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
        
        update_data = product_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)
        
        db.commit()
        db.refresh(product)
        logger.info(f"Product updated: {product_id}")
        return product
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating product: {e}", exc_info=True)
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
        logger.info(f"Product deleted: {product_id}")
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting product: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete product: {str(e)}"
        )


@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(db: Session = Depends(get_db)):
    """Get all unique categories"""
    try:
        categories = db.query(Category).all()
        return categories
    
    except Exception as e:
        logger.error(f"Error fetching categories: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch categories: {str(e)}"
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
        logger.error(f"Error fetching wishlist: {e}", exc_info=True)
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
        logger.error(f"Error adding to wishlist: {e}", exc_info=True)
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
        logger.error(f"Error removing from wishlist: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove from wishlist: {str(e)}"
        )


# =====================================================
# NOTE: Order endpoints have been moved to routes/order_routes.py
# Use /api/orders instead (handled by order_routes.py)
# =====================================================
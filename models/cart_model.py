from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime

# Request Models
class AddToCartRequest(BaseModel):
    product_id: int
    quantity: int = 1

    @validator('quantity')
    def quantity_validator(cls, v):
        if v < 1:
            raise ValueError('Quantity must be at least 1')
        if v > 10:
            raise ValueError('Quantity cannot exceed 10')
        return v

class UpdateCartItemRequest(BaseModel):
    quantity: int

    @validator('quantity')
    def quantity_validator(cls, v):
        if v < 1:
            raise ValueError('Quantity must be at least 1')
        if v > 10:
            raise ValueError('Quantity cannot exceed 10')
        return v

# Response Models
class ProductInCart(BaseModel):
    id: int
    name: str
    price: float
    reference_number: Optional[str]
    category: Optional[str]
    material: Optional[str]
    case_size: Optional[str]
    image_url: Optional[str]

    class Config:
        from_attributes = True

class CartItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    created_at: datetime
    updated_at: datetime
    product: ProductInCart
    subtotal: float

    class Config:
        from_attributes = True

class CartResponse(BaseModel):
    items: list[CartItemResponse]
    total_items: int
    total_amount: float

class CartActionResponse(BaseModel):
    message: str
    cart: CartResponse
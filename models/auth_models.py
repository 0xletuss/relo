from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime

# Request Models
class UserSignUp(BaseModel):
    username: str
    email: EmailStr
    password: str

    @validator('username')
    def username_validator(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
        if len(v) > 50:
            raise ValueError('Username must not exceed 50 characters')
        return v

    @validator('password')
    def password_validator(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        return v

class UserSignIn(BaseModel):
    username: str
    password: str

class TokenRefresh(BaseModel):
    refresh_token: str

# Response Models
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True

class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
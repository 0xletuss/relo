from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from models.database import get_db, User, RefreshToken, Seller, Customer
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import List, Optional
import os

router = APIRouter()
security = HTTPBearer()

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# =====================================================
# Pydantic Models
# =====================================================

class UserSignUp(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "customer"  # Default to customer

class UserSignIn(BaseModel):
    username: str
    password: str

class SellerInfo(BaseModel):
    id: int
    business_name: Optional[str] = None
    verified: bool = False

class CustomerInfo(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    created_at: datetime
    seller_id: Optional[int] = None
    customer_id: Optional[int] = None
    seller_info: Optional[SellerInfo] = None
    customer_info: Optional[CustomerInfo] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str

class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str

# =====================================================
# Helper functions
# =====================================================

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def create_user_response(user: User) -> dict:
    """Create user response with seller/customer info"""
    response_data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at,
        "seller_id": None,
        "customer_id": None,
        "seller_info": None,
        "customer_info": None
    }
    
    if user.role == 'seller' and user.seller:
        response_data["seller_id"] = user.seller.id
        response_data["seller_info"] = {
            "id": user.seller.id,
            "business_name": user.seller.business_name,
            "verified": user.seller.verified
        }
    elif user.role == 'customer' and user.customer:
        response_data["customer_id"] = user.customer.id
        response_data["customer_info"] = {
            "id": user.customer.id,
            "first_name": user.customer.first_name,
            "last_name": user.customer.last_name
        }
    
    return response_data

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if username is None or token_type != "access":
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_username(db, username)
    if user is None:
        raise credentials_exception
    return user

# =====================================================
# Routes
# =====================================================

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def sign_up(user_data: UserSignUp, db: Session = Depends(get_db)):
    """Sign up endpoint - accessible via both /signup and /register"""
    try:
        # Check if username already exists
        if get_user_by_username(db, user_data.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # Check if email already exists
        if get_user_by_email(db, user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Validate role
        valid_roles = ['customer', 'seller']
        role = user_data.role.lower() if user_data.role else 'customer'
        if role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
            )
        
        # Create new user
        hashed_password = hash_password(user_data.password)
        new_user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            role=role,
            created_at=datetime.utcnow(),
            is_active=True
        )
        
        db.add(new_user)
        db.flush()  # Flush to get the user ID
        
        # Create corresponding seller or customer record
        if role == 'seller':
            new_seller = Seller(
                user_id=new_user.id,
                business_name=user_data.full_name or user_data.username,
                verified=False,
                created_at=datetime.utcnow()
            )
            db.add(new_seller)
        else:  # customer
            # Parse full_name if provided
            first_name = None
            last_name = None
            if user_data.full_name:
                name_parts = user_data.full_name.split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else None
            
            new_customer = Customer(
                user_id=new_user.id,
                first_name=first_name,
                last_name=last_name,
                created_at=datetime.utcnow()
            )
            db.add(new_customer)
        
        db.commit()
        db.refresh(new_user)
        
        # Create tokens
        access_token = create_access_token(
            data={"sub": new_user.username, "role": new_user.role},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        refresh_token = create_refresh_token(
            data={"sub": new_user.username, "role": new_user.role}
        )
        
        # Create response with seller/customer info
        user_response_data = create_user_response(new_user)
        
        return AuthResponse(
            user=UserResponse(**user_response_data),
            access_token=access_token,
            refresh_token=refresh_token
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error during signup: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating account: {str(e)}"
        )

@router.post("/signin", response_model=AuthResponse)
@router.post("/login", response_model=AuthResponse)
async def sign_in(user_data: UserSignIn, db: Session = Depends(get_db)):
    """Sign in endpoint - accessible via both /signin and /login"""
    # Find user by username OR email
    user = get_user_by_username(db, user_data.username)
    if not user:
        # Try email if username not found
        user = get_user_by_email(db, user_data.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Verify password
    if not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create tokens with role
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_refresh_token(
        data={"sub": user.username, "role": user.role}
    )
    
    # Create response with seller/customer info
    user_response_data = create_user_response(user)
    
    return AuthResponse(
        user=UserResponse(**user_response_data),
        access_token=access_token,
        refresh_token=refresh_token
    )

@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if username is None or token_type != "refresh":
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_username(db, username)
    if user is None:
        raise credentials_exception
    
    # Create new access token with role
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    new_refresh_token = create_refresh_token(
        data={"sub": user.username, "role": user.role}
    )
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token
    )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    user_response_data = create_user_response(current_user)
    return UserResponse(**user_response_data)

@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all users (protected route example)"""
    users = db.query(User).all()
    return [
        UserResponse(**create_user_response(user))
        for user in users
    ]
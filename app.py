from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routes.auth_routes import router as auth_router
from routes.product_routes import router as product_router
from models.database import create_tables
from routes.cart_routes import router as cart_router
from routes.order_routes import router as order_router
from routes.seller_routes import router as seller_router

import traceback
import os
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Configure Cloudinary using environment variables
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# Create FastAPI app
app = FastAPI(
    title="Rolex Store API",
    description="E-commerce API with Authentication and Products",
    version="1.0.0"
)

# CRITICAL: Add CORS middleware BEFORE any routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Add manual CORS headers to every response
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    # Log the request
    print(f"📨 {request.method} {request.url.path}")
    
    # Handle OPTIONS (preflight) requests
    if request.method == "OPTIONS":
        return JSONResponse(
            content={"message": "OK"},
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, Origin",
                "Access-Control-Max-Age": "3600",
            }
        )
    
    # Process the request
    try:
        response = await call_next(request)
    except Exception as e:
        print(f"❌ Error in request: {e}")
        traceback.print_exc()
        return JSONResponse(
            content={"detail": str(e)},
            status_code=500,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": "true",
            }
        )
    
    # Add CORS headers to the response
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, Origin"
    
    print(f"📤 Response: {response.status_code}")
    return response

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"❌ Global exception: {exc}")
    print(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "type": type(exc).__name__
        },
        headers={
            "Access-Control-Allow-Origin": "*",
        }
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    try:
        print("=" * 50)
        print("🚀 Starting Rolex Store API...")
        create_tables()
        print("✅ Database tables created/verified")
        
        # Verify Cloudinary configuration
        cloud_name = cloudinary.config().cloud_name
        if cloud_name:
            print("☁️  Cloudinary configured successfully")
            print(f"   Cloud Name: {cloud_name}")
        else:
            print("⚠️  Warning: Cloudinary credentials not found in environment variables")
        
        print("✅ Server is ready!")
        print("=" * 50)
    except Exception as e:
        print(f"❌ Startup error: {e}")
        print(traceback.format_exc())

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(product_router, prefix="/api", tags=["Products"])
app.include_router(cart_router, prefix="/api", tags=["Cart"])
app.include_router(order_router, prefix="/api", tags=["Orders"])
app.include_router(seller_router, prefix="/api", tags=["Seller"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to Rolex Store API",
        "status": "running",
        "version": "1.0.0",
        "cloudinary": "enabled" if cloudinary.config().cloud_name else "not configured",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "auth": "/api/auth",
            "products": "/api/products"
        }
    }

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "cors": "enabled",
        "cloudinary": "configured" if cloudinary.config().cloud_name else "not configured"
    }

# Explicit OPTIONS handler for auth routes (belt and suspenders approach)
@app.options("/api/auth/login")
@app.options("/api/auth/register")
@app.options("/api/auth/me")
async def auth_options():
    return JSONResponse(
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "app:app",  # Changed from "main:app" to "app:app"
        host="0.0.0.0",
        port=port,
        reload=True
    )
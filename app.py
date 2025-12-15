from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routes.auth_routes import router as auth_router
from routes.product_routes import router as product_router
from models.database import create_tables
from routes.cart_routes import router as cart_router

import traceback
import os

# Create FastAPI app
app = FastAPI(
    title="Rolex Store API",
    description="E-commerce API with Authentication and Products",
    version="1.0.0"
)

# CORS middleware - MUST be before routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Global exception handler caught: {exc}")
    print(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "type": type(exc).__name__,
            "path": str(request.url)
        }
    )

# Create database tables on startup
@app.on_event("startup")
async def startup_event():
    try:
        create_tables()
        print("✓ Database tables created/verified")
        print("✓ Server starting...")
        print(f"✓ Database URL: {os.getenv('DATABASE_URL', 'Using default SQLite')}")
    except Exception as e:
        print(f"✗ Error creating tables: {e}")
        print(traceback.format_exc())

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(product_router, prefix="/api", tags=["Products"])
app.include_router(cart_router, prefix="/api", tags=["Cart"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to Rolex Store API",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
        "version": "1.0.0"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "connected"
    }

# Debug endpoint to check routes
@app.get("/api/debug/routes")
async def debug_routes():
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path,
            "name": route.name,
            "methods": list(route.methods) if hasattr(route, 'methods') else []
        })
    return {"routes": routes}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
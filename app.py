from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.auth_routes import router
from models.database import create_tables
import uvicorn
import os

# Create tables on startup
create_tables()

app = FastAPI(title="Timeless Treasures API", version="1.0.0")

# CORS middleware to allow frontend requests
origins = ["*"] if os.getenv("ENVIRONMENT") == "development" else [
    "https://your-frontend-domain.com",  # Replace with your actual frontend URL
    "http://localhost:3000",  # For local development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include authentication routes
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])

@app.get("/")
async def root():
    return {"message": "Welcome to Timeless Treasures API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
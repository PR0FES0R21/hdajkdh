# ===========================================================================
# File: app/main.py (MODIFIKASI: Menggunakan lifespan, bukan on_event)
# ===========================================================================
from fastapi import FastAPI, HTTPException, Request, status as HttpStatus
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager # Untuk lifespan

from app.core.config import settings, logger
from app.db.session import mongo_db_manager
from app.db.redis_conn import redis_manager
from app.api.v1 import api_v1_router
from jose import JWTError
from pydantic import ValidationError

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kode yang dijalankan sebelum aplikasi mulai menerima request (startup)
    logger.info(f"Starting up {settings.PROJECT_NAME}...")
    await mongo_db_manager.connect_to_mongo()
    await redis_manager.connect_to_redis()
    logger.info(f"--- {settings.PROJECT_NAME} v{getattr(app, 'version', 'N/A')} startup complete ---")
    yield
    # Kode yang dijalankan setelah aplikasi selesai menerima request (shutdown)
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")
    await redis_manager.close_redis_connection()
    await mongo_db_manager.close_mongo_connection()
    logger.info(f"--- {settings.PROJECT_NAME} shutdown complete ---")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API Backend untuk Project Cigar DS ($CIGAR).",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan # Menggunakan lifespan context manager
)

# Pengaturan CORS (sama seperti sebelumnya)
origins = [
    "https://dashboard.cigarverse.space",
    "https://cigarverse.space"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Exception Handlers (sama seperti sebelumnya)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTPException: {exc.status_code} - {exc.detail} for {request.url.path}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)

@app.exception_handler(JWTError)
async def jwt_exception_handler(request: Request, exc: JWTError):
    logger.error(f"Unhandled JWTError: {exc} for {request.url.path}")
    return JSONResponse(status_code=HttpStatus.HTTP_401_UNAUTHORIZED, content={"detail": "Invalid or expired token."}, headers={"WWW-Authenticate": "Bearer"})

@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    logger.error(f"Pydantic ValidationError: {exc.errors()} for {request.url.path}")
    # Mengambil detail error yang lebih ramah dari Pydantic v2
    error_details = exc.errors(include_url=False, include_input=False) 
    return JSONResponse(
        status_code=HttpStatus.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": error_details},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled generic exception: {exc} for {request.url.path}", exc_info=True)
    return JSONResponse(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "An unexpected internal server error occurred."})

@app.get("/", tags=["Root"], summary="API Root Endpoint")
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}!",
        "version": getattr(app, 'version', 'N/A'),
        "docs": app.docs_url,
        "redoc": app.redoc_url,
        "api_v1_path": settings.API_V1_STR
    }

app.include_router(api_v1_router, prefix=settings.API_V1_STR)

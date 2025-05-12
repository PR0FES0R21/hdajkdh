from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
import os
from dotenv import load_dotenv
import aiohttp
import logging
import redis.asyncio as redis
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from eth_utils import is_address
from fastapi.responses import JSONResponse
import json

# Load env vars
load_dotenv()

# Config
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
REDIS_URI = os.getenv("REDIS_URI", "redis://localhost:6379")
DB_NAME = os.getenv("DB_NAME", "wallet_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "wallet_addresses")
ALCHEMY_URL = "https://base-mainnet.g.alchemy.com/v2/HmwNcVZ6e8G-MUMQKcCONESlediOWZor"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Wallet Registration API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Mongo
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client[DB_NAME]
collection = db[COLLECTION_NAME]

# Redis (initialized on startup)
redis_client = None

@app.on_event("startup")
async def startup_event():
    global redis_client
    redis_client = redis.Redis.from_url(REDIS_URI, decode_responses=True)

@app.on_event("shutdown")
async def shutdown_event():
    await redis_client.close()

class WalletRegistration(BaseModel):
    wallet_address: str = Field(..., description="Blockchain wallet address")

class RegistrationResponse(BaseModel):
    status: str
    message: str
    wallet_address: str
    amount: int

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/register", response_model=RegistrationResponse)
@limiter.limit("5/minute")
async def register_wallet(registration: WalletRegistration, request: Request):
    addr = registration.wallet_address.lower()

    if not is_address(addr):
        raise HTTPException(status_code=400, detail="Invalid wallet address format.")

    logger.info(f"New registration from IP: {request.client.host} wallet: {addr}")

    # Check Redis cache
    cached = await redis_client.get(f"wallet:{addr}")
    if cached:
        cached_data = json.loads(cached)
        return {
            "status": "success",
            "message": "Wallet already registered (cache)",
            "wallet_address": addr,
            "amount": cached_data["amount"] * 10
        }

    # Check Mongo
    existing = await collection.find_one({"wallet_address": addr}, {"_id": 0})
    if existing:
        await redis_client.set(f"wallet:{addr}", json.dumps(existing), ex=3600)
        return {
            "status": "success",
            "message": "Wallet already registered",
            "wallet_address": addr,
            "amount": existing.get("amount", 0) * 10
        }

    # Fetch from Alchemy
    async with aiohttp.ClientSession() as session:
        async with session.post(ALCHEMY_URL, json={
            "jsonrpc": "2.0",
            "method": "eth_getTransactionCount",
            "params": [addr, "latest"],
            "id": 1
        }) as resp:
            alchemy_data = await resp.json()
            hex_value = alchemy_data.get("result", "0x0")
            tx_count = int(hex_value, 16)

    record = {
        "wallet_address": addr,
        "amount": tx_count
    }

    if tx_count < 1:
        await redis_client.set(f"wallet:{addr}", json.dumps(record), ex=3600)
        return {
            "status": "success",
            "message": "Wallet registered successfully",
            "wallet_address": addr,
            "amount": tx_count * 10
        }


    await collection.insert_one(record)
    record.pop("_id", None)
    await redis_client.set(f"wallet:{addr}", json.dumps(record), ex=3600)

    return {
        "status": "success",
        "message": "Wallet registered successfully",
        "wallet_address": addr,
        "amount": tx_count * 10
    }

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP Error: {exc.detail} from IP: {request.client.host}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {str(exc)} from IP: {request.client.host}")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

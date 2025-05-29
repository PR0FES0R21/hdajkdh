# main.py
from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel, Field, validator
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from typing import Optional, Any
import os
from dotenv import load_dotenv
import aiohttp
import logging
import redis.asyncio as redis
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from eth_utils import is_address
from fastapi.responses import JSONResponse
import json
import random
import string
import re # Untuk validasi regex kode referral
from datetime import datetime # Import datetime

# Load environment variables from .env file
load_dotenv()

# Configuration
MONGO_URI = os.getenv("MONGO_URI")
REDIS_URI = os.getenv("REDIS_URL")
DB_NAME = os.getenv("DB_NAME", "cigar_db_prod")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "user_registrations")
ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")
if not ALCHEMY_API_KEY:
    # Ini akan menghentikan aplikasi jika API Key tidak ada, yang merupakan perilaku yang baik.
    logger.critical("FATAL: ALCHEMY_API_KEY environment variable not set.")
    raise ValueError("ALCHEMY_API_KEY environment variable not set.")
ALCHEMY_URL = f"https://base-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"

REFERRAL_CODE_LENGTH = 8
CACHE_EXPIRY_SECONDS = 3600 # 1 jam untuk cache Redis

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler() # Output ke console
        # Anda bisa menambahkan FileHandler di sini jika ingin log ke file
        # logging.FileHandler("api.log"),
    ]
)
logger = logging.getLogger(__name__)

# FastAPI app initialization
app = FastAPI(
    title="CIGAR Protocol - Alliance Registration API",
    description="API for user wallet registration, referral code generation, and transaction count retrieval for the CIGAR Protocol mission.",
    version="1.1.0"
)

# CORS Middleware Configuration
# Sesuaikan allow_origins dengan domain frontend Anda untuk produksi
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["POST", "GET"], # Lebih spesifik lebih baik
    allow_headers=["*"], # Atau spesifikasikan header yang dibutuhkan
)

# Rate Limiter Setup
limiter = Limiter(key_func=get_remote_address, default_limits=["100/hour", "20/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Database and Cache Client Placeholders
# Akan diinisialisasi saat startup
mongo_client: Optional[AsyncIOMotorClient] = None
db: Optional[AsyncIOMotorDatabase] = None
collection: Optional[AsyncIOMotorCollection] = None
redis_client: Optional[redis.Redis] = None

# --- Startup and Shutdown Events ---
@app.on_event("startup")
async def startup_event():
    global mongo_client, db, collection, redis_client
    logger.info("API starting up...")
    try:
        # Initialize MongoDB connection
        logger.info(f"Connecting to MongoDB at {MONGO_URI}...")
        mongo_client = AsyncIOMotorClient(MONGO_URI)
        db = mongo_client[DB_NAME]
        collection = db[COLLECTION_NAME]
        # Ensure indexes are created (Motor handles this efficiently)
        await collection.create_index("wallet_address", unique=True)
        await collection.create_index("user_referral_code", unique=True)
        await collection.create_index("invited_by_referral_code") # Indeks untuk query referral
        logger.info(f"MongoDB connected. Database: {DB_NAME}, Collection: {COLLECTION_NAME}. Indexes ensured.")

        # Initialize Redis connection
        logger.info(f"Connecting to Redis at {REDIS_URI}...")
        redis_client = redis.Redis.from_url(REDIS_URI, decode_responses=True)
        await redis_client.ping() # Test connection
        logger.info("Redis connected successfully.")

    except Exception as e:
        logger.error(f"FATAL: Error during startup: {e}", exc_info=True)
        # Menghentikan aplikasi jika koneksi penting gagal adalah praktik yang baik
        # raise SystemExit(f"Failed to connect to critical services: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("API shutting down...")
    if redis_client:
        try:
            await redis_client.close()
            logger.info("Redis connection closed.")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}", exc_info=True)
    if mongo_client:
        try:
            mongo_client.close()
            logger.info("MongoDB connection closed.")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}", exc_info=True)

# --- Helper Functions ---
def generate_referral_code(length: int = REFERRAL_CODE_LENGTH) -> str:
    """Generates a random uppercase alphanumeric referral code."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for i in range(length))

async def get_unique_referral_code(
    current_collection: AsyncIOMotorCollection, # Terima collection sebagai argumen
    length: int = REFERRAL_CODE_LENGTH
) -> str:
    """Generates a referral code and ensures it's unique in the collection."""
    if current_collection is None: # Perbaikan di sini
        logger.error("MongoDB collection not initialized in get_unique_referral_code.")
        raise HTTPException(status_code=503, detail="Service not fully initialized, please try again.")
    
    max_retries = 10 
    for _ in range(max_retries):
        code = generate_referral_code(length)
        if await current_collection.find_one({"user_referral_code": code}) is None:
            return code
    logger.error(f"Failed to generate a unique referral code after {max_retries} retries.")
    raise HTTPException(status_code=500, detail="Could not generate a unique referral identifier.")

# --- Pydantic Models ---
class WalletRegistration(BaseModel):
    wallet_address: str = Field(..., description="User's blockchain wallet address (Base Network)", example="0x123...")
    referral_code_used: Optional[str] = Field(None, description=f"Referral code of the inviter (optional, {REFERRAL_CODE_LENGTH} alphanumeric chars)", example="ABC123XY", max_length=REFERRAL_CODE_LENGTH)

    @validator('referral_code_used')
    def validate_referral_code_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not re.match(r"^[A-Z0-9]{" + str(REFERRAL_CODE_LENGTH) + r"}$", v):
            raise ValueError(f"Referral code must be {REFERRAL_CODE_LENGTH} uppercase alphanumeric characters.")
        return v.upper() 

class RegistrationResponse(BaseModel):
    status: str = Field(..., example="success")
    message: str = Field(..., example="Wallet registered successfully!")
    wallet_address: str = Field(..., example="0x123...")
    points: int = Field(..., example=100)
    user_referral_code: Optional[str] = Field(None, example="NEWREF123")
    invited_by_wallet_address: Optional[str] = Field(None, example="0xabc...")

# --- Dependency to check service readiness ---
async def get_db() -> AsyncIOMotorDatabase: # Ganti nama agar lebih generik
    if db is None: # Perbaikan di sini
        logger.error("MongoDB database client not initialized.")
        raise HTTPException(status_code=503, detail="Database service temporarily unavailable.")
    return db

async def get_collection() -> AsyncIOMotorCollection: # Dependency baru untuk collection
    if collection is None: # Perbaikan di sini
        logger.error("MongoDB collection not initialized.")
        raise HTTPException(status_code=503, detail="Database service temporarily unavailable.")
    return collection

async def get_redis() -> redis.Redis: # Ganti nama agar lebih generik
    if redis_client is None: # Perbaikan di sini
        logger.error("Redis client not initialized.")
        raise HTTPException(status_code=503, detail="Cache service temporarily unavailable.")
    return redis_client


# --- Endpoints ---
@app.get("/health", summary="Check API Health Status")
async def health_check(
    # Menggunakan dependency yang sudah diperbaiki
    current_db: AsyncIOMotorDatabase = Depends(get_db), 
    current_redis: redis.Redis = Depends(get_redis)
):
    """
    Performs a health check on the API and its connected services (MongoDB, Redis).
    """
    mongo_ok = False
    redis_ok = False
    try:
        await current_db.command('ping')
        mongo_ok = True
    except Exception as e:
        logger.error(f"MongoDB ping failed: {e}")
    
    try:
        await current_redis.ping()
        redis_ok = True
    except Exception as e:
        logger.error(f"Redis ping failed: {e}")

    if mongo_ok and redis_ok:
        return {"status": "healthy", "services": {"mongodb": "connected", "redis": "connected"}}
    else:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy", 
                "services": {
                    "mongodb": "connected" if mongo_ok else "error", 
                    "redis": "connected" if redis_ok else "error"
                }
            }
        )

@app.post("/register", response_model=RegistrationResponse, summary="Register Wallet for Airdrop")
@limiter.limit("5/minute") 
async def register_wallet(
    registration: WalletRegistration, 
    request: Request,
    # Menggunakan dependency yang sudah diperbaiki
    current_collection: AsyncIOMotorCollection = Depends(get_collection), 
    current_redis: redis.Redis = Depends(get_redis)
):
    """
    Registers a user's wallet address.
    - Checks if the wallet is already registered (via cache or DB).
    - Validates an optional referral code used.
    - Fetches transaction count from Base Mainnet via Alchemy.
    - Generates a new unique referral code for the user.
    - Stores registration data in MongoDB and caches it in Redis.
    - Returns registration status, points, user's new referral code, and inviter's address if any.
    """
    registered_addr_lower = registration.wallet_address.lower()
    referral_code_used_input = registration.referral_code_used 

    if not is_address(registered_addr_lower):
        raise HTTPException(status_code=400, detail="Invalid wallet address format.")

    client_ip = get_remote_address(request) # type: ignore
    logger.info(f"Registration attempt: Wallet={registered_addr_lower}, ReferrerCode={referral_code_used_input}, IP={client_ip}")

    # 1. Check Redis cache
    cache_key = f"wallet_data:{registered_addr_lower}"
    cached_user_data_str = await current_redis.get(cache_key)
    if cached_user_data_str:
        try:
            cached_user_data = json.loads(cached_user_data_str)
            logger.info(f"Cache hit for {registered_addr_lower}")
            # Pastikan semua field yang dibutuhkan RegistrationResponse ada di cached_user_data
            return RegistrationResponse(
                status=cached_user_data.get("status", "success"),
                message=cached_user_data.get("message", "Wallet already registered."),
                wallet_address=cached_user_data.get("wallet_address", registered_addr_lower),
                points=cached_user_data.get("points", 0),
                user_referral_code=cached_user_data.get("user_referral_code"),
                invited_by_wallet_address=cached_user_data.get("invited_by_wallet_address")
            )
        except (json.JSONDecodeError, TypeError) as e: # Tambah TypeError untuk **cached_user_data
            logger.warning(f"Failed to parse or unpack cached data for {registered_addr_lower}: {e}. Fetching from DB.")


    # 2. Check MongoDB
    existing_user_doc = await current_collection.find_one({"wallet_address": registered_addr_lower})
    if existing_user_doc:
        logger.info(f"DB hit for {registered_addr_lower}")
        response_payload = RegistrationResponse(
            status="success",
            message="Wallet already registered.",
            wallet_address=registered_addr_lower,
            points=existing_user_doc.get("points_basis", 0), 
            user_referral_code=existing_user_doc.get("user_referral_code"),
            invited_by_wallet_address=existing_user_doc.get("referrer_wallet_address")
        )
        try:
            await current_redis.set(cache_key, response_payload.model_dump_json(), ex=CACHE_EXPIRY_SECONDS)
        except Exception as e:
            logger.error(f"Redis set failed for {cache_key}: {e}")
        return response_payload

    # 3. New registration: Validate referrer_code if provided
    actual_referrer_wallet_address: Optional[str] = None
    if referral_code_used_input:
        logger.info(f"Validating referral code used: {referral_code_used_input}")
        referrer_doc = await current_collection.find_one({"user_referral_code": referral_code_used_input})
        if not referrer_doc:
            logger.warning(f"Invalid or non-existent referral code used: {referral_code_used_input}")
            raise HTTPException(status_code=400, detail="Invalid or expired referral code provided.")
        else:
            actual_referrer_wallet_address = referrer_doc["wallet_address"]
            if actual_referrer_wallet_address == registered_addr_lower:
                logger.warning(f"User {registered_addr_lower} attempted to refer themselves.")
                raise HTTPException(status_code=400, detail="Cannot use your own referral code.")
            logger.info(f"Referral code {referral_code_used_input} is valid, referrer: {actual_referrer_wallet_address}")
            # TODO: Implement bonus logic for the referrer (e.g., increment a counter, send notification)

    # 4. Fetch transaction count from Alchemy
    tx_count = 0
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "jsonrpc": "2.0", "method": "eth_getTransactionCount",
                "params": [registered_addr_lower, "latest"], "id": 1
            }
            async with session.post(ALCHEMY_URL, json=payload, timeout=10) as resp: 
                if resp.status == 200:
                    alchemy_data = await resp.json()
                    if alchemy_data and "result" in alchemy_data:
                        hex_value = alchemy_data["result"]
                        tx_count = int(hex_value, 16)
                        logger.info(f"Transaction count for {registered_addr_lower}: {tx_count}")
                    else:
                        logger.error(f"Alchemy response missing 'result' for {registered_addr_lower}: {alchemy_data}")
                else:
                    logger.error(f"Alchemy API error for {registered_addr_lower}: Status={resp.status}, Body={await resp.text()}")
    except aiohttp.ClientError as e: 
        logger.error(f"AIOHTTP client error fetching tx count for {registered_addr_lower}: {e}")
    except Exception as e:
        logger.error(f"Generic error fetching tx count for {registered_addr_lower}: {e}", exc_info=True)
    
    points = tx_count * 10
    new_user_referral_code = await get_unique_referral_code(current_collection) # Kirim collection

    # 5. Prepare record for MongoDB
    user_document = {
        "wallet_address": registered_addr_lower,
        "transaction_count": tx_count,
        "points_basis": points,
        "user_referral_code": new_user_referral_code,
        "invited_by_referral_code": referral_code_used_input,
        "referrer_wallet_address": actual_referrer_wallet_address,
        "registration_timestamp": datetime.utcnow() 
    }
   
    # 6. Insert into MongoDB
    try:
        await current_collection.insert_one(user_document)
        logger.info(f"Successfully registered {registered_addr_lower} to MongoDB.")
    except Exception as e: 
        logger.error(f"Error inserting {registered_addr_lower} to MongoDB: {e}", exc_info=True)
        error_message_lower = str(e).lower()
        if "duplicate key error" in error_message_lower:
            if "wallet_address" in error_message_lower:
                logger.warning(f"Race condition: Wallet {registered_addr_lower} registered concurrently.")
                existing_doc_after_fail = await current_collection.find_one({"wallet_address": registered_addr_lower})
                if existing_doc_after_fail:
                    response_payload_race = RegistrationResponse(
                        status="success",
                        message="Wallet already registered (concurrently).",
                        wallet_address=registered_addr_lower,
                        points=existing_doc_after_fail.get("points_basis", 0),
                        user_referral_code=existing_doc_after_fail.get("user_referral_code"),
                        invited_by_wallet_address=existing_doc_after_fail.get("referrer_wallet_address")
                    )
                    try:
                        await current_redis.set(cache_key, response_payload_race.model_dump_json(), ex=CACHE_EXPIRY_SECONDS)
                    except Exception as redis_e:
                        logger.error(f"Redis set failed for {cache_key} after race condition: {redis_e}")
                    return response_payload_race
            elif "user_referral_code" in error_message_lower:
                 logger.error(f"Generated referral code collision: {new_user_referral_code}. This should be extremely rare.")
                 raise HTTPException(status_code=500, detail="Internal error generating unique ID. Please try again.")
        raise HTTPException(status_code=500, detail="Database error during registration.")

    # 7. Update Redis cache
    response_payload_new = RegistrationResponse(
        status="success",
        message="Wallet registered successfully!",
        wallet_address=registered_addr_lower,
        points=points,
        user_referral_code=new_user_referral_code,
        invited_by_wallet_address=actual_referrer_wallet_address
    )
    try:
        await current_redis.set(cache_key, response_payload_new.model_dump_json(), ex=CACHE_EXPIRY_SECONDS)
        logger.info(f"Cached data for new user {registered_addr_lower}")
    except Exception as e:
        logger.error(f"Redis set failed for new user {registered_addr_lower}: {e}")


    return response_payload_new

# --- Exception Handlers ---
@app.exception_handler(HTTPException)
async def http_exception_handler_custom(request: Request, exc: HTTPException):
    client_ip = get_remote_address(request) # type: ignore
    logger.error(f"HTTP Error: Status={exc.status_code}, Detail='{exc.detail}', IP={client_ip}, Path='{request.url.path}'")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler_custom(request: Request, exc: Exception):
    client_ip = get_remote_address(request) # type: ignore
    logger.error(f"Unhandled Error: Type='{type(exc).__name__}', Msg='{str(exc)}', IP={client_ip}, Path='{request.url.path}'", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal server error occurred. Please try again later."}
    )

# Untuk menjalankan dengan uvicorn:
# uvicorn main:app --reload --host 0.0.0.0 --port 8000

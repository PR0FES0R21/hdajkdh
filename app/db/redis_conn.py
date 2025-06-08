# ===========================================================================
# File: app/db/redis_conn.py
# ===========================================================================
# (Sama seperti versi sebelumnya)
import redis.asyncio as aioredis
from typing import Optional
from app.core.config import settings, logger

class RedisManager:
    redis_client: Optional[aioredis.Redis] = None

    async def connect_to_redis(self):
        if self.redis_client is None:
            logger.info(f"Attempting to connect to Redis at {settings.NONCE_REDIS_URL} for nonces...")
            try:
                self.redis_client = aioredis.from_url(
                    settings.NONCE_REDIS_URL,
                    encoding="utf-8", 
                    decode_responses=True
                )
                await self.redis_client.ping()
                logger.info("Successfully connected to Redis for nonces.")
            except Exception as e:
                logger.error(f"Could not connect to Redis for nonces: {e}", exc_info=True)
                self.redis_client = None

    async def close_redis_connection(self):
        if self.redis_client:
            logger.info("Closing Redis connection for nonces...")
            await self.redis_client.aclose()
            logger.info("Redis connection for nonces closed.")
            self.redis_client = None
    
    async def get_redis_client(self) -> Optional[aioredis.Redis]:
        if self.redis_client is None:
            logger.warning("Redis client for nonces is None. Attempting to connect (should be done at startup).")
        return self.redis_client

redis_manager = RedisManager()

async def get_redis_nonce_client() -> Optional[aioredis.Redis]:
    client = await redis_manager.get_redis_client()
    if client is None:
        logger.error("Failed to get Redis client for nonces. Nonce functionality will be impaired or unavailable.")
    return client

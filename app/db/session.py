# ===========================================================================
# File: app/db/session.py
# ===========================================================================
# (Sama seperti versi sebelumnya)
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings, logger
from typing import Optional

class MongoDbContextManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    async def connect_to_mongo(self):
        logger.info(f"Attempting to connect to MongoDB at {settings.MONGODB_URL}...")
        try:
            self.client = AsyncIOMotorClient(
                settings.MONGODB_URL, 
                serverSelectionTimeoutMS=5000,
                tz_aware=True
            )
            await self.client.admin.command('ping')
            self.db = self.client[settings.MONGODB_DB_NAME]
            logger.info(f"Successfully connected to MongoDB database: {settings.MONGODB_DB_NAME}")
        except Exception as e:
            logger.error(f"Could not connect to MongoDB: {e}", exc_info=True)

    async def close_mongo_connection(self):
        if self.client:
            logger.info("Closing MongoDB connection...")
            self.client.close()
            logger.info("MongoDB connection closed.")

mongo_db_manager = MongoDbContextManager()

async def get_db() -> AsyncIOMotorDatabase:
    if mongo_db_manager.db is None:
        logger.critical("MongoDB not initialized. Application might not have started correctly or DB connection failed at startup.")
        raise RuntimeError("MongoDB not connected. Ensure connect_to_mongo is called successfully at application startup.")
    return mongo_db_manager.db
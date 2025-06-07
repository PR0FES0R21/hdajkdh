# ===========================================================================
# File: app/core/config.py (MODIFIKASI: Tambahkan settings Twitter)
# ===========================================================================
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, Any, List
import logging
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Cigar DS API"
    API_V1_STR: str = "/api/v1"
    
    MONGODB_URL: str
    MONGODB_DB_NAME: str

    REDIS_URL: str
    REDIS_DB_NONCE: int = 0
    REDIS_DB_CACHE: int = 1
    REDIS_DB_CELERY: int = 2

    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # X (Twitter) OAuth 2.0 Settings
    TWITTER_CLIENT_ID: str
    TWITTER_CLIENT_SECRET: str
    TWITTER_CALLBACK_URL: str # URL callback yang didaftarkan di Twitter Dev Portal

    DEFAULT_RANK_OBSERVER: str = "Observer"
    
    RANK_THRESHOLDS: Dict[str, int] = {
        "Observer": 0, "Ally": 100, "Field Agent": 500,
        "Strategist": 1500, "Commander": 5000, "Overseer": 15000
    }
    RANK_ORDER: List[str] = ["Observer", "Ally", "Field Agent", "Strategist", "Commander", "Overseer"]

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    NONCE_EXPIRY_SECONDS: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore'
    )

    from pydantic import model_validator

    @model_validator(mode='after')
    def set_computed_urls(self) -> 'Settings':
        self.NONCE_REDIS_URL = f"{self.REDIS_URL}/{self.REDIS_DB_NONCE}"
        
        celery_redis_url = f"{self.REDIS_URL}/{self.REDIS_DB_CELERY}"
        if self.CELERY_BROKER_URL is None:
            self.CELERY_BROKER_URL = celery_redis_url
        if self.CELERY_RESULT_BACKEND is None:
            self.CELERY_RESULT_BACKEND = celery_redis_url
        return self
    
    NONCE_REDIS_URL: Optional[str] = None

settings = Settings()

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(settings.PROJECT_NAME)
logger.info(f"Logger initialized with level: {settings.LOG_LEVEL}")
if "YOUR_VERY_STRONG_AND_LONG_SECRET_KEY" in settings.SECRET_KEY: # Check default secret
    logger.critical("SECURITY WARNING: Default SECRET_KEY is in use or too weak. Please change it in your .env file immediately!")
if not settings.TWITTER_CLIENT_ID or not settings.TWITTER_CLIENT_SECRET:
    logger.warning("TWITTER_CLIENT_ID or TWITTER_CLIENT_SECRET is not set. 'Connect X' feature will not work.")

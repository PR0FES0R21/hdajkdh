# ===========================================================================
# File: app/tests/conftest.py (MODIFIKASI: Import UserProfile dari app.models.user)
# ===========================================================================
import pytest
import asyncio
from httpx import AsyncClient
from typing import AsyncGenerator, Generator, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from asgi_lifespan import LifespanManager

from app.main import app
from app.core.config import settings, logger
from app.db.session import get_db as app_get_db
from app.db.session import mongo_db_manager
from app.db.redis_conn import redis_manager, get_redis_nonce_client as app_get_redis_nonce_client
from app.models.user import UserInDB
from app.api.v1.schemas.user import UserCreate # Hanya UserCreate dari schemas.user
from app.models.user import UserProfile # UserProfile diimpor dari models.user
from app.utils.helpers import generate_sci_fi_username
from app.core.security import create_access_token
from fastapi import Depends # Menambahkan Depends

settings.TESTING_MODE = True
settings.MONGODB_DB_NAME = settings.MONGODB_TEST_DB_NAME
settings.LOG_LEVEL = "DEBUG"
# settings.REDIS_DB_NONCE = 10 # Pastikan ini sesuai dengan Redis test Anda jika berbeda

logger.info(f"--- RUNNING IN TESTING MODE (conftest.py) ---")
logger.info(f"Test MongoDB: {settings.MONGODB_URL}/{settings.MONGODB_DB_NAME}")
logger.info(f"Test Redis Nonce DB: {settings.REDIS_DB_NONCE}")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
async def lifespan_manager_fixture() -> AsyncGenerator[LifespanManager, None]: # Mengganti nama fixture
    logger.debug("Initializing LifespanManager for test session...")
    async with LifespanManager(app) as manager:
        yield manager
    logger.debug("LifespanManager for test session shut down.")


@pytest.fixture(scope="session")
async def test_db(lifespan_manager_fixture: LifespanManager) -> AsyncIOMotorDatabase: # Menggunakan nama fixture baru
    if mongo_db_manager.db is None:
        logger.error("Test DB not initialized by lifespan_manager!")
        raise RuntimeError("Failed to get test MongoDB from lifespan_manager.")
    
    logger.debug(f"Using test database: {mongo_db_manager.db.name}")
    # Bersihkan database sebelum yield (opsional, tergantung strategi)
    # await mongo_db_manager.client.drop_database(settings.MONGODB_TEST_DB_NAME)
    yield mongo_db_manager.db
    
    logger.info(f"Dropping test database: {settings.MONGODB_TEST_DB_NAME} after all tests.")
    if mongo_db_manager.client:
        await mongo_db_manager.client.drop_database(settings.MONGODB_TEST_DB_NAME)

@pytest.fixture(scope="session")
async def test_redis_nonce_client_fixture(lifespan_manager_fixture: LifespanManager): # Mengganti nama fixture
    if redis_manager.redis_client is None:
        logger.error("Test Redis Nonce client not initialized by lifespan_manager!")
        raise RuntimeError("Failed to get test Redis Nonce client from lifespan_manager.")
    
    logger.debug(f"Using test Redis Nonce DB: {settings.REDIS_DB_NONCE}")
    # Bersihkan DB Redis nonce sebelum yield (opsional)
    # await redis_manager.redis_client.flushdb()
    yield redis_manager.redis_client
    # if redis_manager.redis_client:
    #     await redis_manager.redis_client.flushdb()


async def override_get_db_for_test(db_session = Depends(test_db)) -> AsyncIOMotorDatabase:
    yield db_session

app.dependency_overrides[app_get_db] = override_get_db_for_test

async def override_get_redis_nonce_client_for_test(
    redis_client_session = Depends(test_redis_nonce_client_fixture) # Menggunakan nama fixture baru
):
    yield redis_client_session

app.dependency_overrides[app_get_redis_nonce_client] = override_get_redis_nonce_client_for_test


@pytest.fixture(scope="module")
async def async_test_client() -> AsyncGenerator[AsyncClient, None]:
    # LifespanManager sudah aktif via autouse fixture, jadi client bisa langsung dibuat
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client

@pytest.fixture(scope="function")
async def test_user(test_db: AsyncIOMotorDatabase) -> UserInDB:
    from app.crud.crud_user import crud_user
    
    test_wallet_address = "0x0000000000000000000000000000000000000001"
    existing_user = await crud_user.get_by_wallet_address(db=test_db, wallet_address=test_wallet_address)
    if existing_user:
        logger.debug(f"Removing existing test user: {existing_user.username}")
        await crud_user.remove(db=test_db, id=existing_user.id)

    username = generate_sci_fi_username(prefix="TestUser")
    # UserProfile diimpor dari app.models.user
    profile = UserProfile(commanderName=username) 
    
    user = await crud_user.create_new_user_from_wallet_connect(
        db=test_db, 
        wallet_address=test_wallet_address,
        profile_details=profile
    )
    logger.debug(f"Created test user: {user.username} with ID {user.id}")
    return user

@pytest.fixture(scope="function")
def test_user_auth_headers(test_user: UserInDB) -> Dict[str, str]:
    token = create_access_token(subject=test_user.walletAddress, user_id=str(test_user.id))
    return {"Authorization": f"Bearer {token}"}

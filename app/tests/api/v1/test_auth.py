# ===========================================================================
# File: app/tests/api/v1/test_auth.py (Contoh Tes Auth - Lebih Lengkap)
# ===========================================================================
import pytest
from httpx import AsyncClient
from fastapi import status as HttpStatus
from app.core.config import settings, logger
from app.models.user import UserInDB # Untuk tipe data
from app.crud.crud_user import crud_user # Untuk verifikasi DB
from motor.motor_asyncio import AsyncIOMotorDatabase # Untuk tipe data DB
from unittest.mock import patch # Untuk mocking

# Tandai semua tes di file ini sebagai asyncio
pytestmark = pytest.mark.asyncio

VALID_TEST_WALLET_ADDRESS_NEW = "0x1234567890123456789012345678901234567890"
VALID_TEST_WALLET_ADDRESS_EXISTING = "0x0000000000000000000000000000000000000001" # Sama dengan test_user fixture

async def test_request_challenge_message_success(async_test_client: AsyncClient):
    logger.info("Testing GET /auth/challenge - Success")
    response = await async_test_client.get(
        f"{settings.API_V1_STR}/auth/challenge", 
        params={"walletAddress": VALID_TEST_WALLET_ADDRESS_NEW}
    )
    assert response.status_code == HttpStatus.HTTP_200_OK
    data = response.json()
    assert "messageToSign" in data
    assert "nonce" in data
    assert len(data["nonce"]) == 32
    assert data["nonce"] in data["messageToSign"]
    logger.info(f"Challenge received: {data['messageToSign']}")

async def test_request_challenge_message_invalid_wallet_format(async_test_client: AsyncClient):
    logger.info("Testing GET /auth/challenge - Invalid Wallet Format")
    response = await async_test_client.get(
        f"{settings.API_V1_STR}/auth/challenge", 
        params={"walletAddress": "0xInvalidAddress"}
    )
    # Pydantic akan raise 422 Unprocessable Entity karena regex di Query param gagal
    assert response.status_code == HttpStatus.HTTP_422_UNPROCESSABLE_ENTITY 

async def test_request_challenge_message_missing_wallet(async_test_client: AsyncClient):
    logger.info("Testing GET /auth/challenge - Missing Wallet Address")
    response = await async_test_client.get(f"{settings.API_V1_STR}/auth/challenge")
    # FastAPI akan return 422 karena query parameter 'walletAddress' wajib
    assert response.status_code == HttpStatus.HTTP_422_UNPROCESSABLE_ENTITY


@patch("app.core.security.verify_wallet_signature", return_value=True) # Mock fungsi verifikasi signature
async def test_connect_wallet_new_user_success(
    mock_verify_signature, # Argumen untuk mock
    async_test_client: AsyncClient, 
    test_db: AsyncIOMotorDatabase # Menggunakan test_db dari conftest
):
    logger.info("Testing POST /auth/connect - New User Success")
    # 1. Dapatkan challenge
    challenge_response = await async_test_client.get(
        f"{settings.API_V1_STR}/auth/challenge", 
        params={"walletAddress": VALID_TEST_WALLET_ADDRESS_NEW}
    )
    assert challenge_response.status_code == HttpStatus.HTTP_200_OK
    challenge_data = challenge_response.json()
    message_to_sign = challenge_data["messageToSign"]
    nonce = challenge_data["nonce"]

    # 2. Persiapkan payload untuk connect
    dummy_signature = "0x" + "a" * 130 # Signature dummy karena kita mock verifikasinya
    connect_payload = {
        "walletAddress": VALID_TEST_WALLET_ADDRESS_NEW,
        "message": message_to_sign,
        "signature": dummy_signature,
        "nonce": nonce
    }
    
    # 3. Lakukan connect
    connect_response = await async_test_client.post(
        f"{settings.API_V1_STR}/auth/connect",
        json=connect_payload
    )
    
    assert connect_response.status_code == HttpStatus.HTTP_200_OK, connect_response.text
    token_data = connect_response.json()
    
    # 4. Verifikasi respons token
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert "user" in token_data
    user_resp = token_data["user"]
    assert user_resp["walletAddress"] == VALID_TEST_WALLET_ADDRESS_NEW.lower()
    assert user_resp["rank"] == settings.DEFAULT_RANK_OBSERVER
    assert user_resp["xp"] == 0
    assert user_resp["profile"]["commanderName"] is not None
    assert user_resp["referralCode"] is not None

    # 5. Verifikasi user dibuat di DB
    db_user = await crud_user.get_by_wallet_address(test_db, wallet_address=VALID_TEST_WALLET_ADDRESS_NEW)
    assert db_user is not None
    assert db_user.username == user_resp["username"]
    assert db_user.rank == settings.DEFAULT_RANK_OBSERVER

    # 6. Pastikan mock dipanggil dengan benar
    mock_verify_signature.assert_called_once_with(
        wallet_address=VALID_TEST_WALLET_ADDRESS_NEW,
        original_message=message_to_sign,
        signature=dummy_signature
    )

@patch("app.core.security.verify_wallet_signature", return_value=True)
async def test_connect_wallet_existing_user_success(
    mock_verify_signature,
    async_test_client: AsyncClient, 
    test_db: AsyncIOMotorDatabase,
    test_user: UserInDB # Menggunakan fixture user yang sudah ada
):
    logger.info("Testing POST /auth/connect - Existing User Success")
    existing_wallet_address = test_user.walletAddress # Ini adalah VALID_TEST_WALLET_ADDRESS_EXISTING

    # 1. Dapatkan challenge
    challenge_response = await async_test_client.get(
        f"{settings.API_V1_STR}/auth/challenge", 
        params={"walletAddress": existing_wallet_address}
    )
    assert challenge_response.status_code == HttpStatus.HTTP_200_OK
    challenge_data = challenge_response.json()
    message_to_sign = challenge_data["messageToSign"]
    nonce = challenge_data["nonce"]

    # 2. Persiapkan payload
    dummy_signature = "0x" + "b" * 130
    connect_payload = {
        "walletAddress": existing_wallet_address,
        "message": message_to_sign,
        "signature": dummy_signature,
        "nonce": nonce
    }
    
    # 3. Lakukan connect
    connect_response = await async_test_client.post(
        f"{settings.API_V1_STR}/auth/connect",
        json=connect_payload
    )
    assert connect_response.status_code == HttpStatus.HTTP_200_OK, connect_response.text
    token_data = connect_response.json()

    # 4. Verifikasi respons
    assert token_data["user"]["walletAddress"] == existing_wallet_address.lower()
    assert token_data["user"]["username"] == test_user.username # Username harus sama
    assert token_data["user"]["rank"] == test_user.rank # Rank harus sama

    # 5. Verifikasi lastLogin di DB terupdate (sulit dites presisi tanpa mock datetime)
    # Cukup pastikan user masih ada dan tidak ada error
    db_user_after_login = await crud_user.get_by_wallet_address(test_db, wallet_address=existing_wallet_address)
    assert db_user_after_login is not None
    assert db_user_after_login.lastLogin is not None
    if test_user.lastLogin: # Jika user test awal punya lastLogin
         assert db_user_after_login.lastLogin > test_user.lastLogin


async def test_connect_wallet_invalid_nonce(async_test_client: AsyncClient):
    logger.info("Testing POST /auth/connect - Invalid Nonce")
    # 1. Dapatkan challenge
    challenge_response = await async_test_client.get(
        f"{settings.API_V1_STR}/auth/challenge", 
        params={"walletAddress": VALID_TEST_WALLET_ADDRESS_NEW}
    )
    challenge_data = challenge_response.json()
    message_to_sign_correct_nonce = challenge_data["messageToSign"]
    # Nonce yang salah
    invalid_nonce = "wrongnonce" + challenge_data["nonce"][:22] # Buat nonce yang salah tapi panjangnya sama

    dummy_signature = "0x" + "c" * 130
    connect_payload = {
        "walletAddress": VALID_TEST_WALLET_ADDRESS_NEW,
        "message": message_to_sign_correct_nonce.replace(challenge_data["nonce"], invalid_nonce), # Pesan dengan nonce salah
        "signature": dummy_signature,
        "nonce": invalid_nonce # Nonce yang salah
    }
    
    connect_response = await async_test_client.post(
        f"{settings.API_V1_STR}/auth/connect",
        json=connect_payload
    )
    assert connect_response.status_code == HttpStatus.HTTP_400_BAD_REQUEST
    assert "Nonce tidak cocok" in connect_response.json()["detail"]


@patch("app.core.security.verify_wallet_signature", return_value=False) # Mock signature gagal
async def test_connect_wallet_invalid_signature(
    mock_verify_signature_false,
    async_test_client: AsyncClient
):
    logger.info("Testing POST /auth/connect - Invalid Signature")
    challenge_response = await async_test_client.get(
        f"{settings.API_V1_STR}/auth/challenge", 
        params={"walletAddress": VALID_TEST_WALLET_ADDRESS_NEW}
    )
    challenge_data = challenge_response.json()
    
    connect_payload = {
        "walletAddress": VALID_TEST_WALLET_ADDRESS_NEW,
        "message": challenge_data["messageToSign"],
        "signature": "0x" + "d" * 130, # Signature apapun karena akan di-mock gagal
        "nonce": challenge_data["nonce"]
    }
    connect_response = await async_test_client.post(
        f"{settings.API_V1_STR}/auth/connect",
        json=connect_payload
    )
    assert connect_response.status_code == HttpStatus.HTTP_401_UNAUTHORIZED
    assert "Signature tidak valid" in connect_response.json()["detail"]

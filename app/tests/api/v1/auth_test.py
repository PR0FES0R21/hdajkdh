# ===========================================================================
# File: app/tests/api/v1/test_auth.py (Contoh Tes Auth)
# ===========================================================================
"""
import pytest
from httpx import AsyncClient
from fastapi import status as HttpStatus # Menggunakan alias yang konsisten
from app.core.config import settings # Untuk API_V1_STR

# Tandai semua tes di file ini sebagai asyncio
pytestmark = pytest.mark.asyncio

# Contoh alamat wallet yang valid untuk testing
VALID_TEST_WALLET_ADDRESS = "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B" # Vitalik's address

async def test_request_challenge_message_success(async_test_client: AsyncClient):
    response = await async_test_client.get(
        f"{settings.API_V1_STR}/auth/challenge", 
        params={"walletAddress": VALID_TEST_WALLET_ADDRESS}
    )
    assert response.status_code == HttpStatus.HTTP_200_OK
    data = response.json()
    assert "messageToSign" in data
    assert "nonce" in data
    assert len(data["nonce"]) == 32 # Nonce hex 16 bytes = 32 chars
    assert VALID_TEST_WALLET_ADDRESS.lower() not in data["messageToSign"] # Pesan challenge seharusnya generik + nonce
    assert data["nonce"] in data["messageToSign"] # Nonce harus ada di pesan

async def test_request_challenge_message_invalid_wallet(async_test_client: AsyncClient):
    response = await async_test_client.get(
        f"{settings.API_V1_STR}/auth/challenge", 
        params={"walletAddress": "0xInvalidAddress"}
    )
    assert response.status_code == HttpStatus.HTTP_400_BAD_REQUEST # Atau 422 jika Pydantic regex gagal
    # Detail error bisa dicek jika perlu

async def test_connect_wallet_flow_new_user(async_test_client: AsyncClient, test_db_session_manager: AsyncIOMotorDatabase):
    # 1. Dapatkan challenge
    challenge_response = await async_test_client.get(
        f"{settings.API_V1_STR}/auth/challenge", 
        params={"walletAddress": VALID_TEST_WALLET_ADDRESS}
    )
    assert challenge_response.status_code == HttpStatus.HTTP_200_OK
    challenge_data = challenge_response.json()
    message_to_sign = challenge_data["messageToSign"]
    nonce = challenge_data["nonce"]

    # 2. Sign message (simulasi di test, butuh private key)
    # Untuk tes nyata, kita mungkin mock `verify_wallet_signature` atau pakai wallet test dengan private key
    # Di sini kita akan mock `verify_wallet_signature` di service atau gunakan private key test jika ada
    # Untuk contoh ini, kita asumsikan signature valid dan akan di-mock di level service jika perlu.
    # Atau, kita bisa buat endpoint test khusus yang tidak verifikasi signature tapi tetap create user.
    # Untuk sekarang, kita akan coba dengan signature dummy dan berharap verify_wallet_signature di-mock.
    
    # Mocking verify_wallet_signature (cara sederhana, idealnya pakai pytest-mock)
    from app.core import security as core_security
    original_verify_signature = core_security.verify_wallet_signature
    core_security.verify_wallet_signature = lambda wa, om, sig: True # Selalu return True untuk tes ini

    dummy_signature = "0x" + "a" * 130 # Signature dummy

    connect_payload = {
        "walletAddress": VALID_TEST_WALLET_ADDRESS,
        "message": message_to_sign,
        "signature": dummy_signature,
        "nonce": nonce
    }
    
    connect_response = await async_test_client.post(
        f"{settings.API_V1_STR}/auth/connect",
        json=connect_payload
    )
    
    # Kembalikan fungsi original setelah tes
    core_security.verify_wallet_signature = original_verify_signature

    assert connect_response.status_code == HttpStatus.HTTP_200_OK, connect_response.text
    token_data = connect_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert "user" in token_data
    assert token_data["user"]["walletAddress"] == VALID_TEST_WALLET_ADDRESS.lower() # Disimpan lowercase
    assert token_data["user"]["rank"] == settings.DEFAULT_RANK_OBSERVER

    # Cek apakah user dibuat di DB
    from app.crud.crud_user import crud_user
    db_user = await crud_user.get_by_wallet_address(test_db_session_manager, wallet_address=VALID_TEST_WALLET_ADDRESS)
    assert db_user is not None
    assert db_user.username == token_data["user"]["username"]

# Tambahkan tes lain: connect user yang sudah ada, nonce salah, signature salah, dll.
"""
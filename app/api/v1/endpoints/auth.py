# ===========================================================================
# File: app/api/v1/endpoints/auth.py (MODIFIKASI: Endpoint /x/initiate-oauth dan /x/callback)
# ===========================================================================
from fastapi import APIRouter, Depends, HTTPException, status as HttpStatus, Query, Request as FastAPIRequest
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
import redis.asyncio as aioredis
from typing import Optional
from urllib.parse import quote

from app.db.session import get_db
from app.db.redis_conn import get_redis_nonce_client
from app.services.auth_service import auth_service
from app.api.v1.schemas.auth import (
    ChallengeMessageResponse, WalletConnectRequest, EthAddress, 
    TwitterOAuthInitiateResponse, TwitterOAuthCallbackResponse
)
from app.api.v1.schemas.token import TokenResponse
from app.core.config import logger, settings
from app.api.deps import get_current_active_user
from app.models.user import UserInDB

router = APIRouter()

# ... (Endpoint /challenge dan /connect sama seperti sebelumnya) ...
@router.get(
    "/challenge",
    response_model=ChallengeMessageResponse,
    summary="Request Challenge Message for Wallet Signature"
)
async def request_challenge_message_endpoint(
    walletAddress: EthAddress = Query(..., description="Alamat wallet pengguna Ethereum (hex string)"),
    redis_client: Optional[aioredis.Redis] = Depends(get_redis_nonce_client)
):
    logger.info(f"Challenge requested for wallet: {walletAddress}")
    challenge = await auth_service.generate_challenge_message(
        wallet_address=str(walletAddress),
        redis_client=redis_client
    )
    return ChallengeMessageResponse(**challenge)


@router.post(
    "/connect",
    response_model=TokenResponse,
    summary="Connect Wallet, Authenticate, and Get Session Token"
)
async def connect_wallet_endpoint(
    *,
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_data: WalletConnectRequest,
    redis_client: Optional[aioredis.Redis] = Depends(get_redis_nonce_client)
):
    try:
        logger.info(f"Connect attempt from wallet: {request_data.walletAddress}")
        token_response_obj = await auth_service.connect_wallet_and_get_token(
            db=db, 
            request_data=request_data,
            redis_client=redis_client
        )
        return token_response_obj
    except HTTPException as e:
        logger.warning(f"HTTPException during connect for {request_data.walletAddress}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during connect for {request_data.walletAddress}: {e}", exc_info=True)
        raise HTTPException(
            status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Terjadi kesalahan internal saat menghubungkan wallet."
        )

@router.get(
    "/x/initiate-oauth", # Endpoint yang dipanggil frontend
    response_model=TwitterOAuthInitiateResponse,
    summary="Initiate X (Twitter) OAuth Flow",
    description="Frontend memanggil endpoint ini (dengan JWT CigarDS). Backend akan men-generate URL otorisasi Twitter dan mengembalikannya sebagai JSON. Frontend kemudian akan me-redirect pengguna ke URL tersebut."
)
async def twitter_initiate_oauth_endpoint(
    redis_client: Optional[aioredis.Redis] = Depends(get_redis_nonce_client),
    current_user: UserInDB = Depends(get_current_active_user) # Memastikan user CigarDS sudah login
):
    if not settings.TWITTER_CLIENT_ID or not settings.TWITTER_CLIENT_SECRET:
        logger.error("Twitter OAuth credentials not configured in settings.")
        raise HTTPException(status_code=HttpStatus.HTTP_501_NOT_IMPLEMENTED, detail="Fitur koneksi X belum dikonfigurasi.")
    
    logger.info(f"User {current_user.username} initiating X OAuth flow.")
    
    # auth_service.initiate_twitter_oauth sekarang mengembalikan RedirectResponse
    # Kita ekstrak URL dari header 'location' untuk dikirim sebagai JSON
    redirect_response_obj = await auth_service.initiate_twitter_oauth(
        redis_client=redis_client, 
        current_user=current_user
    )
    
    twitter_auth_url = redirect_response_obj.headers.get("location")
    if not twitter_auth_url:
        logger.error("Failed to get location header from initiate_twitter_oauth's RedirectResponse.")
        raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal membuat URL otorisasi X.")

    return TwitterOAuthInitiateResponse(redirect_url=twitter_auth_url)


@router.get(
    "/x/callback",
    summary="X (Twitter) OAuth Callback",
    description="Endpoint callback yang akan dipanggil oleh Twitter setelah otorisasi pengguna. Endpoint ini akan me-redirect kembali ke frontend.",
    # Tidak ada response_model eksplisit karena akan selalu RedirectResponse ke frontend
)
async def twitter_oauth_callback_endpoint(
    request: FastAPIRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    redis_client: Optional[aioredis.Redis] = Depends(get_redis_nonce_client)
):
    code = request.query_params.get("code")
    state_from_twitter = request.query_params.get("state")
    error_from_twitter = request.query_params.get("error")
    error_description_from_twitter = request.query_params.get("error_description")

    # Tentukan URL redirect ke frontend (bisa dari settings atau hardcode untuk dev)
    frontend_redirect_base_url = "https://dashboard.cigarverse.space/mission-terminal" # SESUAIKAN DENGAN URL FRONTEND ANDA

    if error_from_twitter:
        logger.error(f"Twitter OAuth error on callback: {error_from_twitter} - {error_description_from_twitter}. State: {state_from_twitter}")
        error_message = quote(error_description_from_twitter or error_from_twitter or "Unknown Twitter OAuth error.")
        return RedirectResponse(url=f"{frontend_redirect_base_url}?x_connected=false&error={error_message}", status_code=HttpStatus.HTTP_307_TEMPORARY_REDIRECT)

    if not code or not state_from_twitter:
        logger.error(f"Twitter callback missing 'code' or 'state'. Query params: {request.query_params}")
        error_message = quote("Parameter callback tidak lengkap dari Twitter.")
        return RedirectResponse(url=f"{frontend_redirect_base_url}?x_connected=false&error={error_message}", status_code=HttpStatus.HTTP_307_TEMPORARY_REDIRECT)

    logger.info(f"Received Twitter callback with state: {state_from_twitter} and code: {code[:10]}...")
    
    try:
        callback_response_data = await auth_service.handle_twitter_oauth_callback(
            db=db, 
            code=code, 
            state_from_twitter=state_from_twitter,
            redis_client=redis_client
        )
        success_message = quote(callback_response_data.message)
        success_redirect_url = f"{frontend_redirect_base_url}?x_connected=true&message={success_message}"
        logger.info(f"Redirecting user to: {success_redirect_url} after X OAuth callback success.")
        return RedirectResponse(url=success_redirect_url, status_code=HttpStatus.HTTP_307_TEMPORARY_REDIRECT)

    except HTTPException as e:
        logger.error(f"HTTPException during Twitter callback processing for state {state_from_twitter}: {e.detail}")
        error_message = quote(e.detail if isinstance(e.detail, str) else "OAuth X processing error.")
        error_redirect_url = f"{frontend_redirect_base_url}?x_connected=false&error={error_message}"
        return RedirectResponse(url=error_redirect_url, status_code=HttpStatus.HTTP_307_TEMPORARY_REDIRECT)
    except Exception as e:
        logger.error(f"Unexpected error during Twitter callback processing for state {state_from_twitter}: {e}", exc_info=True)
        error_message = quote("InternalErrorXCallbackProcessing")
        error_redirect_url = f"{frontend_redirect_base_url}?x_connected=false&error={error_message}"
        return RedirectResponse(url=error_redirect_url, status_code=HttpStatus.HTTP_307_TEMPORARY_REDIRECT)

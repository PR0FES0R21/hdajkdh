# ===========================================================================
# File: app/services/auth_service.py (MODIFIKASI: Pastikan signature initiate_twitter_oauth)
# ===========================================================================
from fastapi import HTTPException, status as HttpStatus, Depends, Request as FastAPIRequest
from fastapi.responses import RedirectResponse
from datetime import timedelta, datetime, timezone
import secrets
import json
import httpx
import hashlib
import base64
from urllib.parse import urlencode, quote

from app.core.config import settings, logger
from app.core.security import create_access_token, verify_wallet_signature, encrypt_data
from app.crud.crud_user import crud_user
from app.api.v1.schemas.auth import WalletConnectRequest, TwitterOAuthCallbackResponse, TwitterOAuthInitiateResponse
from app.api.v1.schemas.token import TokenResponse
from app.api.v1.schemas.user import UserPublic
from app.models.user import UserInDB, UserProfile as UserProfileModel, UserSystemStatus as UserSystemStatusModel, UserTwitterData
from app.utils.helpers import generate_sci_fi_username, generate_unique_referral_code
from app.services.user_service import user_service
from app.services.mission_service import mission_service
from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db.redis_conn import get_redis_nonce_client
import redis.asyncio as aioredis
from app.models.base import PyObjectId
from pydantic import HttpUrl as PydanticHttpUrl

TWITTER_AUTHORIZATION_URL = "https://twitter.com/i/oauth2/authorize"
TWITTER_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
TWITTER_USER_ME_URL = "https://api.twitter.com/2/users/me"
TWITTER_SCOPES = ["users.read", "tweet.read", "like.read", "follows.read", "offline.access"]
CONNECT_X_MISSION_ID_STR = "connect-x-account" 
OAUTH_STATE_EXPIRY_SECONDS = 600

class AuthService:
    # ... (generate_challenge_message dan connect_wallet_and_get_token sama seperti versi sebelumnya) ...
    async def generate_challenge_message(
        self, 
        wallet_address: str, 
        redis_client: Optional[aioredis.Redis] = None
    ) -> Dict[str, str]:
        # ... (logika sama seperti sebelumnya) ...
        if redis_client is None:
            logger.error("Redis client not available for nonce generation. Auth will fail or be insecure.")
            raise HTTPException(status_code=HttpStatus.HTTP_503_SERVICE_UNAVAILABLE, detail="Nonce service unavailable.")

        wallet_address_lower = wallet_address.lower()
        nonce_key = f"nonce:{wallet_address_lower}"

        await redis_client.delete(nonce_key)

        nonce = secrets.token_hex(16)
        message_to_sign = f"Selamat datang di {settings.PROJECT_NAME}! Silakan tandatangani pesan ini untuk melanjutkan. Nonce unik Anda: {nonce}"
        
        nonce_data = {"nonce": nonce, "message_to_sign": message_to_sign}
        await redis_client.set(
            nonce_key, 
            json.dumps(nonce_data),
            ex=settings.NONCE_EXPIRY_SECONDS 
        )
        logger.info(f"Generated challenge (Redis) for {wallet_address_lower}, nonce: {nonce[:8]}..., key: {nonce_key}")
        return {"messageToSign": message_to_sign, "nonce": nonce}


    async def connect_wallet_and_get_token(
        self, 
        db: AsyncIOMotorDatabase, 
        *, 
        request_data: WalletConnectRequest,
        redis_client: Optional[aioredis.Redis] = None
    ) -> TokenResponse:
        # ... (logika verifikasi nonce dan signature sama seperti sebelumnya) ...
        if redis_client is None:
            logger.error("Redis client not available for nonce verification. Auth will fail.")
            raise HTTPException(status_code=HttpStatus.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication service temporarily unavailable.")

        wallet_address_lower = request_data.walletAddress.lower()
        nonce_key = f"nonce:{wallet_address_lower}"
        
        stored_nonce_json = await redis_client.get(nonce_key)

        if not stored_nonce_json:
            logger.warning(f"Nonce not found or expired in Redis for {wallet_address_lower}. Key: {nonce_key}")
            raise HTTPException(
                status_code=HttpStatus.HTTP_400_BAD_REQUEST, 
                detail="Nonce tidak ditemukan atau sudah kadaluarsa. Silakan minta challenge baru."
            )
        
        try:
            stored_data = json.loads(stored_nonce_json)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode nonce data from Redis for {wallet_address_lower}. Data: {stored_nonce_json}")
            await redis_client.delete(nonce_key)
            raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="Kesalahan data internal.")
        
        if request_data.nonce != stored_data.get("nonce"):
            logger.warning(f"Nonce mismatch for {wallet_address_lower}. Expected: {stored_data.get('nonce','')[:8]}..., Got: {request_data.nonce[:8]}...")
            raise HTTPException(status_code=HttpStatus.HTTP_400_BAD_REQUEST, detail="Nonce tidak cocok.")
        
        if request_data.message != stored_data.get("message_to_sign"):
            logger.warning(f"Message mismatch for {wallet_address_lower}.")
            await redis_client.delete(nonce_key)
            raise HTTPException(
                status_code=HttpStatus.HTTP_400_BAD_REQUEST,
                detail="Pesan yang ditandatangani tidak cocok dengan challenge yang diberikan."
            )

        is_signature_valid = verify_wallet_signature(
            wallet_address=request_data.walletAddress,
            original_message=request_data.message,
            signature=request_data.signature
        )

        if not is_signature_valid:
            logger.warning(f"Invalid signature for {request_data.walletAddress}")
            raise HTTPException(
                status_code=HttpStatus.HTTP_401_UNAUTHORIZED,
                detail="Signature tidak valid atau alamat wallet tidak cocok.",
            )

        await redis_client.delete(nonce_key)
        logger.info(f"Nonce {nonce_key} used and deleted from Redis for {wallet_address_lower}.")


        db_user = await crud_user.get_by_wallet_address(db, wallet_address=request_data.walletAddress)
        
        user_was_created = False
        if not db_user:
            logger.info(f"New user connecting: {request_data.walletAddress}. Creating account...")
            user_was_created = True
            
            initial_username = await self._generate_unique_username(db)
            initial_profile = await user_service.prepare_initial_user_profile(commander_name=initial_username)
            initial_system_status = UserSystemStatusModel()
            initial_referral_code = await self._generate_unique_referral_code(db)
            
            referred_by_user_id_val: Optional[PyObjectId] = None
            if request_data.referral_code_input:
                referrer_user = await crud_user.get_by_referral_code(db, referral_code=request_data.referral_code_input)
                if referrer_user:
                    if referrer_user.walletAddress.lower() == request_data.walletAddress.lower():
                        logger.warning(f"User {request_data.walletAddress} attempted to refer themselves. Ignoring referral code.")
                    else:
                        referred_by_user_id_val = referrer_user.id
                        logger.info(f"New user {request_data.walletAddress} referred by {referrer_user.username} (ID: {referrer_user.id})")
                else:
                    logger.warning(f"Referral code '{request_data.referral_code_input}' not found for new user {request_data.walletAddress}.")
            
            db_user = await crud_user.create_new_user_with_complete_data(
                db, 
                wallet_address=request_data.walletAddress,
                username=initial_username,
                profile=initial_profile,
                system_status=initial_system_status,
                referral_code=initial_referral_code,
                referred_by_user_id=referred_by_user_id_val
            )
            if not db_user:
                 logger.critical(f"CRITICAL: Failed to create user in DB for wallet {request_data.walletAddress} after all checks.")
                 raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal membuat pengguna baru.")

            logger.info(f"New user '{db_user.username}' created for wallet {db_user.walletAddress}{f' (referred by ID: {referred_by_user_id_val})' if referred_by_user_id_val else ''}.")
            
            if referred_by_user_id_val:
                updated_referrer = await crud_user.increment_allies_count(db, user_id=referred_by_user_id_val)
                if not updated_referrer:
                    logger.error(f"Failed to increment allies_count for referrer ID: {referred_by_user_id_val}")
            
        if not db_user or not db_user.is_active:
            logger.warning(f"Login attempt by inactive or non-existent user: {request_data.walletAddress}")
            raise HTTPException(status_code=HttpStatus.HTTP_400_BAD_REQUEST, detail="Akun tidak aktif atau bermasalah.")

        user_after_last_login_update = await crud_user.update_last_login(db, user_id=db_user.id)
        if user_after_last_login_update:
            db_user = user_after_last_login_update
        else:
            logger.error(f"Failed to update last_login for user {db_user.username}. Fetching user again.")
            refetched_db_user = await crud_user.get(db, id=db_user.id)
            if not refetched_db_user:
                 logger.critical(f"CRITICAL: User {db_user.username} (ID: {db_user.id}) not found after attempting to update last_login.")
                 raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="Kesalahan kritis data pengguna.")
            db_user = refetched_db_user
        
        access_token = create_access_token(
            subject=db_user.walletAddress, 
            user_id=str(db_user.id)
        )
        
        user_public_data = UserPublic.model_validate(db_user)
        
        logger.info(f"User {db_user.username} authenticated successfully. Was created: {user_was_created}")
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_public_data
        )

    async def _generate_unique_username(self, db: AsyncIOMotorDatabase) -> str:
        # ... (logika sama seperti sebelumnya) ...
        username_candidate = generate_sci_fi_username()
        counter = 0
        base_username_for_suffix = username_candidate 
        while await crud_user.get_by_username(db, username=username_candidate):
            counter += 1
            username_candidate = f"{base_username_for_suffix}_{counter}" 
            if counter > 20:
                logger.error(f"Could not generate unique username after {counter} attempts for base {base_username_for_suffix}")
                return f"Agent{secrets.token_hex(4)}"
        return username_candidate

    async def _generate_unique_referral_code(self, db: AsyncIOMotorDatabase) -> str:
        # ... (logika sama seperti sebelumnya) ...
        referral_code_candidate = generate_unique_referral_code()
        counter = 0
        while await crud_user.get_by_referral_code(db, referral_code=referral_code_candidate):
            counter +=1
            referral_code_candidate = generate_unique_referral_code(length=7 if counter < 5 else 8)
            if counter > 10:
                logger.error(f"Could not generate unique referral code after {counter} attempts.")
                return f"REF{secrets.token_hex(5).upper()}"
        return referral_code_candidate

    async def initiate_twitter_oauth(
        self, 
        # request: FastAPIRequest, # Parameter ini sudah dihapus dari definisi
        redis_client: Optional[aioredis.Redis],
        current_user: UserInDB
    ) -> RedirectResponse: # Mengembalikan RedirectResponse langsung
        if not redis_client:
            logger.error("Redis client is unavailable for initiating Twitter OAuth.")
            raise HTTPException(status_code=HttpStatus.HTTP_503_SERVICE_UNAVAILABLE, detail="Layanan autentikasi X tidak tersedia saat ini.")

        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(60)
        code_challenge_raw = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge_raw).decode('utf-8').replace('=', '')
        
        oauth_state_data = {
            "code_verifier": code_verifier,
            "user_id": str(current_user.id)
        }
        state_redis_key = f"twitter_oauth_state:{state}"
        await redis_client.set(state_redis_key, json.dumps(oauth_state_data), ex=OAUTH_STATE_EXPIRY_SECONDS)
        logger.info(f"Stored Twitter OAuth state in Redis for user {current_user.username} with key {state_redis_key}")

        twitter_auth_params = {
            "response_type": "code",
            "client_id": settings.TWITTER_CLIENT_ID,
            "redirect_uri": settings.TWITTER_CALLBACK_URL,
            "scope": " ".join(TWITTER_SCOPES),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        authorization_url_str = f"{TWITTER_AUTHORIZATION_URL}?{urlencode(twitter_auth_params)}"
        
        logger.info(f"Redirecting user {current_user.username} to Twitter authorization URL.")
        return RedirectResponse(url=authorization_url_str, status_code=307)


    async def handle_twitter_oauth_callback(
        self, db: AsyncIOMotorDatabase, code: str, state_from_twitter: str, 
        redis_client: Optional[aioredis.Redis]
    ) -> TwitterOAuthCallbackResponse: 
        # ... (logika sama seperti versi sebelumnya, memastikan mengambil platform_user dari state Redis) ...
        if not redis_client:
            logger.error("Redis client is unavailable for handling Twitter OAuth callback.")
            raise HTTPException(status_code=HttpStatus.HTTP_503_SERVICE_UNAVAILABLE, detail="Layanan autentikasi X tidak tersedia saat ini (Redis).")

        state_redis_key = f"twitter_oauth_state:{state_from_twitter}"
        stored_oauth_context_json = await redis_client.get(state_redis_key)
        await redis_client.delete(state_redis_key)

        if not stored_oauth_context_json:
            logger.error(f"Invalid or expired OAuth state '{state_from_twitter}' received from Twitter callback.")
            raise HTTPException(status_code=HttpStatus.HTTP_400_BAD_REQUEST, detail="Sesi otorisasi X tidak valid atau sudah kadaluarsa.")
        
        try:
            stored_oauth_context = json.loads(stored_oauth_context_json)
            code_verifier = stored_oauth_context.get("code_verifier")
            original_user_id_str_from_state = stored_oauth_context.get("user_id")
        except json.JSONDecodeError:
            logger.error(f"Failed to decode stored OAuth state data from Redis for state: {state_from_twitter}")
            raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="Kesalahan internal state otorisasi X.")

        if not code_verifier or not original_user_id_str_from_state:
            logger.error(f"Code verifier or original_user_id missing in stored OAuth state for state: {state_from_twitter}")
            raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="Kesalahan internal state otorisasi X (verifier).")
        
        try:
            user_object_id = PyObjectId(original_user_id_str_from_state)
            platform_user = await crud_user.get(db, id=user_object_id)
            if not platform_user:
                logger.error(f"User with ID {original_user_id_str_from_state} from OAuth state not found in DB.")
                raise HTTPException(status_code=HttpStatus.HTTP_404_NOT_FOUND, detail="Pengguna otorisasi tidak ditemukan.")
        except Exception as e_user:
            logger.error(f"Error fetching platform user from state: {e_user}", exc_info=True)
            raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal memuat data pengguna platform.")


        token_payload = {
            "code": code, "grant_type": "authorization_code",
            "client_id": settings.TWITTER_CLIENT_ID,
            "redirect_uri": settings.TWITTER_CALLBACK_URL,
            "code_verifier": code_verifier
        }
        auth_string = f"{settings.TWITTER_CLIENT_ID}:{settings.TWITTER_CLIENT_SECRET}"
        auth_header_value = base64.b64encode(auth_string.encode()).decode()
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth_header_value}"
        }

        async with httpx.AsyncClient() as client:
            try:
                logger.debug(f"Requesting X access token with payload: {token_payload}")
                token_response = await client.post(TWITTER_TOKEN_URL, data=token_payload, headers=headers)
                token_response.raise_for_status()
                token_json = token_response.json()
                logger.debug(f"X access token response: {token_json}")
            except httpx.HTTPStatusError as e:
                logger.error(f"Twitter token exchange failed: {e.response.status_code} - {e.response.text}", exc_info=True)
                error_detail = e.response.json().get('error_description', e.response.json().get('error', e.response.text))
                raise HTTPException(status_code=HttpStatus.HTTP_502_BAD_GATEWAY, detail=f"Gagal mendapatkan token dari Twitter: {error_detail}")
            except Exception as e:
                logger.error(f"Error during Twitter token exchange: {e}", exc_info=True)
                raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="Kesalahan saat komunikasi dengan Twitter.")
            
        x_refresh_token = token_json.get("refresh_token")
        expires_in = token_json.get("expires_in")
        scope = token_json.get("scope")

        x_access_token = token_json.get("access_token")
        if not x_access_token:
            logger.error("Access token not found in Twitter's response.")
            raise HTTPException(status_code=HttpStatus.HTTP_502_BAD_GATEWAY, detail="Gagal mendapatkan access token dari Twitter.")

        user_info_headers = {"Authorization": f"Bearer {x_access_token}"}
        user_fields = "id,username,name"
        
        async with httpx.AsyncClient() as client:
            try:
                user_info_response = await client.get(f"{TWITTER_USER_ME_URL}?user.fields={user_fields}", headers=user_info_headers)
                user_info_response.raise_for_status()
                twitter_user_info = user_info_response.json().get("data")
                logger.debug(f"X user info response: {twitter_user_info}")
            except httpx.HTTPStatusError as e:
                logger.error(f"Twitter get user info failed: {e.response.status_code} - {e.response.text}", exc_info=True)
                raise HTTPException(status_code=HttpStatus.HTTP_502_BAD_GATEWAY, detail="Gagal mendapatkan info user dari Twitter.")
            except Exception as e:
                logger.error(f"Error during Twitter get user info: {e}", exc_info=True)
                raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="Kesalahan saat mengambil info user Twitter.")

        if not twitter_user_info:
            logger.error("No user data ('data' field) found in Twitter's user info response.")
            raise HTTPException(status_code=HttpStatus.HTTP_502_BAD_GATEWAY, detail="Data user tidak ditemukan dari Twitter.")

        twitter_user_id_str = twitter_user_info.get("id")
        twitter_username_str = twitter_user_info.get("username")

        if not twitter_user_id_str or not twitter_username_str:
            logger.error(f"Twitter user ID or username missing in response: {twitter_user_info}")
            raise HTTPException(status_code=HttpStatus.HTTP_502_BAD_GATEWAY, detail="Data user Twitter tidak lengkap.")

        user_twitter_data_to_save = UserTwitterData(
            twitter_user_id=twitter_user_id_str,
            twitter_username=twitter_username_str,
            access_token= encrypt_data(x_access_token),
            refresh_token= encrypt_data(x_refresh_token),
            expires_in=expires_in,
            expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
            connected_at=datetime.utcnow(),
        )

        updated_user = await crud_user.update_twitter_data(
            db, user_id=platform_user.id, twitter_data=user_twitter_data_to_save
        )
        if not updated_user:
            logger.error(f"Failed to update user {platform_user.username} with Twitter data. User ID: {platform_user.id}")
        
        logger.info(f"User {platform_user.username} successfully connected X account @{twitter_username_str} (ID: {twitter_user_id_str})")

        try:
            completion_response = await mission_service.process_mission_completion(
                db=db,
                user=platform_user, 
                mission_id_str_to_complete=CONNECT_X_MISSION_ID_STR,
                completion_data={"twitter_user_id": twitter_user_id_str}
            )
            logger.info(f"Mission '{CONNECT_X_MISSION_ID_STR}' completion processed for user {platform_user.username}: {completion_response.message}")
        except Exception as e:
            logger.error(f"Error processing mission completion for '{CONNECT_X_MISSION_ID_STR}' for user {platform_user.username} after X connect: {e}", exc_info=True)

        return TwitterOAuthCallbackResponse(
            message=f"Akun X @{twitter_username_str} berhasil terhubung!"
        )


auth_service = AuthService()
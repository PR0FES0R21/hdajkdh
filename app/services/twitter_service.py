# File: app/services/twitter_service.py

import httpx
from typing import Optional, Dict, Any

from fastapi import HTTPException
from starlette import status as HttpStatus

# [IMPROVEMENT] Import yang diperlukan untuk perbaikan
from app.core.config import logger, settings
from app.models.user import UserInDB, UserTwitterData
from app.crud import crud_user
from app.db.session import get_db
from app.core.security import encrypt_data, decrypt_data
from datetime import datetime, timezone, timedelta
TWITTER_API_BASE_URL = "https://api.twitter.com/2"

class TwitterService:
    # [IMPROVEMENT] Fungsi untuk refresh token
    async def _refresh_and_save_token(self, user: UserInDB) -> Optional[str]:
        """Gunakan refresh token untuk mendapatkan access token baru dan simpan ke DB."""
        decrypted_refresh_token = decrypt_data(user.twitter_data.refresh_token)
        if not decrypted_refresh_token:
            logger.error(f"User {user.username} has no valid refresh token to decrypt.")
            return None

        logger.info(f"Attempting to refresh Twitter token for user {user.username}")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url=f"{TWITTER_API_BASE_URL}/oauth2/token",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": decrypted_refresh_token,
                        "client_id": settings.TWITTER_CLIENT_ID,
                    },
                    auth=(settings.TWITTER_CLIENT_ID, settings.TWITTER_CLIENT_SECRET),
                )
                response.raise_for_status()
                token_json = response.json()
                
                new_access_token = token_json.get("access_token")
                new_refresh_token = token_json.get("refresh_token")
                expires_in_seconds = token_json.get("expires_in")
                new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

                # Update user di database dengan token baru yang sudah dienkripsi
                user.twitter_data.access_token = encrypt_data(new_access_token)
                user.twitter_data.refresh_token = encrypt_data(new_refresh_token)
                user.twitter_data.expires_in = expires_in_seconds
                user.twitter_data.expires_at = new_expires_at
                
                async for db in get_db():
                    await crud_user.update(db, db_obj=user, obj_in={"twitter_data": user.twitter_data.model_dump()})
                
                logger.info(f"Successfully refreshed Twitter token for user {user.username}")
                return new_access_token

            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to refresh token for user {user.username}. Status: {e.response.status_code}, Response: {e.response.text}")
                return None
            except Exception as e:
                logger.error(f"An unexpected error occurred during token refresh for {user.username}: {e}")
                return None
            
    async def _get_valid_twitter_data(self, user: UserInDB) -> Optional[UserTwitterData]:
        """
        Memastikan user memiliki data Twitter yang valid dan token yang aktif.
        Jika token kadaluarsa, fungsi ini akan mencoba me-refresh-nya.
        """
        if not user.twitter_data or not user.twitter_data.access_token:
            logger.warning(f"User {user.username} has no Twitter data.")
            return None
        
        # Cek apakah token sudah kadaluarsa (proaktif)
        # Beri sedikit buffer, misalnya 60 detik, untuk menghindari race condition
        is_expired = user.twitter_data.expires_at <= (datetime.now(timezone.utc) - timedelta(seconds=60))
        
        if is_expired:
            logger.info(f"Token for user {user.username} is expired. Refreshing...")
            return await self._refresh_and_save_token(user)
        
        return user.twitter_data

    async def _make_twitter_api_request(self, method: str, endpoint: str, user: UserInDB, params: Optional[dict] = None) -> Optional[dict]:
        """Helper untuk membuat request, sekarang menggunakan token yang sudah divalidasi."""
        
        # [PENYEMPURNAAN] Dapatkan data token yang valid (cek kadaluarsa/refresh)
        valid_twitter_data = await self._get_valid_twitter_data(user)
        if not valid_twitter_data:
            raise HTTPException(status_code=HttpStatus.HTTP_401_UNAUTHORIZED, detail="Could not get a valid Twitter token. Please reconnect your account.")
            
        decrypted_access_token = decrypt_data(valid_twitter_data.access_token)
        headers = {"Authorization": f"Bearer {decrypted_access_token}"}
        transport = httpx.AsyncHTTPTransport(retries=3)

        async with httpx.AsyncClient(transport=transport) as client:
            try:
                response = await client.request(
                    method=method, url=f"{TWITTER_API_BASE_URL}{endpoint}", headers=headers, params=params, timeout=10.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # Fallback jika refresh token gagal atau error lain
                if e.response.status_code == 429:
                    raise HTTPException(status_code=HttpStatus.HTTP_429_TOO_MANY_REQUESTS, detail="Twitter API rate limit reached. Please try again later.")
                logger.error(f"Twitter API error for user {user.username} on {endpoint}: {e.response.status_code} - {e.response.text}")
                # Melempar error agar pemanggil tahu ada masalah
                raise HTTPException(status_code=e.response.status_code, detail=f"Twitter API error: {e.response.text}")
            except Exception as e:
                logger.error(f"Unexpected error calling Twitter API: {e}", exc_info=True)
                raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while contacting Twitter.")
            

    async def check_if_user_follows(self, user: UserInDB, target_username: str) -> bool:
        if not user.twitter_data or not user.twitter_data.twitter_user_id:
            logger.warning(f"User {user.username} has no Twitter data for validation.")
            return False

        # [IMPROVEMENT] Bersihkan username dari karakter '@'
        sanitized_username = target_username.lstrip('@')

        # 1. Dapatkan ID dari target_username
        target_user_info = await self._make_twitter_api_request(
            "GET", f"/users/by/username/{sanitized_username}", user
        )
        if not target_user_info or "data" not in target_user_info:
            logger.error(f"Could not find Twitter user ID for username: {sanitized_username}")
            return False
            
        target_user_id = target_user_info["data"]["id"]
        source_user_id = user.twitter_data.twitter_user_id

        # [IMPROVEMENT] Cek jika user mencoba mem-follow diri sendiri
        if source_user_id == target_user_id:
            logger.info(f"User {user.username} tried to follow themself.")
            return False

        # 2. Iterasi melalui daftar following dengan pagination
        endpoint = f"/users/{source_user_id}/following"
        params = {"max_results": 100}
        pagination_token = None
        page_count = 0 # [IMPROVEMENT] Logging untuk jumlah halaman

        while True:
            page_count += 1
            current_params = params.copy() # [IMPROVEMENT] Gunakan copy untuk kebersihan params
            if pagination_token:
                current_params["pagination_token"] = pagination_token

            logger.debug(f"Checking page {page_count} of following list for user {source_user_id}...")
            response_data = await self._make_twitter_api_request("GET", endpoint, user, params=current_params)

            if not response_data or "data" not in response_data:
                logger.info(f"Validation fail: No 'following' data returned for user {source_user_id} on page {page_count}.")
                return False

            if any(followed_user["id"] == target_user_id for followed_user in response_data["data"]):
                logger.info(f"Validation success: User {source_user_id} follows {target_user_id}. Found on page {page_count}.")
                return True

            meta = response_data.get("meta", {})
            pagination_token = meta.get("next_token")

            if not pagination_token:
                logger.info(f"Validation fail: User {source_user_id} does not follow {target_user_id} after checking all {page_count} pages.")
                return False

    async def check_if_user_liked_tweet(self, user: UserInDB, tweet_id: str) -> bool:
        """Memvalidasi apakah seorang user me-like sebuah tweet."""
        # Logika ini bisa diperluas dengan pagination seperti `check_if_user_follows` jika diperlukan
        if not user.twitter_data or not user.twitter_data.twitter_user_id: return False
        
        endpoint = f"/users/{user.twitter_data.twitter_user_id}/liked_tweets"
        response_data = await self._make_twitter_api_request("GET", endpoint, user, params={"max_results": 100})
        
        if not response_data or "data" not in response_data: return False
        return any(tweet["id"] == tweet_id for tweet in response_data["data"])

    async def check_if_user_retweeted_tweet(self, user: UserInDB, tweet_id: str) -> bool:
        """Memvalidasi apakah seorang user me-retweet sebuah tweet."""
        # Logika ini bisa diperluas dengan pagination seperti `check_if_user_follows` jika diperlukan
        if not user.twitter_data or not user.twitter_data.twitter_user_id: return False

        endpoint = f"/tweets/{tweet_id}/retweeted_by"
        response_data = await self._make_twitter_api_request("GET", endpoint, user, params={"max_results": 100})
        
        if not response_data or "data" not in response_data: return False
        return any(rt_user["id"] == user.twitter_data.twitter_user_id for rt_user in response_data["data"])

twitter_service = TwitterService()
# ===========================================================================
# File: app/api/deps.py
# ===========================================================================
from typing import AsyncGenerator, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import Depends, HTTPException, status as HttpStatus
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError # BaseModel tidak dipakai di sini

from app.db.session import get_db
from app.core.config import settings, logger
from app.models.user import UserInDB
from app.crud.crud_user import crud_user
from app.api.v1.schemas.token import TokenData as TokenDataSchema # Skema untuk validasi payload token
from app.models.base import PyObjectId

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/connect")

async def get_current_active_user(
    db: AsyncIOMotorDatabase = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> UserInDB: # Mengembalikan UserInDB, bukan UserPublic
    credentials_exception = HTTPException(
        status_code=HttpStatus.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        # Validasi payload menggunakan skema TokenData
        token_data = TokenDataSchema.model_validate(payload) # Pydantic v2
        
        if token_data.user_id is None or token_data.sub is None: # sub adalah wallet_address
            logger.warning(f"JWT payload missing user_id or sub. Payload: {payload}")
            raise credentials_exception
        
    except JWTError as e:
        logger.error(f"JWT Error during token decode: {e}", exc_info=True)
        raise credentials_exception
    except ValidationError as e: # Error dari Pydantic jika payload tidak sesuai TokenDataSchema
        logger.error(f"JWT Payload Validation Error (TokenDataSchema): {e}", exc_info=True)
        raise credentials_exception
        
    try:
        user_object_id = PyObjectId(token_data.user_id) # Konversi string ID ke ObjectId
    except ValueError: # Error jika user_id bukan string ObjectId yang valid
        logger.error(f"Invalid ObjectId string in JWT user_id: {token_data.user_id}")
        raise credentials_exception

    user = await crud_user.get(db, id=user_object_id) # Ambil user dari DB berdasarkan ID
    
    if user is None:
        logger.warning(f"User with ID {token_data.user_id} not found in DB (from JWT).")
        raise credentials_exception
    if not user.is_active:
        logger.warning(f"User {user.username} (ID: {token_data.user_id}) is inactive. Login denied.")
        raise HTTPException(status_code=HttpStatus.HTTP_400_BAD_REQUEST, detail="Inactive user")
    
    # Verifikasi tambahan: pastikan wallet address di token (sub) masih cocok dengan yang di DB
    if user.walletAddress.lower() != token_data.sub.lower():
        logger.error(
            f"Wallet address mismatch for user ID {token_data.user_id}. "
            f"DB: {user.walletAddress}, JWT sub: {token_data.sub}"
        )
        raise credentials_exception
        
    return user
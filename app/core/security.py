# ===========================================================================
# File: app/core/security.py (MODIFIKASI)
# ===========================================================================
from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from eth_account.messages import encode_defunct
from eth_account import Account # Import Account dari eth_account
from web3 import Web3 # Web3 masih dipakai untuk is_address

from app.core.config import settings, logger

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(subject: Union[str, Any], user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject), "user_id": str(user_id), "iat": datetime.now(timezone.utc)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_wallet_signature(wallet_address: str, original_message: str, signature: str) -> bool:
    """
    Memverifikasi signature dari sebuah pesan menggunakan alamat wallet.
    Mengembalikan True jika signature valid dan berasal dari wallet_address yang diklaim.
    """
    try:
        # Web3.is_address adalah static method, jadi bisa dipanggil langsung
        if not Web3.is_address(wallet_address):
            logger.warning(f"Attempt to verify signature with invalid wallet address format: {wallet_address}")
            return False
            
        message_hash_obj = encode_defunct(text=original_message)
        
        # Menggunakan Account.recover_message untuk memulihkan alamat dari signature
        # Tidak perlu instance Web3 (w3) untuk ini.
        recovered_address = Account.recover_message(message_hash_obj, signature=signature)
        
        is_valid = recovered_address.lower() == wallet_address.lower()
        if not is_valid:
            logger.warning(
                f"Signature verification failed. Expected: {wallet_address.lower()}, Recovered: {recovered_address.lower()}"
            )
        return is_valid
    except Exception as e:
        # Tangkap error yang lebih spesifik jika memungkinkan, misal dari eth_keys.exceptions.BadSignature
        logger.error(f"Error during signature verification for {wallet_address}: {e}", exc_info=True)
        return False
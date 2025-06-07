# ===========================================================================
# File: app/api/v1/schemas/token.py (MODIFIKASI: TokenData field 'sub' harus ada)
# ===========================================================================
from pydantic import BaseModel
from typing import Optional
from app.api.v1.schemas.user import UserPublic

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic

class TokenData(BaseModel): # Untuk validasi payload JWT internal
    sub: str # Subject dari JWT, akan berisi wallet_address (dibuat wajib)
    user_id: str
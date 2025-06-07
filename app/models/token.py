# ===========================================================================
# File: app/models/token.py (MODIFIKASI: TokenPayload field 'sub' harus ada)
# ===========================================================================
from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenPayload(BaseModel): # Data yang disimpan di dalam JWT
    sub: str # Subject (wallet_address), sekarang wajib
    user_id: str # ObjectId user sebagai string, sekarang wajib
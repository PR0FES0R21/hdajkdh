# ===========================================================================
# File: app/api/v1/schemas/auth.py (MODIFIKASI: Pastikan TwitterOAuthInitiateResponse benar)
# ===========================================================================
from pydantic import BaseModel, Field, StringConstraints, HttpUrl as PydanticHttpUrl
from typing import Annotated, Optional

EthAddress = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, 
        to_lower=True, 
        pattern=r"^0x[a-fA-F0-9]{40}$"
    ),
    Field(description="Alamat wallet pengguna Ethereum (Format: 0x... 40 karakter hex)")
]

HexSignature = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, 
        pattern=r"^0x[a-fA-F0-9]{130}$"
    ),
    Field(description="Signature dari 'message' (Format: 0x... 130 karakter hex, 65 bytes)")
]

class ChallengeMessageResponse(BaseModel):
    messageToSign: str
    nonce: str

class WalletConnectRequest(BaseModel):
    walletAddress: EthAddress
    message: Annotated[str, Field(description="Pesan original yang ditandatangani (harus mengandung nonce)")]
    signature: HexSignature
    nonce: Annotated[
        str, 
        Field(
            min_length=32, 
            max_length=32,
            description="Nonce yang diterima dari /challenge (32 karakter hex string)"
        )
    ]
    referral_code_input: Optional[str] = Field(
        default=None, 
        description="Kode referral yang diinput pengguna (opsional)", 
        min_length=3, 
        max_length=20 
    )

# Skema untuk respons inisiasi OAuth X
class TwitterOAuthInitiateResponse(BaseModel):
    redirect_url: PydanticHttpUrl # Pastikan field ini bernama 'redirect_url'

# Skema untuk respons callback OAuth X
class TwitterOAuthCallbackResponse(BaseModel):
    message: str
    # user: Optional[UserPublic] = None # Opsional

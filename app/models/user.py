# ===========================================================================
# File: app/models/user.py (MODIFIKASI: Tambahkan field last_daily_checkin)
# ===========================================================================
from pydantic import BaseModel, Field, EmailStr, HttpUrl as PydanticHttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from app.models.base import PyObjectId
from app.core.config import settings
from app.utils.helpers import generate_stardate
import random

class UserProfile(BaseModel):
    commanderName: str
    rankBadgeUrl: Optional[PydanticHttpUrl] = None
    rankProgressPercent: float = Field(default=0.0, ge=0, le=100)
    nextRank: Optional[str] = None

    model_config = {
        "json_encoders": {
            PydanticHttpUrl: lambda v: str(v) if v else None
        },
        "arbitrary_types_allowed": True,
        "from_attributes": True
    }


class UserSystemStatus(BaseModel):
    starDate: str = Field(default_factory=generate_stardate)
    signalStatus: str = Field(default="Optimal")
    networkLoadPercent: float = Field(default_factory=lambda: round(random.uniform(20.0, 60.0), 2))
    anomaliesResolved: int = Field(default=0, ge=0)

class UserTwitterData(BaseModel):
    twitter_user_id: str = Field(..., index=True, unique=True)
    twitter_username: str
    access_token: Optional[str] = Field(default=None, description="Encrypted Twitter OAuth 2.0 access token.")
    refresh_token: Optional[str] = Field(default=None, description="Encrypted Twitter OAuth 2.0 refresh token.")
    expires_in: Optional[int] = None
    expires_at: Optional[datetime] = None
    connected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserInDB(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    walletAddress: str = Field(..., min_length=42, max_length=42)
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = Field(default=None)
    
    rank: str = Field(default=settings.DEFAULT_RANK_OBSERVER)
    xp: int = Field(default=0, ge=0)
    
    cigarBalance: float = Field(default=0.0, ge=0)
    
    referralCode: Optional[str] = Field(default=None, min_length=6, max_length=10)
    referredBy: Optional[PyObjectId] = None
    alliesCount: int = Field(default=0, ge=0)

    profile: UserProfile
    systemStatus: UserSystemStatus = Field(default_factory=UserSystemStatus)
    
    twitter_data: Optional[UserTwitterData] = None

    hashed_password: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False

    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    lastLogin: Optional[datetime] = None
    
    # Field baru untuk melacak check-in harian
    last_daily_checkin: Optional[datetime] = None
    daily_checkin_streak: int = Field(default=0, ge=0)

    model_config = {
        "populate_by_name": True,
        "json_encoders": {
            PyObjectId: str, 
            datetime: lambda dt: dt.isoformat().replace("+00:00", "Z"),
            PydanticHttpUrl: lambda v: str(v) if v else None
        },
        "arbitrary_types_allowed": True,
        "validate_assignment": True,
        "from_attributes": True
    }
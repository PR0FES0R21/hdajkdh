# ===========================================================================
# File: app/api/v1/schemas/user.py (MODIFIKASI: Tambahkan twitter_data di UserPublic)
# ===========================================================================
from pydantic import BaseModel, EmailStr, Field, HttpUrl as PydanticHttpUrl
from typing import Optional, List
from datetime import datetime
from app.models.base import PyObjectId
from app.models.user import UserProfile as UserProfileModel, UserSystemStatus as UserSystemStatusModel, UserTwitterData as UserTwitterDataModel # Import UserTwitterDataModel

class UserCreate(BaseModel):
    walletAddress: str = Field(..., min_length=42, max_length=42)
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    profile: UserProfileModel
    systemStatus: Optional[UserSystemStatusModel] = None
    rank: Optional[str] = None
    referralCode: Optional[str] = None
    referredBy: Optional[PyObjectId] = None
    twitter_data: Optional[UserTwitterDataModel] = None # Tambahkan twitter_data

class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    profile: Optional[UserProfileModel] = None
    # twitter_data tidak diupdate oleh user secara langsung via endpoint ini

class UserPublic(BaseModel):
    id: PyObjectId = Field(alias="_id")
    walletAddress: str
    username: str
    email: Optional[EmailStr] = None
    rank: str
    xp: int
    referralCode: Optional[str] = None
    alliesCount: int
    profile: UserProfileModel
    systemStatus: UserSystemStatusModel
    twitter_data: Optional[UserTwitterDataModel] = None # Tambahkan twitter_data untuk info ke frontend
    lastLogin: Optional[datetime] = None
    createdAt: datetime
    
    model_config = {
        "populate_by_name": True,
        "json_encoders": {PyObjectId: str, datetime: lambda dt: dt.isoformat().replace("+00:00", "Z")},
        "arbitrary_types_allowed": True,
        "from_attributes": True
    }

class AllyInfo(BaseModel):
    id: PyObjectId = Field(alias="_id")
    username: str
    rank: str
    joinedAt: datetime

    model_config = {
        "populate_by_name": True,
        "json_encoders": {PyObjectId: str, datetime: lambda dt: dt.isoformat().replace("+00:00", "Z")},
        "arbitrary_types_allowed": True,
        "from_attributes": True
    }

class AlliesListResponse(BaseModel):
    totalAllies: int
    allies: List[AllyInfo]
    page: int
    limit: int
    totalPages: int
# ===========================================================================
# File: app/models/badge.py (BARU)
# ===========================================================================
from pydantic import BaseModel, Field, HttpUrl as PydanticHttpUrl
from typing import Optional
from datetime import datetime, timezone
from app.models.base import PyObjectId

class BadgeInDB(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    badgeId_str: str = Field(..., index=True, unique=True) # ID string unik, misal "telegram-join-master"
    name: str = Field(...)
    description: Optional[str] = None
    imageUrl: PydanticHttpUrl
    criteria: Optional[str] = None # Deskripsi bagaimana cara mendapatkan badge ini
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
        "json_encoders": {PyObjectId: str, datetime: lambda dt: dt.isoformat().replace("+00:00", "Z")},
        "arbitrary_types_allowed": True
    }

class UserBadgeLink(BaseModel): # Untuk koleksi user_badges
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    userId: PyObjectId = Field(..., index=True)
    badgeId: PyObjectId = Field(..., index=True) # Merujuk ke _id di BadgeInDB
    acquiredAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
        "json_encoders": {PyObjectId: str, datetime: lambda dt: dt.isoformat().replace("+00:00", "Z")},
        "arbitrary_types_allowed": True
    }
# ===========================================================================
# File: app/api/v1/schemas/badge.py (BARU)
# ===========================================================================
from pydantic import BaseModel, Field, HttpUrl as PydanticHttpUrl
from typing import Optional, List
from datetime import datetime
from app.models.base import PyObjectId # Menggunakan PyObjectId

class UserBadgeResponse(BaseModel): # Skema untuk menampilkan badge milik user
    id: PyObjectId = Field(alias="_id") # ID dari UserBadgeLink
    badge_doc_id: PyObjectId # ID dari dokumen BadgeInDB
    badgeId_str: str # ID string badge, misal "telegram-join-master"
    name: str
    imageUrl: PydanticHttpUrl
    description: Optional[str] = None
    acquiredAt: datetime

    model_config = {
        "populate_by_name": True,
        "json_encoders": {PyObjectId: str, datetime: lambda dt: dt.isoformat().replace("+00:00", "Z")},
        "arbitrary_types_allowed": True,
        "from_attributes": True # Memungkinkan dibuat dari objek UserBadgeLink + join BadgeInDB
    }

class UserBadgeListResponse(BaseModel):
    badges: List[UserBadgeResponse]
    total: int
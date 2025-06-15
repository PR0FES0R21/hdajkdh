# ===========================================================================
# File: app/models/mission.py (MODIFIKASI: Tambahkan requiredAllies dan tipe aksi baru)
# ===========================================================================
from pydantic import BaseModel, Field, HttpUrl as PydanticHttpUrl
from typing import Optional, List, Literal
from datetime import datetime, timezone
from app.models.base import PyObjectId

# Tambahkan "claim_if_eligible" untuk misi invite
MissionActionType = Literal["redirect_and_verify", "disabled", "completed", "oauth_connect", "claim_if_eligible"] 
MissionStatusType = Literal["available", "in_progress", "completed", "pending_verification", "failed"]
MissionCategoryType = Literal["connect", "interact", "contribute", "special"]

class MissionActionDetails(BaseModel):
    label: str 
    type: MissionActionType
    url: Optional[PydanticHttpUrl] = None
    icon: Optional[str] = None
    platform: Optional[str] = None

class RewardBadgeDetails(BaseModel):
    badge_id_str: str 
    name: str 
    imageUrl: PydanticHttpUrl

class MissionInDB(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    missionId_str: str = Field(..., index=True, unique=True)
    title: str = Field(...)
    description: str = Field(...)
    type: MissionCategoryType
    rewardXp: int = Field(..., ge=0)
    rewardBadge: Optional[RewardBadgeDetails] = None
    action: MissionActionDetails
    prerequisites: Optional[List[str]] = Field(default_factory=list)
    isActive: bool = True
    order: Optional[int] = None
    
    # Field baru untuk misi invite
    requiredAllies: Optional[int] = Field(default=None, description="Jumlah ally yang dibutuhkan untuk menyelesaikan misi ini.")

    targetTwitterUsername: Optional[str] = Field(default=None, description="Username target di Twitter (tanpa @) untuk misi follow.")
    targetTweetId: Optional[str] = Field(default=None, description="ID Tweet target untuk misi like atau retweet.")
    
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
        "json_encoders": {PyObjectId: str, datetime: lambda dt: dt.isoformat().replace("+00:00", "Z")},
        "arbitrary_types_allowed": True
    }

class CheckInInDB(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    userId: PyObjectId
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {
            PyObjectId: str,
            datetime: lambda dt: dt.isoformat().replace("+00:00", "Z"),
        },
        "from_attributes": True
    }

class UserMissionLink(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    userId: PyObjectId = Field(..., index=True)
    missionId: PyObjectId = Field(..., index=True)
    status: MissionStatusType = Field(default="available")
    completedAt: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "json_encoders": {PyObjectId: str, datetime: lambda dt: dt.isoformat().replace("+00:00", "Z")},
        "arbitrary_types_allowed": True
    }

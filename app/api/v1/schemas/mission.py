# ===========================================================================
# File: app/api/v1/schemas/mission.py (MODIFIKASI: Perbaiki nama field di MissionRewardBadgeResponse)
# ===========================================================================
from pydantic import BaseModel, Field, HttpUrl as PydanticHttpUrl
from typing import Optional, List, Dict, Any
from app.models.base import PyObjectId
from app.models.mission import MissionActionType, MissionStatusType, MissionCategoryType

# Skema untuk detail aksi di MissionDirectiveResponse
class MissionActionResponse(BaseModel):
    label: str
    type: MissionActionType
    url: Optional[PydanticHttpUrl] = None

# Skema untuk detail badge hadiah di MissionDirectiveResponse
class MissionRewardBadgeResponse(BaseModel):
    badge_id_str: str # FIX: Ubah nama field menjadi snake_case agar cocok dengan source model RewardBadgeDetails
    name: str
    imageUrl: PydanticHttpUrl

# Skema untuk respons daftar misi (Active Directives)
class MissionDirectiveResponse(BaseModel):
    id: PyObjectId = Field(alias="_id")
    missionId_str: str
    title: str
    description: str
    type: MissionCategoryType
    rewardXp: int
    rewardBadge: Optional[MissionRewardBadgeResponse] = None
    status: MissionStatusType
    action: MissionActionResponse
    
    currentProgress: Optional[int] = None
    requiredProgress: Optional[int] = None

    model_config = {
        "populate_by_name": True,
        "json_encoders": {PyObjectId: str, PydanticHttpUrl: str},
        "arbitrary_types_allowed": True,
        "from_attributes": True
    }

class MissionDirectivesListResponse(BaseModel):
    directives: List[MissionDirectiveResponse]

# Skema untuk respons ringkasan progres misi (Operation Status)
class MissionProgressSummaryResponse(BaseModel):
    completedMissions: int
    totalMissions: int
    activeSignals: int

# Skema untuk request penyelesaian misi
class MissionCompletionRequest(BaseModel):
    validation_data: Optional[Dict[str, Any]] = None

class MissionCompletionResponse(BaseModel):
    message: str
    xp_gained: Optional[int] = None
    badge_awarded: Optional[MissionRewardBadgeResponse] = None

# ===========================================================================
# File: app/models/checkin.py (BARU)
# ===========================================================================
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from app.models.base import PyObjectId

class CheckinRecord(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    userId: PyObjectId = Field(..., index=True)
    checkinAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    streak_day_number: int = Field(..., ge=1)

    model_config = {
        "populate_by_name": True,
        "json_encoders": {PyObjectId: str, datetime: lambda dt: dt.isoformat().replace("+00:00", "Z")},
        "arbitrary_types_allowed": True
    }
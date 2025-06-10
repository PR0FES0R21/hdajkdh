# ===========================================================================
# File: app/crud/crud_mission.py (BARU)
# ===========================================================================
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Dict, Any
from app.models.base import PyObjectId
from app.crud.base import CRUDBase
from app.models.mission import MissionInDB, CheckInInDB, UserMissionLink, MissionStatusType
from pydantic import BaseModel as PydanticBaseModel

class CRUDMission(CRUDBase[MissionInDB, PydanticBaseModel, PydanticBaseModel]):
    async def get_by_mission_id_str(self, db: AsyncIOMotorDatabase, *, mission_id_str: str) -> Optional[MissionInDB]:
        collection = await self.get_collection(db)
        doc = await collection.find_one({"missionId_str": mission_id_str})
        return MissionInDB.model_validate(doc) if doc else None

    async def get_active_missions(self, db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 100) -> List[MissionInDB]:
        return await self.get_multi(db, query={"isActive": True}, skip=skip, limit=limit, sort=[("order", 1), ("createdAt", 1)])

class CRUDUserMissionLink(CRUDBase[UserMissionLink, PydanticBaseModel, PydanticBaseModel]):
    async def get_by_user_and_mission(
        self, db: AsyncIOMotorDatabase, *, user_id: PyObjectId, mission_db_id: PyObjectId
    ) -> Optional[UserMissionLink]:
        collection = await self.get_collection(db)
        doc = await collection.find_one({"userId": user_id, "missionId": mission_db_id})
        return UserMissionLink.model_validate(doc) if doc else None

    async def get_missions_by_user_id(
        self, db: AsyncIOMotorDatabase, *, user_id: PyObjectId, status: Optional[MissionStatusType] = None
    ) -> List[UserMissionLink]:
        query: Dict[str, Any] = {"userId": user_id}
        if status:
            query["status"] = status
        return await self.get_multi(db, query=query, sort=[("assignedAt", -1)]) # Atau updatedAt jika ada

    async def count_user_missions_by_status(
        self, db: AsyncIOMotorDatabase, *, user_id: PyObjectId, status: MissionStatusType
    ) -> int:
        collection = await self.get_collection(db)
        return await collection.count_documents({"userId": user_id, "status": status})
    
class CRUDCheckin(CRUDBase[CheckInInDB, PydanticBaseModel, PydanticBaseModel]):
    async def get_checkin_by_user_id(
        self, db:AsyncIOMotorDatabase, *, user_id: PyObjectId, limit: int = 0
    ) -> Optional[CheckInInDB]:
        query = Dict[str, Any] = {"userId": user_id}
        return await self.get_multi(db, query=query, limit=limit, sort=[("timestamp", -1)])
    
    async def store_checkin_entry(
        self, db: AsyncIOMotorDatabase, *, user_id: PyObjectId, timestamp: str
    ) -> CheckInInDB:
        checkin_data_to_create_model = CheckInInDB (
            userId=user_id,
            timestamp=timestamp
        )
        return await super().create(db, obj_in=checkin_data_to_create_model)
    

crud_mission = CRUDMission(MissionInDB, "missions")
crud_user_mission_link = CRUDUserMissionLink(UserMissionLink, "user_missions")
crud_checkin = CRUDCheckin(CheckInInDB, "checkins")

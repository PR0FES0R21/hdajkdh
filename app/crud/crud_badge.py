# ===========================================================================
# File: app/crud/crud_badge.py (BARU)
# ===========================================================================
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List
from app.models.base import PyObjectId
from app.crud.base import CRUDBase
from app.models.badge import BadgeInDB, UserBadgeLink
# Skema untuk create/update bisa dibuat jika ada admin panel, untuk sekarang CRUD dasar saja
from pydantic import BaseModel as PydanticBaseModel # Placeholder

class CRUDUserBadgeLink(CRUDBase[UserBadgeLink, PydanticBaseModel, PydanticBaseModel]):
    async def get_by_user_and_badge(
        self, db: AsyncIOMotorDatabase, *, user_id: PyObjectId, badge_db_id: PyObjectId
    ) -> Optional[UserBadgeLink]:
        collection = await self.get_collection(db)
        doc = await collection.find_one({"userId": user_id, "badgeId": badge_db_id})
        return UserBadgeLink.model_validate(doc) if doc else None

    async def get_badges_by_user_id(
        self, db: AsyncIOMotorDatabase, *, user_id: PyObjectId
    ) -> List[UserBadgeLink]:
        return await self.get_multi(db, query={"userId": user_id}, sort=[("acquiredAt", -1)])

class CRUDBadge(CRUDBase[BadgeInDB, PydanticBaseModel, PydanticBaseModel]):
    async def get_by_badge_id_str(self, db: AsyncIOMotorDatabase, *, badge_id_str: str) -> Optional[BadgeInDB]:
        collection = await self.get_collection(db)
        doc = await collection.find_one({"badgeId_str": badge_id_str})
        return BadgeInDB.model_validate(doc) if doc else None

crud_badge = CRUDBadge(BadgeInDB, "badges")
crud_user_badge_link = CRUDUserBadgeLink(UserBadgeLink, "user_badges")

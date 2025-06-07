# ===========================================================================
# File: app/services/mission_service.py (MODIFIKASI: Perbaiki Pydantic Validation)
# ===========================================================================
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status as HttpStatus

from app.core.config import settings, logger
from app.crud.crud_mission import crud_mission, crud_user_mission_link
from app.crud.crud_user import crud_user
from app.crud.crud_badge import crud_badge, crud_user_badge_link
from app.models.user import UserInDB
from app.models.mission import MissionInDB, UserMissionLink, MissionStatusType
from app.models.badge import BadgeInDB, UserBadgeLink
from app.api.v1.schemas.mission import MissionDirectiveResponse, MissionProgressSummaryResponse, MissionCompletionResponse, MissionActionResponse, MissionRewardBadgeResponse
from app.api.v1.schemas.badge import UserBadgeResponse
from app.models.base import PyObjectId
from app.services.user_service import user_service
from datetime import datetime, timezone, timedelta

class MissionService:
    async def get_directives_for_user(self, db: AsyncIOMotorDatabase, user: UserInDB) -> List[MissionDirectiveResponse]:
        active_missions_db = await crud_mission.get_active_missions(db, limit=100)
        user_missions_links = await crud_user_mission_link.get_missions_by_user_id(db, user_id=user.id)
        
        user_mission_status_map: Dict[PyObjectId, MissionStatusType] = {
            link.missionId: link.status for link in user_missions_links
        }

        directives: List[MissionDirectiveResponse] = []
        for mission_db in active_missions_db:
            status: MissionStatusType = "available"
            current_progress: Optional[int] = None
            required_progress: Optional[int] = None
            has_been_claimed = user_mission_status_map.get(mission_db.id) == "completed"
            
            if has_been_claimed:
                status = "completed"
            elif mission_db.requiredAllies is not None and mission_db.requiredAllies > 0:
                current_progress = user.alliesCount
                required_progress = mission_db.requiredAllies
                if current_progress >= required_progress:
                    status = "available"
                else:
                    status = "in_progress"
            elif mission_db.missionId_str == "daily-checkin":
                if user.last_daily_checkin and user.last_daily_checkin.date() == datetime.now(timezone.utc).date():
                    status = "completed"
                else:
                    status = "available"
            else:
                status = user_mission_status_map.get(mission_db.id, "available")

            reward_badge_resp = None
            if mission_db.rewardBadge:
                # FIX: Ubah objek menjadi dict sebelum validasi
                reward_badge_resp = MissionRewardBadgeResponse.model_validate(mission_db.rewardBadge.model_dump())
            
            # FIX: Ubah objek menjadi dict sebelum validasi
            action_resp = MissionActionResponse.model_validate(mission_db.action.model_dump())

            directives.append(
                MissionDirectiveResponse(
                    id=mission_db.id,
                    missionId_str=mission_db.missionId_str,
                    title=mission_db.title,
                    description=mission_db.description,
                    type=mission_db.type,
                    rewardXp=mission_db.rewardXp,
                    rewardBadge=reward_badge_resp,
                    status=status,
                    action=action_resp,
                    currentProgress=current_progress,
                    requiredProgress=required_progress
                )
            )
        return directives

    async def get_user_mission_progress_summary(self, db: AsyncIOMotorDatabase, user: UserInDB) -> MissionProgressSummaryResponse:
        active_missions_count = await db["missions"].count_documents({"isActive": True})
        
        completed_non_daily_missions_count = await crud_user_mission_link.count_user_missions_by_status(
            db, user_id=user.id, status="completed"
        )
        
        return MissionProgressSummaryResponse(
            completedMissions=completed_non_daily_missions_count,
            totalMissions=active_missions_count,
            activeSignals=completed_non_daily_missions_count 
        )

    async def get_user_badges(self, db: AsyncIOMotorDatabase, user: UserInDB) -> List[UserBadgeResponse]:
        user_badge_links = await crud_user_badge_link.get_badges_by_user_id(db, user_id=user.id)
        badges_resp: List[UserBadgeResponse] = []
        for link in user_badge_links:
            badge_doc = await crud_badge.get(db, id=link.badgeId)
            if badge_doc:
                badges_resp.append(
                    UserBadgeResponse(
                        id=link.id,
                        badge_doc_id=badge_doc.id,
                        badgeId_str=badge_doc.badgeId_str,
                        name=badge_doc.name,
                        imageUrl=badge_doc.imageUrl,
                        description=badge_doc.description,
                        acquiredAt=link.acquiredAt
                    )
                )
        return badges_resp

    async def process_mission_completion(
        self, db: AsyncIOMotorDatabase, user: UserInDB, mission_id_str_to_complete: str, completion_data: Optional[Dict[str, Any]] = None
    ) -> MissionCompletionResponse:
        logger.info(f"User {user.username} attempting to complete mission: {mission_id_str_to_complete}")

        mission_to_complete = await crud_mission.get_by_mission_id_str(db, mission_id_str=mission_id_str_to_complete)
        if not mission_to_complete or not mission_to_complete.isActive:
            logger.warning(f"Mission {mission_id_str_to_complete} not found or not active for user {user.username}.")
            raise HTTPException(status_code=HttpStatus.HTTP_404_NOT_FOUND, detail="Misi tidak ditemukan atau tidak aktif.")
        
        user_mission_link = await crud_user_mission_link.get_by_user_and_mission(
            db, user_id=user.id, mission_db_id=mission_to_complete.id
        )
        if user_mission_link and user_mission_link.status == "completed":
            logger.info(f"Mission {mission_id_str_to_complete} already completed by user {user.username}.")
            return MissionCompletionResponse(message="Misi sudah pernah diselesaikan.")

        if mission_id_str_to_complete == "daily-checkin":
            return await self._process_daily_checkin(db, user, mission_to_complete)
        
        if mission_to_complete.requiredAllies is not None and mission_to_complete.requiredAllies > 0:
            return await self._process_invite_mission_claim(db, user, mission_to_complete)
        
        return await self._process_standard_mission(db, user, mission_to_complete, user_mission_link)


    async def _process_daily_checkin(self, db: AsyncIOMotorDatabase, user: UserInDB, mission: MissionInDB) -> MissionCompletionResponse:
        now_utc = datetime.now(timezone.utc)
        if user.last_daily_checkin and user.last_daily_checkin.date() == now_utc.date():
            logger.warning(f"User {user.username} already completed daily check-in today.")
            raise HTTPException(status_code=HttpStatus.HTTP_400_BAD_REQUEST, detail="Anda sudah melakukan check-in hari ini.")
        
        await crud_user.update(db, db_obj_id=user.id, obj_in={"last_daily_checkin": now_utc})
        logger.info(f"User {user.username} daily check-in timestamp updated.")
        
        return await self._grant_rewards(db, user, mission)


    async def _process_invite_mission_claim(self, db: AsyncIOMotorDatabase, user: UserInDB, mission: MissionInDB) -> MissionCompletionResponse:
        required_allies = mission.requiredAllies or 0
        if user.alliesCount < required_allies:
            logger.warning(f"User {user.username} tried to claim invite mission '{mission.title}' but has {user.alliesCount}/{required_allies} allies.")
            raise HTTPException(status_code=HttpStatus.HTTP_400_BAD_REQUEST, detail=f"Target undangan ({required_allies} allies) belum tercapai.")

        logger.info(f"User {user.username} is eligible to claim invite mission '{mission.title}'.")
        await self._mark_mission_as_completed(db, user.id, mission.id)
        return await self._grant_rewards(db, user, mission)


    async def _process_standard_mission(self, db: AsyncIOMotorDatabase, user: UserInDB, mission: MissionInDB, link: Optional[UserMissionLink]) -> MissionCompletionResponse:
        # TODO: Implementasi validasi penyelesaian misi yang sebenarnya di sini
        is_completion_valid = True 
        if not is_completion_valid:
            raise HTTPException(status_code=HttpStatus.HTTP_400_BAD_REQUEST, detail="Verifikasi penyelesaian misi gagal.")
        
        await self._mark_mission_as_completed(db, user.id, mission.id, existing_link=link)
        return await self._grant_rewards(db, user, mission)


    async def _mark_mission_as_completed(self, db: AsyncIOMotorDatabase, user_id: PyObjectId, mission_id: PyObjectId, existing_link: Optional[UserMissionLink] = None):
        if existing_link:
            await crud_user_mission_link.update(
                db, db_obj_id=existing_link.id, 
                obj_in={"status": "completed", "completedAt": datetime.now(timezone.utc)}
            )
        else:
            new_link_data = UserMissionLink(
                userId=user_id, 
                missionId=mission_id, 
                status="completed",
                completedAt=datetime.now(timezone.utc)
            )
            await crud_user_mission_link.create(db, obj_in=new_link_data)
        logger.info(f"Mission {mission_id} marked as completed for user {user_id}.")


    async def _grant_rewards(self, db: AsyncIOMotorDatabase, user: UserInDB, mission: MissionInDB) -> MissionCompletionResponse:
        xp_gained = 0
        if mission.rewardXp > 0:
            await user_service.grant_xp_and_manage_rank(db, user_id=user.id, xp_to_add=mission.rewardXp)
            xp_gained = mission.rewardXp
            logger.info(f"Granted {xp_gained} XP to user {user.username} for mission '{mission.title}'.")
        
        badge_awarded_resp = None
        if mission.rewardBadge:
            badge_def = await crud_badge.get_by_badge_id_str(db, badge_id_str=mission.rewardBadge.badge_id_str)
            if badge_def:
                existing_link = await crud_user_badge_link.get_by_user_and_badge(db, user_id=user.id, badge_db_id=badge_def.id)
                if not existing_link:
                    await crud_user_badge_link.create(db, obj_in=UserBadgeLink(userId=user.id, badgeId=badge_def.id))
                    badge_awarded_resp = MissionRewardBadgeResponse.model_validate(badge_def.model_dump()) # Gunakan model_dump()
                    logger.info(f"Awarded badge '{badge_def.name}' to user {user.username}.")
            else:
                logger.error(f"Badge definition not found for badge_id_str: {mission.rewardBadge.badge_id_str}")

        return MissionCompletionResponse(
            message=f"Misi '{mission.title}' berhasil diselesaikan!",
            xp_gained=xp_gained if xp_gained > 0 else None,
            badge_awarded=badge_awarded_resp
        )

mission_service = MissionService()
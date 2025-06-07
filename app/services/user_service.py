# ===========================================================================
# File: app/services/user_service.py (UPDATE SESUAI KODE DARI USER)
# ===========================================================================
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Any, Dict
from app.crud.crud_user import crud_user
from app.models.user import UserInDB, UserProfile as UserProfileModel
from app.api.v1.schemas.user import UserUpdate as UserUpdateSchema, UserPublic, AllyInfo, AlliesListResponse
from app.models.base import PyObjectId
from app.core.config import settings, logger
from fastapi import HTTPException, status as HttpStatus
from pydantic import HttpUrl as PydanticHttpUrl
import math

class UserService:
    async def get_user_by_id_public(self, db: AsyncIOMotorDatabase, user_id: PyObjectId) -> Optional[UserPublic]:
        user_doc = await crud_user.get(db, id=user_id)
        return UserPublic.model_validate(user_doc) if user_doc else None

    async def get_user_by_wallet_public(self, db: AsyncIOMotorDatabase, wallet_address: str) -> Optional[UserPublic]:
        user_doc = await crud_user.get_by_wallet_address(db, wallet_address=wallet_address)
        return UserPublic.model_validate(user_doc) if user_doc else None

    def _calculate_rank_details_for_profile(self, current_rank: str, current_xp: int) -> Dict[str, Any]:
        rank_details_for_profile: Dict[str, Any] = {
            "rankBadgeUrl": None,
            "rankProgressPercent": 0.0,
            "nextRank": None
        }
        try:
            current_rank_index = settings.RANK_ORDER.index(current_rank)
        except ValueError:
            logger.error(f"Rank '{current_rank}' not found in RANK_ORDER. Defaulting calculation using Observer.")
            current_rank_for_calc = settings.DEFAULT_RANK_OBSERVER
            current_rank_index = settings.RANK_ORDER.index(current_rank_for_calc)
        else:
            current_rank_for_calc = current_rank

        if 0 <= current_rank_index < len(settings.RANK_ORDER) - 1:
            rank_details_for_profile["nextRank"] = settings.RANK_ORDER[current_rank_index + 1]
        else:
            rank_details_for_profile["nextRank"] = None
            rank_details_for_profile["rankProgressPercent"] = 100.0 if current_rank_index >=0 else 0.0

        if rank_details_for_profile["nextRank"]:
            current_rank_xp_threshold = settings.RANK_THRESHOLDS.get(current_rank_for_calc, 0)
            next_rank_xp_threshold = settings.RANK_THRESHOLDS.get(rank_details_for_profile["nextRank"], float('inf'))
            
            xp_needed_for_next_rank = next_rank_xp_threshold - current_rank_xp_threshold
            xp_progress_in_current_rank = current_xp - current_rank_xp_threshold

            if xp_needed_for_next_rank > 0:
                rank_details_for_profile["rankProgressPercent"] = min(100.0, max(0.0, (xp_progress_in_current_rank / xp_needed_for_next_rank) * 100))
            else:
                rank_details_for_profile["rankProgressPercent"] = 100.0 if current_xp >= next_rank_xp_threshold else 0.0
        
        rank_badge_map = {
            "Observer": "https://placehold.co/64x64/333/FFF?text=OBS", "Ally": "https://placehold.co/64x64/555/FFF?text=ALY",
            "Field Agent": "https://placehold.co/64x64/777/FFF?text=FAG", "Strategist": "https://placehold.co/64x64/999/FFF?text=STR",
            "Commander": "https://placehold.co/64x64/BBB/000?text=CMD", "Overseer": "https://placehold.co/64x64/DDD/000?text=OVR",
        }
        badge_url_str = rank_badge_map.get(current_rank_for_calc)
        if badge_url_str:
            try:
                rank_details_for_profile["rankBadgeUrl"] = PydanticHttpUrl(badge_url_str)
            except Exception:
                rank_details_for_profile["rankBadgeUrl"] = None
        
        rank_details_for_profile["rankProgressPercent"] = round(rank_details_for_profile["rankProgressPercent"], 2)
        return rank_details_for_profile

    async def prepare_initial_user_profile(self, commander_name: str) -> UserProfileModel:
        initial_rank = settings.DEFAULT_RANK_OBSERVER
        initial_xp = 0
        rank_calc_details = self._calculate_rank_details_for_profile(current_rank=initial_rank, current_xp=initial_xp)
        
        return UserProfileModel(
            commanderName=commander_name,
            rankBadgeUrl=rank_calc_details["rankBadgeUrl"],
            rankProgressPercent=rank_calc_details["rankProgressPercent"],
            nextRank=rank_calc_details["nextRank"]
        )

    async def update_user_rank_profile_details(
        self, db: AsyncIOMotorDatabase, user: UserInDB
    ) -> UserInDB:
        if not user.profile:
            logger.error(f"User {user.username} does not have a profile. Initializing.")
            user.profile = await self.prepare_initial_user_profile(commander_name=user.username)

        rank_calc_details = self._calculate_rank_details_for_profile(current_rank=user.rank, current_xp=user.xp)
        
        profile_updates_for_db: Dict[str, Any] = {}
        
        changed = False
        current_badge_url_str = str(getattr(user.profile, 'rankBadgeUrl', None)) if getattr(user.profile, 'rankBadgeUrl', None) else None
        new_badge_url_obj = rank_calc_details["rankBadgeUrl"]
        new_badge_url_str_for_compare = str(new_badge_url_obj) if new_badge_url_obj else None

        if current_badge_url_str != new_badge_url_str_for_compare:
            profile_updates_for_db["rankBadgeUrl"] = new_badge_url_obj
            changed = True
        if getattr(user.profile, 'rankProgressPercent', 0.0) != rank_calc_details["rankProgressPercent"]:
            profile_updates_for_db["rankProgressPercent"] = rank_calc_details["rankProgressPercent"]
            changed = True
        if getattr(user.profile, 'nextRank', None) != rank_calc_details["nextRank"]:
            profile_updates_for_db["nextRank"] = rank_calc_details["nextRank"]
        
        if changed:
            updated_profile_obj = user.profile.model_copy(update=profile_updates_for_db)
            
            updated_user_doc = await crud_user.update(db, db_obj_id=user.id, obj_in={"profile": updated_profile_obj})
            if not updated_user_doc:
                logger.error(f"Failed to update profile rank details for user {user.username}")
                return user
            logger.info(f"Profile rank details updated for user {user.username}: Rank {updated_user_doc.rank}, Next {updated_user_doc.profile.nextRank}, Progress {updated_user_doc.profile.rankProgressPercent}%")
            return updated_user_doc
        
        logger.debug(f"No change in profile rank details for user {user.username}. Skipping DB update for profile.")
        return user

    async def update_user_profile(
        self, db: AsyncIOMotorDatabase, user_id: PyObjectId, profile_update_data: UserUpdateSchema
    ) -> Optional[UserPublic]:
        current_user = await crud_user.get(db, id=user_id)
        if not current_user:
            raise HTTPException(status_code=HttpStatus.HTTP_404_NOT_FOUND, detail="User tidak ditemukan.")

        update_dict = profile_update_data.model_dump(exclude_unset=True)
        
        if not update_dict:
            return UserPublic.model_validate(current_user)

        if "username" in update_dict and update_dict["username"] != current_user.username:
            existing_user_with_username = await crud_user.get_by_username(db, username=update_dict["username"])
            if existing_user_with_username and existing_user_with_username.id != user_id:
                raise HTTPException(status_code=HttpStatus.HTTP_400_BAD_REQUEST, detail="Username sudah digunakan oleh pengguna lain.")
        
        if "email" in update_dict and update_dict["email"] and update_dict["email"] != current_user.email:
            if update_dict["email"]:
                existing_user_with_email = await crud_user.get_by_email(db, email=update_dict["email"])
                if existing_user_with_email and existing_user_with_email.id != user_id:
                    raise HTTPException(status_code=HttpStatus.HTTP_400_BAD_REQUEST, detail="Email sudah digunakan oleh pengguna lain.")

        if "profile" in update_dict and update_dict["profile"] is not None:
            current_profile_data = current_user.profile.model_dump()
            profile_update_payload = update_dict["profile"]
            
            profile_payload_dict: Dict[str, Any]
            if isinstance(profile_update_payload, UserProfileModel):
                profile_payload_dict = profile_update_payload.model_dump(exclude_unset=True)
            elif isinstance(profile_update_payload, dict):
                profile_payload_dict = profile_update_payload
            else:
                profile_payload_dict = {}

            for key, value in profile_payload_dict.items():
                if key in current_profile_data:
                    current_profile_data[key] = value
            update_dict["profile"] = UserProfileModel.model_validate(current_profile_data).model_dump(mode='json')


        updated_user_doc = await crud_user.update(db, db_obj_id=user_id, obj_in=update_dict)
        if not updated_user_doc:
            logger.error(f"Update profile failed for user ID {user_id} despite user existence.")
            raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal memperbarui profil pengguna.")
        
        final_updated_user = await self.update_user_rank_profile_details(db, user=updated_user_doc)
        return UserPublic.model_validate(final_updated_user)


    async def grant_xp_and_manage_rank(
        self, db: AsyncIOMotorDatabase, user_id: PyObjectId, xp_to_add: int
    ) -> Optional[UserPublic]:
        """
        MODIFIKASI: Alur yang lebih jelas untuk update XP dan detail profil.
        """
        if xp_to_add <= 0:
            logger.info(f"Attempt to add non-positive XP ({xp_to_add}) to user {user_id}. No change.")
            user_doc = await crud_user.get(db, id=user_id)
            return UserPublic.model_validate(user_doc) if user_doc else None

        logger.info(f"Granting {xp_to_add} XP to user {user_id}.")
        
        # 1. Panggil CRUD yang HANYA update XP dan field 'rank' (string)
        user_after_xp_rank_update = await crud_user.add_xp_and_update_rank(db, user_id=user_id, xp_to_add=xp_to_add)
        
        if not user_after_xp_rank_update:
            logger.error(f"Failed to add XP or update rank string for user {user_id}.")
            return None
        
        # 2. SELALU panggil update_user_rank_profile_details untuk menghitung ulang
        #    dan menyimpan rankProgressPercent, nextRank, dan rankBadgeUrl yang baru.
        user_with_full_profile_update = await self.update_user_rank_profile_details(db, user=user_after_xp_rank_update)

        if not user_with_full_profile_update:
             logger.error(f"Failed to update profile details after XP grant for user {user_id}.")
             # Kembalikan user dengan XP/rank terupdate saja jika update detail profile gagal
             return UserPublic.model_validate(user_after_xp_rank_update) 

        return UserPublic.model_validate(user_with_full_profile_update)

    async def get_user_allies_list(
        self, db: AsyncIOMotorDatabase, current_user: UserInDB, page: int = 1, limit: int = 10
    ) -> AlliesListResponse:
        """
        Mengambil daftar pengguna yang telah direferensikan oleh pengguna saat ini,
        beserta informasi paginasi.
        """
        if page < 1: page = 1
        if limit < 1: limit = 1
        if limit > 100: limit = 100 # Batasi limit maksimum

        skip = (page - 1) * limit
        
        referred_users_docs = await crud_user.get_referred_users(
            db, referrer_id=current_user.id, skip=skip, limit=limit
        )
        
        total_allies = current_user.alliesCount 

        allies_info_list: List[AllyInfo] = []
        for user_doc in referred_users_docs:
            allies_info_list.append(
                AllyInfo(
                    id=user_doc.id,
                    username=user_doc.username,
                    rank=user_doc.rank,
                    joinedAt=user_doc.createdAt
                )
            )
            
        total_pages = math.ceil(total_allies / limit) if limit > 0 else 0
        if total_pages == 0 and total_allies > 0 : total_pages = 1

        return AlliesListResponse(
            totalAllies=total_allies,
            allies=allies_info_list,
            page=page,
            limit=limit,
            totalPages=total_pages
        )

user_service = UserService()
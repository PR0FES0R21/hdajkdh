# ===========================================================================
# File: app/crud/crud_user.py (MODIFIKASI: Fungsi update data Twitter)
# ===========================================================================
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List, Dict, Any
from app.models.base import PyObjectId

from app.crud.base import CRUDBase
from app.models.user import UserInDB, UserProfile as UserProfileModel, UserSystemStatus as UserSystemStatusModel, UserTwitterData # Import UserTwitterData
from app.api.v1.schemas.user import UserCreate as UserCreateSchemaApi, UserUpdate as UserUpdateSchemaApi
from app.core.config import settings, logger
from app.utils.helpers import generate_sci_fi_username, generate_random_numeric_suffix, generate_unique_referral_code
from datetime import datetime, timezone

class CRUDUser(CRUDBase[UserInDB, UserCreateSchemaApi, UserUpdateSchemaApi]):
    # ... (get_by_wallet_address, get_by_username, get_by_referral_code, get_referred_users, count_referred_users sama) ...
    async def get_by_wallet_address(self, db: AsyncIOMotorDatabase, *, wallet_address: str) -> Optional[UserInDB]:
        collection = await self.get_collection(db)
        logger.debug(f"CRUDUser: Getting user by wallet_address: {wallet_address.lower()}")
        doc = await collection.find_one({"walletAddress": wallet_address.lower()})
        return UserInDB.model_validate(doc) if doc else None

    async def get_by_username(self, db: AsyncIOMotorDatabase, *, username: str) -> Optional[UserInDB]:
        collection = await self.get_collection(db)
        logger.debug(f"CRUDUser: Getting user by username (case-insensitive): {username}")
        doc = await collection.find_one({"username": {"$regex": f"^{username}$", "$options": "i"}})
        return UserInDB.model_validate(doc) if doc else None
    
    async def get_by_referral_code(self, db: AsyncIOMotorDatabase, *, referral_code: str) -> Optional[UserInDB]:
        collection = await self.get_collection(db)
        logger.debug(f"CRUDUser: Getting user by referral_code: {referral_code}")
        doc = await collection.find_one({"referralCode": referral_code})
        return UserInDB.model_validate(doc) if doc else None

    async def get_referred_users(
        self, db: AsyncIOMotorDatabase, *, referrer_id: PyObjectId, skip: int = 0, limit: int = 10
    ) -> List[UserInDB]:
        logger.debug(f"CRUDUser: Getting referred users for referrer_id: {referrer_id}, skip: {skip}, limit: {limit}")
        return await self.get_multi(db, query={"referredBy": referrer_id}, skip=skip, limit=limit, sort=[("createdAt", -1)])

    async def count_referred_users(self, db: AsyncIOMotorDatabase, *, referrer_id: PyObjectId) -> int:
        collection = await self.get_collection(db)
        count = await collection.count_documents({"referredBy": referrer_id})
        logger.debug(f"CRUDUser: Counted {count} referred users for referrer_id: {referrer_id}")
        return count

    async def create_new_user_with_complete_data(
        self, db: AsyncIOMotorDatabase, *, 
        wallet_address: str, 
        username: str,
        profile: UserProfileModel,
        system_status: UserSystemStatusModel,
        referral_code: str,
        referred_by_user_id: Optional[PyObjectId] = None,
        twitter_data: Optional[UserTwitterData] = None # Tambahkan twitter_data
    ) -> UserInDB:
        logger.info(f"CRUDUser: Creating new user '{username}' for wallet {wallet_address}")
        user_to_create_model = UserInDB(
            walletAddress=wallet_address.lower(),
            username=username,
            rank=settings.DEFAULT_RANK_OBSERVER,
            profile=profile, 
            referralCode=referral_code,
            systemStatus=system_status,
            referredBy=referred_by_user_id,
            twitter_data=twitter_data # Simpan twitter_data jika ada
        )
        return await super().create(db, obj_in=user_to_create_model)

    async def update_twitter_data(
        self, db: AsyncIOMotorDatabase, *, user_id: PyObjectId, twitter_data: UserTwitterData
    ) -> Optional[UserInDB]:
        logger.info(f"CRUDUser: Updating Twitter data for user_id: {user_id}")
        # twitter_data adalah objek Pydantic, perlu di-dump ke dict untuk update
        return await super().update(db, db_obj_id=user_id, obj_in={"twitter_data": twitter_data.model_dump()})

    async def increment_allies_count(self, db: AsyncIOMotorDatabase, *, user_id: PyObjectId) -> Optional[UserInDB]:
        logger.info(f"CRUDUser: Attempting to increment allies_count for user_id: {user_id}")
        updated_user = await super().update(
            db, 
            db_obj_id=user_id, 
            obj_in={"$inc": {"alliesCount": 1}} 
        )
        if updated_user:
            logger.info(f"CRUDUser: Successfully incremented allies_count for user_id: {user_id}. New count: {updated_user.alliesCount}")
        else:
            logger.error(f"CRUDUser: Failed to increment allies_count for user ID: {user_id} or update failed.")
        return updated_user

    async def update_last_login(self, db: AsyncIOMotorDatabase, *, user_id: PyObjectId) -> Optional[UserInDB]:
        now = datetime.now(timezone.utc)
        logger.info(f"CRUDUser: Updating last_login for user_id: {user_id} to {now.isoformat()}")
        updated_user = await super().update(db, db_obj_id=user_id, obj_in={"lastLogin": now})
        if not updated_user:
             logger.warning(f"CRUDUser: Attempted to update last_login for user ID: {user_id}, but user was not found or update failed.")
        return updated_user

    async def add_xp_and_update_rank(self, db: AsyncIOMotorDatabase, *, user_id: PyObjectId, xp_to_add: int) -> Optional[UserInDB]:
        """
        MODIFIKASI: Fungsi ini sekarang HANYA mengupdate XP dan field 'rank' (string).
        Tanggung jawab untuk mengupdate detail profile diserahkan ke service layer.
        """
        user_doc = await self.get(db, id=user_id)
        if not user_doc:
            logger.warning(f"CRUDUser: User not found with id {user_id} for XP update.")
            return None

        new_xp = user_doc.xp + xp_to_add
        current_rank_str = user_doc.rank
        new_rank_str = current_rank_str

        # Tentukan apakah rank string berubah
        for rank_name_iter in reversed(settings.RANK_ORDER):
            if new_xp >= settings.RANK_THRESHOLDS.get(rank_name_iter, float('inf')):
                new_rank_str = rank_name_iter
                break
        
        update_fields: Dict[str, Any] = {"xp": new_xp}
        if new_rank_str != current_rank_str:
            update_fields["rank"] = new_rank_str
            logger.info(f"CRUDUser: User {user_doc.username} (ID: {user_id}) rank string will be updated to {new_rank_str} with {new_xp} XP.")
        
        # Panggil super().update untuk update XP dan/atau rank string.
        updated_user = await super().update(db, db_obj_id=user_id, obj_in=update_fields)
            
        return updated_user


crud_user = CRUDUser(UserInDB, "users")
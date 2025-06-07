# ===========================================================================
# File: app/api/v1/endpoints/users.py (MODIFIKASI: Tambahkan endpoint /me/badges)
# ===========================================================================
from fastapi import APIRouter, Depends, HTTPException, status as HttpStatus, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List # Menambahkan List

from app.db.session import get_db
from app.api.deps import get_current_active_user
from app.models.user import UserInDB
from app.api.v1.schemas.user import UserPublic, UserUpdate, AlliesListResponse
from app.api.v1.schemas.badge import UserBadgeResponse, UserBadgeListResponse # BARU
from app.services.user_service import user_service
from app.services.mission_service import mission_service # BARU (untuk badges)
from app.core.config import logger

router = APIRouter()

@router.get("/me", response_model=UserPublic, summary="Get Current User Profile")
async def read_current_user_me(
    current_user_from_dep: UserInDB = Depends(get_current_active_user)
):
    logger.info(f"Fetching profile for user: {current_user_from_dep.username}")
    return UserPublic.model_validate(current_user_from_dep)

@router.put("/me", response_model=UserPublic, summary="Update Current User Profile")
async def update_current_user_me(
    *,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user_update_data: UserUpdate,
    current_user_from_dep: UserInDB = Depends(get_current_active_user)
):
    logger.info(f"Updating profile for user: {current_user_from_dep.username}")
    try:
        updated_user_public = await user_service.update_user_profile(
            db=db, user_id=current_user_from_dep.id, profile_update_data=user_update_data
        )
        if not updated_user_public:
            logger.error(f"User service returned None for profile update: {current_user_from_dep.username}")
            raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal memperbarui profil.")
        return updated_user_public
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error updating profile for {current_user_from_dep.username}: {e}", exc_info=True)
        raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="Kesalahan server internal.")

@router.get("/me/allies", response_model=AlliesListResponse, summary="Get List of Referred Users (Allies)")
async def get_my_allies(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user),
    page: int = Query(1, ge=1, description="Nomor halaman"),
    limit: int = Query(10, ge=1, le=100, description="Jumlah item per halaman (maks 100)")
):
    logger.info(f"Fetching allies for user: {current_user.username}, page: {page}, limit: {limit}")
    allies_data = await user_service.get_user_allies_list(
        db=db, current_user=current_user, page=page, limit=limit
    )
    return allies_data

@router.get("/me/badges", response_model=UserBadgeListResponse, summary="Get Current User's Acquired Badges")
async def get_my_neural_imprints(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Mengambil daftar badge (Neural Imprints) yang telah diperoleh oleh pengguna yang sedang login.
    """
    logger.info(f"Fetching badges for user: {current_user.username}")
    badges = await mission_service.get_user_badges(db=db, user=current_user)
    return UserBadgeListResponse(badges=badges, total=len(badges))

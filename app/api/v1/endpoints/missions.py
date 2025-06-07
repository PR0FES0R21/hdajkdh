# ===========================================================================
# File: app/api/v1/endpoints/missions.py (MODIFIKASI: Implementasi endpoint)
# ===========================================================================
from fastapi import APIRouter, Depends, HTTPException, status as HttpStatus
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List

from app.db.session import get_db
from app.api.deps import get_current_active_user
from app.models.user import UserInDB
from app.services.mission_service import mission_service
from app.api.v1.schemas.mission import (
    MissionDirectiveResponse, 
    MissionDirectivesListResponse,
    MissionProgressSummaryResponse,
    MissionCompletionRequest, # Jika ada body untuk complete
    MissionCompletionResponse
)
from app.core.config import logger

router = APIRouter()

@router.get(
    "/directives", 
    response_model=MissionDirectivesListResponse, # Menggunakan skema list
    summary="Get List of Active Mission Directives"
)
async def get_active_directives(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Mengambil daftar semua direktif misi yang aktif dan relevan untuk pengguna.
    Status misi (available, completed, dll.) akan disesuaikan untuk pengguna yang login.
    """
    logger.info(f"Fetching active directives for user: {current_user.username}")
    directives = await mission_service.get_directives_for_user(db=db, user=current_user)
    return MissionDirectivesListResponse(directives=directives)

@router.get(
    "/me/summary", 
    response_model=MissionProgressSummaryResponse,
    summary="Get Current User's Mission Progress Summary"
)
async def get_my_mission_summary(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Mengambil ringkasan progres misi untuk pengguna yang sedang login
    (Operation Status, Active Signals).
    """
    logger.info(f"Fetching mission progress summary for user: {current_user.username}")
    summary = await mission_service.get_user_mission_progress_summary(db=db, user=current_user)
    return summary

@router.post(
    "/directives/{mission_id_str}/complete", 
    response_model=MissionCompletionResponse,
    summary="Attempt to Complete a Mission Directive"
)
async def complete_mission_directive_endpoint(
    mission_id_str: str, # ID string misi, bukan ObjectId DB
    # completion_data: Optional[MissionCompletionRequest] = None, # Jika ada body
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Endpoint untuk pengguna mencoba menyelesaikan sebuah misi.
    - **mission_id_str**: ID string dari misi yang ingin diselesaikan.
    - **Request Body (Opsional)**: Bisa berisi data pendukung untuk validasi penyelesaian.
    """
    logger.info(f"User {current_user.username} attempting to complete mission_id_str: {mission_id_str}")
    try:
        # Mengambil data dari body jika ada, atau None jika tidak
        # request_body_data = completion_data.validation_data if completion_data else None
        # Untuk sekarang kita anggap tidak ada body spesifik.
        result = await mission_service.process_mission_completion(
            db=db, 
            user=current_user, 
            mission_id_str_to_complete=mission_id_str,
            # completion_data=request_body_data 
        )
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error completing mission {mission_id_str} for user {current_user.username}: {e}", exc_info=True)
        raise HTTPException(status_code=HttpStatus.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal memproses penyelesaian misi.")

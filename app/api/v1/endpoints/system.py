# ===========================================================================
# File: app/api/v1/endpoints/system.py (Stub)
# ===========================================================================
from fastapi import APIRouter

router = APIRouter()

@router.get("/status", summary="Get System Status (Stub)")
async def get_system_status():
    return {"message": "System status endpoint (coming soon)", "status": "All systems nominal"}

# @router.get("/logs", summary="Get System Logs (Stub - Admin Only)")
# async def get_system_logs(current_user: UserInDB = Depends(get_current_active_admin_user)): # Perlu dependency admin
# return {"message": "System logs endpoint (coming soon, admin only)"}

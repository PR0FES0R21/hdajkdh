# ===========================================================================
# File: app/api/v1/__init__.py
# ===========================================================================
from fastapi import APIRouter
from .endpoints import auth, users, missions, news, system 

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Wallet"])
api_v1_router.include_router(users.router, prefix="/users", tags=["Users & Profile"])
api_v1_router.include_router(missions.router, prefix="/missions", tags=["Missions & Progress"])
# api_v1_router.include_router(portfolio.router, prefix="/portfolio", tags=["User Portfolio"]) # Coming Soon
api_v1_router.include_router(news.router, prefix="/news", tags=["News & Announcements"])
api_v1_router.include_router(system.router, prefix="/system", tags=["System Information"])

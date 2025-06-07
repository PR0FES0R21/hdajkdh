# ===========================================================================
# File: app/api/v1/schemas/__init__.py (MODIFIKASI: Tambahkan skema baru)
# ===========================================================================
from .token import TokenResponse, TokenData
from .auth import ChallengeMessageResponse, WalletConnectRequest
from .user import UserCreate, UserUpdate, UserPublic, AllyInfo, AlliesListResponse
from .badge import UserBadgeResponse # BARU
from .mission import MissionDirectiveResponse, MissionProgressSummaryResponse, MissionCompletionRequest # BARU

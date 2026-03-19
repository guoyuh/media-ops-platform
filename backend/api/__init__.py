from api.collect import router as collect_router
from api.users import router as users_router
from api.message import router as message_router
from api.accounts import router as accounts_router
from api.dashboard import router as dashboard_router
from api.creative import router as creative_router
from api.auth import router as auth_router

__all__ = [
    "collect_router",
    "users_router",
    "message_router",
    "accounts_router",
    "dashboard_router",
    "creative_router",
    "auth_router",
]

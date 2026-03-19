from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sa_func
from database import get_db
from models.user import CollectedUser
from models.task import CollectTask, TouchRecord
from models.auth_user import AuthUser
from services.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    users_count = await db.scalar(
        select(sa_func.count(CollectedUser.id)).where(CollectedUser.owner_id == current_user.id)
    )
    tasks_count = await db.scalar(
        select(sa_func.count(CollectTask.id)).where(CollectTask.owner_id == current_user.id)
    )
    touch_count = await db.scalar(
        select(sa_func.count(TouchRecord.id)).where(TouchRecord.user_id == current_user.id)
    )
    return {
        "total_users": users_count or 0,
        "total_tasks": tasks_count or 0,
        "total_touches": touch_count or 0,
    }

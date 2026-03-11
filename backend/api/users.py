from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sa_func
from database import get_db
from models.user import CollectedUser
from models.auth_user import AuthUser
from services.auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["UserPool"])


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    platform: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    query = select(CollectedUser)
    count_query = select(sa_func.count(CollectedUser.id))

    if platform:
        query = query.where(CollectedUser.platform == platform)
        count_query = count_query.where(CollectedUser.platform == platform)
    if status:
        query = query.where(CollectedUser.status == status)
        count_query = count_query.where(CollectedUser.status == status)
    if keyword:
        query = query.where(CollectedUser.nickname.contains(keyword))
        count_query = count_query.where(CollectedUser.nickname.contains(keyword))

    total = await db.scalar(count_query) or 0
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    users = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": u.id,
                "platform": u.platform,
                "platform_uid": u.platform_uid,
                "nickname": u.nickname,
                "avatar_url": u.avatar_url,
                "signature": u.signature,
                "follower_count": u.follower_count,
                "following_count": u.following_count,
                "liked_count": u.liked_count,
                "video_count": u.video_count,
                "tags": u.tags,
                "status": u.status,
                "created_at": str(u.created_at) if u.created_at else None,
            }
            for u in users
        ],
    }


@router.patch("/{user_id}/tags")
async def update_tags(
    user_id: int, tags: str, db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    user = await db.get(CollectedUser, user_id)
    if not user:
        return {"error": "User not found"}
    user.tags = tags
    await db.commit()
    return {"ok": True}

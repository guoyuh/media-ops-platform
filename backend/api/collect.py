from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sa_func, delete as sa_delete
from database import get_db
from models.task import CollectTask, VideoPost, PostComment, XhsNote, XhsComment, XhsVideo, XhsImage
from models.user import CollectedUser
from pydantic import BaseModel

router = APIRouter(prefix="/api/collect", tags=["Collect"])


class CollectTaskCreate(BaseModel):
    name: str
    platform: str = "bilibili"
    task_type: str  # keyword / video_comment / follower
    keyword: str | None = None
    target_url: str | None = None
    max_count: int = 100


@router.post("/tasks")
async def create_task(body: CollectTaskCreate, db: AsyncSession = Depends(get_db)):
    task = CollectTask(**body.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"id": task.id, "status": task.status}


@router.get("/tasks")
async def list_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CollectTask).order_by(CollectTask.id.desc()))
    tasks = result.scalars().all()
    return {
        "items": [
            {
                "id": t.id,
                "name": t.name,
                "platform": t.platform,
                "task_type": t.task_type,
                "keyword": t.keyword,
                "target_url": t.target_url,
                "max_count": t.max_count,
                "collected_count": t.collected_count,
                "status": t.status,
                "error_message": t.error_message or "",
                "created_at": str(t.created_at) if t.created_at else None,
            }
            for t in tasks
        ]
    }


@router.post("/tasks/{task_id}/run")
async def run_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(CollectTask, task_id)
    if not task:
        return {"error": "Task not found"}

    task.status = "running"
    task.error_message = ""
    await db.commit()

    try:
        result = await _do_collect(task)
    except Exception as exc:
        task.status = "failed"
        task.error_message = str(exc)[:500]
        await db.commit()
        return {"error": str(exc), "collected": 0, "duplicates_skipped": 0}

    if task.task_type == "video_comment":
        return await _save_video_comments(db, task, result)
    if task.platform == "xhs":
        return await _save_xhs_notes(db, task, result)
    return await _save_users(db, task, result)


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(CollectTask, task_id)
    if not task:
        return {"error": "Task not found"}
    # 删除关联的视频和评论
    video_ids_q = select(VideoPost.id).where(VideoPost.source_task_id == task_id)
    video_ids = (await db.execute(video_ids_q)).scalars().all()
    if video_ids:
        await db.execute(
            sa_delete(PostComment).where(PostComment.post_id.in_(video_ids))
        )
        await db.execute(
            sa_delete(VideoPost).where(VideoPost.source_task_id == task_id)
        )
    # 删除关联的用户
    await db.execute(
        sa_delete(CollectedUser).where(CollectedUser.source_task_id == task_id)
    )
    # 删除关联的 XHS 数据
    await db.execute(
        sa_delete(XhsComment).where(XhsComment.source_task_id == task_id)
    )
    await db.execute(
        sa_delete(XhsNote).where(XhsNote.source_task_id == task_id)
    )
    await db.delete(task)
    await db.commit()
    return {"ok": True}


async def _save_video_comments(db: AsyncSession, task, data: dict) -> dict:
    videos = data.get("videos", [])
    comments = data.get("comments", [])

    # Save videos (dedup by aid)
    video_count = 0
    aid_to_post_id: dict[int, int] = {}
    for v in videos:
        exists = await db.execute(
            select(VideoPost.id).where(VideoPost.aid == v["aid"]).limit(1)
        )
        row = exists.scalar()
        if row is not None:
            aid_to_post_id[v["aid"]] = row
            continue
        vp = VideoPost(
            aid=v["aid"], bvid=v.get("bvid", ""),
            title=v.get("title", ""), author=v.get("author", ""),
            mid=v.get("mid", 0), play_count=v.get("play_count", 0),
            like_count=v.get("like_count", 0),
            reply_count=v.get("reply_count", 0),
            pubdate=v.get("pubdate", 0), source_task_id=task.id,
        )
        db.add(vp)
        await db.flush()
        aid_to_post_id[v["aid"]] = vp.id
        video_count += 1

    # Save comments (dedup by rpid)
    comment_count = 0
    for c in comments:
        exists = await db.execute(
            select(PostComment.id).where(
                PostComment.rpid == c["rpid"]
            ).limit(1)
        )
        if exists.scalar() is not None:
            continue
        post_id = aid_to_post_id.get(c["aid"], 0)
        db.add(PostComment(
            rpid=c["rpid"], post_id=post_id,
            mid=c.get("mid", 0), uname=c.get("uname", ""),
            avatar=c.get("avatar", ""), message=c.get("message", ""),
            like_count=c.get("like_count", 0), ctime=c.get("ctime", 0),
            parent_rpid=c.get("parent_rpid", 0),
            source_task_id=task.id,
        ))
        comment_count += 1

    task.collected_count = comment_count
    task.status = "done"
    await db.commit()
    return {
        "collected_videos": video_count,
        "collected_comments": comment_count,
    }


async def _save_users(db: AsyncSession, task, users: list[dict]) -> dict:
    new_count = 0
    dup_count = 0
    for u in users:
        exists = await db.execute(
            select(CollectedUser.id).where(
                CollectedUser.platform == "bilibili",
                CollectedUser.platform_uid == u["mid"],
            ).limit(1)
        )
        if exists.scalar() is not None:
            dup_count += 1
            continue
        db.add(CollectedUser(
            platform="bilibili",
            platform_uid=u["mid"],
            nickname=u.get("name", ""),
            avatar_url=u.get("face", ""),
            signature=u.get("sign", ""),
            follower_count=u.get("follower_count", 0),
            following_count=u.get("following_count", 0),
            video_count=u.get("video_count", 0),
            source_task_id=task.id,
        ))
        new_count += 1

    task.collected_count = new_count
    task.status = "done"
    await db.commit()
    return {"collected": new_count, "duplicates_skipped": dup_count}


async def _do_collect(task: CollectTask):
    from collector.factory import create_crawler
    crawler = create_crawler(task.platform)
    return await crawler.collect(task)


async def _save_xhs_notes(db: AsyncSession, task, data: dict) -> dict:
    notes = data.get("notes", [])
    comments = data.get("comments", [])
    note_count = 0
    for n in notes:
        exists = await db.execute(
            select(XhsNote.id).where(XhsNote.note_id == n["note_id"]).limit(1)
        )
        if exists.scalar() is not None:
            continue
        db.add(XhsNote(
            note_id=n["note_id"], title=n.get("title", ""),
            desc=n.get("desc", ""), type=n.get("type", "normal"),
            user_id=n.get("user_id", ""), nickname=n.get("nickname", ""),
            avatar=n.get("avatar", ""),
            liked_count=n.get("liked_count", 0),
            collected_count=n.get("collected_count", 0),
            comment_count=n.get("comment_count", 0),
            share_count=n.get("share_count", 0),
            note_url=f"https://www.xiaohongshu.com/explore/{n['note_id']}",
            source_task_id=task.id,
        ))
        note_count += 1
    comment_count = 0
    for c in comments:
        exists = await db.execute(
            select(XhsComment.id).where(
                XhsComment.comment_id == c["comment_id"]
            ).limit(1)
        )
        if exists.scalar() is not None:
            continue
        db.add(XhsComment(
            comment_id=c["comment_id"], note_id=c.get("note_id", ""),
            content=c.get("content", ""), user_id=c.get("user_id", ""),
            nickname=c.get("nickname", ""), avatar=c.get("avatar", ""),
            ip_location=c.get("ip_location", ""),
            like_count=c.get("like_count", 0),
            sub_comment_count=c.get("sub_comment_count", 0),
            parent_comment_id=c.get("parent_comment_id", ""),
            create_time=c.get("create_time", 0),
            source_task_id=task.id,
        ))
        comment_count += 1
    task.collected_count = note_count
    task.status = "done"
    await db.commit()
    return {"collected_notes": note_count, "collected_comments": comment_count}


# ── Video / Comment query endpoints ─────────────────────────

@router.get("/videos")
async def list_videos(
    task_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(VideoPost).where(
        VideoPost.source_task_id == task_id
    ).order_by(VideoPost.like_count.desc())
    total_q = select(sa_func.count(VideoPost.id)).where(
        VideoPost.source_task_id == task_id
    )
    total = await db.scalar(total_q) or 0
    result = await db.execute(q.offset((page - 1) * size).limit(size))
    videos = result.scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": v.id, "aid": v.aid, "bvid": v.bvid,
                "title": v.title, "author": v.author, "mid": v.mid,
                "play_count": v.play_count, "like_count": v.like_count,
                "reply_count": v.reply_count, "pubdate": v.pubdate,
            }
            for v in videos
        ],
    }


@router.get("/comments")
async def list_comments(
    post_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # Fetch parent video info for aid/title
    video = await db.get(VideoPost, post_id)
    video_aid = video.aid if video else 0
    video_title = video.title if video else ""

    q = select(PostComment).where(
        PostComment.post_id == post_id,
        PostComment.parent_rpid == 0,
    ).order_by(PostComment.like_count.desc())
    total_q = select(sa_func.count(PostComment.id)).where(
        PostComment.post_id == post_id,
        PostComment.parent_rpid == 0,
    )
    total = await db.scalar(total_q) or 0
    result = await db.execute(q.offset((page - 1) * size).limit(size))
    comments = result.scalars().all()
    return {
        "total": total,
        "video_aid": video_aid,
        "video_title": video_title,
        "items": [
            {
                "id": c.id, "rpid": c.rpid, "mid": c.mid,
                "uname": c.uname, "avatar": c.avatar,
                "message": c.message, "like_count": c.like_count,
                "ctime": c.ctime,
            }
            for c in comments
        ],
    }


# ── XHS Note / Comment query endpoints ──────────────────────

@router.get("/xhs-notes")
async def list_xhs_notes(
    task_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(XhsNote).where(
        XhsNote.source_task_id == task_id
    ).order_by(
        XhsNote.liked_count.desc(),
        XhsNote.collected_count.desc(),
        XhsNote.comment_count.desc(),
    )
    total_q = select(sa_func.count(XhsNote.id)).where(
        XhsNote.source_task_id == task_id
    )
    total = await db.scalar(total_q) or 0
    result = await db.execute(q.offset((page - 1) * size).limit(size))
    notes = result.scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": n.id, "note_id": n.note_id, "title": n.title,
                "desc": n.desc, "type": n.type,
                "user_id": n.user_id, "nickname": n.nickname,
                "avatar": n.avatar,
                "liked_count": n.liked_count,
                "collected_count": n.collected_count,
                "comment_count": n.comment_count,
                "share_count": n.share_count,
                "note_url": n.note_url,
            }
            for n in notes
        ],
    }


@router.get("/xhs-comments")
async def list_xhs_comments(
    note_id: str = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(XhsComment).where(
        XhsComment.note_id == note_id,
        XhsComment.parent_comment_id == "",
    ).order_by(XhsComment.like_count.desc())
    total_q = select(sa_func.count(XhsComment.id)).where(
        XhsComment.note_id == note_id,
        XhsComment.parent_comment_id == "",
    )
    total = await db.scalar(total_q) or 0
    result = await db.execute(q.offset((page - 1) * size).limit(size))
    comments = result.scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": c.id, "comment_id": c.comment_id,
                "note_id": c.note_id, "content": c.content,
                "user_id": c.user_id, "nickname": c.nickname,
                "avatar": c.avatar, "ip_location": c.ip_location,
                "like_count": c.like_count,
                "sub_comment_count": c.sub_comment_count,
                "create_time": c.create_time,
            }
            for c in comments
        ],
    }


# ── 小红书用户信息 ──────────────────────────────────────────────

class ExtractUsersBody(BaseModel):
    """从评论中提取用户"""
    note_id: str
    comment_ids: list[str] = []  # 为空则提取该笔记所有评论者
    account_id: int | None = None  # 如果提供，自动获取用户详情


@router.post("/xhs-extract-users")
async def extract_users_from_comments(
    body: ExtractUsersBody,
    db: AsyncSession = Depends(get_db),
):
    """从小红书评论中提取潜在用户并保存"""
    from models.user import CollectedUser
    from models.account import PlatformAccount
    from services.xhs_user import get_xhs_user_info
    import asyncio

    if body.comment_ids:
        # 提取指定评论的用户
        q = select(XhsComment).where(
            XhsComment.comment_id.in_(body.comment_ids)
        )
    else:
        # 提取该笔记所有评论者
        q = select(XhsComment).where(
            XhsComment.note_id == body.note_id
        )

    result = await db.execute(q)
    comments = result.scalars().all()

    added = 0
    skipped = 0
    new_users = []  # 新添加的用户

    for c in comments:
        if not c.user_id:
            continue
        # 检查是否已存在
        exists = await db.scalar(
            select(CollectedUser.id).where(
                CollectedUser.platform == "xhs",
                CollectedUser.platform_uid == c.user_id,
            ).limit(1)
        )
        if exists:
            skipped += 1
            continue

        # 创建用户记录
        user = CollectedUser(
            platform="xhs",
            platform_uid=c.user_id,
            nickname=c.nickname,
            avatar_url=c.avatar,
            source_task_id=c.source_task_id,
            source_note_id=c.note_id,
            source_comment_id=c.comment_id,
            status="new",
        )
        db.add(user)
        new_users.append(user)
        added += 1

    await db.commit()

    # 如果提供了账号，自动获取用户详情
    fetched = 0
    if body.account_id and new_users:
        account = await db.get(PlatformAccount, body.account_id)
        if account and account.cookies and account.platform == "xhs":
            for user in new_users:
                try:
                    info = await get_xhs_user_info(account.cookies, user.platform_uid)
                    if info.get("success"):
                        user.nickname = info.get("nickname") or user.nickname
                        user.avatar_url = info.get("avatar") or user.avatar_url
                        user.signature = info.get("desc", "")
                        user.follower_count = info.get("fans", 0)
                        user.following_count = info.get("follows", 0)
                        user.liked_count = info.get("interaction", 0)
                        fetched += 1
                except Exception:
                    pass
                await asyncio.sleep(2)  # 避免频繁请求
            await db.commit()

    return {"added": added, "skipped": skipped, "fetched": fetched}


class ExtractAuthorsBody(BaseModel):
    """从笔记中提取作者"""
    note_ids: list[str]
    account_id: int | None = None  # 如果提供，自动获取用户详情


@router.post("/xhs-extract-authors")
async def extract_authors_from_notes(
    body: ExtractAuthorsBody,
    db: AsyncSession = Depends(get_db),
):
    """从小红书笔记中提取作者并保存到用户库"""
    from models.user import CollectedUser
    from models.account import PlatformAccount
    from services.xhs_user import get_xhs_user_info
    import asyncio

    # 获取指定的笔记
    q = select(XhsNote).where(XhsNote.note_id.in_(body.note_ids))
    result = await db.execute(q)
    notes = result.scalars().all()

    added = 0
    skipped = 0
    new_users = []  # 新添加的用户

    for n in notes:
        if not n.user_id:
            continue
        # 检查是否已存在
        exists = await db.scalar(
            select(CollectedUser.id).where(
                CollectedUser.platform == "xhs",
                CollectedUser.platform_uid == n.user_id,
            ).limit(1)
        )
        if exists:
            skipped += 1
            continue

        # 创建用户记录
        user = CollectedUser(
            platform="xhs",
            platform_uid=n.user_id,
            nickname=n.nickname,
            avatar_url=n.avatar,
            source_task_id=n.source_task_id,
            source_note_id=n.note_id,
            status="new",
        )
        db.add(user)
        new_users.append(user)
        added += 1

    await db.commit()

    # 如果提供了账号，自动获取用户详情
    fetched = 0
    if body.account_id and new_users:
        account = await db.get(PlatformAccount, body.account_id)
        if account and account.cookies and account.platform == "xhs":
            for user in new_users:
                try:
                    info = await get_xhs_user_info(account.cookies, user.platform_uid)
                    if info.get("success"):
                        user.nickname = info.get("nickname") or user.nickname
                        user.avatar_url = info.get("avatar") or user.avatar_url
                        user.signature = info.get("desc", "")
                        user.follower_count = info.get("fans", 0)
                        user.following_count = info.get("follows", 0)
                        user.liked_count = info.get("interaction", 0)
                        fetched += 1
                except Exception:
                    pass
                await asyncio.sleep(2)  # 避免频繁请求
            await db.commit()

    return {"added": added, "skipped": skipped, "fetched": fetched}


class FetchUserInfoBody(BaseModel):
    """获取用户详细信息"""
    user_ids: list[int]  # CollectedUser.id 列表
    account_id: int  # 使用哪个小红书账号


@router.post("/xhs-fetch-user-info")
async def fetch_xhs_user_info(
    body: FetchUserInfoBody,
    db: AsyncSession = Depends(get_db),
):
    """获取小红书用户详细信息（粉丝数、获赞数等）"""
    from models.account import PlatformAccount
    from services.xhs_user import get_xhs_user_info
    import asyncio

    account = await db.get(PlatformAccount, body.account_id)
    if not account or not account.cookies:
        return {"error": "Account not found or no cookies"}
    if account.platform != "xhs":
        return {"error": "账号不是小红书平台"}

    # 获取待更新的用户
    result = await db.execute(
        select(CollectedUser).where(
            CollectedUser.id.in_(body.user_ids),
            CollectedUser.platform == "xhs",
        )
    )
    users = result.scalars().all()

    updated = 0
    failed = 0

    for user in users:
        try:
            info = await get_xhs_user_info(account.cookies, user.platform_uid)
            if info.get("success"):
                user.nickname = info.get("nickname") or user.nickname
                user.avatar_url = info.get("avatar") or user.avatar_url
                user.signature = info.get("desc", "")
                user.follower_count = info.get("fans", 0)
                user.following_count = info.get("follows", 0)
                user.liked_count = info.get("interaction", 0)  # 获赞与收藏
                updated += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
        # 间隔避免频繁请求
        await asyncio.sleep(2)

    await db.commit()
    return {"updated": updated, "failed": failed}


@router.get("/xhs-users")
async def list_xhs_users(
    db: AsyncSession = Depends(get_db),
    task_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
):
    """列出已采集的小红书用户"""
    q = select(CollectedUser).where(CollectedUser.platform == "xhs")
    total_q = select(sa_func.count(CollectedUser.id)).where(CollectedUser.platform == "xhs")

    if task_id:
        q = q.where(CollectedUser.source_task_id == task_id)
        total_q = total_q.where(CollectedUser.source_task_id == task_id)
    if status:
        q = q.where(CollectedUser.status == status)
        total_q = total_q.where(CollectedUser.status == status)

    q = q.order_by(CollectedUser.follower_count.desc())
    total = await db.scalar(total_q) or 0
    result = await db.execute(q.offset((page - 1) * size).limit(size))
    users = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": u.id,
                "platform_uid": u.platform_uid,
                "nickname": u.nickname,
                "avatar_url": u.avatar_url,
                "signature": u.signature,
                "follower_count": u.follower_count,
                "following_count": u.following_count,
                "liked_count": u.liked_count,
                "collected_count": u.collected_count,
                "source_note_id": u.source_note_id,
                "status": u.status,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


# ── 小红书视频/图片解析 ──────────────────────────────────────────

class ParseMediaBody(BaseModel):
    """解析笔记媒体资源"""
    note_ids: list[str]
    account_id: int
    save_to_db: bool = True  # 是否保存到数据库


@router.post("/xhs-parse-media")
async def parse_xhs_media(
    body: ParseMediaBody,
    db: AsyncSession = Depends(get_db),
):
    """
    解析小红书笔记的视频/图片资源

    返回多画质视频直链和有水印/无水印图片链接
    """
    from models.account import PlatformAccount
    from services.xhs_media import parse_xhs_note_media
    import asyncio

    account = await db.get(PlatformAccount, body.account_id)
    if not account or not account.cookies:
        return {"error": "Account not found or no cookies"}
    if account.platform != "xhs":
        return {"error": "账号不是小红书平台"}

    results = []
    videos_added = 0
    images_added = 0

    for note_id in body.note_ids:
        try:
            result = await parse_xhs_note_media(account.cookies, note_id)
            results.append(result)

            if body.save_to_db and result.get("success"):
                if result.get("type") == "video" and result.get("video"):
                    # 保存视频信息
                    video_info = result["video"]
                    # 检查是否已存在
                    exists = await db.scalar(
                        select(XhsVideo.id).where(XhsVideo.note_id == note_id).limit(1)
                    )
                    if not exists:
                        video = XhsVideo(
                            note_id=note_id,
                            title=result.get("title", ""),
                            cover_url=result.get("cover_url", ""),
                            video_url_1080p=video_info.get("video_url_1080p", ""),
                            video_url_720p=video_info.get("video_url_720p", ""),
                            video_url_480p=video_info.get("video_url_480p", ""),
                            video_url_default=video_info.get("video_url_default", ""),
                            duration=video_info.get("duration", 0),
                            width=video_info.get("width", 0),
                            height=video_info.get("height", 0),
                        )
                        db.add(video)
                        videos_added += 1

                elif result.get("images"):
                    # 保存图片信息
                    for img in result["images"]:
                        # 检查是否已存在
                        exists = await db.scalar(
                            select(XhsImage.id).where(
                                XhsImage.note_id == note_id,
                                XhsImage.image_index == img["index"],
                            ).limit(1)
                        )
                        if not exists:
                            image = XhsImage(
                                note_id=note_id,
                                image_index=img["index"],
                                url_watermark=img.get("url_watermark", ""),
                                url_original=img.get("url_original", ""),
                                width=img.get("width", 0),
                                height=img.get("height", 0),
                            )
                            db.add(image)
                            images_added += 1

        except Exception as e:
            results.append({"note_id": note_id, "success": False, "error": str(e)})

        await asyncio.sleep(2)  # 避免频繁请求

    await db.commit()

    return {
        "results": results,
        "videos_added": videos_added,
        "images_added": images_added,
    }


@router.get("/xhs-videos")
async def list_xhs_videos(
    db: AsyncSession = Depends(get_db),
    note_id: str | None = None,
    page: int = 1,
    size: int = 20,
):
    """列出已解析的小红书视频"""
    q = select(XhsVideo)
    total_q = select(sa_func.count(XhsVideo.id))

    if note_id:
        q = q.where(XhsVideo.note_id == note_id)
        total_q = total_q.where(XhsVideo.note_id == note_id)

    q = q.order_by(XhsVideo.id.desc())
    total = await db.scalar(total_q) or 0
    result = await db.execute(q.offset((page - 1) * size).limit(size))
    videos = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": v.id,
                "note_id": v.note_id,
                "title": v.title,
                "cover_url": v.cover_url,
                "video_url_1080p": v.video_url_1080p,
                "video_url_720p": v.video_url_720p,
                "video_url_480p": v.video_url_480p,
                "video_url_default": v.video_url_default,
                "duration": v.duration,
                "width": v.width,
                "height": v.height,
                "download_status": v.download_status,
                "local_path": v.local_path,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in videos
        ],
    }


@router.get("/xhs-images")
async def list_xhs_images(
    db: AsyncSession = Depends(get_db),
    note_id: str | None = None,
    page: int = 1,
    size: int = 50,
):
    """列出已解析的小红书图片"""
    q = select(XhsImage)
    total_q = select(sa_func.count(XhsImage.id))

    if note_id:
        q = q.where(XhsImage.note_id == note_id)
        total_q = total_q.where(XhsImage.note_id == note_id)

    q = q.order_by(XhsImage.note_id, XhsImage.image_index)
    total = await db.scalar(total_q) or 0
    result = await db.execute(q.offset((page - 1) * size).limit(size))
    images = result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": i.id,
                "note_id": i.note_id,
                "image_index": i.image_index,
                "url_watermark": i.url_watermark,
                "url_original": i.url_original,
                "width": i.width,
                "height": i.height,
                "download_status": i.download_status,
                "local_path": i.local_path,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in images
        ],
    }


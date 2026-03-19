import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func as sa_func
from pydantic import BaseModel
from database import get_db
from models.creative import CreativePost
from models.task import XhsNote
from models.auth_user import AuthUser
from services.auth import get_current_user
from services.llm import generate_xhs_note

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/creative", tags=["Creative"])


# ── Request / Response schemas ────────────────────────────────
class GenerateRequest(BaseModel):
    topic: str
    style: str = "种草"
    ref_count: int = 3


class PostCreate(BaseModel):
    title: str = ""
    content: str = ""
    tags: list[str] = []
    style: str = ""
    topic: str = ""
    reference_note_ids: list[str] = []
    status: str = "draft"


class PostUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    status: str | None = None


# ── AI 生成 ───────────────────────────────────────────────────
@router.post("/generate")
async def generate_note(body: GenerateRequest, db: AsyncSession = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    """AI 生成小红书风格笔记，自动从 xhs_notes 取 top-N 参考"""
    ref_notes = []
    if body.ref_count > 0:
        q = (
            select(XhsNote)
            .order_by(desc(XhsNote.liked_count))
            .limit(body.ref_count)
        )
        result = await db.execute(q)
        rows = result.scalars().all()
        ref_notes = [
            {"title": r.title, "desc": r.desc} for r in rows
        ]
    try:
        note = await generate_xhs_note(
            topic=body.topic,
            style=body.style,
            reference_notes=ref_notes or None,
        )
    except Exception as e:
        logger.exception("LLM generate failed")
        raise HTTPException(status_code=500, detail=str(e))
    return note


# ── 草稿列表（分页 + status 筛选）─────────────────────────────
@router.get("/posts")
async def list_posts(
    status: str = "",
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    q = select(CreativePost).order_by(desc(CreativePost.id))
    count_q = select(sa_func.count()).select_from(CreativePost)
    if status:
        q = q.where(CreativePost.status == status)
        count_q = count_q.where(CreativePost.status == status)
    total = (await db.execute(count_q)).scalar() or 0
    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()
    return {
        "total": total,
        "items": [_post_to_dict(r) for r in rows],
    }


# ── 保存草稿 ──────────────────────────────────────────────────
@router.post("/posts")
async def create_post(body: PostCreate, db: AsyncSession = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    post = CreativePost(
        title=body.title,
        content=body.content,
        tags=json.dumps(body.tags, ensure_ascii=False),
        style=body.style,
        topic=body.topic,
        reference_note_ids=json.dumps(body.reference_note_ids),
        status=body.status,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return _post_to_dict(post)


# ── 更新草稿 ──────────────────────────────────────────────────
@router.put("/posts/{post_id}")
async def update_post(
    post_id: int, body: PostUpdate, db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    post = await db.get(CreativePost, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    if body.title is not None:
        post.title = body.title
    if body.content is not None:
        post.content = body.content
    if body.tags is not None:
        post.tags = json.dumps(body.tags, ensure_ascii=False)
    if body.status is not None:
        post.status = body.status
    await db.commit()
    await db.refresh(post)
    return _post_to_dict(post)


# ── 删除 ──────────────────────────────────────────────────────
@router.delete("/posts/{post_id}")
async def delete_post(post_id: int, db: AsyncSession = Depends(get_db), current_user: AuthUser = Depends(get_current_user)):
    post = await db.get(CreativePost, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    await db.delete(post)
    await db.commit()
    return {"ok": True}


# ── 重新生成 ──────────────────────────────────────────────────
@router.post("/posts/{post_id}/regenerate")
async def regenerate_post(
    post_id: int, db: AsyncSession = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    post = await db.get(CreativePost, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    ref_ids = json.loads(post.reference_note_ids or "[]")
    ref_notes = []
    if ref_ids:
        q = select(XhsNote).where(XhsNote.note_id.in_(ref_ids))
        rows = (await db.execute(q)).scalars().all()
        ref_notes = [{"title": r.title, "desc": r.desc} for r in rows]
    note = await generate_xhs_note(
        topic=post.topic or "通用",
        style=post.style or "种草",
        reference_notes=ref_notes or None,
    )
    post.title = note["title"]
    post.content = note["content"]
    post.tags = json.dumps(note["tags"], ensure_ascii=False)
    await db.commit()
    await db.refresh(post)
    return _post_to_dict(post)


# ── helper ────────────────────────────────────────────────────
def _post_to_dict(p: CreativePost) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "content": p.content,
        "tags": json.loads(p.tags or "[]"),
        "style": p.style,
        "topic": p.topic,
        "reference_note_ids": json.loads(p.reference_note_ids or "[]"),
        "status": p.status,
        "created_at": str(p.created_at) if p.created_at else None,
        "updated_at": str(p.updated_at) if p.updated_at else None,
    }

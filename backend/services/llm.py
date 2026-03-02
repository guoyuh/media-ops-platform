import re
import asyncio
import httpx
from config import settings

_DEFAULT_SYSTEM_PROMPT = (
    "你是一个B站评论回复助手。根据视频标题和用户评论，"
    "生成一条自然、友好、有互动感的回复。"
    "回复不超过60字，不要使用 # 号或 markdown 格式。"
)

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.DOTALL)


def _clean_reply(text: str) -> str:
    """Remove <think>...</think> blocks and strip whitespace."""
    return _THINK_RE.sub("", text).strip()


async def generate_comment_reply(
    video_title: str,
    comment_text: str,
    commenter_name: str,
    custom_prompt: str = "",
) -> str:
    """Call LLM to generate a reply for a Bilibili comment."""
    system_prompt = custom_prompt or _DEFAULT_SYSTEM_PROMPT
    if comment_text:
        user_msg = (
            f"视频标题：{video_title}\n"
            f"评论者：{commenter_name}\n"
            f"评论内容：{comment_text}\n\n"
            "请生成一条合适的回复："
        )
    else:
        user_msg = (
            f"视频标题：{video_title}\n\n"
            "请针对这个视频生成一条合适的一级评论："
        )
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 256,
        "temperature": 0.8,
    }
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    f"{settings.LLM_BASE_URL}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(2)
    raw = data["choices"][0]["message"]["content"]
    return _clean_reply(raw)


_XHS_COMMENT_SYSTEM = (
    "你是一个小红书评论助手。根据笔记标题，"
    "生成一条自然、友好的评论。不超过60字。"
)

_XHS_REPLY_SYSTEM = (
    "你是一个小红书评论回复助手。根据笔记标题和用户评论，"
    "生成一条自然、友好的回复。不超过60字。"
)


async def generate_xhs_reply(
    note_title: str,
    comment_text: str,
    commenter_name: str,
    custom_prompt: str = "",
) -> str:
    """Call LLM to generate a reply for an XHS comment/note."""
    if comment_text:
        system_prompt = custom_prompt or _XHS_REPLY_SYSTEM
        user_msg = (
            f"笔记标题：{note_title}\n"
            f"评论者：{commenter_name}\n"
            f"评论内容：{comment_text}\n\n"
            "请生成一条合适的回复："
        )
    else:
        system_prompt = custom_prompt or _XHS_COMMENT_SYSTEM
        user_msg = (
            f"笔记标题：{note_title}\n\n"
            "请生成一条合适的评论："
        )
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 256,
        "temperature": 0.8,
    }
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    f"{settings.LLM_BASE_URL}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(2)
    raw = data["choices"][0]["message"]["content"]
    return _clean_reply(raw)

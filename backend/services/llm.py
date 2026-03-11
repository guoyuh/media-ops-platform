import re
import json
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


async def _call_llm(payload: dict, timeout: int = 60) -> str:
    """Shared helper: call ModelScope LLM and return raw content."""
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    f"{settings.LLM_BASE_URL}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(2)


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
    raw = await _call_llm(payload)
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
    raw = await _call_llm(payload)
    return _clean_reply(raw)


_XHS_NOTE_SYSTEM = (
    "你是一个专业的小红书爆款笔记写手。根据用户给出的主题和风格，"
    "生成一篇小红书风格的图文笔记。\n"
    "要求：\n"
    "1. 标题要有吸引力，可以使用 emoji，不超过20字\n"
    "2. 正文自然口语化，适当使用 emoji，300-500字\n"
    "3. 生成3-5个相关话题标签\n"
    "4. 严格以 JSON 格式输出："
    '{"title": "...", "content": "...", "tags": ["..."]}\n'
    "5. 不要输出 JSON 以外的任何内容"
)


async def generate_xhs_note(
    topic: str,
    style: str = "种草",
    reference_notes: list[dict] | None = None,
) -> dict:
    """Call LLM to generate a Xiaohongshu-style note.

    Returns dict with keys: title, content, tags.
    On JSON parse failure, returns raw text in content.
    """
    ref_block = ""
    if reference_notes:
        examples = []
        for i, n in enumerate(reference_notes[:5], 1):
            examples.append(
                f"参考笔记{i}：\n标题：{n.get('title','')}\n"
                f"正文：{(n.get('desc','') or '')[:200]}"
            )
        ref_block = (
            "\n\n以下是一些爆款笔记供参考风格：\n"
            + "\n\n".join(examples)
        )

    user_msg = f"主题：{topic}\n风格：{style}{ref_block}\n\n请生成笔记："
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": _XHS_NOTE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 2048,
        "temperature": 0.85,
    }
    raw = _clean_reply(await _call_llm(payload, timeout=120))
    try:
        cleaned = re.sub(r"```json?\s*", "", raw)
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()
        result = json.loads(cleaned)
        return {
            "title": result.get("title", ""),
            "content": result.get("content", ""),
            "tags": result.get("tags", []),
        }
    except (json.JSONDecodeError, KeyError):
        return {"title": "", "content": raw, "tags": []}

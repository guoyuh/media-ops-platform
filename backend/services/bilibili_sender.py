import httpx

_API = "https://api.bilibili.com"


def extract_csrf(cookies_str: str) -> str:
    """Extract bili_jct (CSRF token) from cookie string."""
    for part in cookies_str.split(";"):
        part = part.strip()
        if part.startswith("bili_jct="):
            return part.split("=", 1)[1]
    return ""


async def send_reply_comment(
    cookies_str: str,
    aid: int,
    target_rpid: int,
    message: str,
) -> dict:
    """Post a reply comment on Bilibili.

    Returns the API response dict.
    """
    csrf = extract_csrf(cookies_str)
    if not csrf:
        raise ValueError("Cookie 中未找到 bili_jct (CSRF)")

    form_data = {
        "type": 1,
        "oid": aid,
        "message": message,
        "csrf": csrf,
    }
    # target_rpid=0 means top-level comment; >0 means reply to that comment
    if target_rpid:
        form_data["root"] = target_rpid
        form_data["parent"] = target_rpid
    headers = {
        "Cookie": cookies_str,
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        ),
        "Referer": "https://www.bilibili.com",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_API}/x/v2/reply/add",
            data=form_data,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()

"""小红书视频/图片下载服务

将解析到的视频/图片下载到本地服务器
"""
import asyncio
import logging
import os
import aiohttp
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# 默认下载目录
DEFAULT_DOWNLOAD_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "downloads"
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.xiaohongshu.com/",
}


def _ensure_dir(path: str) -> str:
    """确保目录存在"""
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def _get_file_extension(url: str, content_type: str = "") -> str:
    """从 URL 或 Content-Type 获取文件扩展名"""
    # 先从 URL 获取
    url_path = url.split("?")[0]
    if "." in url_path:
        ext = url_path.split(".")[-1].lower()
        if ext in ["mp4", "webm", "mov", "avi", "jpg", "jpeg", "png", "webp", "gif"]:
            return ext

    # 从 Content-Type 获取
    if "video/mp4" in content_type:
        return "mp4"
    elif "video/webm" in content_type:
        return "webm"
    elif "image/jpeg" in content_type:
        return "jpg"
    elif "image/png" in content_type:
        return "png"
    elif "image/webp" in content_type:
        return "webp"

    # 默认
    return "mp4" if "video" in content_type else "jpg"


async def download_file(
    url: str,
    save_path: str,
    timeout: int = 300,
    extra_headers: Dict | None = None,
) -> Dict:
    """
    下载单个文件

    Args:
        url: 文件 URL
        save_path: 保存路径
        timeout: 超时时间（秒）
        extra_headers: 额外请求头（如 Cookie）

    Returns:
        {"success": True, "path": "xxx", "size": 12345}
    """
    if not url:
        return {"success": False, "error": "URL 为空"}

    try:
        # 确保目录存在
        _ensure_dir(os.path.dirname(save_path))

        # http -> https
        if url.startswith("http://"):
            url = "https://" + url[7:]

        headers = {**_HEADERS}
        if extra_headers:
            headers.update(extra_headers)

        print(f"[DL] Downloading: {url[:80]}...")
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    print(f"[DL] HTTP {resp.status} for {url[:60]}")
                    return {"success": False, "error": f"HTTP {resp.status}"}

                content_type = resp.headers.get("Content-Type", "")
                total_size = 0

                # 如果没有扩展名，根据 Content-Type 添加
                if "." not in os.path.basename(save_path):
                    ext = _get_file_extension(url, content_type)
                    save_path = f"{save_path}.{ext}"

                with open(save_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        f.write(chunk)
                        total_size += len(chunk)

                logger.info(f"Downloaded: {save_path} ({total_size} bytes)")
                return {
                    "success": True,
                    "path": save_path,
                    "size": total_size,
                }

    except asyncio.TimeoutError:
        return {"success": False, "error": "下载超时"}
    except Exception as e:
        logger.error(f"Download failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def download_xhs_video(
    note_id: str,
    video_url: str,
    quality: str = "default",
    download_dir: str = "",
    extra_headers: Dict | None = None,
) -> Dict:
    """
    下载小红书视频
    """
    if not download_dir:
        download_dir = os.path.join(DEFAULT_DOWNLOAD_DIR, "videos")

    _ensure_dir(download_dir)
    filename = f"{note_id}_{quality}.mp4"
    save_path = os.path.join(download_dir, filename)

    if os.path.exists(save_path):
        size = os.path.getsize(save_path)
        return {"success": True, "path": save_path, "size": size, "cached": True}

    return await download_file(video_url, save_path, extra_headers=extra_headers)


async def download_xhs_image(
    note_id: str,
    image_url: str,
    image_index: int = 0,
    watermark: bool = False,
    download_dir: str = "",
    extra_headers: Dict | None = None,
) -> Dict:
    """
    下载小红书图片
    """
    if not download_dir:
        download_dir = os.path.join(DEFAULT_DOWNLOAD_DIR, "images")

    _ensure_dir(download_dir)
    suffix = "_wm" if watermark else ""
    filename = f"{note_id}_{image_index}{suffix}"
    save_path = os.path.join(download_dir, filename)

    ext = _get_file_extension(image_url)
    full_path = f"{save_path}.{ext}"

    if os.path.exists(full_path):
        size = os.path.getsize(full_path)
        return {"success": True, "path": full_path, "size": size, "cached": True}

    return await download_file(image_url, save_path, extra_headers=extra_headers)


async def batch_download_videos(
    videos: list,
    quality: str = "default",
    download_dir: str = "",
    interval: float = 1.0,
) -> list:
    """
    批量下载视频

    Args:
        videos: [{"note_id": "xxx", "video_url": "xxx"}, ...]
        quality: 画质
        download_dir: 下载目录
        interval: 下载间隔（秒）

    Returns:
        [{"note_id": "xxx", "success": True, "path": "xxx"}, ...]
    """
    results = []
    for v in videos:
        result = await download_xhs_video(
            note_id=v["note_id"],
            video_url=v["video_url"],
            quality=quality,
            download_dir=download_dir,
        )
        result["note_id"] = v["note_id"]
        results.append(result)
        await asyncio.sleep(interval)
    return results


async def batch_download_images(
    images: list,
    use_original: bool = True,
    download_dir: str = "",
    interval: float = 0.5,
) -> list:
    """
    批量下载图片

    Args:
        images: [{"note_id": "xxx", "image_index": 0, "url_original": "xxx", "url_watermark": "xxx"}, ...]
        use_original: 是否下载无水印版
        download_dir: 下载目录
        interval: 下载间隔（秒）

    Returns:
        [{"note_id": "xxx", "image_index": 0, "success": True, "path": "xxx"}, ...]
    """
    results = []
    for img in images:
        url = img.get("url_original") if use_original else img.get("url_watermark")
        result = await download_xhs_image(
            note_id=img["note_id"],
            image_url=url,
            image_index=img.get("image_index", 0),
            watermark=not use_original,
            download_dir=download_dir,
        )
        result["note_id"] = img["note_id"]
        result["image_index"] = img.get("image_index", 0)
        results.append(result)
        await asyncio.sleep(interval)
    return results

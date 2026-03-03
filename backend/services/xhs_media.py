"""小红书视频/图片解析服务

解析笔记获取：
- 视频：多画质 CDN 直链
- 图片：有水印/无水印版本
"""
import asyncio
import json
import logging
import os
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

_STEALTH_JS = os.path.join(
    os.path.dirname(__file__), "..", "libs", "stealth.min.js"
)

_XHS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}


def _parse_cookie_str(cookie_str: str) -> dict:
    result = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def _extract_note_detail_from_html(note_id: str, html: str) -> Optional[Dict]:
    """从 HTML 中提取笔记详情"""
    match = re.search(
        r'<script>window.__INITIAL_STATE__=(.+?)</script>', html, re.DOTALL
    )
    if match is None:
        logger.warning("No __INITIAL_STATE__ found")
        return None
    try:
        raw_json = match.group(1).replace(":undefined", ":null")
        state = json.loads(raw_json, strict=False)
        note_detail_map = state.get("note", {}).get("noteDetailMap", {})
        note_data = note_detail_map.get(note_id, {}).get("note", {})
        return note_data
    except Exception as e:
        logger.error(f"Failed to parse note detail: {e}")
        return None


def _convert_to_original_image_url(url: str) -> str:
    """
    将小红书图片 URL 转换为无水印版本

    小红书图片 URL 格式：
    https://sns-webpic-qc.xhscdn.com/xxx/xxx.jpg!nd_dft_wlteh_webp_3

    去水印方法：
    1. 移除 URL 末尾的 !nd_xxx 后缀
    2. 或替换域名为 ci.xiaohongshu.com
    """
    if not url:
        return url

    # 方法1：移除 ! 后缀
    if "!" in url:
        url = url.split("!")[0]

    # 方法2：替换域名（备用）
    # url = url.replace("sns-webpic-qc.xhscdn.com", "ci.xiaohongshu.com")

    return url


def _parse_video_streams(video_data: Dict) -> Dict[str, str]:
    """
    解析视频流，获取多画质直链

    video_data 结构：
    {
        "media": {
            "stream": {
                "h264": [
                    {"masterUrl": "xxx", "videoBitrate": 1234, "videoWidth": 1080, ...}
                ],
                "h265": [...]
            },
            "video": {...}
        },
        ...
    }
    """
    result = {
        "video_url_1080p": "",
        "video_url_720p": "",
        "video_url_480p": "",
        "video_url_default": "",
    }

    media = video_data.get("media", {})
    stream = media.get("stream", {})

    # 优先使用 h264（兼容性好）
    streams = stream.get("h264", []) or stream.get("h265", [])

    if not streams:
        # 尝试直接获取 video URL
        video_info = media.get("video", {})
        if video_info:
            result["video_url_default"] = video_info.get("url", "")
        return result

    # 按分辨率排序
    sorted_streams = sorted(
        streams,
        key=lambda x: x.get("videoWidth", 0) * x.get("videoHeight", 0),
        reverse=True
    )

    for s in sorted_streams:
        width = s.get("videoWidth", 0)
        url = s.get("masterUrl", "") or s.get("backupUrls", [""])[0]

        if not url:
            continue

        if width >= 1080 and not result["video_url_1080p"]:
            result["video_url_1080p"] = url
        elif width >= 720 and not result["video_url_720p"]:
            result["video_url_720p"] = url
        elif width >= 480 and not result["video_url_480p"]:
            result["video_url_480p"] = url

    # 设置默认（最高画质）
    result["video_url_default"] = (
        result["video_url_1080p"] or
        result["video_url_720p"] or
        result["video_url_480p"] or
        (sorted_streams[0].get("masterUrl", "") if sorted_streams else "")
    )

    return result


def _parse_image_list(image_list: List[Dict]) -> List[Dict]:
    """
    解析图片列表，获取有水印/无水印版本

    image_list 结构：
    [
        {
            "urlDefault": "https://...",
            "urlPre": "https://...",
            "width": 1080,
            "height": 1920,
            "infoList": [
                {"url": "...", "imageScene": "WB_DFT"}
            ]
        }
    ]
    """
    result = []

    for idx, img in enumerate(image_list):
        url_watermark = img.get("urlDefault", "") or img.get("urlPre", "")

        # 尝试从 infoList 获取更高质量的图片
        info_list = img.get("infoList", [])
        for info in info_list:
            scene = info.get("imageScene", "")
            # WB_DFT 是默认水印版，WB_PRE 是预览版
            if scene in ["WB_DFT", "CRD_WM"]:
                url_watermark = info.get("url", url_watermark)
                break

        url_original = _convert_to_original_image_url(url_watermark)

        result.append({
            "index": idx,
            "url_watermark": url_watermark,
            "url_original": url_original,
            "width": img.get("width", 0),
            "height": img.get("height", 0),
        })

    return result


async def parse_xhs_note_media(
    cookie_str: str,
    note_id: str,
) -> Dict:
    """
    解析小红书笔记的媒体资源

    Args:
        cookie_str: 小红书 cookie
        note_id: 笔记 ID

    Returns:
        {
            "success": True/False,
            "note_id": "xxx",
            "title": "xxx",
            "type": "video" | "normal",
            "cover_url": "xxx",

            # 视频笔记
            "video": {
                "video_url_1080p": "xxx",
                "video_url_720p": "xxx",
                "video_url_480p": "xxx",
                "video_url_default": "xxx",
                "duration": 12345,
                "width": 1080,
                "height": 1920,
            },

            # 图文笔记
            "images": [
                {
                    "index": 0,
                    "url_watermark": "xxx",
                    "url_original": "xxx",
                    "width": 1080,
                    "height": 1920,
                }
            ]
        }
    """
    if not cookie_str:
        return {"success": False, "error": "Cookie 未配置"}

    cookie_dict = _parse_cookie_str(cookie_str)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=_XHS_HEADERS["User-Agent"])

        # 注入 stealth.js
        if os.path.exists(_STEALTH_JS):
            await context.add_init_script(path=_STEALTH_JS)

        # 设置 cookie
        await context.add_cookies([
            {"name": k, "value": v, "domain": ".xiaohongshu.com", "path": "/"}
            for k, v in cookie_dict.items()
        ])

        page = await context.new_page()

        try:
            url = f"https://www.xiaohongshu.com/explore/{note_id}"
            logger.info(f"Fetching note media: {url}")

            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            html = await page.content()
            note_data = _extract_note_detail_from_html(note_id, html)

            if not note_data:
                return {"success": False, "error": "无法解析笔记信息"}

            note_type = note_data.get("type", "normal")
            title = note_data.get("title", "")

            # 封面图
            cover = note_data.get("cover", {}) or note_data.get("imageList", [{}])[0]
            cover_url = cover.get("urlDefault", "") or cover.get("urlPre", "")

            result = {
                "success": True,
                "note_id": note_id,
                "title": title,
                "type": note_type,
                "cover_url": cover_url,
            }

            if note_type == "video":
                # 视频笔记
                video_data = note_data.get("video", {})
                video_streams = _parse_video_streams(video_data)

                # 视频尺寸和时长
                media = video_data.get("media", {}) or video_data
                video_info = media.get("video", {}) or video_data

                result["video"] = {
                    **video_streams,
                    "duration": video_info.get("duration", 0),
                    "width": video_info.get("width", 0) or cover.get("width", 0),
                    "height": video_info.get("height", 0) or cover.get("height", 0),
                }
            else:
                # 图文笔记
                image_list = note_data.get("imageList", [])
                result["images"] = _parse_image_list(image_list)

            return result

        except Exception as e:
            logger.error(f"Parse note media failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            await browser.close()


async def batch_parse_xhs_notes_media(
    cookie_str: str,
    note_ids: List[str],
    interval: float = 2.0,
) -> List[Dict]:
    """
    批量解析小红书笔记媒体资源
    """
    results = []
    for note_id in note_ids:
        result = await parse_xhs_note_media(cookie_str, note_id)
        results.append(result)
        await asyncio.sleep(interval)
    return results

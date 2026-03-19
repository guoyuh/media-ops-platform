"""抖音评论发送服务（Playwright UI 自动化方式）

核心思路：
1. Playwright 打开视频页面，注入 cookie
2. 定位评论输入框，模拟真实用户输入文字
3. 点击发送按钮提交评论
4. 绕过 API 签名校验，由浏览器自身完成请求

不构造 API 签名，不用 fetch，完全模拟用户操作。
"""

import asyncio
import logging
import os
import random

from playwright.async_api import async_playwright

from collector.douyin.client import _USER_AGENT

logger = logging.getLogger(__name__)

_STEALTH_JS = os.path.join(
    os.path.dirname(__file__), "..", "libs", "stealth.min.js"
)

# debug 目录，保存失败时的截图和页面信息
_DEBUG_DIR = os.path.join(
    os.path.dirname(__file__), "..", "debug", "douyin_debug"
)


def _parse_cookie_str(cookie_str: str) -> dict:
    result = {}
    for item in (cookie_str or "").split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            result[k.strip()] = v.strip()
    return result


async def _save_debug_info(page, tag: str):
    """保存调试截图和页面信息。"""
    try:
        os.makedirs(_DEBUG_DIR, exist_ok=True)
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = os.path.join(_DEBUG_DIR, f"{ts}_{tag}")
        await page.screenshot(path=f"{prefix}.png", full_page=False)
        with open(f"{prefix}.txt", "w") as f:
            f.write(f"url={page.url}\n")
            f.write(f"title={await page.title()}\n")
        # 保存页面 HTML 片段用于分析 DOM 结构
        try:
            html = await page.content()
            with open(f"{prefix}.html", "w", encoding="utf-8") as f:
                f.write(html)
        except Exception:
            pass
        logger.info("debug info saved: %s", prefix)
    except Exception as e:
        logger.warning("save debug info failed: %s", e)


async def _launch_browser(cookie_str: str):
    """启动浏览器并注入 cookie，返回 (pw, browser, context)。"""
    cookie_dict = _parse_cookie_str(cookie_str)
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent=_USER_AGENT,
        viewport={"width": 1280, "height": 900},
    )
    if os.path.exists(_STEALTH_JS):
        await context.add_init_script(path=_STEALTH_JS)
    await context.add_cookies([
        {"name": k, "value": v, "domain": ".douyin.com", "path": "/"}
        for k, v in cookie_dict.items()
    ])
    return pw, browser, context


async def _goto_video(context, aweme_id: str):
    """先访问首页预热（建立正常会话），再导航到视频页。"""
    page = await context.new_page()

    # ---- 第一步：首页预热，让 cookie/JS 环境生效 ----
    logger.info("warming up: goto douyin homepage")
    await page.goto(
        "https://www.douyin.com", wait_until="domcontentloaded"
    )
    await asyncio.sleep(5)

    # 检查首页是否也弹了验证码
    title = await page.title()
    if "验证" in title:
        logger.warning("homepage hit captcha, title=%s", title)
        await _save_debug_info(page, "homepage_captcha")
        # 尝试等更久让验证码自动消失（部分场景会自动跳过）
        await asyncio.sleep(5)

    # ---- 第二步：导航到视频页 ----
    url = f"https://www.douyin.com/video/{aweme_id}"
    logger.info("navigating to %s", url)
    await page.goto(url, wait_until="domcontentloaded")
    await asyncio.sleep(3)

    # 检查视频页是否被验证码拦截
    title = await page.title()
    if "验证" in title:
        logger.warning("video page hit captcha, title=%s", title)
        await _save_debug_info(page, "video_captcha")

    # ---- 第三步：等待视频内容渲染 + 滚动到评论区 ----
    # 抖音视频页是 SPA，内容异步加载，需要等待并滚动
    # 先尝试等待视频播放器或评论区出现
    video_selectors = [
        'div[data-e2e="detail-video"]',
        'video',
        'xg-video-container',
        'div[class*="video-player"]',
        'div[class*="videoPlayer"]',
    ]
    for sel in video_selectors:
        try:
            await page.locator(sel).first.wait_for(
                state="visible", timeout=5000
            )
            logger.info("video element found: %s", sel)
            break
        except Exception:
            continue
    else:
        logger.warning("no video element found, page may not loaded")
        await _save_debug_info(page, "video_not_rendered")

    # 滚动页面，触发评论区懒加载
    await page.mouse.wheel(0, 500)
    await asyncio.sleep(2)
    await page.mouse.wheel(0, 300)
    await asyncio.sleep(2)

    return page


# ---------- 评论框定位选择器（按优先级尝试） ----------
# 抖音评论框有两个阶段：
# 1. 未激活：显示 placeholder（"留下你的精彩评论吧"），无 contenteditable
# 2. 点击后激活：出现 contenteditable 的真正输入框
# 所以需要先点击 placeholder 区域，再找 contenteditable

# 未激活状态的评论框区域（点击后激活）
_COMMENT_PLACEHOLDER_SELECTORS = [
    'div.comment-input-inner-container',
    'span:has-text("留下你的精彩评论")',
    'span:has-text("善语结善缘")',
    'span:has-text("说点什么")',
    'div[class*="comment-input"]',
    'div[class*="commentInput"]',
]

# 激活后的真正输入框
_COMMENT_INPUT_SELECTORS = [
    'div[contenteditable="true"]',
    'div.comment-input-inner div[contenteditable="true"]',
    'div[data-e2e="comment-input"] div[contenteditable="true"]',
    'div[class*="comment"] div[contenteditable="true"]',
]

_SEND_BTN_SELECTORS = [
    # 红色箭头发送按钮：commentInput-right-ct 下最后一个带 class 的 span
    'div.commentInput-right-ct span:last-child',
    'div[class*="commentInput-right"] span:last-child',
    # 通过 SVG fill 颜色定位（红色 #FE2C55 是抖音品牌色）
    'div[class*="commentInput"] span:has(svg path[fill="#FE2C55"])',
    # 兜底：comment-input-container 内的最后一个 span（有多个 class 的）
    '#comment-input-container span[class]:not([class=""])',
    # 旧版选择器保留兼容
    'div[data-e2e="comment-post"]',
    'div[class*="comment"] span:has-text("发布")',
]


async def _find_element(page, selectors: list, label: str, timeout=8000):
    """依次尝试多个选择器，返回第一个找到的元素。"""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            await el.wait_for(state="visible", timeout=timeout)
            logger.info("found %s with selector: %s", label, sel)
            return el
        except Exception:
            continue
    return None


async def _type_and_send(page, content: str, reply_cid: str) -> dict:
    """在视频页面定位评论框、输入文字、点击发送。"""

    # 前置检查：页面是否被验证码拦截
    title = await page.title()
    if "验证" in title:
        await _save_debug_info(page, "captcha_blocked")
        return {
            "success": False,
            "msg": "页面被验证码拦截，请检查 cookie 是否有效",
        }

    # 如果是回复某条评论，先点击该评论的"回复"按钮
    if reply_cid:
        reply_btn = await _find_reply_btn(page, reply_cid)
        if reply_btn:
            await reply_btn.click()
            await asyncio.sleep(1)
            logger.info("clicked reply button for cid=%s", reply_cid)
        else:
            logger.warning("reply button not found for cid=%s", reply_cid)

    # 1. 先点击评论框 placeholder 区域，激活输入框
    placeholder = await _find_element(
        page, _COMMENT_PLACEHOLDER_SELECTORS, "comment-placeholder"
    )
    if placeholder:
        await placeholder.click()
        logger.info("clicked comment placeholder to activate input")
        await asyncio.sleep(1.5)
    else:
        logger.warning("comment placeholder not found")

    # 2. 定位激活后的 contenteditable 输入框
    input_el = await _find_element(
        page, _COMMENT_INPUT_SELECTORS, "comment-input"
    )
    if not input_el:
        await _save_debug_info(page, "input_not_found")
        return {"success": False, "msg": "未找到评论输入框"}

    # 3. 点击输入框确保焦点
    await input_el.click()
    await asyncio.sleep(0.5)

    # 4. 逐字输入（模拟真人打字节奏）
    for ch in content:
        await page.keyboard.type(ch, delay=random.randint(50, 150))
        await asyncio.sleep(random.uniform(0.05, 0.15))
    logger.info("typed %d chars into comment box", len(content))
    await asyncio.sleep(0.5)

    # 5. 点击发送按钮
    send_btn = await _find_element(
        page, _SEND_BTN_SELECTORS, "send-btn", timeout=5000
    )
    if not send_btn:
        # 备选：按 Ctrl+Enter 发送
        logger.info("send button not found, trying Ctrl+Enter")
        await page.keyboard.press("Control+Enter")
    else:
        await send_btn.click()
    logger.info("send action triggered")

    # 6. 等待发送结果（观察评论框是否被清空 / 出现成功提示）
    await asyncio.sleep(3)

    # 检查是否有错误提示（如频率限制、内容违规等）
    error_msg = await _check_error_toast(page)
    if error_msg:
        await _save_debug_info(page, "send_error")
        return {"success": False, "msg": error_msg}

    # 检查输入框是否已清空（说明发送成功）
    remaining = await _get_input_text(page)
    if remaining and remaining.strip() == content.strip():
        # 输入框没清空，但也可能是发送延迟，再等一下
        await asyncio.sleep(2)
        remaining = await _get_input_text(page)
        if remaining and remaining.strip() == content.strip():
            await _save_debug_info(page, "send_not_cleared")
            return {"success": False, "msg": "评论框未清空，发送可能失败"}

    await _save_debug_info(page, "send_ok")
    return {"success": True, "msg": "ok"}


async def _find_reply_btn(page, reply_cid: str):
    """在评论列表中找到指定 cid 评论的回复按钮。"""
    # 尝试通过 data 属性定位
    selectors = [
        f'div[data-cid="{reply_cid}"] span:has-text("回复")',
        f'div[data-cid="{reply_cid}"] div:has-text("回复")',
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            await el.wait_for(state="visible", timeout=3000)
            return el
        except Exception:
            continue
    # 兜底：滚动评论区找"回复"按钮
    reply_links = page.locator('span:has-text("回复")')
    count = await reply_links.count()
    if count > 0:
        logger.info("found %d reply links, clicking first", count)
        return reply_links.first
    return None


async def _check_error_toast(page) -> str:
    """检查页面上是否出现错误 toast 提示。"""
    toast_selectors = [
        'div[class*="toast"] span',
        'div[class*="Toast"] span',
        'div[class*="semi-toast"] span',
        'div[class*="notice"] span',
    ]
    for sel in toast_selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible():
                text = (await el.text_content() or "").strip()
                if text:
                    logger.warning("toast error: %s", text)
                    return text
        except Exception:
            continue
    return ""


async def _get_input_text(page) -> str:
    """获取评论输入框当前文本。"""
    for sel in _COMMENT_INPUT_SELECTORS[:4]:
        try:
            el = page.locator(sel).first
            if await el.is_visible():
                return (await el.text_content() or "").strip()
        except Exception:
            continue
    return ""


async def send_douyin_comment(
    *,
    cookie_str: str,
    aweme_id: str,
    content: str,
    reply_to_cid: str = "",
    reply_to_text: str = "",
    reply_to_nickname: str = "",
    timeout_seconds: int = 90,
) -> dict:
    """发送抖音评论/回复（UI 自动化方式，接口签名兼容）。"""
    if not cookie_str:
        return {"success": False, "msg": "Cookie 未配置"}
    if not aweme_id:
        return {"success": False, "msg": "aweme_id 为空"}
    if not content:
        return {"success": False, "msg": "发送内容为空"}

    pw = browser = None
    try:
        pw, browser, context = await asyncio.wait_for(
            _launch_browser(cookie_str), timeout=30
        )
        try:
            page = await asyncio.wait_for(
                _goto_video(context, aweme_id), timeout=45
            )
            result = await asyncio.wait_for(
                _type_and_send(page, content, reply_to_cid),
                timeout=timeout_seconds - 30,
            )
            return result
        finally:
            await browser.close()
            await pw.stop()
    except asyncio.TimeoutError:
        msg = f"发送超时（{timeout_seconds}s）"
    except Exception as e:
        logger.error("send douyin comment failed: %s", e, exc_info=True)
        msg = str(e)[:500]
    # cleanup on error
    if browser:
        try:
            await browser.close()
        except Exception:
            pass
    if pw:
        try:
            await pw.stop()
        except Exception:
            pass
    return {"success": False, "msg": msg}

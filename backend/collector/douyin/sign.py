"""抖音 a_bogus 签名模块

基于 execjs 调用 douyin_sign.js 生成签名参数。
"""
import os
import random

import execjs

_JS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "libs", "douyin_sign.js"
)

_sign_obj = None


def _get_sign_obj():
    global _sign_obj
    if _sign_obj is None:
        with open(_JS_PATH, encoding="utf-8-sig") as f:
            _sign_obj = execjs.compile(f.read())
    return _sign_obj


def get_web_id() -> str:
    def e(t):
        if t is not None:
            return str(t ^ (int(16 * random.random()) >> (t // 4)))
        return "".join(
            [str(int(1e7)), "-", str(int(1e3)), "-", str(int(4e3)),
             "-", str(int(8e3)), "-", str(int(1e11))]
        )
    web_id = "".join(
        e(int(x)) if x in "018" else x for x in e(None)
    )
    return web_id.replace("-", "")[:19]


def get_a_bogus(uri: str, query_string: str, user_agent: str) -> str:
    sign_js_name = "sign_datail"
    if "/reply" in uri:
        sign_js_name = "sign_reply"
    return _get_sign_obj().call(sign_js_name, query_string, user_agent)

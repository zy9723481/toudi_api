#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智联招聘 CDP API 测试脚本 v2
通过 Chrome DevTools Protocol 从真实浏览器发起 API 请求。

已验证的真实 API（2026-05 浏览器抓包）：
  - 用户详情: GET /c/i/user/detail?detail=true&at=...&rt=...&_v=...&x-zp-page-request-id=...
  - 城市信息: GET /c/i/city-page/user-city?...
  - 搜索数据: GET /c/i/search/base/data?...
  - 未读消息: GET /c/i/user/unread-message?...
  - 搜索岗位: POST /c/i/search/positions (加密参数，需CDP)

所有API必需的认证参数：
  - at      = Cookie中的at值（token）
  - rt      = Cookie中的rt值（refresh token）
  - _v      = 随机浮点数（0-1, 8位小数）
  - x-zp-page-request-id = UUID-毫秒时间戳

使用方法：
  1. Chrome 以 --remote-debugging-port=9222 启动
  2. Chrome 已登录 zhaopin.com 并打开搜索页
  3. python test_zhilian_cdp.py
"""

import json
import os
import sys
import time
import uuid
import random
from datetime import datetime
from urllib.parse import urlencode


# ==================== 配置 ====================

DEBUG_PORT = 9222
MAIN_DOMAIN = "zhaopin.com"


class CDPClient:
    """Chrome DevTools Protocol 客户端"""

    def __init__(self, port: int = 9222):
        import requests
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self._req = requests
        self._msg_id = 0

    def list_tabs(self) -> list:
        try:
            resp = self._req.get(f"{self.base_url}/json", timeout=5)
            return resp.json()
        except Exception as e:
            print(f"[ERROR] 无法连接Chrome调试端口 {self.port}: {e}")
            return []

    def find_tab(self, domain: str) -> dict:
        tabs = self.list_tabs()
        for tab in tabs:
            if domain in tab.get("url", ""):
                return tab
        if tabs:
            return tabs[0]
        return {}

    def connect(self, ws_url: str):
        import websocket
        self._ws = websocket.create_connection(ws_url, timeout=15)
        self._msg_id = 0

    def close(self):
        if hasattr(self, '_ws') and self._ws:
            self._ws.close()

    def send_cmd(self, method: str, params: dict = None) -> dict:
        """发送CDP命令并等待响应"""
        self._msg_id += 1
        msg_id = self._msg_id
        cmd = json.dumps({"id": msg_id, "method": method, "params": params or {}})
        self._ws.send(cmd)

        while True:
            try:
                chunk = self._ws.recv()
                msg = json.loads(chunk)
                if msg.get("id") == msg_id:
                    return msg.get("result", {})
                if "error" in msg:
                    return {"error": str(msg["error"])}
            except Exception as e:
                return {"error": str(e)}

    def navigate(self, url: str):
        return self.send_cmd("Page.navigate", {"url": url})

    def evaluate(self, js_code: str, await_promise: bool = False) -> dict:
        params = {"expression": js_code, "returnByValue": True}
        if await_promise:
            params["awaitPromise"] = True
        return self.send_cmd("Runtime.evaluate", params)

    def get_cookies(self, url: str = None) -> dict:
        if not url:
            url = f"https://www.{MAIN_DOMAIN}"
        result = self.send_cmd("Network.getCookies", {"urls": [url]})
        cookies = {}
        for c in result.get("cookies", []):
            cookies[c["name"]] = c["value"]
        return cookies

    def fetch(self, url: str, method: str = "GET",
              body: str = None, extra_headers: dict = None) -> dict:
        """通过浏览器fetch API发起请求"""
        fetch_opts = {
            "method": method,
            "credentials": "include",
            "headers": {"Accept": "application/json, text/plain, */*"},
        }
        if body:
            fetch_opts["body"] = body
            fetch_opts["headers"]["Content-Type"] = "application/json"
        if extra_headers:
            fetch_opts["headers"].update(extra_headers)

        js = f"""
        (async () => {{
            try {{
                const resp = await fetch({json.dumps(url)}, {json.dumps(fetch_opts)});
                const status = resp.status;
                const ct = resp.headers.get('Content-Type') || '';
                const text = await resp.text();
                return JSON.stringify({{
                    status: status,
                    contentType: ct,
                    body: text,
                    bodyLen: text.length,
                    isJson: ct.includes('json') || text.startsWith('{{'),
                }});
            }} catch(e) {{
                return JSON.stringify({{error: e.toString()}});
            }}
        }})()
        """

        result = self.evaluate(js, await_promise=True)
        if "error" in result:
            return {"error": str(result["error"])}

        value = result.get("result", {}).get("value")
        if not value:
            return {"error": "no result value", "raw": str(result)[:300]}

        try:
            data = json.loads(value)
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    return {"raw": data[:500]}
            if data.get("isJson") and data.get("body"):
                try:
                    data["jsonBody"] = json.loads(data["body"])
                except json.JSONDecodeError:
                    pass
            return data
        except json.JSONDecodeError:
            return {"raw": str(value)[:500]}


def build_auth_params(at: str, rt: str) -> str:
    """构建认证查询参数"""
    _v = str(round(random.random(), 8))
    req_id = str(uuid.uuid4()) + "-" + str(int(time.time() * 1000))
    return f"at={at}&rt={rt}&_v={_v}&x-zp-page-request-id={req_id}"


def test_api(cdp, name, base_url, params_str="", method="GET", body=None):
    """测试单个API并打印结果"""
    url = f"{base_url}?{params_str}" if params_str else base_url

    print(f"\n{'─'*60}")
    print(f"  {name}")
    print(f"  {method} {url[:200]}")

    result = cdp.fetch(url, method=method, body=body)

    if "error" in result:
        print(f"  [FAIL] CDP错误: {str(result['error'])[:200]}")
        return None

    status = result.get("status", "?")
    ct = result.get("contentType", "")
    body_len = result.get("bodyLen", 0)
    print(f"  HTTP {status} | {ct} | {body_len} bytes")

    if result.get("jsonBody"):
        data = result["jsonBody"]
        code = data.get("code", "?")
        msg = data.get("message", data.get("msg", ""))
        print(f"  API Code: {code} | Msg: {msg}")

        if code in (200, 0, "200", "0"):
            print(f"  [OK] 成功")
            inner = data.get("data", data)
            if isinstance(inner, dict):
                # 显示关键字段
                for key in ['Name', 'Id', 'userId', 'Resume', 'numTotal', 'numFound',
                           'results', 'FeedBackUnReadCount', 'currentIdentity']:
                    if key in inner:
                        val = inner[key]
                        if isinstance(val, dict):
                            print(f"    {key}: {json.dumps(val, ensure_ascii=False)[:150]}")
                        elif isinstance(val, list):
                            print(f"    {key}: [{len(val)} items]")
                        else:
                            print(f"    {key}: {val}")
            return data
        else:
            print(f"  [FAIL] code={code} msg={msg}")
    else:
        body_preview = result.get("body", "")[:200]
        print(f"  Body: {body_preview}")

    return None


def main():
    print("=" * 70)
    print(f"  智联招聘 CDP API 测试 v2")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Step 1: 连接CDP
    print("\n[*] 连接 Chrome DevTools Protocol...")
    cdp = CDPClient(DEBUG_PORT)
    tabs = cdp.list_tabs()
    if not tabs:
        print("[ERROR] 无法连接到Chrome!")
        print(r"  请确保Chrome以 chrome.exe --remote-debugging-port=9222 启动")
        return
    print(f"   发现 {len(tabs)} 个标签页")

    tab = cdp.find_tab(MAIN_DOMAIN)
    if not tab:
        print(f"[ERROR] 未找到智联招聘标签页")
        return

    ws_url = tab.get("webSocketDebuggerUrl", "")
    if not ws_url:
        print("[ERROR] 无法获取WebSocket URL")
        return

    print(f"   目标: {tab.get('title', '')[:80]}")
    cdp.connect(ws_url)

    # Step 2: 提取Cookie
    print("\n[*] 提取Cookie...")
    cookies = cdp.get_cookies()
    print(f"   {len(cookies)} 个Cookie")
    at = cookies.get("at", "")
    rt = cookies.get("rt", "")

    if not at or not rt:
        print("[ERROR] 缺少 at/rt token，请确保浏览器已登录")
        cdp.close()
        return

    print(f"   at: {at[:20]}...")
    print(f"   rt: {rt[:20]}...")
    if "scrd_user_name" in cookies:
        from urllib.parse import unquote
        print(f"   用户: {unquote(cookies['scrd_user_name'])}")

    # Step 3: 测试真实API端点
    print(f"\n{'='*70}")
    print("测试已验证的真实API端点")
    print(f"{'='*70}")

    auth = build_auth_params(at, rt)
    success = 0
    total = 0

    # --- 用户详情 ---
    total += 1
    r = test_api(cdp, "用户详情",
                 "https://fe-api.zhaopin.com/c/i/user/detail",
                 f"detail=true&{auth}")
    if r:
        success += 1
        # 提取简历ID
        resume_data = r.get("data", {}).get("Resume", {})
        resume_id = resume_data.get("Id", "") if isinstance(resume_data, dict) else ""
        resume_number = resume_data.get("ResumeNumber", "") if isinstance(resume_data, dict) else ""
        print(f"    简历ID: {resume_id}")
        print(f"    简历编号: {resume_number}")

    time.sleep(0.3)

    # --- 城市信息 ---
    total += 1
    city_auth = build_auth_params(at, rt)
    r = test_api(cdp, "城市信息",
                 "https://fe-api.zhaopin.com/c/i/city-page/user-city",
                 f"ipCity=&ipProvince=&userDesiredCity=&{city_auth}")
    if r:
        success += 1

    time.sleep(0.3)

    # --- 搜索基础数据 ---
    total += 1
    search_auth = build_auth_params(at, rt)
    r = test_api(cdp, "搜索基础数据",
                 "https://fe-api.zhaopin.com/c/i/search/base/data",
                 search_auth)
    if r:
        success += 1

    time.sleep(0.3)

    # --- 未读消息 ---
    total += 1
    msg_auth = build_auth_params(at, rt)
    r = test_api(cdp, "未读消息",
                 "https://fe-api.zhaopin.com/c/i/user/unread-message",
                 msg_auth)
    if r:
        success += 1

    time.sleep(0.3)

    # --- 实验配置 ---
    total += 1
    exp_auth = build_auth_params(at, rt)
    r = test_api(cdp, "实验配置",
                 "https://fe-api.zhaopin.com/c/i/experiment/config/initialize",
                 exp_auth)
    if r:
        success += 1

    time.sleep(0.3)

    # --- 搜索（废弃的老接口） ---
    total += 1
    r = test_api(cdp, "搜索(旧接口/c/i/sou)",
                 "https://fe-api.zhaopin.com/c/i/sou",
                 f"kw=Python&cityId=489&start=0&pageSize=15&kt=3&_v={str(round(random.random(),8))}")
    if r:
        # 检查是否有实际数据
        data = r.get("data", {})
        if isinstance(data, dict) and data.get("numTotal", 0) > 0:
            success += 1
        else:
            print(f"  [WARN] 旧接口返回空数据，已废弃")

    # Step 4: 汇总
    print(f"\n{'='*70}")
    print(f"测试汇总: {success}/{total} 成功")
    print(f"{'='*70}")

    if success >= 4:
        print(f"\n[OK] 核心API验证通过！")
        print(f"  可用端点:")
        print(f"    - 用户详情: /c/i/user/detail")
        print(f"    - 城市信息: /c/i/city-page/user-city")
        print(f"    - 搜索数据: /c/i/search/base/data")
        print(f"    - 未读消息: /c/i/user/unread-message")
        print(f"    - 实验配置: /c/i/experiment/config/initialize")
        print(f"\n  认证参数: at, rt, _v, x-zp-page-request-id")
        print(f"  搜索接口: POST /c/i/search/positions (加密，需进一步破解)")

    cdp.close()
    print(f"{'='*70}")


if __name__ == "__main__":
    main()

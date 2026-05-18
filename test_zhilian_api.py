#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智联招聘 API 测试脚本 v4
使用真实API端点（2026-05 CDP抓包验证），通过 requests 库直接调用。

已验证的真实接口：
  - 用户详情: GET /c/i/user/detail?detail=true&at=...&rt=...&_v=...&x-zp-page-request-id=...
  - 城市信息: GET /c/i/city-page/user-city?...
  - 搜索数据: GET /c/i/search/base/data?...
  - 未读消息: GET /c/i/user/unread-message?...
  - 实验配置: GET /c/i/experiment/config/initialize?...

认证参数（所有接口必需）：
  - at: Cookie中的access token
  - rt: Cookie中的refresh token
  - _v: 随机浮点数(0-1, 8位小数)
  - x-zp-page-request-id: UUID-毫秒时间戳

使用方法：
  1. 确保 Chrome 已登录 zhaopin.com
  2. python test_zhilian_api.py
"""

import json
import os
import re
import sys
import time
import uuid
import random
from datetime import datetime
from urllib.parse import unquote


# ==================== 配置 ====================

MANUAL_TOKEN = ""

# ==================== API端点（已验证） ====================

API_PROBES = [
    # --- 用户相关 ---
    {
        "name": "用户详情",
        "url": "https://fe-api.zhaopin.com/c/i/user/detail",
        "params": "detail=true",
        "desc": "获取用户姓名、简历ID、头像等",
        "key_fields": ["Name", "Id", "Resume"],
    },
    {
        "name": "未读消息",
        "url": "https://fe-api.zhaopin.com/c/i/user/unread-message",
        "desc": "获取未读消息数量",
    },

    # --- 搜索相关 ---
    {
        "name": "搜索基础数据",
        "url": "https://fe-api.zhaopin.com/c/i/search/base/data",
        "desc": "获取搜索页下拉数据(行业/职能/薪资等)",
        "key_fields": ["companyType", "jobType", "hotCity"],
    },
    {
        "name": "搜索(旧接口)",
        "url": "https://fe-api.zhaopin.com/c/i/sou",
        "params": "kw=Python&cityId=489&start=0&pageSize=15&kt=3",
        "desc": "已废弃的老接口，返回空数据",
    },

    # --- 城市 ---
    {
        "name": "城市信息",
        "url": "https://fe-api.zhaopin.com/c/i/city-page/user-city",
        "params": "ipCity=&ipProvince=&userDesiredCity=",
        "desc": "获取用户城市偏好",
    },

    # --- 配置 ---
    {
        "name": "实验配置",
        "url": "https://fe-api.zhaopin.com/c/i/experiment/config/initialize",
        "desc": "获取A/B实验配置",
    },

    # --- 页面验证 ---
    {
        "name": "www首页",
        "url": "https://www.zhaopin.com/",
        "is_page": True,
        "desc": "检查Cookie是否过期",
    },
]

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://sou.zhaopin.com/",
    "Sec-Ch-Ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

PAGE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Sec-Ch-Ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
}


def check_import():
    try:
        import requests
        return requests
    except ImportError:
        print("[ERROR] pip install requests")
        sys.exit(1)


def safe_s(text, max_len=200):
    if not text:
        return ""
    text = str(text)[:max_len]
    try:
        text.encode('gbk')
        return text
    except UnicodeEncodeError:
        return text.encode('gbk', errors='replace').decode('gbk', errors='replace')


def safe_p(text):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('gbk', errors='replace').decode('gbk', errors='replace'))


def auto_extract_cookies():
    """自动从浏览器提取智联Cookie"""
    print("\n[*] 自动提取智联招聘Cookie...")

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from boss_zhipin_auto import BrowserAuthHelper
        auth = BrowserAuthHelper()
        cookies = auth.extract_cookies(platform='zhilian')
        if cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            print(f"   [OK] BrowserAuthHelper 提取 {len(cookies)} 个Cookie")
            return cookie_str, cookies
        else:
            print("   [WARN] BrowserAuthHelper 未找到智联Cookie")
    except Exception as e:
        print(f"   [WARN] 主程序导入失败 ({e})")

    try:
        import browser_cookie3
        cookies = {}
        for domain in ('.zhaopin.com', 'zhaopin.com'):
            try:
                cj = browser_cookie3.chrome(domain_name=domain)
                for cookie in cj:
                    if cookie.domain and 'zhaopin' in cookie.domain:
                        cookies[cookie.name] = cookie.value
                if cookies:
                    break
            except Exception:
                pass
        if cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            print(f"   [OK] browser_cookie3 提取 {len(cookies)} 个Cookie")
            return cookie_str, cookies
        print("   [WARN] browser_cookie3 未找到智联Cookie")
    except Exception as e:
        print(f"   [WARN] browser_cookie3 失败: {e}")

    return None, None


def parse_cookies(token: str) -> dict:
    cookies = {}
    for part in token.split(";"):
        part = part.strip()
        if "=" in part:
            key, val = part.split("=", 1)
            key = key.strip()
            val = val.strip()
            if key and val:
                cookies[key] = val
    return cookies


def build_auth_params(at: str, rt: str) -> str:
    """构建认证查询参数"""
    _v = str(round(random.random(), 8))
    req_id = str(uuid.uuid4()) + "-" + str(int(time.time() * 1000))
    return f"at={at}&rt={rt}&_v={_v}&x-zp-page-request-id={req_id}"


def test_endpoint(requests, session, probe: dict, at: str, rt: str) -> dict:
    """测试单个API端点"""
    name = probe["name"]
    url = probe["url"]
    extra_params = probe.get("params", "")
    is_page = probe.get("is_page", False)

    result = {
        "name": name, "url": url, "status_code": None,
        "content_type": None, "code": None, "message": "",
        "success": False, "error": None, "sample_data": None,
    }

    try:
        headers = dict(PAGE_HEADERS if is_page else HEADERS)

        if is_page:
            full_url = url
        else:
            auth = build_auth_params(at, rt)
            sep = "&" if "?" in url or extra_params else ""
            params_str = f"{extra_params}&{auth}" if extra_params else auth
            full_url = f"{url}?{params_str}"

        resp = session.get(full_url, headers=headers, timeout=15, allow_redirects=True)
        result["status_code"] = resp.status_code
        result["content_type"] = resp.headers.get("Content-Type", "")

        final_lower = resp.url.lower()
        if "login" in final_lower or "passport" in final_lower:
            result["error"] = "重定向到登录页 -> Cookie无效"
            return result
        if "security" in final_lower or "verify" in final_lower or "captcha" in final_lower:
            result["error"] = "触发安全验证页"
            return result

        if is_page:
            if resp.status_code == 200:
                result["success"] = True
                title = re.search(r'<title>(.*?)</title>', resp.text, re.I)
                result["message"] = f"页面: {title.group(1).strip()}" if title else "加载成功"
            else:
                result["error"] = f"HTTP {resp.status_code}"
            return result

        if "text/html" in result["content_type"]:
            result["error"] = f"返回HTML({len(resp.content)}字节)"
            result["sample_data"] = safe_s(resp.text, 200)
            return result

        if "application/json" in result["content_type"] or resp.text.strip().startswith("{"):
            data = resp.json()
            code = data.get("code", -999)
            msg = data.get("message", data.get("msg", ""))
            result["code"] = code
            result["message"] = msg

            if code in (200, 0, "200", "0"):
                result["success"] = True
                inner = data.get("data", data)
                sample = {}
                if isinstance(inner, dict):
                    for k in probe.get("key_fields", []):
                        if k in inner:
                            val = inner[k]
                            if isinstance(val, dict):
                                sample[k] = f"{{...{len(val)} keys}}"
                            elif isinstance(val, list):
                                sample[k] = f"[{len(val)} items]"
                            else:
                                sample[k] = val
                result["sample_data"] = json.dumps(sample, ensure_ascii=False) if sample else safe_s(json.dumps(data, ensure_ascii=False), 300)
            elif code == -999:
                result["success"] = True
                result["message"] = "(无code字段)"
                result["sample_data"] = safe_s(json.dumps(data, ensure_ascii=False), 300)
            else:
                result["error"] = f"code={code} msg={safe_s(str(msg), 100)}"
        else:
            result["error"] = f"非JSON: {result['content_type']}"
            result["sample_data"] = safe_s(resp.text, 200)

    except Exception as e:
        result["error"] = str(e)[:100]

    return result


def main():
    print("=" * 70)
    print(f"  智联招聘 API 测试脚本 v4")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  使用真实端点（2026-05 CDP抓包验证）")
    print("=" * 70)

    requests = check_import()

    # Step 1: Cookie
    token, cookie_dict = auto_extract_cookies()
    if token:
        print("\n   [OK] 使用自动提取的Cookie")
    else:
        token = MANUAL_TOKEN.strip()
        if token:
            print("\n   [WARN] 使用手动 TOKEN")
            cookie_dict = parse_cookies(token)
        else:
            print("\n[ERROR] 无法获取智联Cookie!")
            return

    cookies = parse_cookies(token)
    at = cookies.get("at", "")
    rt = cookies.get("rt", "")

    # Step 2: Cookie分析
    print(f"\n{'─'*60}")
    print("Cookie 分析")
    print(f"{'─'*60}")
    print(f"   总数: {len(cookies)}")

    for key in ['at', 'rt', 'x-zp-client-id', 'x-zp-device-sn', 'scrd_user_id', 'scrd_user_name']:
        if key in cookies:
            val = cookies[key]
            preview = val[:40] + "..." if len(val) > 40 else val
            print(f"   [OK] {key}: {preview}")
        else:
            print(f"   [MISS] {key}")

    if not at or not rt:
        print("\n[ERROR] Cookie中缺少 at/rt token，无法调用API")
        return

    if 'scrd_user_name' in cookies:
        safe_p(f"\n   用户: {unquote(cookies['scrd_user_name'])}")

    # Step 3: 创建Session
    print(f"\n{'─'*60}")
    print("创建 Session")
    print(f"{'─'*60}")

    session = requests.Session()
    session.trust_env = False
    session.headers.update(HEADERS)
    for key, val in cookies.items():
        session.cookies.set(key, val, domain=".zhaopin.com", path="/")

    xzp = cookies.get("x-zp-client-id", "")
    if xzp:
        HEADERS["x-zp-client-id"] = xzp
        session.headers["x-zp-client-id"] = xzp
        print(f"   x-zp-client-id: {xzp}")

    print(f"   at: {at[:20]}...")
    print(f"   rt: {rt[:20]}...")
    print(f"   Session 已创建")

    # Step 4: 测试API
    print(f"\n{'='*70}")
    print("测试API端点")
    print(f"{'='*70}")

    results = []
    success_count = 0

    for probe in API_PROBES:
        name = probe["name"]
        desc = probe.get("desc", "")
        print(f"\n{'─'*60}")
        print(f"  {name}")
        if desc:
            print(f"  说明: {desc}")

        result = test_endpoint(requests, session, probe, at, rt)
        results.append(result)

        print(f"  状态码: {result['status_code']}")
        print(f"  API Code: {result['code']}")
        if result["success"]:
            print(f"  [OK] 成功")
            success_count += 1
            if result["sample_data"]:
                safe_p(f"  数据: {result['sample_data']}")
        else:
            safe_p(f"  [FAIL] {result.get('error', '未知')}")
            if result["sample_data"]:
                safe_p(f"  响应片段: {result['sample_data']}")

        time.sleep(0.3)

    # Step 5: 汇总
    print(f"\n{'='*70}")
    print(f"测试汇总")
    print(f"{'='*70}")
    total = len(results)
    print(f"  总接口数: {total}")
    print(f"  成功: {success_count}")
    print(f"  失败: {total - success_count}")

    api_results = [r for r in results if not probe.get("is_page", False)]
    api_ok = [r for r in api_results if r["success"]]

    print(f"\n  成功列表:")
    for r in results:
        if r["success"]:
            print(f"    [OK] {r['name']:15s} code={r['code']} {r['message']}")

    failed = [r for r in results if not r["success"]]
    if failed:
        print(f"\n  失败列表:")
        for r in failed:
            print(f"    [FAIL] {r['name']:15s} -> {r.get('error', '未知')}")

    if api_ok:
        print(f"\n[OK] 核心GET API验证通过！可在主程序中使用智联接口。")
        print(f"  注意: 岗位搜索接口需要CDP浏览器代理（加密POST，需后续适配）")

    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"zhilian_api_test_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cookie_count": len(cookies),
            "total": total,
            "success": success_count,
            "api_success": len(api_ok),
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果: {filename}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()

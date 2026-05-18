#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOSS直聘 API 独立测试脚本
自动从浏览器提取Cookie，调用岗位搜索 + 岗位详情接口，结果输出到控制台。

使用方法：
  1. 确保 Chrome 已登录 zhipin.com
  2. python test_boss_api.py

Cookie 获取策略（自动）：
  1. CDP远程调试 → 从运行中的Chrome实时提取（推荐，token最新）
  2. Windows DPAPI解密 → 读取Chrome加密Cookie数据库
  3. browser_cookie3 → 跨浏览器通用提取
  4. 手动TOKEN → 如以上均失败，可粘贴Cookie到下方TOKEN变量
"""

import json
import os
import sys
import time
from datetime import datetime

# ==================== 配置区 ====================

# 搜索参数
KEYWORD = "软件测试"     # 搜索关键词，留空 = 不限
LOCATION = "全国"        # 工作城市，如：北京、上海、深圳、全国
PAGE_SIZE = 15           # 每页数量
DETAIL_COUNT = 5         # 获取详情的岗位数量

# 手动Cookie（仅自动提取失败时作为降级方案）
# 格式: "__zp_stoken__=xxx; wt2=xxx; wbg=xxx"
MANUAL_TOKEN = ""

# ==================== API 配置 ====================

BASE_URL = "https://www.zhipin.com"
SEARCH_URL = "/wapi/zpgeek/search/joblist.json"
DETAIL_URL = "/wapi/zpgeek/job/detail.json"

# 城市编码映射
CITY_CODE_MAP = {
    "北京": "101010100", "上海": "101020100", "广州": "101280100",
    "深圳": "101280600", "杭州": "101210100", "成都": "101270100",
    "武汉": "101200100", "南京": "101190100", "西安": "101110100",
    "长沙": "101250100", "苏州": "101190400", "重庆": "101040100",
    "天津": "101030100", "合肥": "101220100", "郑州": "101180100",
    "厦门": "101230200", "青岛": "101120200", "大连": "101070200",
    "济南": "101120100", "福州": "101230100", "沈阳": "101070100",
    "东莞": "101281600", "佛山": "101282800", "宁波": "101210400",
    "昆明": "101290100", "贵阳": "101260100", "哈尔滨": "101050100",
    "长春": "101060100", "石家庄": "101090100", "太原": "101100100",
    "南昌": "101240100", "南宁": "101300100", "海口": "101310100",
    "兰州": "101160100", "乌鲁木齐": "101130100", "呼和浩特": "101080100",
}
CITY_NATIONAL = "100010000"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Origin": BASE_URL,
    "Pragma": "no-cache",
    "Referer": f"{BASE_URL}/web/geek/job",
    "Sec-Ch-Ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}


def resolve_city(location: str) -> str:
    """城市名 → 城市编码"""
    if not location or location in ("全国", "不限", ""):
        return CITY_NATIONAL
    if location.isdigit():
        return location
    if location in CITY_CODE_MAP:
        return CITY_CODE_MAP[location]
    for name, code in CITY_CODE_MAP.items():
        if location in name or name in location:
            return code
    return CITY_NATIONAL


def parse_cookies(token: str) -> dict:
    """解析 Cookie 字符串为字典"""
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


def check_import():
    """检查 requests 库是否可用"""
    try:
        import requests
        return requests
    except ImportError:
        print("❌ 缺少 requests 库，请运行: pip install requests")
        sys.exit(1)


def auto_extract_cookies():
    """自动从浏览器提取BOSS直聘Cookie，复用主程序的BrowserAuthHelper"""
    print("\n🔍 自动提取Cookie...")

    # 策略1: 导入主程序的 BrowserAuthHelper（功能最全）
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from boss_zhipin_auto import BrowserAuthHelper
        auth = BrowserAuthHelper()
        cookies = auth.extract_cookies(platform='boss')
        if cookies:
            # 转为Cookie字符串
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            print(f"   ✅ BrowserAuthHelper 成功提取 {len(cookies)} 个Cookie")
            return cookie_str
        else:
            print("   ⚠️  BrowserAuthHelper 未找到Cookie，尝试其他方式...")
    except Exception as e:
        print(f"   ⚠️  主程序导入失败 ({e})，尝试 browser-cookie3...")

    # 策略2: 直接用 browser-cookie3 提取
    try:
        import browser_cookie3
        cj = browser_cookie3.chrome(domain_name='zhipin.com')
        cookies = {}
        for cookie in cj:
            if cookie.domain and 'zhipin.com' in cookie.domain:
                cookies[cookie.name] = cookie.value
        if any('zp_stoken' in k.lower() for k in cookies):
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            print(f"   ✅ browser_cookie3 提取到 {len(cookies)} 个Cookie")
            return cookie_str

        # 降级：全量获取后筛选
        cj = browser_cookie3.chrome()
        for cookie in cj:
            if cookie.domain and 'zhipin.com' in cookie.domain:
                cookies[cookie.name] = cookie.value
        if any('zp_stoken' in k.lower() for k in cookies):
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            print(f"   ✅ browser_cookie3(全量) 提取到 {len(cookies)} 个Cookie")
            return cookie_str

        print("   ⚠️  browser_cookie3 未找到zhipin.com的Cookie")
    except Exception as e:
        print(f"   ⚠️  browser_cookie3 失败: {e}")
        print("   → 请安装: pip install browser-cookie3")

    return None


def fetch_jobs(requests, session, keyword: str, location: str) -> list:
    """搜索岗位列表"""
    city_code = resolve_city(location)
    params = {
        "query": keyword or "",
        "city": city_code,
        "page": 1,
        "pageSize": PAGE_SIZE,
    }

    print(f"\n{'='*60}")
    print(f"🔍 搜索岗位")
    print(f"   关键词: {keyword or '(不限)'}")
    print(f"   城市: {location} (编码: {city_code})")
    print(f"   页大小: {PAGE_SIZE}")
    print(f"   请求URL: {BASE_URL}{SEARCH_URL}")
    print(f"   请求参数: {json.dumps(params, ensure_ascii=False)}")
    print(f"{'='*60}")

    url = f"{BASE_URL}{SEARCH_URL}"
    resp = session.get(url, params=params, timeout=15)

    print(f"\n📡 响应状态码: {resp.status_code}")
    print(f"   Content-Type: {resp.headers.get('Content-Type', '')}")

    if "text/html" in resp.headers.get("Content-Type", ""):
        print("   ❌ 返回了HTML页面 — Cookie 可能已过期，请重新获取")
        return []

    data = resp.json()
    code = data.get("code", -1)
    msg = data.get("message", "")

    print(f"   code: {code}")
    print(f"   message: {msg}")

    if code != 0:
        print(f"   ❌ API返回错误码 {code}: {msg}")
        if code == 37:
            print("   → code=37: zp_stoken 过期，需要在浏览器中刷新页面后重新复制Cookie")
        return []

    zp_data = data.get("zpData", data)
    job_list = zp_data.get("jobList", [])
    total_count = zp_data.get("totalCount", len(job_list))
    has_more = zp_data.get("hasMore", False)

    print(f"   总岗位数: {total_count}")
    print(f"   本次返回: {len(job_list)} 条")
    print(f"   还有更多: {has_more}")

    return job_list


def fetch_job_detail(requests, session, security_id: str, lid: str) -> dict:
    """获取岗位详情"""
    params = {"securityId": security_id}
    if lid:
        params["lid"] = lid

    print(f"\n{'='*60}")
    print(f"📋 获取岗位详情")
    print(f"   securityId: {security_id}")
    print(f"   lid: {lid}")
    print(f"   请求URL: {BASE_URL}{DETAIL_URL}")
    print(f"   请求参数: {json.dumps(params, ensure_ascii=False)}")
    print(f"{'='*60}")

    url = f"{BASE_URL}{DETAIL_URL}"
    resp = session.get(url, params=params, timeout=15)

    print(f"\n📡 响应状态码: {resp.status_code}")

    data = resp.json()
    code = data.get("code", -1)
    msg = data.get("message", "")

    print(f"   code: {code}")
    print(f"   message: {msg}")

    if code != 0:
        print(f"   ❌ API返回错误码 {code}: {msg}")
        return {}

    return data.get("zpData", data)


def print_job_list(jobs: list):
    """格式化打印岗位列表"""
    print(f"\n{'='*80}")
    print(f"📋 岗位列表 (共 {len(jobs)} 条)")
    print(f"{'='*80}")

    for i, job in enumerate(jobs, 1):
        print(f"\n{'─'*60}")
        print(f"  [{i:02d}] {job.get('jobName', '未知')}")
        print(f"  公司: {job.get('brandName', '未知')}")
        print(f"  规模: {job.get('brandScaleName', '')} | 阶段: {job.get('brandStageName', '')} | 行业: {job.get('brandIndustry', '')}")
        print(f"  城市: {job.get('cityName', '')} | 区域: {job.get('areaDistrict', '')}")
        print(f"  薪资: {job.get('salaryDesc', '')}")
        print(f"  学历: {job.get('jobDegree', '')}")
        print(f"  标签: {', '.join(job.get('jobLabels', []))}")
        print(f"  HR: {job.get('bossName', '')} | {job.get('bossTitle', '')}")
        print(f"  encryptJobId: {job.get('encryptJobId', '')}")
        print(f"  securityId: {job.get('securityId', '')}")
        print(f"  lid: {job.get('lid', '')}")


def print_job_detail(detail: dict, job: dict):
    """格式化打印岗位详情"""
    print(f"\n{'='*80}")
    print(f"📄 岗位详情")
    print(f"{'='*80}")

    # 递归打印所有字段
    def print_dict(d, indent=2):
        prefix = " " * indent
        if isinstance(d, dict):
            for key, value in d.items():
                if key in ("jobDescription", "postDescription", "jobDesc"):
                    print(f"\n{prefix}--- {key} (岗位描述) ---")
                    desc = str(value).replace("\\n", "\n")
                    print(f"{prefix}{desc}")
                elif isinstance(value, (dict, list)):
                    print(f"{prefix}{key}:")
                    print_dict(value, indent + 2)
                else:
                    val_str = str(value)
                    if len(val_str) > 120:
                        val_str = val_str[:120] + "..."
                    print(f"{prefix}{key}: {val_str}")
        elif isinstance(d, list):
            for idx, item in enumerate(d):
                print(f"{prefix}[{idx}]:")
                print_dict(item, indent + 2)
        else:
            print(f"{prefix}{str(d)[:200]}")

    print_dict(detail)

    # 提取岗位描述文本
    job_info = detail.get("jobInfo", detail)
    if isinstance(job_info, dict):
        desc = job_info.get("jobDescription", job_info.get("postDescription", ""))
    else:
        desc = ""
    if desc:
        print(f"\n{'─'*60}")
        print(f"📝 岗位描述 (纯文本, {len(desc)} 字符):")
        print(f"{'─'*60}")
        print(desc)


def main():
    print("=" * 60)
    print("  BOSS直聘 API 测试脚本")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 检查依赖
    requests = check_import()

    # 获取Cookie: 自动提取 > 手动Token
    token = auto_extract_cookies()
    if token:
        print("\n   ✅ 使用自动提取的Cookie")
    else:
        token = MANUAL_TOKEN.strip()
        if token:
            print("\n   ⚠️  自动提取失败，使用手动 TOKEN")
        else:
            print("\n❌ 无法获取Cookie！请确保Chrome已登录 zhipin.com")
            print("   或手动粘贴Cookie到 MANUAL_TOKEN 变量后重试")
            print("\n如何获取Cookie：")
            print("  1. Chrome 打开 https://www.zhipin.com 并登录")
            print("  2. F12 → Application → Cookies → www.zhipin.com")
            print("  3. 找到 __zp_stoken__, wt2, wbg 这几个Cookie")
            print('  4. 粘贴到 MANUAL_TOKEN = "__zp_stoken__=xxx; wt2=xxx; wbg=xxx"')
            return

    # 解析 Cookie 并创建 Session
    cookies = parse_cookies(token)
    print(f"\n🍪 解析到 {len(cookies)} 个Cookie:")
    for k in cookies:
        val_preview = cookies[k][:40] + "..." if len(cookies[k]) > 40 else cookies[k]
        print(f"   {k}: {val_preview}")

    has_stoken = any("zp_stoken" in k.lower() for k in cookies)
    has_wt2 = any("wt2" == k for k in cookies)
    print(f"   关键Cookie: zp_stoken={'✅' if has_stoken else '❌'}, wt2={'✅' if has_wt2 else '❌'}")

    if not has_stoken:
        print("\n❌ Cookie 中缺少 __zp_stoken__，无法调用API")
        return

    # 创建 Session
    session = requests.Session()
    session.trust_env = False
    session.headers.update(HEADERS)
    for key, val in cookies.items():
        session.cookies.set(key, val, domain=".zhipin.com", path="/")

    print("\n✅ Session 已创建，开始调用API...")

    # 步骤1: 搜索岗位
    jobs = fetch_jobs(requests, session, KEYWORD, LOCATION)
    if not jobs:
        print("\n❌ 未获取到岗位数据，请检查Cookie是否有效")
        return

    print_job_list(jobs)

    # 步骤2: 获取前N个岗位详情
    target_jobs = jobs[:DETAIL_COUNT]
    print(f"\n{'='*60}")
    print(f"📋 批量获取岗位详情 (共 {len(target_jobs)} 个)")
    print(f"{'='*60}")

    results = []
    success_count = 0
    for i, job in enumerate(target_jobs):
        security_id = job.get("securityId", "")
        lid = job.get("lid", "")
        encrypt_id = job.get("encryptJobId", "")

        print(f"\n[{i+1}/{len(target_jobs)}] {job.get('jobName', '未知')} @ {job.get('brandName', '')}")

        if not security_id:
            print(f"   ⚠️  缺少 securityId, 使用 encryptJobId 替代")
            if not encrypt_id:
                print(f"   ❌ 也没有 encryptJobId，跳过")
                results.append({
                    "job": {
                        "title": job.get("jobName", ""),
                        "company": job.get("brandName", ""),
                        "encryptJobId": encrypt_id,
                        "salary": job.get("salaryDesc", ""),
                        "city": job.get("cityName", ""),
                    },
                    "detail": None,
                    "error": "缺少 securityId/lid"
                })
                continue
            security_id = encrypt_id

        # 详情API有频率限制，每个间隔2秒
        if i > 0:
            print(f"   ⏳ 等待2秒（避免频率限制）...")
            time.sleep(2)

        detail = fetch_job_detail(requests, session, security_id, lid)
        if detail:
            success_count += 1
            # 提取岗位描述
            job_info = detail.get("jobInfo", detail) if isinstance(detail, dict) else {}
            desc = job_info.get("jobDescription", job_info.get("postDescription", "")) if isinstance(job_info, dict) else ""
            print(f"   ✅ 获取成功 ({len(desc)} 字符)")
            results.append({
                "job": {
                    "title": job.get("jobName", ""),
                    "company": job.get("brandName", ""),
                    "encryptJobId": encrypt_id,
                    "securityId": security_id,
                    "lid": lid,
                    "salary": job.get("salaryDesc", ""),
                    "city": job.get("cityName", ""),
                    "district": job.get("areaDistrict", ""),
                    "degree": job.get("jobDegree", ""),
                    "hr_name": job.get("bossName", ""),
                    "hr_title": job.get("bossTitle", ""),
                },
                "detail_raw": detail,
                "job_description": desc,
            })
        else:
            print(f"   ❌ 获取失败")
            results.append({
                "job": {
                    "title": job.get("jobName", ""),
                    "company": job.get("brandName", ""),
                    "encryptJobId": encrypt_id,
                    "securityId": security_id,
                    "lid": lid,
                    "salary": job.get("salaryDesc", ""),
                    "city": job.get("cityName", ""),
                },
                "detail": None,
                "error": "API返回错误或网络异常"
            })

    # 步骤3: 保存到JSON文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"boss_jobs_{timestamp}.json"
    output = {
        "search_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "keyword": KEYWORD,
        "location": LOCATION,
        "total_found": len(jobs),
        "detail_requested": len(target_jobs),
        "detail_success": success_count,
        "results": results,
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ 测试完成")
    print(f"   搜索到 {len(jobs)} 个岗位")
    print(f"   详情获取: {success_count}/{len(target_jobs)} 成功")
    print(f"   已保存到: {filename}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

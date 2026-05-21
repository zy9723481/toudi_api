# -*- coding: utf-8 -*-
"""
BOSS直聘智能投递助手 v2.0
基于 PyQt5 GUI + DeepSeek AI + MySQL/SQLite 双数据库
支持两种投递模式：
  1. API接口投递 — 快速、无需招呼语（BOSSApiClient + wapi端点）
  2. 浏览器自动投递 — 支持AI招呼语（DrissionPage + CDP）
"""

import sys
import os
import json
import time
import uuid
import random
import hashlib
import secrets
import string
import threading
import platform
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from datetime import datetime, timedelta
from urllib.parse import unquote
from typing import Dict, List, Optional, Callable

# ==================== GUI ====================
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QSpinBox,
    QCheckBox, QDateEdit, QRadioButton, QButtonGroup,
    QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QMessageBox, QSizePolicy, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QDate, QTimer
from PyQt5.QtGui import QFont, QColor, QTextCursor

# ==================== AI ====================
import openai

# ==================== 简历解析 ====================
import PyPDF2

# ==================== 数据库 ====================
try:
    import pymysql
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ==================== 浏览器自动化 ====================
try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    from DrissionPage.errors import PageDisconnectedError
    HAS_DRISSION = True
except ImportError:
    HAS_DRISSION = False

try:
    import browser_cookie3
    HAS_BROWSER_COOKIE3 = True
except ImportError:
    HAS_BROWSER_COOKIE3 = False

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


# ==================== 全局配置常量 ====================

DB_HOST = '101.42.35.88'
DB_PORT = 3306
DB_USER = 'boostoudi'
DB_PASSWORD = 'hRpMWyw7Lt4RATE2'
DB_NAME = 'boostoudi'

DEEPSEEK_API_KEY = "sk-669bceefaaf04c45a3f45f42d47a7f8e"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"

MIN_DELAY_SECONDS = 8
MAX_DELAY_SECONDS = 15
BATCH_SIZE = 10
BATCH_PAUSE_MINUTES = 3
FAILED_JOB_RETRY_DAYS = 7

MAX_DELIVERY_COUNT = 100
MAX_DAILY_DELIVERY = 200
DEFAULT_GREETING = "您好，我对贵公司的岗位很感兴趣，我的经验和技能与该岗位要求匹配，希望能有机会进一步沟通，谢谢！"

# BOSS直聘相关URL
BOSS_BASE_URL = "https://www.zhipin.com"
BOSS_LOGIN_URL = "https://www.zhipin.com/web/user/?ka=header-login"
BOSS_RESUME_URL = "https://www.zhipin.com/web/geek/resume"

# 岗位状态标记
JOB_STATUS_INIT = 0       # 初始
JOB_STATUS_DELIVERED = 1  # 已投递
JOB_STATUS_SKIPPED = 2    # 已跳过
JOB_STATUS_FAILED = 3     # 投递失败
JOB_STATUS_FILTERED = 4   # 匹配度不足
JOB_STATUS_TIME = 5       # 时间不符

# 城市编码映射（BOSS直聘，150+城市）
CITY_MAP = {
    "101010100": "北京", "101020100": "上海", "101030100": "天津", "101040100": "重庆",
    "101280100": "广州", "101280600": "深圳", "101280400": "佛山", "101281000": "东莞",
    "101281100": "中山", "101280700": "珠海", "101280900": "惠州", "101280300": "汕头",
    "101280200": "韶关", "101280500": "江门", "101280800": "肇庆", "101281200": "湛江",
    "101281300": "茂名", "101281400": "梅州", "101281500": "汕尾", "101281600": "河源",
    "101281700": "阳江", "101281800": "清远", "101281900": "潮州", "101282000": "揭阳",
    "101282100": "云浮",
    "101190100": "南京", "101190500": "苏州", "101190200": "无锡", "101191100": "常州",
    "101190500": "南通", "101190800": "徐州", "101190700": "扬州", "101190300": "镇江",
    "101190600": "盐城", "101191000": "泰州", "101190900": "淮安", "101191200": "连云港",
    "101191300": "宿迁",
    "101210100": "杭州", "101210400": "宁波", "101210700": "温州", "101210300": "嘉兴",
    "101210500": "湖州", "101210200": "绍兴", "101210600": "金华", "101210800": "衢州",
    "101210900": "舟山", "101211000": "台州", "101211100": "丽水",
    "101120100": "济南", "101120200": "青岛", "101120500": "烟台", "101120600": "潍坊",
    "101120300": "临沂", "101120700": "淄博", "101120800": "济宁", "101120900": "泰安",
    "101121000": "威海", "101121100": "德州", "101121200": "聊城", "101121300": "滨州",
    "101121400": "菏泽", "101121500": "枣庄", "101121600": "日照", "101121700": "东营",
    "101270100": "成都", "101270200": "绵阳", "101270300": "德阳", "101270400": "宜宾",
    "101270500": "南充", "101270600": "泸州", "101270700": "达州", "101270800": "乐山",
    "101270900": "凉山", "101271000": "内江", "101271100": "自贡", "101271200": "眉山",
    "101271300": "广安", "101271400": "攀枝花", "101271500": "遂宁", "101271600": "广元",
    "101090100": "石家庄", "101090200": "唐山", "101090300": "保定", "101090400": "廊坊",
    "101090500": "邯郸", "101090600": "沧州", "101090700": "邢台", "101090800": "秦皇岛",
    "101090900": "衡水", "101091000": "张家口", "101091100": "承德",
    "101180100": "郑州", "101180200": "洛阳", "101180300": "开封", "101180400": "南阳",
    "101180500": "新乡", "101180600": "安阳", "101180700": "许昌", "101180800": "平顶山",
    "101180900": "焦作", "101181000": "商丘", "101181100": "信阳", "101181200": "周口",
    "101200100": "武汉", "101200200": "襄阳", "101200300": "宜昌", "101200400": "荆州",
    "101200500": "黄冈", "101200600": "孝感", "101200700": "十堰", "101200800": "黄石",
    "101200900": "咸宁", "101201000": "恩施", "101201100": "荆门",
    "101250100": "长沙", "101250200": "株洲", "101250300": "湘潭", "101250400": "衡阳",
    "101250500": "邵阳", "101250600": "岳阳", "101250700": "常德", "101250800": "张家界",
    "101110100": "西安", "101110200": "咸阳", "101110300": "宝鸡", "101110400": "延安",
    "101110500": "汉中", "101110600": "榆林",
    "101070100": "沈阳", "101070200": "大连", "101070300": "鞍山", "101070400": "盘锦",
    "101230100": "福州", "101230200": "厦门", "101230300": "泉州", "101230400": "漳州",
    "101220100": "合肥", "101220200": "芜湖", "101220300": "蚌埠", "101220400": "淮南",
    "101240100": "南昌", "101240200": "九江", "101240300": "赣州",
    "101100100": "太原", "101100200": "临汾", "101100300": "大同",
    "101050100": "哈尔滨", "101050200": "齐齐哈尔", "101050300": "大庆",
    "101060100": "长春", "101060200": "吉林", "101060300": "四平",
    "101290100": "昆明", "101290200": "曲靖", "101290300": "玉溪",
    "101260100": "贵阳", "101260200": "遵义", "101260300": "毕节",
    "101300100": "南宁", "101300200": "桂林", "101300300": "柳州",
    "101160100": "兰州", "101160200": "天水", "101160300": "白银",
    "101080100": "呼和浩特", "101080200": "包头", "101080300": "鄂尔多斯",
    "101130100": "乌鲁木齐", "101130200": "昌吉",
    "101150100": "银川", "101150200": "石嘴山",
    "101140100": "西宁", "101140200": "海东",
    "101310100": "海口", "101310200": "三亚",
    "101320100": "拉萨",
}

CITY_NATIONAL = "100010000"

# 城市名称→编码反向映射
CITY_NAME_TO_CODE = {v: k for k, v in CITY_MAP.items()}

# BOSS直聘API端点
BOSS_SEARCH_URL = "/wapi/zpgeek/search/joblist.json"
BOSS_JOB_DETAIL_URL = "/wapi/zpgeek/job/detail.json"
BOSS_ADD_FRIEND_URL = "/wapi/zpgeek/friend/add.json"
BOSS_USER_INFO_URL = "/wapi/zpuser/wap/getUserInfo.json"

# BOSS直聘请求头
BOSS_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Origin": BOSS_BASE_URL,
    "Pragma": "no-cache",
    "Referer": f"{BOSS_BASE_URL}/web/geek/job",
    "Sec-Ch-Ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

# ==================== 工具函数 ====================

def get_machine_fingerprint() -> str:
    """生成机器指纹（WMIC UUID + MAC + 主机名 → SHA-256前32位）"""
    fp_parts = []
    try:
        fp_parts.append(platform.node())
        fp_parts.append(platform.machine())
    except:
        pass
    try:
        if os.name == 'nt':
            r = subprocess.run(['wmic', 'csproduct', 'get', 'uuid'], capture_output=True, text=True, timeout=5)
            if r.stdout:
                fp_parts.append(r.stdout.strip())
    except:
        pass
    try:
        fp_parts.append(str(uuid.getnode()))
    except:
        pass
    raw = '|'.join(fp_parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def resolve_city_code(location: str) -> str:
    """将城市名称解析为BOSS直聘城市编码"""
    if not location or location in ("全国", "不限", ""):
        return CITY_NATIONAL
    if location.isdigit():
        return location
    if location in CITY_NAME_TO_CODE:
        return CITY_NAME_TO_CODE[location]
    for name, code in CITY_NAME_TO_CODE.items():
        if location in name or name in location:
            return code
    return CITY_NATIONAL


def city_code_to_name(code: str) -> str:
    """城市编码 → 名称"""
    return CITY_MAP.get(code, code)


class LogEmitter(QObject):
    """线程安全的日志信号发射器"""
    log_signal = pyqtSignal(str)


_log_emitter = LogEmitter()

# 脚本所在目录（PyInstaller打包后为exe所在目录）
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 机器码缓存（首次生成立即缓存）
_MACHINE_CODE = None


def get_machine_code() -> str:
    """生成机器唯一标识码，用于多机器去重隔离"""
    global _MACHINE_CODE
    if _MACHINE_CODE:
        return _MACHINE_CODE

    import hashlib
    parts = []

    # 1. MAC地址
    try:
        mac = uuid.getnode()
        parts.append(f"mac:{mac:012x}")
    except Exception:
        pass

    # 2. Windows MachineGuid (注册表)
    if os.name == 'nt':
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Microsoft\Cryptography")
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            parts.append(f"guid:{guid}")
        except Exception:
            pass

    # 3. 兜底：计算机名 + 用户名
    if len(parts) < 2:
        parts.append(f"host:{os.environ.get('COMPUTERNAME', '')}")
        parts.append(f"user:{os.environ.get('USERNAME', '')}")

    raw = "|".join(parts)
    _MACHINE_CODE = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return _MACHINE_CODE


def setup_file_logging():
    """将日志信号同时写入脚本目录下的日志文件（每次启动覆盖）"""
    log_path = os.path.join(SCRIPT_DIR, "boss_delivery.log")
    try:
        fh = open(log_path, 'w', encoding='utf-8')
        def _write_to_file(msg: str):
            try:
                fh.write(msg + '\n')
                fh.flush()
            except Exception:
                pass
        _log_emitter.log_signal.connect(_write_to_file)
    except Exception:
        pass  # 写文件失败不影响主流程


def _log_fmt(prefix: str, msg: str) -> str:
    ts = datetime.now().strftime('%H:%M:%S')
    return f"[{ts}] [{prefix}] {msg}"


# ==================== 配置持久化 ====================

def _config_path(filename: str = "config.json") -> str:
    """获取配置文件完整路径"""
    return os.path.join(SCRIPT_DIR, filename)


def save_delivery_config(keyword: str = "", location: str = "", min_score: int = 60,
                         target: int = 10, delay_min: int = 8, delay_max: int = 15,
                         delivery_mode: str = "api", use_greeting: bool = False,
                         resume_text: str = ""):
    """保存投递配置到 config.json（含简历文本）"""
    # 先加载已有数据（保留 resume_text 等不被覆盖）
    existing = {}
    try:
        p = _config_path("config.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                existing = json.load(f)
    except Exception:
        pass
    data = {
        "keyword": keyword or existing.get("keyword", ""),
        "location": location or existing.get("location", ""),
        "min_score": min_score if min_score != 60 or not existing else existing.get("min_score", 60),
        "target": target if target != 10 or not existing else existing.get("target", 10),
        "delay_min": delay_min if delay_min != 8 or not existing else existing.get("delay_min", 8),
        "delay_max": delay_max if delay_max != 15 or not existing else existing.get("delay_max", 15),
        "delivery_mode": delivery_mode or existing.get("delivery_mode", "api"),
        "use_greeting": use_greeting if use_greeting else existing.get("use_greeting", False),
        "resume_text": resume_text or existing.get("resume_text", ""),
    }
    try:
        with open(_config_path("config.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_delivery_config() -> dict:
    """加载投递配置，失败返回空字典"""
    try:
        path = _config_path("config.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_resume_text(resume_text: str):
    """仅保存简历文本到 config.json（保留其他配置）"""
    existing = load_delivery_config()
    existing["resume_text"] = resume_text
    try:
        with open(_config_path("config.json"), "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def save_user_credentials(username: str, password: str):
    """保存用户登录凭证到 user_config.json"""
    try:
        with open(_config_path("user_config.json"), "w", encoding="utf-8") as f:
            json.dump({"username": username, "password": password}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_user_credentials() -> dict:
    """加载用户登录凭证，失败返回空字典"""
    try:
        path = _config_path("user_config.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


# ==================== 数据库层 ====================

class AccountDatabase:
    """MySQL 远程数据库操作 — 用户/卡密/许可证管理"""

    def __init__(self):
        self._conn = None

    def connect(self):
        if not HAS_PYMYSQL:
            raise RuntimeError("pymysql 未安装")
        self._conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, database=DB_NAME,
            charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )
        return self._conn

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            except:
                pass
            self._conn = None

    def get_conn(self):
        try:
            if self._conn and self._conn.open:
                self._conn.ping(reconnect=True)
                return self._conn
        except:
            pass
        return self.connect()

    def init_tables(self):
        """初始化数据库表"""
        conn = self.get_conn()
        cur = conn.cursor()

        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            email VARCHAR(200) DEFAULT '',
            created_at DATETIME NOT NULL DEFAULT NOW(),
            last_login DATETIME,
            is_banned TINYINT DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

        cur.execute("""CREATE TABLE IF NOT EXISTS cards (
            id INT AUTO_INCREMENT PRIMARY KEY,
            card_key VARCHAR(255) NOT NULL UNIQUE,
            card_hash VARCHAR(255) NOT NULL UNIQUE,
            card_type VARCHAR(20) NOT NULL,
            duration_days INT NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'unused',
            created_at DATETIME NOT NULL DEFAULT NOW(),
            used_by INT,
            used_at DATETIME,
            expires_at DATETIME,
            machine_fp VARCHAR(100) DEFAULT ''
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

        cur.execute("""CREATE TABLE IF NOT EXISTS licenses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            card_id INT NOT NULL,
            machine_fp VARCHAR(100) NOT NULL DEFAULT '',
            activated_at DATETIME NOT NULL DEFAULT NOW(),
            expires_at DATETIME,
            is_active TINYINT DEFAULT 1
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

        conn.commit()

    def register_user(self, username: str, password: str, email: str = "") -> tuple:
        """注册新用户，返回 (success, message)"""
        import bcrypt
        conn = self.get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                return False, "用户名已存在"
            pwd_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (%s,%s,%s)",
                (username, pwd_hash, email)
            )
            conn.commit()
            return True, f"注册成功！用户名: {username}"
        except Exception as e:
            return False, f"注册失败: {e}"

    def validate_login(self, username: str, password: str) -> tuple:
        """验证登录，返回 (success, user_dict_or_error)"""
        import bcrypt
        conn = self.get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            user = cur.fetchone()
            if not user:
                return False, "用户名不存在"
            if user.get('is_banned'):
                return False, "该账号已被禁用"
            if bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
                cur.execute("UPDATE users SET last_login=NOW() WHERE id=%s", (user['id'],))
                conn.commit()
                return True, {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user.get('email', ''),
                    'created_at': str(user.get('created_at', '')),
                }
            return False, "密码错误"
        except Exception as e:
            return False, f"登录失败: {e}"


class CardManager:
    """卡密系统 — 卡密生成/验证/激活"""

    CARD_TYPES = {
        'trial':      {'label': '试用卡(3天)',  'days': 3},
        'monthly':    {'label': '月卡(30天)',   'days': 30},
        'quarterly':  {'label': '季卡(90天)',   'days': 90},
        'yearly':     {'label': '年卡(365天)',  'days': 365},
        'permanent':  {'label': '永久卡',       'days': 0},
    }
    SEGMENT_LENGTH = 4
    SEGMENT_COUNT = 4

    def __init__(self, db: AccountDatabase):
        self.db = db

    @classmethod
    def _generate_segment(cls):
        chars = string.ascii_uppercase + string.digits
        chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '').replace('L', '')
        return ''.join(secrets.choice(chars) for _ in range(cls.SEGMENT_LENGTH))

    def generate_card_keys(self, card_type: str, count: int = 1) -> List[str]:
        if card_type not in self.CARD_TYPES:
            raise ValueError(f"无效卡类型: {card_type}")
        days = self.CARD_TYPES[card_type]['days']
        conn = self.db.get_conn()
        cur = conn.cursor()
        generated = []
        for _ in range(count):
            while True:
                segments = [self._generate_segment() for _ in range(self.SEGMENT_COUNT)]
                card_key = '-'.join(segments)
                card_hash = hashlib.sha256(card_key.encode()).hexdigest()
                cur.execute("SELECT id FROM cards WHERE card_hash=%s", (card_hash,))
                if not cur.fetchone():
                    break
            cur.execute(
                "INSERT INTO cards (card_key, card_hash, card_type, duration_days) VALUES (%s,%s,%s,%s)",
                (card_key, card_hash, card_type, days)
            )
            generated.append(card_key)
        conn.commit()
        return generated

    def verify_and_activate(self, card_key: str, user_id: int, machine_fp: str) -> tuple:
        """激活卡密，返回 (success, message)"""
        card_hash_value = hashlib.sha256(card_key.strip().upper().encode()).hexdigest()
        conn = self.db.get_conn()
        cur = conn.cursor()

        cur.execute("SELECT * FROM cards WHERE card_hash=%s", (card_hash_value,))
        card = cur.fetchone()
        if not card:
            return False, "卡密无效，请检查是否输入正确"
        if card['status'] == 'used':
            return False, "此卡密已被使用"
        if card['status'] == 'disabled':
            return False, "此卡密已被禁用"
        if card['status'] == 'expired':
            return False, "此卡密已过期"

        now = datetime.now()
        days = card['duration_days']
        expires_at = None if days == 0 else (now + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

        # 更新卡密状态
        cur.execute(
            "UPDATE cards SET status='used', used_by=%s, used_at=%s, machine_fp=%s WHERE id=%s",
            (user_id, now.strftime('%Y-%m-%d %H:%M:%S'), machine_fp, card['id'])
        )

        # 创建许可证
        cur.execute(
            "INSERT INTO licenses (user_id, card_id, machine_fp, expires_at, is_active) VALUES (%s,%s,%s,%s,1)",
            (user_id, card['id'], machine_fp, expires_at)
        )

        conn.commit()

        if card['card_type'] == 'permanent':
            return True, "永久卡激活成功，永久有效！"
        else:
            exp_str = expires_at[:10] if expires_at else '永久'
            return True, f"{self.CARD_TYPES[card['card_type']]['label']}激活成功，到期时间: {exp_str}"

    def check_license(self, user_id: int) -> dict:
        """检查用户许可证状态"""
        conn = self.db.get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM licenses WHERE user_id=%s AND is_active=1 ORDER BY activated_at DESC LIMIT 1",
            (user_id,)
        )
        lic = cur.fetchone()
        if not lic:
            return {'active': False, 'reason': '未激活', 'expires_at': None, 'card_type': None}

        if lic['expires_at']:
            exp = lic['expires_at']
            if isinstance(exp, str):
                exp = datetime.strptime(exp, '%Y-%m-%d %H:%M:%S') if ' ' in exp else datetime.strptime(exp, '%Y-%m-%d')
            if datetime.now() > exp:
                return {'active': False, 'reason': '已过期', 'expires_at': str(lic['expires_at']), 'card_type': None}

        cur.execute("SELECT card_type FROM cards WHERE id=%s", (lic['card_id'],))
        card = cur.fetchone()
        return {
            'active': True,
            'reason': '正常',
            'expires_at': str(lic['expires_at']) if lic['expires_at'] else None,
            'card_type': card['card_type'] if card else 'unknown',
            'activated_at': str(lic.get('activated_at', ''))
        }


def get_expiry_text(expires_at) -> str:
    """许可证到期时间文本描述"""
    if not expires_at:
        return '永久有效'
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S')
        except:
            return '永久有效'
    days_left = (expires_at - datetime.now()).days
    if days_left < 0:
        return '已过期'
    elif days_left == 0:
        return '今日到期'
    elif days_left <= 3:
        return f'剩余 {days_left} 天 (即将到期)'
    else:
        return f'剩余 {days_left} 天'


class JobDatabase:
    """SQLite 本地投递记录数据库"""

    DB_FILE = "jobs_delivery_v2.db"

    def __init__(self):
        self._machine_code = get_machine_code()
        self._init_db()

    def _get_path(self):
        return os.path.join(SCRIPT_DIR, self.DB_FILE)

    def _init_db(self):
        import sqlite3
        conn = sqlite3.connect(self._get_path())
        cur = conn.cursor()

        # 检查是否需要迁移（旧表无machine_code列）
        cur.execute("PRAGMA table_info(delivered_jobs)")
        columns = [row[1] for row in cur.fetchall()]
        need_migrate = 'machine_code' not in columns

        if need_migrate and columns:
            # 迁移旧数据：重建表，新UNIQUE=(machine_code, job_url)
            cur.execute("ALTER TABLE delivered_jobs RENAME TO delivered_jobs_old")
            cur.execute("""CREATE TABLE delivered_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_code TEXT NOT NULL DEFAULT '',
                job_url TEXT NOT NULL,
                title TEXT DEFAULT '',
                company TEXT DEFAULT '',
                status INTEGER DEFAULT 0,
                match_score INTEGER DEFAULT 0,
                platform TEXT DEFAULT 'boss',
                delivery_mode TEXT DEFAULT 'api',
                greeting TEXT DEFAULT '',
                active_time INTEGER DEFAULT 0,
                active_time_desc TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT '',
                UNIQUE(machine_code, job_url)
            )""")
            # 将旧数据迁移，machine_code用本机码
            cur.execute(f"""INSERT OR IGNORE INTO delivered_jobs
                (machine_code, job_url, title, company, status, match_score,
                 platform, delivery_mode, greeting, active_time, active_time_desc,
                 created_at, updated_at)
                SELECT '{self._machine_code}', job_url, title, company, status, match_score,
                       platform, delivery_mode, greeting, active_time, active_time_desc,
                       created_at, updated_at
                FROM delivered_jobs_old""")
            cur.execute("DROP TABLE delivered_jobs_old")
        else:
            cur.execute("""CREATE TABLE IF NOT EXISTS delivered_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_code TEXT NOT NULL DEFAULT '',
                job_url TEXT NOT NULL,
                title TEXT DEFAULT '',
                company TEXT DEFAULT '',
                status INTEGER DEFAULT 0,
                match_score INTEGER DEFAULT 0,
                platform TEXT DEFAULT 'boss',
                delivery_mode TEXT DEFAULT 'api',
                greeting TEXT DEFAULT '',
                active_time INTEGER DEFAULT 0,
                active_time_desc TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT '',
                UNIQUE(machine_code, job_url)
            )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS delivery_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_code TEXT NOT NULL DEFAULT '',
            date TEXT NOT NULL,
            platform TEXT DEFAULT 'boss',
            delivery_mode TEXT DEFAULT 'api',
            count INTEGER DEFAULT 0,
            UNIQUE(machine_code, date, platform, delivery_mode)
        )""")
        conn.commit()
        conn.close()

    def is_delivered(self, job_url: str) -> bool:
        import sqlite3
        conn = sqlite3.connect(self._get_path())
        cur = conn.cursor()
        cur.execute("SELECT id FROM delivered_jobs WHERE machine_code=? AND job_url=? AND status=1",
                   (self._machine_code, job_url))
        result = cur.fetchone()
        conn.close()
        return result is not None

    def is_skipped(self, job_url: str) -> bool:
        import sqlite3
        conn = sqlite3.connect(self._get_path())
        cur = conn.cursor()
        cur.execute("SELECT id FROM delivered_jobs WHERE machine_code=? AND job_url=? AND status IN (2,4,5)",
                   (self._machine_code, job_url))
        result = cur.fetchone()
        conn.close()
        return result is not None

    def add_job(self, job_url: str, title: str = "", company: str = "", status: int = 0,
                match_score: int = 0, platform: str = "boss", delivery_mode: str = "api",
                greeting: str = "", active_time: int = 0, active_time_desc: str = ""):
        import sqlite3
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self._get_path())
        cur = conn.cursor()
        cur.execute("""INSERT OR REPLACE INTO delivered_jobs
            (machine_code, job_url, title, company, status, match_score, platform, delivery_mode, greeting,
             active_time, active_time_desc, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (self._machine_code, job_url, title, company, status, match_score,
             platform, delivery_mode, greeting,
             active_time, active_time_desc, now, now))
        conn.commit()
        conn.close()

    def update_status(self, job_url: str, status: int, match_score: int = 0):
        import sqlite3
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self._get_path())
        cur = conn.cursor()
        if match_score > 0:
            cur.execute("UPDATE delivered_jobs SET status=?, match_score=?, updated_at=? "
                       "WHERE machine_code=? AND job_url=?",
                       (status, match_score, now, self._machine_code, job_url))
        else:
            cur.execute("UPDATE delivered_jobs SET status=?, updated_at=? "
                       "WHERE machine_code=? AND job_url=?",
                       (status, now, self._machine_code, job_url))
        conn.commit()
        conn.close()

    def get_today_delivery_count(self, platform: str = "boss", delivery_mode: str = None) -> int:
        import sqlite3
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(self._get_path())
        cur = conn.cursor()
        if delivery_mode:
            cur.execute(
                "SELECT COUNT(*) as cnt FROM delivered_jobs "
                "WHERE machine_code=? AND platform=? AND delivery_mode=? AND status=1 AND date(updated_at)=?",
                (self._machine_code, platform, delivery_mode, today))
        else:
            cur.execute(
                "SELECT COUNT(*) as cnt FROM delivered_jobs "
                "WHERE machine_code=? AND platform=? AND status=1 AND date(updated_at)=?",
                (self._machine_code, platform, today))
        result = cur.fetchone()
        conn.close()
        return result[0] if result else 0

    def get_delivery_records(self, limit: int = 200, platform: str = None, delivery_mode: str = None) -> list:
        import sqlite3
        conn = sqlite3.connect(self._get_path())
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        conditions = ["machine_code=?"]
        params = [self._machine_code]
        if platform:
            conditions.append("platform=?")
            params.append(platform)
        if delivery_mode:
            conditions.append("delivery_mode=?")
            params.append(delivery_mode)
        where = " WHERE " + " AND ".join(conditions)
        cur.execute(f"SELECT * FROM delivered_jobs{where} ORDER BY updated_at DESC LIMIT ?",
                   params + [limit])
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def exists(self, job_url: str) -> bool:
        """检查岗位URL是否已在数据库中（本机、任意状态）"""
        import sqlite3
        conn = sqlite3.connect(self._get_path())
        cur = conn.cursor()
        cur.execute("SELECT id FROM delivered_jobs WHERE machine_code=? AND job_url=?",
                   (self._machine_code, job_url))
        result = cur.fetchone()
        conn.close()
        return result is not None

    def get_status(self, job_url: str) -> int:
        """获取岗位状态（本机），不存在返回-1"""
        import sqlite3
        conn = sqlite3.connect(self._get_path())
        cur = conn.cursor()
        cur.execute("SELECT status FROM delivered_jobs WHERE machine_code=? AND job_url=?",
                   (self._machine_code, job_url))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else -1

    def filter_new_jobs(self, jobs: Dict) -> Dict:
        """过滤已投递/处理中的岗位，跳过低分/失败的可重新评估（本机隔离）
        状态说明: 0=待投递 1=已投递(严禁重投) 2=失败 3=无详情 4=低分跳过
        仅过滤状态0和1，状态2/3/4允许重新进入投递流程"""
        new_jobs = {}
        for url, job in jobs.items():
            status = self.get_status(url)
            if status < 0:
                new_jobs[url] = job  # 全新岗位
            elif status >= 2:
                new_jobs[url] = job  # 失败/无详情/低分 → 允许重新评估
            # status 0/1 → 过滤掉（待投递中 / 已投递成功）
        return new_jobs

    def get_daily_stats(self, date: str = None) -> dict:
        import sqlite3
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(self._get_path())
        cur = conn.cursor()
        cur.execute(
            "SELECT platform, delivery_mode, COUNT(*) as cnt FROM delivered_jobs "
            "WHERE machine_code=? AND status=1 AND date(updated_at)=? "
            "GROUP BY platform, delivery_mode",
            (self._machine_code, date))
        rows = cur.fetchall()
        conn.close()
        stats = {'api': 0, 'browser': 0, 'total': 0}
        for row in rows:
            mode = row[1] if row[1] else 'api'
            stats[mode] += row[2]
            stats['total'] += row[2]
        return stats


class BrowserAuthHelper:
    """浏览器认证辅助类 — 自动从浏览器中提取BOSS直聘Cookie"""

    # Cookie域名过滤器
    ZHIPIN_DOMAINS = ('.zhipin.com', 'www.zhipin.com', 'zhipin.com')
    ZHILIAN_DOMAINS = ('.zhaopin.com', 'www.zhaopin.com', 'zhaopin.com', '.zhaopin.cn', 'www.zhaopin.cn')

    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self._available_browsers = self._detect_browsers()

    def _log(self, msg):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_msg = f"[{timestamp}] [Browser] {msg}"
        print(log_msg)
        if self.log_callback:
            try:
                self.log_callback(log_msg)
            except Exception:
                pass
        else:
            try:
                _log_emitter.log_signal.emit(log_msg)
            except Exception:
                pass

    def _detect_browsers(self) -> List[str]:
        """检测系统上安装的浏览器"""
        browsers = []
        if not HAS_BROWSER_COOKIE3:
            return browsers

        user_data = os.path.expandvars(r'%LOCALAPPDATA%')

        # Chrome
        chrome_path = os.path.join(user_data, r'Google\Chrome\User Data')
        if os.path.exists(chrome_path):
            browsers.append('chrome')

        # Edge
        edge_path = os.path.join(user_data, r'Microsoft\Edge\User Data')
        if os.path.exists(edge_path):
            browsers.append('edge')

        # Firefox
        firefox_path = os.path.join(os.path.expandvars(r'%APPDATA%'), r'Mozilla\Firefox\Profiles')
        if os.path.exists(firefox_path):
            browsers.append('firefox')

        # Brave
        brave_path = os.path.join(user_data, r'BraveSoftware\Brave-Browser\User Data')
        if os.path.exists(brave_path):
            browsers.append('brave')

        # Opera
        opera_path = os.path.join(os.path.expandvars(r'%APPDATA%'), r'Opera Software\Opera Stable')
        if os.path.exists(opera_path):
            browsers.append('opera')

        self._log(f"检测到浏览器: {browsers if browsers else '无'}")
        return browsers

    def get_available_browsers(self) -> List[str]:
        return self._available_browsers

    @staticmethod
    def _is_chrome_running() -> bool:
        """检测Chrome浏览器是否正在运行"""
        try:
            import subprocess
            output = subprocess.check_output(
                ['tasklist', '/FI', 'IMAGENAME eq chrome.exe'],
                creationflags=subprocess.CREATE_NO_WINDOW
            ).decode('gbk', errors='replace')
            return 'chrome.exe' in output.lower()
        except Exception:
            return False

    @staticmethod
    def open_zhipin():
        """用默认浏览器打开BOSS直聘"""
        import webbrowser
        webbrowser.open("https://www.zhipin.com")

    @staticmethod
    def open_zhilian():
        """用默认浏览器打开智联招聘"""
        import webbrowser
        webbrowser.open("https://www.zhaopin.com")

    def extract_cookies(self, browser: str = None, platform: str = 'boss') -> Optional[Dict[str, str]]:
        """从指定浏览器提取Cookie
        platform: 'boss' → BOSS直聘, 'zhilian' → 智联招聘
        返回: {"__zp_stoken__": "xxx", "wt2": "yyy", ...} 或 None
        """
        if not HAS_BROWSER_COOKIE3:
            self._log("browser_cookie3 未安装，请执行: pip install browser-cookie3")
            return None

        browsers_to_try = [browser] if browser else self._available_browsers
        if not browsers_to_try:
            platform_name = "BOSS直聘" if platform == 'boss' else "智联招聘"
            self._log(f"未检测到支持的浏览器，请先使用Chrome/Edge/Firefox登录{platform_name}")
            return None

        for browser_name in browsers_to_try:
            try:
                cookies = self._extract_from_browser(browser_name, platform)
                if cookies:
                    self._log(f"成功从 {browser_name} 提取到 {len(cookies)} 个Cookie")
                    return cookies
                platform_name = "BOSS直聘" if platform == 'boss' else "智联招聘"
                self._log(f"{browser_name} 中未找到{platform_name}Cookie")
            except Exception as e:
                self._log(f"从 {browser_name} 提取Cookie失败: {e}")

        platform_name = "BOSS直聘" if platform == 'boss' else "智联招聘"
        self._log(f"所有浏览器均未找到{platform_name}Cookie，请确认已在浏览器中登录")
        return None

    def _extract_from_browser(self, browser_name: str, platform: str = 'boss') -> Optional[Dict[str, str]]:
        """从单个浏览器提取Cookie（Chrome优先多种尝试）"""
        domains = self.ZHIPIN_DOMAINS if platform == 'boss' else self.ZHILIAN_DOMAINS
        main_domain = 'zhipin.com' if platform == 'boss' else 'zhaopin.com'
        try:
            if browser_name == 'chrome':
                return self._extract_chrome_cookies(platform)
            elif browser_name == 'edge':
                return self._extract_edge_cookies(platform)
            elif browser_name == 'firefox':
                cj = browser_cookie3.firefox(domain_name=main_domain)
            elif browser_name == 'brave':
                cj = browser_cookie3.brave(domain_name=main_domain)
            elif browser_name == 'opera':
                cj = browser_cookie3.opera(domain_name=main_domain)
            else:
                return None

            cookies = {}
            for cookie in cj:
                if cookie.domain and main_domain in cookie.domain:
                    cookies[cookie.name] = cookie.value
            if platform == 'boss' and any('zp_stoken' in k.lower() for k in cookies):
                return cookies
            elif platform == 'zhilian' and len(cookies) >= 2:
                return cookies
            return None
        except Exception as e:
            error_msg = str(e)
            if 'admin' in error_msg.lower():
                self._log(f"{browser_name} 需要管理员权限，请以管理员身份运行程序")
            else:
                self._log(f"{browser_name} 提取异常: {e}")
            return None

    def _extract_chrome_cookies(self, platform: str = 'boss') -> Optional[Dict[str, str]]:
        """从Chrome提取Cookie，按优先级尝试多种策略"""
        main_domain = 'zhipin.com' if platform == 'boss' else 'zhaopin.com'
        chrome_running = self._is_chrome_running()

        result = self._extract_chrome_cdp(platform)
        if result:
            return result

        if not chrome_running:
            if os.name == 'nt':
                result = self._extract_chrome_win32(platform)
                if result:
                    return result

        try:
            cj = browser_cookie3.chrome(domain_name=main_domain)
            cookies = {}
            for cookie in cj:
                cookies[cookie.name] = cookie.value
            has_valid = (platform == 'boss' and any('zp_stoken' in k.lower() for k in cookies)) or \
                        (platform == 'zhilian' and len(cookies) >= 2)
            if has_valid:
                self._log(f"Chrome: browser_cookie3域名过滤成功 ({platform})")
                return cookies
        except Exception:
            pass

        try:
            self._log("Chrome: browser_cookie3全量获取...")
            cj = browser_cookie3.chrome()
            cookies = {}
            for cookie in cj:
                if cookie.domain and main_domain in cookie.domain:
                    cookies[cookie.name] = cookie.value
            has_valid = (platform == 'boss' and any('zp_stoken' in k.lower() for k in cookies)) or \
                        (platform == 'zhilian' and len(cookies) >= 2)
            if has_valid:
                self._log(f"Chrome: browser_cookie3全量筛选成功 ({platform})")
                return cookies
        except Exception as e:
            self._log(f"Chrome: browser_cookie3全量失败: {e}")

        return None

    def _extract_chrome_win32(self, platform: str = 'boss') -> Optional[Dict[str, str]]:
        """Windows原生方式：直接读Chrome Cookie数据库并用DPAPI解密"""
        main_domain = 'zhipin.com' if platform == 'boss' else 'zhaopin.com'
        if not HAS_CRYPTO:
            self._log("Chrome: 需要安装 cryptography 库: pip install cryptography")
            return None
        try:
            import sqlite3
            import shutil
            import tempfile
            import base64
            import ctypes
            from ctypes import wintypes

            user_data = os.path.expandvars(r'%LOCALAPPDATA%')
            chrome_dir = os.path.join(user_data, r'Google\Chrome\User Data')
            if not os.path.exists(chrome_dir):
                return None

            local_state_path = os.path.join(chrome_dir, 'Local State')
            if not os.path.exists(local_state_path):
                self._log("Chrome: Local State 文件不存在")
                return None

            with open(local_state_path, 'r', encoding='utf-8') as f:
                local_state = json.load(f)
            encrypted_key = base64.b64decode(
                local_state.get('os_crypt', {}).get('encrypted_key', '')
            )
            if not encrypted_key:
                self._log("Chrome: 无法读取加密密钥")
                return None

            encrypted_key = encrypted_key[5:]

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

            crypt32 = ctypes.windll.crypt32
            kernel32 = ctypes.windll.kernel32

            p_data_in = DATA_BLOB(len(encrypted_key), ctypes.create_string_buffer(encrypted_key, len(encrypted_key)))
            p_data_out = DATA_BLOB(0, None)

            if not crypt32.CryptUnprotectData(
                ctypes.byref(p_data_in), None, None, None, None, 0, ctypes.byref(p_data_out)
            ):
                self._log("Chrome: DPAPI解密密钥失败")
                return None

            decrypted_key = ctypes.string_at(p_data_out.pbData, p_data_out.cbData)
            kernel32.LocalFree(p_data_out.pbData)

            possible_dirs = [os.path.join(chrome_dir, d) for d in os.listdir(chrome_dir)
                           if os.path.isdir(os.path.join(chrome_dir, d))
                           and (d == 'Default' or d.startswith('Profile'))]
            cookie_dbs = []
            for profile_dir in possible_dirs:
                for subpath in ['Network/Cookies', 'Cookies']:
                    p = os.path.join(profile_dir, subpath)
                    if os.path.exists(p):
                        cookie_dbs.append((profile_dir, p))
            if not cookie_dbs:
                self._log("Chrome: 未找到Cookies数据库")
                return None

            def _decrypt_value(ciphertext: bytes, key: bytes) -> Optional[str]:
                try:
                    if len(ciphertext) < 15:
                        return None
                    nonce = ciphertext[3:15]
                    ct = ciphertext[15:]
                    aesgcm = AESGCM(key)
                    plaintext = aesgcm.decrypt(nonce, ct, None)
                    return plaintext.decode('utf-8', errors='replace')
                except Exception:
                    return None

            def _clean_cookie_value(name: str, raw_val: str) -> str:
                if not raw_val:
                    return raw_val
                if all(32 <= ord(c) < 127 for c in raw_val):
                    return raw_val
                import re as _re
                patterns = {
                    'wt2': r'Dop[A-Za-z0-9~=_\-]+',
                    'zp_at': r'Ey[A-Za-z0-9~=_\-]+',
                    '__zp_stoken__': r'4854[A-Za-z0-9%+/=]+',
                    '__zp_stoken': r'4854[A-Za-z0-9%+/=]+',
                    'bst': r'V2[A-Za-z0-9~|_=\-]+',
                    'ab_guid': r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
                    '__a': r'\d+\.\d+(?:\.\d+)+',
                    'Hm_lvt_194df3105ad7148dcf2b98a91b5e727a': r'\d+(?:,\d+)+',
                    'Hm_lpvt_194df3105ad7148dcf2b98a91b5e727a': r'\d+(?:,\d+)+',
                }
                if name in patterns:
                    m = _re.search(patterns[name], raw_val)
                    if m:
                        return m.group()
                if name == 'wbg':
                    nums = _re.findall(r'\d+', raw_val)
                    if nums:
                        return nums[-1]
                if name == 'lastCity':
                    nums = _re.findall(r'\d{6,}', raw_val)
                    if nums:
                        return nums[-1]
                if name == '__g':
                    nums = _re.findall(r'[-\d]+', raw_val)
                    if nums:
                        return nums[-1]
                printable = ''.join(c for c in raw_val if 32 <= ord(c) < 127)
                return printable if printable else raw_val

            all_cookies = {}
            for profile_dir_path, cookie_db_path in cookie_dbs:
                safe_name = os.path.basename(profile_dir_path)
                tmp_db = os.path.join(tempfile.gettempdir(),
                                      f'chrome_cookies_decrypt_{os.getpid()}_{safe_name}.db')
                try:
                    shutil.copy2(cookie_db_path, tmp_db)
                except PermissionError:
                    self._log(f"Chrome: {safe_name}/Cookies被锁定，跳过")
                    continue
                except Exception as e:
                    self._log(f"Chrome: 复制{safe_name}/Cookies失败: {e}")
                    continue

                rows = []
                try:
                    try:
                        conn = sqlite3.connect(f"file:{tmp_db}?mode=ro&nolock=1", uri=True)
                    except Exception:
                        conn = sqlite3.connect(tmp_db)
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT host_key, name, encrypted_value FROM cookies "
                        f"WHERE host_key LIKE '%{main_domain}%'"
                    )
                    rows = cursor.fetchall()
                    conn.close()
                except Exception as e:
                    self._log(f"Chrome: {safe_name} SQLite查询失败: {e}")

                if rows:
                    profile_cookies = {}
                    decrypted_count = 0
                    for host_key, name, encrypted_value in rows:
                        if encrypted_value:
                            val = _decrypt_value(encrypted_value, decrypted_key)
                            if val:
                                cleaned = _clean_cookie_value(name, val)
                                if cleaned:
                                    profile_cookies[name] = cleaned
                                    decrypted_count += 1
                    self._log(f"Chrome: {safe_name}解密成功 {decrypted_count}/{len(rows)} 条")
                    all_cookies.update(profile_cookies)

                try:
                    os.unlink(tmp_db)
                except Exception:
                    pass

            if any('zp_stoken' in k.lower() for k in all_cookies):
                self._log(f"Chrome: 总计从 {len(cookie_dbs)} 个Profile提取到 {len(all_cookies)} 个Cookie")
                return all_cookies
            return None

        except ImportError as e:
            self._log(f"Chrome: 缺少必要模块 ({e})")
            return None
        except Exception as e:
            self._log(f"Chrome: Windows解密失败: {e}")
            return None

    def _extract_chrome_cdp(self, platform: str = 'boss') -> Optional[Dict[str, str]]:
        """通过 Chrome DevTools Protocol 从运行中的Chrome实时提取Cookie
        如果Chrome未运行：启动Chrome → 加载目标网站 → JS生成最新token → CDP提取 → 关闭
        如果Chrome已运行：尝试连接现有调试端口
        """
        import subprocess

        main_domain = 'zhipin.com' if platform == 'boss' else 'zhaopin.com'
        target_url = 'https://www.zhipin.com/web/geek/job' if platform == 'boss' else 'https://www.zhaopin.com'
        search_url = 'https://www.zhipin.com/web/geek/job?city=101010100&query=测试' if platform == 'boss' else 'https://www.zhaopin.com'

        chrome_exe = None
        search_paths = [
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
            os.path.join(os.environ.get('LOCALAPPDATA', ''),
                        'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'),
                        'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'),
                        'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop', 'chrome-win64', 'chrome.exe'),
            'D:/Desktop/chrome-win64/chrome.exe',
            'D:/chrome-win64/chrome.exe',
        ]
        try:
            result = subprocess.check_output(['where', 'chrome'],
                stderr=subprocess.DEVNULL, timeout=5).decode('gbk', errors='replace').strip()
            if result:
                for line in result.split('\n'):
                    line = line.strip()
                    if line and os.path.exists(line):
                        search_paths.insert(0, line)
                        break
        except Exception:
            pass
        for d_root in ['D:/', 'C:/']:
            for sub in ['chrome-win64/chrome.exe', 'Chrome/Application/chrome.exe']:
                p = os.path.join(d_root, sub)
                if os.path.exists(p):
                    search_paths.insert(0, p)
                    break
        for path in search_paths:
            if os.path.exists(path):
                chrome_exe = path
                break
        if not chrome_exe:
            return None

        user_data = os.path.expandvars(r'%LOCALAPPDATA%')
        chrome_dir = os.path.join(user_data, 'Google', 'Chrome', 'User Data')
        if not os.path.exists(chrome_dir):
            return None

        # 优先选Default，其次选BOSS直聘Cookie最多的profile
        target_profile = 'Default'
        best_count = 0
        default_count = 0
        for profile_name in sorted(os.listdir(chrome_dir)):
            profile_path = os.path.join(chrome_dir, profile_name)
            if not os.path.isdir(profile_path):
                continue
            cookies_db = os.path.join(profile_path, 'Network', 'Cookies')
            if os.path.exists(cookies_db):
                try:
                    import sqlite3, shutil, tempfile
                    tmp = os.path.join(tempfile.gettempdir(), f'cdp_probe_{os.getpid()}.db')
                    shutil.copy2(cookies_db, tmp)
                    conn = sqlite3.connect(tmp)
                    cur = conn.cursor()
                    cur.execute(f"SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%{main_domain}%'")
                    count = cur.fetchone()[0]
                    conn.close()
                    os.remove(tmp)
                    if profile_name == 'Default':
                        default_count = count
                    if count > best_count:
                        best_count = count
                        target_profile = profile_name
                except Exception:
                    pass
        # 如果Default也有Cookie，优先用Default（确保最新登录的profile）
        if default_count > 0:
            target_profile = 'Default'
        self._log(f"CDP: 选用Chrome profile={target_profile} (Cookie数={best_count})")

        import subprocess as _sp
        chrome_running = False
        try:
            tasklist = _sp.check_output(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'],
                                        creationflags=_sp.CREATE_NO_WINDOW).decode('gbk', errors='replace')
            chrome_running = 'chrome.exe' in tasklist.lower()
        except Exception:
            pass

        debug_port = 9222
        import socket

        chrome_need_restart = False
        if chrome_running:
            self._log("CDP: 检测到Chrome正在运行，尝试连接现有调试端口...")
            for port in range(9222, 9240):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('127.0.0.1', port))
                sock.close()
                if result == 0:
                    try:
                        import requests as _req
                        resp = _req.get(f'http://127.0.0.1:{port}/json/version', timeout=2)
                        if resp.status_code == 200:
                            debug_port = port
                            # 检测 --remote-allow-origins 是否已设置
                            # 尝试WebSocket连接以验证
                            try:
                                page_resp = _req.get(f'http://127.0.0.1:{port}/json', timeout=2)
                                tabs_test = page_resp.json()
                                test_ws_url = None
                                for t in tabs_test:
                                    if t.get('webSocketDebuggerUrl'):
                                        test_ws_url = t['webSocketDebuggerUrl']
                                        break
                                if test_ws_url:
                                    import websocket as _ws_test
                                    test_ws = _ws_test.create_connection(test_ws_url, timeout=3)
                                    test_ws.close()
                            except Exception as ws_err:
                                if '403' in str(ws_err) or 'Forbidden' in str(ws_err):
                                    self._log(f"CDP: Chrome缺少 --remote-allow-origins=* 参数(403)，将自动重启Chrome")
                                    chrome_need_restart = True
                                    break
                                # 其他WebSocket错误，重试下一个端口
                                continue
                            self._log(f"CDP: 成功连接到现有Chrome调试端口 {port}")
                            break
                    except Exception:
                        continue
            if chrome_need_restart:
                # 杀掉旧Chrome进程，下面会重新启动
                self._log("CDP: 正在关闭旧Chrome实例...")
                try:
                    _sp.check_call(['taskkill', '/F', '/IM', 'chrome.exe'],
                                   stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                    time.sleep(2)
                    chrome_running = False
                except Exception:
                    self._log("CDP: 无法自动关闭Chrome，请手动关闭后重试")
                    self._log(f"CDP: 或手动以正确参数启动: \"{chrome_exe}\" --remote-debugging-port=9222 --remote-allow-origins=*")
                    return None
            elif not chrome_need_restart and debug_port:
                pass  # 已成功连接
            else:
                platform_name = "BOSS直聘" if platform == 'boss' else "智联招聘"
                self._log(f"CDP: Chrome运行中且无调试端口，无法获取实时{platform_name}Cookie")
                self._log(f"CDP: 请关闭Chrome后以 --remote-debugging-port=9222 启动: {chrome_exe}")
                return None

        if not chrome_running:
            while True:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('127.0.0.1', debug_port))
                sock.close()
                if result != 0:
                    break
                debug_port += 1
                if debug_port > 9240:
                    return None

            self._log(f"CDP: 启动Chrome调试实例(端口{debug_port}, profile={target_profile})")

            try:
                chrome_process = _sp.Popen(
                    [chrome_exe,
                     f'--remote-debugging-port={debug_port}',
                     f'--user-data-dir={chrome_dir}',
                     f'--profile-directory={target_profile}',
                     '--no-first-run', '--no-default-browser-check',
                     '--remote-allow-origins=*',
                     target_url],
                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL
                )
            except FileNotFoundError:
                return None
            except Exception as e:
                self._log(f"CDP: 启动Chrome失败: {e}")
                return None

            platform_name = "BOSS直聘" if platform == 'boss' else "智联招聘"
            self._log(f"CDP: 等待Chrome启动和{platform_name}JS执行(8秒)...")
            time.sleep(8)

        try:
            import requests as _req
            resp = _req.get(f'http://127.0.0.1:{debug_port}/json', timeout=5)
            tabs = resp.json()
        except Exception as e:
            self._log(f"CDP: 连接调试端口失败: {e}")
            if not chrome_running:
                chrome_process.terminate()
            return None

        ws_url = None
        for tab in tabs:
            if main_domain in tab.get('url', ''):
                ws_url = tab.get('webSocketDebuggerUrl', '')
                break
        if not ws_url and tabs:
            ws_url = tabs[0].get('webSocketDebuggerUrl', '')

        if not ws_url:
            self._log("CDP: 未找到可用tab")
            if not chrome_running:
                chrome_process.terminate()
            return None

        try:
            import websocket
            import json as _json

            nav_ws = websocket.create_connection(ws_url, timeout=10)
            nav_cmd = _json.dumps({
                "id": 1,
                "method": "Page.navigate",
                "params": {"url": search_url}
            })
            nav_ws.send(nav_cmd)
            nav_response = ""
            while True:
                chunk = nav_ws.recv()
                nav_response += chunk
                try:
                    msg = _json.loads(chunk)
                    if msg.get('id') == 1:
                        break
                except Exception:
                    if len(nav_response) > 100000:
                        break
            nav_ws.close()
            platform_name = "BOSS直聘" if platform == 'boss' else "智联招聘"
            self._log(f"CDP: 已导航到{platform_name}，等待JS生成最新token(8秒)...")
            time.sleep(8)

            # 导航后重新获取WebSocket URL（页面切换后URL可能已变）
            try:
                resp2 = _req.get(f'http://127.0.0.1:{debug_port}/json', timeout=5)
                tabs2 = resp2.json()
                ws_url2 = None
                for t in tabs2:
                    if main_domain in t.get('url', ''):
                        ws_url2 = t.get('webSocketDebuggerUrl', '')
                        break
                if not ws_url2 and tabs2:
                    ws_url2 = tabs2[0].get('webSocketDebuggerUrl', '')
                if ws_url2:
                    ws_url = ws_url2
            except Exception:
                pass  # 保留原ws_url
        except Exception as e:
            self._log(f"CDP: 页面导航失败({e})，使用现有页面继续提取...")

        try:
            ws = websocket.create_connection(ws_url, timeout=10)

            cookie_url = f"https://www.{main_domain}"
            cmd = _json.dumps({
                "id": 1,
                "method": "Network.getCookies",
                "params": {"urls": [cookie_url]}
            })
            ws.send(cmd)

            response_data = ""
            while True:
                chunk = ws.recv()
                response_data += chunk
                try:
                    msg = _json.loads(chunk)
                    if msg.get('id') == 1:
                        break
                except Exception:
                    if len(response_data) > 100000:
                        break

            ws.close()

            response = _json.loads(response_data)
            result = response.get('result', {})
            cdp_cookies = result.get('cookies', [])

            cookies = {}
            for c in cdp_cookies:
                cookies[c['name']] = c['value']

            has_zp_stoken = any('zp_stoken' in k.lower() for k in cookies)
            has_wt2 = any('wt2' == k for k in cookies)
            has_wbg = any('wbg' == k for k in cookies)

            has_valid = (platform == 'boss' and has_zp_stoken) or \
                        (platform == 'zhilian' and len(cookies) >= 2)

            if has_valid and platform == 'boss' and (not has_wt2 or not has_wbg):
                # zp_stoken存在但wt2/wbg缺失 → 用户未真正登录，需等待登录
                if not chrome_running:
                    # Chrome是我们启动的，保持打开并轮询等待用户登录
                    self._log(f"CDP: zp_stoken存在但wt2={'OK' if has_wt2 else 'NO'}/wbg={'OK' if has_wbg else 'NO'}，等待用户登录...")
                    self._log(f"CDP: 请在Chrome窗口中登录BOSS直聘，程序将持续检测...")
                    for attempt in range(1, 25):  # 最多轮询24次 = 2分钟
                        time.sleep(5)
                        self._log(f"CDP: 第{attempt}次检测登录状态...")
                        try:
                            import requests as _req2
                            resp2 = _req2.get(f'http://127.0.0.1:{debug_port}/json', timeout=5)
                            tabs2 = resp2.json()
                            ws_url2 = None
                            for t in tabs2:
                                if main_domain in t.get('url', ''):
                                    ws_url2 = t.get('webSocketDebuggerUrl', '')
                                    break
                            if not ws_url2 and tabs2:
                                ws_url2 = tabs2[0].get('webSocketDebuggerUrl', '')
                            if not ws_url2:
                                continue

                            # 导航到搜索页让JS生成最新token
                            nav_ws2 = websocket.create_connection(ws_url2, timeout=10)
                            nav_cmd2 = _json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": search_url}})
                            nav_ws2.send(nav_cmd2)
                            nav_resp2 = ""
                            while True:
                                chunk2 = nav_ws2.recv()
                                nav_resp2 += chunk2
                                try:
                                    msg2 = _json.loads(chunk2)
                                    if msg2.get('id') == 1:
                                        break
                                except Exception:
                                    if len(nav_resp2) > 100000:
                                        break
                            nav_ws2.close()
                            time.sleep(5)

                            # 重新提取cookie
                            resp3 = _req2.get(f'http://127.0.0.1:{debug_port}/json', timeout=5)
                            tabs3 = resp3.json()
                            ws_url3 = None
                            for t in tabs3:
                                if main_domain in t.get('url', ''):
                                    ws_url3 = t.get('webSocketDebuggerUrl', '')
                                    break
                            if not ws_url3 and tabs3:
                                ws_url3 = tabs3[0].get('webSocketDebuggerUrl', '')
                            if not ws_url3:
                                continue

                            ws2 = websocket.create_connection(ws_url3, timeout=10)
                            cmd2 = _json.dumps({"id": 1, "method": "Network.getCookies", "params": {"urls": [f"https://www.{main_domain}"]}})
                            ws2.send(cmd2)
                            resp_data2 = ""
                            while True:
                                chunk2 = ws2.recv()
                                resp_data2 += chunk2
                                try:
                                    msg2 = _json.loads(chunk2)
                                    if msg2.get('id') == 1:
                                        break
                                except Exception:
                                    if len(resp_data2) > 100000:
                                        break
                            ws2.close()

                            resp_json2 = _json.loads(resp_data2)
                            result2 = resp_json2.get('result', {})
                            cdp_cookies2 = result2.get('cookies', [])
                            cookies2 = {}
                            for c in cdp_cookies2:
                                cookies2[c['name']] = c['value']

                            has_wt2_2 = any('wt2' == k for k in cookies2)
                            has_wbg_2 = any('wbg' == k for k in cookies2)
                            self._log(f"CDP: 第{attempt}次检测 wt2={'OK' if has_wt2_2 else 'NO'} wbg={'OK' if has_wbg_2 else 'NO'}")

                            if has_wt2_2 and has_wbg_2:
                                self._log(f"CDP: 登录检测成功！提取到 {len(cookies2)} 个Cookie")
                                return cookies2
                        except Exception as poll_err:
                            self._log(f"CDP: 第{attempt}次检测失败: {poll_err}")

                    # 超时
                    self._log("CDP: 等待登录超时(2分钟)，请确保在Chrome中已登录BOSS直聘后重试")
                    try:
                        chrome_process.terminate()
                    except Exception:
                        pass
                    return None
                else:
                    # Chrome已在运行，但缺少wt2/wbg，提示用户
                    self._log(f"CDP: 提取到Cookie但wt2={'OK' if has_wt2 else 'NO'}/wbg={'OK' if has_wbg else 'NO'}，请在Chrome中刷新BOSS直聘页面后重试")
                    return None

            if has_valid:
                self._log(f"CDP: 成功提取 {len(cookies)} 个实时Cookie (wt2={'OK' if has_wt2 else 'NO'} wbg={'OK' if has_wbg else 'NO'})")
                return cookies
            else:
                self._log(f"CDP: 提取到 {len(cookies)} 个Cookie但验证未通过 ({platform})")

        except ImportError:
            self._log("CDP: 缺少websocket-client库")
        except Exception as e:
            self._log(f"CDP: WebSocket通信失败: {e}")

        if not chrome_running:
            try:
                chrome_process.terminate()
            except Exception:
                pass
        return None

    def _extract_edge_cookies(self, platform: str = 'boss') -> Optional[Dict[str, str]]:
        """从Edge提取Cookie"""
        main_domain = 'zhipin.com' if platform == 'boss' else 'zhaopin.com'
        try:
            cj = browser_cookie3.edge(domain_name=main_domain)
            cookies = {}
            for cookie in cj:
                cookies[cookie.name] = cookie.value
            has_valid = (platform == 'boss' and any('zp_stoken' in k.lower() for k in cookies)) or \
                        (platform == 'zhilian' and len(cookies) >= 2)
            if has_valid:
                return cookies
            cj = browser_cookie3.edge()
            cookies = {}
            for cookie in cj:
                if cookie.domain and main_domain in cookie.domain:
                    cookies[cookie.name] = cookie.value
            has_valid = (platform == 'boss' and any('zp_stoken' in k.lower() for k in cookies)) or \
                        (platform == 'zhilian' and len(cookies) >= 2)
            if has_valid:
                return cookies
            return None
        except Exception as e:
            error_msg = str(e)
            if 'admin' in error_msg.lower():
                self._log("Edge 需要管理员权限读取Cookie，请以管理员身份运行")
            else:
                self._log(f"Edge 提取异常: {e}")
            return None

    @staticmethod
    def format_cookies_for_api(cookies: Dict[str, str]) -> Dict[str, str]:
        """格式化Cookie字典，只保留API需要的字段（兼容BOSS直聘和智联招聘）"""
        key_cookies = {}
        boss_keywords = ('zp_stoken', 'wt2', 'wbg', 'zp_at', 'security', '_bl_uid', 'lid')
        zhilian_keys = {'at', 'rt', 'x-zp-client-id', 'x-zp-device-sn',
                        'zp_passport_deepknow_sessionId', 'scrd_user_id', 'sts_deviceid',
                        'ZP_OLD_FLAG', 'scrd_user_name'}
        for key, val in cookies.items():
            if key in zhilian_keys:
                key_cookies[key] = val
            elif any(kw in key.lower() for kw in boss_keywords):
                key_cookies[key] = val
        return key_cookies


class BOSSApiClient:
    """BOSS直聘 API 客户端
    真实API：通过浏览器Cookie认证调用BOSS直聘WAPI接口

    === 真实API端点（来源：kabi-boss-cli 逆向分析） ===
    搜索岗位:  GET /wapi/zpgeek/search/joblist.json
             参数: query, city, page, pageSize, experience, degree, salary, industry, scale, stage, jobType
             返回: {"code":0, "zpData": {"jobList": [...], "totalCount": N, "hasMore": bool}}

    岗位卡片:  GET /wapi/zpgeek/job/card.json
             参数: securityId, lid
             返回: {"code":0, "zpData": {...}}

    打招呼/投递: GET /wapi/zpgeek/friend/add.json
             参数: securityId, lid
             返回: {"code":0, "zpData": {...}}
             code=0 成功, code=9 频率限制, code=37 session过期

    已投递列表: GET /wapi/zprelation/resume/geekDeliverList
             参数: page
             返回: {"code":0, "zpData": [...]}

    认证方式: Cookie: __zp_stoken__, wt2, wbg, zp_at
             反爬核心: zp_stoken 由浏览器端JS动态生成，需定期从浏览器更新
    """

    # ---- 真实API端点 ----
    BASE_URL = "https://www.zhipin.com"
    SEARCH_URL = "/wapi/zpgeek/search/joblist.json"
    JOB_CARD_URL = "/wapi/zpgeek/job/card.json"
    JOB_DETAIL_URL = "/wapi/zpgeek/job/detail.json"
    ADD_FRIEND_URL = "/wapi/zpgeek/friend/add.json"
    GEEK_GET_JOB_URL = "/wapi/zprelation/interaction/geekGetJob"
    DELIVER_LIST_URL = "/wapi/zprelation/resume/geekDeliverList"
    FRIEND_LIST_URL = "/wapi/zprelation/friend/getGeekFriendList.json"
    USER_INFO_URL = "/wapi/zpuser/wap/getUserInfo.json"
    RESUME_STATUS_URL = "/wapi/zpgeek/resume/status.json"

    # 浏览器Headers（匹配Windows Chrome，与CDP提取的Cookie来源一致）
    DEFAULT_HEADERS = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Origin": BASE_URL,
        "Pragma": "no-cache",
        "Priority": "u=1, i",
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

    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.cookies: Dict[str, str] = {}
        self.is_logged_in = False
        self.use_real_api = HAS_REQUESTS
        self.session: Optional[object] = None
        self._cookie_refresh_count = 0
        self._consecutive_37_count = 0
        self._api_lock = threading.RLock()     # 序列化所有API调用
        self._last_api_call = 0                # 上次API调用时间戳
        self._min_api_interval = 10            # 最小API调用间隔（秒）
        self._last_delivery_time = 0           # 上次投递时间戳
        self._min_delivery_interval = 30       # 投递最小间隔（秒），投递端点更敏感
        self.daily_limit_reached = False       # 是否触发每日120次沟通上限

        if self.use_real_api:
            self.session = requests.Session()
            self.session.trust_env = False
            self.session.headers.update(self.DEFAULT_HEADERS)
            self._log("requests 库就绪，支持真实API调用")
        else:
            self._log("requests 库未安装，将使用模拟数据 (pip install requests)")

    def refresh_cookies_from_browser(self) -> bool:
        """尝试从浏览器自动刷新Cookie（当zp_stoken过期时调用）"""
        if self._cookie_refresh_count >= 5:
            self._log("Cookie刷新次数已达上限(5次)，请手动在Chrome中刷新zhipin.com页面后重试")
            return False
        self._cookie_refresh_count += 1
        self._log(f"尝试从浏览器刷新Cookie (第{self._cookie_refresh_count}次)...")
        try:
            auth = BrowserAuthHelper(log_callback=self.log_callback)
            cookies = auth.extract_cookies()
            if cookies and self.set_cookies(cookies):
                self._cookie_refresh_count = 0
                self._log("Cookie刷新成功，重置计数器")
                return True
            else:
                self._log("浏览器中未找到有效Cookie，请确保Chrome已登录")
                return False
        except Exception as e:
            self._log(f"Cookie刷新异常: {e}")
            return False

    def _log(self, msg):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_msg = f"[{timestamp}] [API] {msg}"
        print(log_msg)
        if self.log_callback:
            try:
                self.log_callback(log_msg)
            except Exception:
                pass

    # ---- Cookie 管理 ----

    ZHILIAN_KEY_COOKIES = ('at', 'rt', 'x-zp-client-id', 'x-zp-device-sn',
                           'zp_passport_deepknow_sessionId', 'scrd_user_id')

    def set_cookies(self, cookie_data, platform: str = 'boss') -> bool:
        """设置认证Cookie，接受两种格式：
        - 字符串: "zp_stoken=xxx; wt2=yyy; wbg=zzz; zp_at=aaa"
        - 字典: {"__zp_stoken__": "xxx", "wt2": "yyy", ...}
        platform: 'boss' → BOSS直聘, 'zhilian' → 智联招聘"""
        if isinstance(cookie_data, dict):
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookie_data.items()])
        else:
            cookie_str = cookie_data
        if not cookie_str or not cookie_str.strip():
            self._log("Cookie字符串为空")
            return False
        try:
            self.cookies = {}
            for part in cookie_str.split(";"):
                part = part.strip()
                if "=" in part:
                    key, val = part.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key and val:
                        self.cookies[key] = val
            self.cookie_platform = platform
            if platform == 'zhilian':
                key_names = self.ZHILIAN_KEY_COOKIES
                found_keys = [k for k in self.cookies if k in key_names]
                self._log(f"解析到 {len(self.cookies)} 个Cookie "
                          f"(关键字段: {found_keys if found_keys else 'NO'})")
                if len(found_keys) >= 2:
                    self.is_logged_in = True
                    if self.use_real_api and self.session:
                        self.session.cookies.clear()
                        for key, val in self.cookies.items():
                            self.session.cookies.set(key, val, domain=".zhaopin.com", path="/")
                    return True
                else:
                    self._log(f"Cookie中缺少智联关键字段(at/rt/x-zp-client-id)，认证失败")
                    return False
            else:
                has_stoken = any('zp_stoken' in k.lower() for k in self.cookies)
                has_wt2 = any('wt2' == k for k in self.cookies)
                has_wbg = any('wbg' == k for k in self.cookies)
                self._log(f"解析到 {len(self.cookies)} 个Cookie "
                          f"(zp_stoken={'OK' if has_stoken else 'NO'}, "
                          f"wt2={'OK' if has_wt2 else 'NO'}, "
                          f"wbg={'OK' if has_wbg else 'NO'})")
                if has_stoken:
                    self.is_logged_in = True
                    if self.use_real_api and self.session:
                        self.session.cookies.clear()
                        for key, val in self.cookies.items():
                            self.session.cookies.set(key, val, domain=".zhipin.com", path="/")
                    return True
                else:
                    self._log("Cookie中未找到 zp_stoken，认证失败")
                    return False
        except Exception as e:
            self._log(f"Cookie解析失败: {e}")
            return False

    def get_cookie_status(self, platform: str = 'boss') -> Dict:
        """获取当前Cookie状态"""
        if platform == 'zhilian':
            required = list(self.ZHILIAN_KEY_COOKIES)
        else:
            required = ["__zp_stoken__", "zp_stoken", "wt2", "wbg", "zp_at"]
        found = []
        missing = []
        for key in required:
            if platform == 'zhilian':
                matched = key in self.cookies
            else:
                matched = any(key in k for k in self.cookies)
            if matched:
                found.append(key)
            else:
                missing.append(key)
        return {
            "total": len(self.cookies),
            "found": found,
            "missing": missing,
            "is_valid": len(found) >= 2
        }

    # ---- 通用请求方法 ----

    def _api_get(self, path: str, params: dict = None, action: str = "API请求",
                 retry_on_expire: bool = True, _fast_retry: int = 0) -> Optional[Dict]:
        """通用GET请求（线程安全，自动限速，最多3次"操作太快"重试）"""
        if not self.use_real_api or not self.session:
            return None

        with self._api_lock:
            # 冷却等待：确保两次API调用间隔≥10秒
            elapsed = time.time() - self._last_api_call
            if elapsed < self._min_api_interval:
                wait = self._min_api_interval - elapsed + random.uniform(0, 2)
                if wait > 0.5:
                    self._log(f"[{action}] API冷却 {wait:.1f}秒...")
                time.sleep(wait)
            self._last_api_call = time.time()

            url = f"{self.BASE_URL}{path}"
            try:
                resp = self.session.get(url, params=params, timeout=15)
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    self._log(f"[{action}] 登录已过期，正尝试自动刷新...")
                    if retry_on_expire and self.refresh_cookies_from_browser():
                        time.sleep(2)
                        return self._api_get(path, params, action, retry_on_expire=False)
                    return None
                data = resp.json()
                code = data.get("code", -1)
                msg = data.get("message", "")
                if code == 0:
                    self._consecutive_37_count = 0
                    return data.get("zpData", data)
                elif code == 37:
                    self._consecutive_37_count += 1
                    self._log(f"[{action}] 需要重新验证(第{self._consecutive_37_count}次)")
                    if self._consecutive_37_count >= 3 or retry_on_expire:
                        self._log(f"[{action}] 正在自动刷新验证信息...")
                        if self.refresh_cookies_from_browser():
                            self._consecutive_37_count = 0
                            time.sleep(2)
                            return self._api_get(path, params, action, retry_on_expire=False)
                    return None
                elif code in (1, 9):
                    # "开聊提醒" = 每日120次沟通上限，必须手动在APP触发，重试无效
                    if "开聊" in str(msg):
                        self._log(f"[{action}] 触发每日沟通上限(120次): code={code} msg={msg}")
                        self._log(f"[{action}] 完整响应: {json.dumps(data, ensure_ascii=False)}")
                        self.daily_limit_reached = True
                        return None
                    if _fast_retry < 2:  # 最多重试3次(0,1,2)，等待递增
                        wait = 8 * (_fast_retry + 1)
                        self._log(f"[{action}] 操作太快(code={code} {msg}), {wait}秒后重试({_fast_retry+1}/3)...")
                        time.sleep(wait)
                        return self._api_get(path, params, action, retry_on_expire,
                                            _fast_retry=_fast_retry + 1)
                    self._log(f"[{action}] 操作太快(code={code} {msg})，已达最大重试次数")
                    return None
                elif code in (17, 19):
                    self._log(f"[{action}] 参数有误: {msg}")
                    return None
                elif code in (121, 122):
                    self._log(f"[{action}] 安全验证未通过，请刷新登录")
                    return None
                else:
                    if msg:
                        self._log(f"[{action}] 失败({code}): {msg}")
                    return None
            except requests.exceptions.Timeout:
                self._log(f"[{action}] 请求超时，请检查网络")
                return None
            except requests.exceptions.ConnectionError:
                self._log(f"[{action}] 网络连接失败，请检查网络")
                return None
            except Exception as e:
                self._log(f"[{action}] 网络异常: {e}")
                return None

    def _api_post(self, path: str, json_data: dict = None, action: str = "API请求",
                  retry_on_expire: bool = True, _fast_retry: int = 0) -> Optional[Dict]:
        """通用POST请求（线程安全，自动限速，最多3次"操作太快"重试）"""
        if not self.use_real_api or not self.session:
            return None

        with self._api_lock:
            # 冷却等待：确保两次API调用间隔≥10秒
            elapsed = time.time() - self._last_api_call
            if elapsed < self._min_api_interval:
                wait = self._min_api_interval - elapsed + random.uniform(0, 2)
                if wait > 0.5:
                    self._log(f"[{action}] API冷却 {wait:.1f}秒...")
                time.sleep(wait)
            self._last_api_call = time.time()

            url = f"{self.BASE_URL}{path}"
            try:
                resp = self.session.post(url, json=json_data, timeout=15)
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    self._log(f"[{action}] 登录已过期，正尝试自动刷新...")
                    if retry_on_expire and self.refresh_cookies_from_browser():
                        time.sleep(2)
                        return self._api_post(path, json_data, action, retry_on_expire=False)
                    return None
                data = resp.json()
                code = data.get("code", -1)
                msg = data.get("message", "")
                if code == 0:
                    self._consecutive_37_count = 0
                    return data.get("zpData", data)
                elif code == 37:
                    self._consecutive_37_count += 1
                    self._log(f"[{action}] 需要重新验证(第{self._consecutive_37_count}次)")
                    if self._consecutive_37_count >= 3 or retry_on_expire:
                        self._log(f"[{action}] 正在自动刷新验证信息...")
                        if self.refresh_cookies_from_browser():
                            self._consecutive_37_count = 0
                            time.sleep(2)
                            return self._api_post(path, json_data, action, retry_on_expire=False)
                    return None
                elif code in (1, 9):
                    # "开聊提醒" = 每日120次沟通上限，必须手动在APP触发，重试无效
                    if "开聊" in str(msg):
                        self._log(f"[{action}] 触发每日沟通上限(120次): code={code} msg={msg}")
                        self._log(f"[{action}] 完整响应: {json.dumps(data, ensure_ascii=False)}")
                        self.daily_limit_reached = True
                        return None
                    if _fast_retry < 2:  # 最多重试3次(0,1,2)，等待递增
                        wait = 8 * (_fast_retry + 1)
                        self._log(f"[{action}] 操作太快(code={code} {msg}), {wait}秒后重试({_fast_retry+1}/3)...")
                        time.sleep(wait)
                        return self._api_post(path, json_data, action, retry_on_expire,
                                             _fast_retry=_fast_retry + 1)
                    self._log(f"[{action}] 操作太快(code={code} {msg})，已达最大重试次数")
                    return None
                else:
                    if msg:
                        self._log(f"[{action}] 失败({code}): {msg}")
                    return None
            except requests.exceptions.Timeout:
                self._log(f"[{action}] 请求超时，请检查网络")
                return None
            except requests.exceptions.ConnectionError:
                self._log(f"[{action}] 网络连接失败，请检查网络")
                return None
            except Exception as e:
                self._log(f"[{action}] 网络异常: {e}")
                return None

    # ---- 真实API：搜索岗位 ----

    def _fetch_jobs_real(self, keyword: str = "", location: str = "",
                         page: int = 1, page_size: int = 15) -> Optional[Dict]:
        """真实API：搜索岗位列表
        GET /wapi/zpgeek/search/joblist.json
        参数: query, city, page, pageSize
        返回字段(jobList[]): jobName, salaryDesc, cityName, areaDistrict,
              brandName, brandScaleName, brandStageName, brandIndustry,
              jobDegree, jobLabels, encryptJobId, securityId, lid, bossName, bossTitle
        """
        city_code = resolve_city_code(location)
        params = {
            "query": keyword or "",
            "city": city_code,
            "page": page,
            "pageSize": page_size,
        }
        self._log(f"搜索岗位: {keyword or '不限'} {location or '全国'} 第{page}页")

        result = self._api_get(self.SEARCH_URL, params=params, action="搜索岗位")
        if result is None and self._cookie_refresh_count < 1:
            if self.refresh_cookies_from_browser():
                result = self._api_get(self.SEARCH_URL, params=params, action="搜索岗位(重试)")
        if not result:
            return None

        job_list = result.get("jobList", [])
        jobs = {}
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in job_list:
            encrypt_id = item.get("encryptJobId", "")
            if not encrypt_id:
                continue

            url = f"https://www.zhipin.com/job_detail/{encrypt_id}.html"
            jobs[url] = {
                "status": 0,
                "title": item.get("jobName", "未知岗位"),
                "company": item.get("brandName", "未知"),
                "hr_name": item.get("bossName", ""),
                "match_score": 0,
                "updated_at": now_str,
                "salary": item.get("salaryDesc", ""),
                "location": item.get("cityName", ""),
                "district": item.get("areaDistrict", ""),
                "job_detail": "",
                "_security_id": item.get("securityId", ""),
                "_lid": item.get("lid", ""),
                "_encrypt_id": encrypt_id,
                "degree": item.get("jobDegree", ""),
                "labels": item.get("jobLabels", []),
                "company_scale": item.get("brandScaleName", ""),
                "company_stage": item.get("brandStageName", ""),
                "company_industry": item.get("brandIndustry", ""),
            }
        self._log(f"真实API获取到 {len(jobs)} 个岗位 (第{page}页, 共{result.get('totalCount', '?')}个)")
        return jobs

    # ---- 真实API：打招呼/投递 ----

    def _deliver_job_real(self, security_id: str, lid: str = "", greeting: str = "") -> Optional[Dict]:
        """真实API：打招呼/投递简历 + 发送招呼语
        GET /wapi/zpgeek/friend/add.json?securityId=xxx&lid=xxx&greeting=xxx
        返回: 响应数据(含encBossId) 或 None
        """
        if not security_id:
            self._log("缺少 securityId，无法投递")
            return None

        # 投递端点比搜索更敏感，强制30秒最小间隔
        elapsed = time.time() - self._last_delivery_time
        if elapsed < self._min_delivery_interval:
            wait = self._min_delivery_interval - elapsed + random.uniform(0, 3)
            self._log(f"投递冷却 {wait:.1f}秒（上次投递距今仅{elapsed:.0f}秒）...")
            time.sleep(wait)

        params = {"securityId": security_id}
        if lid:
            params["lid"] = lid
        if greeting:
            params["greeting"] = greeting

        if self.session:
            self.session.headers["Referer"] = f"{self.BASE_URL}/web/geek/chat"

        result = self._api_get(self.ADD_FRIEND_URL, params=params, action="打招呼/投递")
        self._last_delivery_time = time.time()

        if self.session:
            self.session.headers["Referer"] = f"{self.BASE_URL}/web/geek/job"

        return result

    # ---- 真实API：岗位详情 ----

    def _get_job_detail_real(self, security_id: str, lid: str = "") -> Optional[dict]:
        """真实API：获取岗位详情
        GET /wapi/zpgeek/job/detail.json?securityId=xxx&lid=xxx
        返回 dict: {description, active_time, active_time_desc}
        """
        if not security_id:
            return None
        params = {"securityId": security_id}
        if lid:
            params["lid"] = lid

        result = self._api_get(self.JOB_DETAIL_URL, params=params, action="获取岗位详情")
        if result:
            job_info = result.get("jobInfo", result)
            if isinstance(job_info, dict):
                desc = job_info.get("jobDescription", job_info.get("postDescription", ""))
                boss_info = result.get("bossInfo", {}) or {}
                brand_info = result.get("brandComInfo", {}) or {}
                active_time = brand_info.get("activeTime", 0) or boss_info.get("activeTime", 0) or 0
                active_time_desc = boss_info.get("activeTimeDesc", "")
            else:
                desc = ""
                active_time = 0
                active_time_desc = ""
            if desc:
                self._log(f"获取岗位详情成功 ({len(desc)}字符, activeTime={active_time})")
            return {
                "description": desc,
                "active_time": active_time,
                "active_time_desc": active_time_desc,
            }
        return None

    # ---- 对外统一接口 ----

    def login(self, cookie_str: str = "", platform: str = 'boss') -> bool:
        """登录：设置Cookie认证
        真实模式：Cookie解析成功即视为登录成功（实际验证在后续API调用中进行）
        模拟模式：直接标记登录成功
        platform: 'boss' → BOSS直聘, 'zhilian' → 智联招聘
        """
        platform_name = "智联招聘" if platform == 'zhilian' else "BOSS直聘"
        if cookie_str and cookie_str.strip():
            self._log(f"正在解析 {platform_name} Cookie...")
            if self.set_cookies(cookie_str, platform=platform):
                if self.use_real_api:
                    result = self._api_get(self.USER_INFO_URL, action="验证Cookie有效性")
                    if result is not None:
                        self._log(f"{platform_name} Cookie有效，登录成功")
                    else:
                        self._log(f"{platform_name} Cookie已设置（在线验证未通过，可在后续操作中验证）")
                else:
                    self._log(f"{platform_name} Cookie已设置（离线模式）")
                return True
            key_field = "at/rt/x-zp-client-id" if platform == 'zhilian' else "zp_stoken"
            self._log(f"{platform_name} Cookie解析失败，缺少关键认证字段({key_field})")
            return False
        else:
            self._log("未提供Cookie，使用模拟登录模式")
            self.is_logged_in = True
            self._log("模拟登录成功 → 后续操作使用模拟数据")
            return True

    def refresh_token(self) -> bool:
        """刷新登录态：提示用户重新获取Cookie"""
        self._log("Cookie过期后需要从浏览器重新复制Cookie")
        self.is_logged_in = False
        self.cookies = {}
        if self.session:
            self.session.cookies.clear()
        return True

    def fetch_jobs(self, keyword: str = "", location: str = "", page: int = 1) -> Dict:
        """获取岗位列表（真实API，Cookie未设置时返回空）
        多关键字以空格分隔，客户端二次筛选：岗位标题必须包含所有关键字
        """
        if not self.cookies:
            self._log("未设置Cookie，无法获取岗位")
            return {}

        # 解析多关键字
        keywords = [k.strip() for k in (keyword or "").split() if k.strip()]
        self._log(f"获取岗位列表: 关键词={keyword or '全部'}, 地区={location or '全国'}, 页码={page}")

        result = self._fetch_jobs_real(keyword=keyword, location=location, page=page)
        if result is None:
            self._log("真实API获取岗位失败，请检查Cookie是否有效")
            return {}

        # 多关键字AND筛选：标题必须包含所有关键字
        if len(keywords) > 1 and result:
            filtered = {}
            for url, job in result.items():
                title = job.get("title", "")
                if all(kw.lower() in title.lower() for kw in keywords):
                    filtered[url] = job
            skipped = len(result) - len(filtered)
            if skipped > 0:
                self._log(f"多关键字筛选: {len(result)}个→{len(filtered)}个（需同时包含{' + '.join(keywords)}，过滤{skipped}个）")
            return filtered
        return result

    def deliver_job(self, job_url: str, greeting: str = "", job_data: Dict = None) -> bool:
        """投递岗位/打招呼（仅真实API，无模拟降级）
        job_data: 岗位数据字典，需包含 _security_id 和 _lid 字段
        招呼语通过 friend/add.json 的 greeting 参数直接发送
        """
        if not self.cookies:
            self._log("未设置Cookie，无法投递")
            return False

        greet_preview = greeting[:50] if greeting else "(无)"
        self._log(f"投递岗位: {job_url} | 招呼语: {greet_preview}...")

        delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
        self._log(f"延时 {delay:.1f} 秒（防封控）...")

        if self.use_real_api and self.cookies and job_data:
            security_id = job_data.get("_security_id", "")
            lid = job_data.get("_lid", "")
            if not security_id:
                self._log("缺少 securityId，无法投递（岗位数据不完整）")
                return False

            time.sleep(delay)
            result = self._deliver_job_real(security_id, lid, greeting)
            if not result:
                self._log("真实API投递失败，可能是频率限制/Cookie过期/岗位已下架")
                return False

            self._log(f"真实API投递成功: {job_url}")
            return True

        self._log("缺少必要参数，无法投递")
        return False

    def get_job_detail(self, job_url: str, job_data: Dict = None) -> Optional[str]:
        """获取岗位详情描述（仅真实API）"""
        self._log(f"获取岗位详情: {job_url}")

        if self.use_real_api and self.cookies and job_data:
            security_id = job_data.get("_security_id", "")
            lid = job_data.get("_lid", "")
            if security_id:
                detail = self._get_job_detail_real(security_id, lid)
                if detail:
                    return detail

        return None


# ==================== ResumeAnalyzer ====================

class ResumeAnalyzer:
    """简历分析器，负责简历解析、AI分析、匹配度计算、招呼语生成"""

    def __init__(self):
        self.client = openai.OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL
        )
        self.resume_content = None
        self.resume_text = None
        self.log_callback = None

    def _log(self, msg):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_msg = f"[{timestamp}] [AI] {msg}"
        print(log_msg)
        if self.log_callback:
            try:
                self.log_callback(log_msg)
            except Exception:
                pass

    def extract_text_from_pdf(self, pdf_path):
        """从PDF文件中提取文本"""
        try:
            text = ""
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            self.resume_text = text
            self._log(f"PDF解析完成，共提取 {len(text)} 个字符")
            return text
        except Exception as e:
            self._log(f"PDF解析失败: {e}")
            return None

    def analyze_resume(self, resume_text=None):
        """AI分析简历内容，推荐岗位类型和搜索关键词"""
        text = resume_text or self.resume_text
        if not text:
            self._log("简历内容为空，无法分析")
            return None

        prompt = f"""请分析以下简历内容，并推荐适合投递的岗位类型和关键词。

简历内容：
{text}

请从以下角度分析：
1. 候选人的核心技能和优势
2. 适合投递的岗位类型（列出5-10个具体岗位名称）
3. 搜索岗位时应使用的关键词
4. 建议投递的行业方向
5. 从简历中推断候选人期望的工作城市（如简历无明确信息，根据工作经历所在城市推断）

请以JSON格式返回结果，格式如下：
{{
    "skills": ["技能1", "技能2"],
    "recommended_positions": ["岗位1", "岗位2"],
    "search_keywords": ["关键词1", "关键词2"],
    "recommended_industries": ["行业1", "行业2"],
    "preferred_cities": ["城市1", "城市2"]
}}
"""

        try:
            self._log(f"请求简历分析 (模型: {DEEPSEEK_MODEL})")
            t0 = time.time()

            response = self.client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的职业规划顾问，擅长分析简历并推荐合适的岗位。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4096,
            )

            elapsed = time.time() - t0
            result = response.choices[0].message.content
            self._log(f"简历分析响应成功 (耗时 {elapsed:.1f}s): {result}")

            try:
                json_start = result.find('{')
                json_end = result.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    json_str = result[json_start:json_end]
                    data = json.loads(json_str)
                    self._log(f"简历分析解析成功: 推荐{len(data.get('recommended_positions', []))}个岗位")
                    return data
            except Exception:
                pass

            return {"raw_analysis": result}
        except Exception as e:
            self._log(f"简历分析API请求失败: {e}")
            return None

    def calculate_match_score(self, resume_text, job_title, job_detail, company_name=""):
        """AI计算简历与岗位的匹配度（每次调用使用独立请求ID，确保无上下文污染）"""
        request_id = uuid.uuid4().hex[:8]
        prompt = f"""请以专业HR视角，公正评估简历与岗位的匹配程度。注意：只要岗位方向与候选人背景大致对口，基础分就应在50-65之间；技能和经验有较多重叠时应在65-80之间；高度吻合时80以上。

【简历内容】
{resume_text[:2500]}

【岗位信息】
岗位名称：{job_title}
公司名称：{company_name}
岗位详情：
{job_detail[:2000]}

【评估维度】（每个维度0-100分）
1. 技能匹配：候选人掌握的技能/工具/技术栈与岗位要求的吻合度
2. 经验匹配：工作年限、项目经验、职位层级是否匹配
3. 行业匹配：是否有该行业/领域的相关经验
4. 职责匹配：是否能胜任岗位描述中的核心工作内容
5. 综合匹配：综合以上维度加权计算（非简单平均，技能和职责权重最高）

【评分标准】
0-30: 完全不搭边 | 30-50: 匹配度较低 | 50-65: 大致对口 | 65-80: 匹配良好 | 80-100: 高度匹配

请以JSON格式返回：
{{
    "score": 72,
    "skill_score": 70,
    "experience_score": 68,
    "industry_score": 65,
    "duty_score": 75,
    "reasons": ["简历中的XXX技能与岗位要求的XXX高度吻合", "有N年XXX行业经验，符合岗位行业偏好"],
    "concerns": ["岗位要求XXX，但简历中未体现相关经验"],
    "job_requirements": ["技能要求1", "技能要求2"],
    "analysis": "总体评价：该候选人...（50字以内的综合判断）"
}}

score为综合匹配度0-100整数。reasons为匹配点列表。concerns为不匹配/风险点列表。analysis为50字内综合判断。
请求ID: {request_id}"""
        try:
            self._log(f"请求匹配度: {job_title} @ {company_name} (模型: {DEEPSEEK_MODEL}, rid={request_id})")
            t0 = time.time()

            response = self.client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": f"你是专业HR，擅长公正、严格、差异化地评估简历与岗位匹配度。每次评估完全独立，必须根据岗位实际要求与候选人背景的对比给出不同分数，严禁给出千篇一律的分数。评分范围0-100，真正匹配的给高分，不匹配的给低分，不要锚定在某个区间。本次评估ID: {request_id}"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4096,
            )

            elapsed = time.time() - t0
            result = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            if finish_reason == "length":
                self._log(f"匹配度响应被截断(finish_reason=length)，可能评分不准，原始: {result[:200]}...")
            self._log(f"匹配度响应成功 (耗时 {elapsed:.1f}s, finish={finish_reason}): {result}")

            try:
                json_start = result.find('{')
                json_end = result.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    json_str = result[json_start:json_end]
                    data = json.loads(json_str)
                    score = data.get('match_score', data.get('score', 50))
                    self._log(f"匹配度解析成功: score={score}")
                    return {
                        'score': int(score),
                        'skill_score': data.get('skill_score', 0),
                        'experience_score': data.get('experience_score', 0),
                        'industry_score': data.get('industry_score', 0),
                        'duty_score': data.get('duty_score', 0),
                        'skill_match': data.get('skill_match', ''),
                        'experience_match': data.get('experience_match', ''),
                        'industry_match': data.get('industry_match', ''),
                        'reasons': data.get('reasons', []),
                        'concerns': data.get('concerns', []),
                        'job_requirements': data.get('job_requirements', []),
                        'analysis': data.get('analysis', ''),
                    }
            except Exception as e:
                self._log(f"匹配度JSON解析失败: {e}, 原始: {result[:100]}")

            return {'score': 50, 'reasons': [], 'concerns': [], 'job_requirements': []}
        except Exception as e:
            self._log(f"匹配度API请求失败: {e}")
            return {'score': 50, 'reasons': [], 'concerns': [], 'job_requirements': []}

    def generate_greeting_message(self, job_title, company_name, resume_text=None, job_detail=""):
        """AI生成个性化的打招呼语"""
        text = resume_text or self.resume_text

        prompt = f"""请根据简历和岗位详情，生成一段专业、诚实且多样化的打招呼语。

【重要规则 - 绝对不能违反】
1. 绝对不能编造简历中没有的技能、经验或项目
2. 只能使用简历中明确提到的内容
3. 如果简历中没有明确提到的内容，绝对不能在打招呼语中出现
4. 不要过度引申或夸大简历内容
5. 绝对不要提及HR的姓名
6. 每次生成的打招呼语都要不一样，不要重复相同的开场白
7. 不要固定说"拥有X年测试与需求分析结合经验"这种话，要根据简历内容灵活组织语言

简历内容（必须严格基于此生成）：
{text[:2000] if text else '无'}

岗位名称：{job_title}
公司名称：{company_name}
岗位详情：
{job_detail[:1500] if job_detail else '无'}

要求：
1. 长度控制在80-120字
2. 只突出简历中明确提到的技能和经验
3. 绝对不能编造任何简历中没有的内容
4. 不要提及HR姓名
5. 表达求职意向，语气专业、真诚
6. 不要使用"贵公司"等过于客套的词
7. 每次生成的打招呼语都要有变化，不要千篇一律
8. 直接返回打招呼内容，不要其他解释"""

        try:
            self._log(f"请求生成打招呼语: {job_title} @ {company_name}")
            t0 = time.time()

            response = self.client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": "你是诚实且有创意的求职助手，生成专业、诚实、多样化的打招呼语，绝不编造简历内容。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9,
                max_tokens=512,
            )

            elapsed = time.time() - t0
            result = response.choices[0].message.content.strip()
            self._log(f"打招呼语生成成功 (耗时 {elapsed:.1f}s): {result[:80]}...")
            return result
        except Exception as e:
            self._log(f"打招呼语API请求失败: {e}")
            return f"您好，我对{company_name}的{job_title}岗位很感兴趣，我有相关经验，希望能有机会进一步沟通，谢谢！"


# ==================== BossBrowserDeliverer ====================

class BossBrowserDeliverer:
    """BOSS直聘浏览器投递引擎（基于DrissionPage）

    职责：搜索岗位、提取信息、获取详情、投递（含招呼语）
    注意：不含search_and_deliver主循环 — 由QThread Worker驱动
    使用方式：
        page = ChromiumPage()
        deliverer = BossBrowserDeliverer(page, resume_analyzer, log_callback)
        deliverer.navigate(url)
        cards = deliverer.get_job_cards()
        for card in cards:
            info = deliverer.extract_job_info_from_card(card)
            detail, hr = deliverer.get_job_detail_and_hr(info)
            info['job_detail'] = detail
            info['hr_name'] = hr
            deliverer.deliver_job(info, greeting=greeting)
    """

    def __init__(self, page, resume_analyzer=None, log_callback=None):
        """初始化投递引擎

        Args:
            page: ChromiumPage实例（已登录BOSS直聘）
            resume_analyzer: ResumeAnalyzer实例（可选，用于AI招呼语生成）
            log_callback: 日志回调函数（可选）
        """
        self.page = page
        self.resume_analyzer = resume_analyzer
        self.log_callback = log_callback
        self.delivery_count = 0
        self.max_delivery = MAX_DELIVERY_COUNT
        self.running = True
        self.delivery_log = []
        self.seen_job_urls = set()

    # ═══════════════════════════════════════════════════════
    #  日志 & 控制
    # ═══════════════════════════════════════════════════════

    def log(self, msg):
        """输出日志（同时输出到控制台和回调）"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_msg = f"[{timestamp}] {msg}"
        print(log_msg)
        if self.log_callback:
            try:
                self.log_callback(log_msg)
            except Exception:
                pass

    def stop(self):
        """安全停止投递引擎"""
        self.running = False
        self.log("正在停止投递引擎...")

    # ═══════════════════════════════════════════════════════
    #  导航
    # ═══════════════════════════════════════════════════════

    def navigate(self, url, max_retries=3):
        """导航到目标URL，支持断线自动重连

        Args:
            url: 目标URL
            max_retries: 最大重试次数

        Returns:
            bool: 是否导航成功
        """
        for attempt in range(max_retries):
            try:
                self.page.get(url)
                time.sleep(random.uniform(1.5, 3.0))
                return True
            except PageDisconnectedError:
                self.log(f"  >> 页面连接断开 (第{attempt + 1}次重试)...")
                time.sleep(3 * (attempt + 1))
            except Exception as e:
                if 'disconnect' in str(e).lower() or 'disconnected' in str(e).lower():
                    self.log(f"  >> 连接异常 (第{attempt + 1}次): {e}")
                    time.sleep(3 * (attempt + 1))
                    if attempt == max_retries - 1:
                        return False
                    continue
                raise
        return False

    # ═══════════════════════════════════════════════════════
    #  URL 构建
    # ═══════════════════════════════════════════════════════

    def build_search_url(self, city_code, keyword):
        """构建BOSS直聘搜索URL

        Args:
            city_code: 城市编码
            keyword: 搜索关键词

        Returns:
            str: 完整搜索URL
        """
        base = f"https://www.zhipin.com/web/geek/jobs?city={city_code}"
        return f"{base}&query={keyword}"

    def load_more_content(self):
        """滚动加载更多岗位卡片，返回 True 表示加载成功"""
        try:
            for i in range(3):
                self.page.scroll.to_bottom()
                time.sleep(1)
            return True
        except:
            return False

    # ═══════════════════════════════════════════════════════
    #  通用DOM工具
    # ═══════════════════════════════════════════════════════

    def wait_for_element(self, page, selector, timeout=5):
        """等待元素出现并返回"""
        try:
            return page.ele(selector, timeout=timeout)
        except:
            return None

    def log_delivery(self, job_info, success, reason=""):
        """记录投递日志"""
        log_entry = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'job_title': job_info.get('title', '未知'),
            'company': job_info.get('company', '未知'),
            'success': success,
            'reason': reason
        }
        self.delivery_log.append(log_entry)
        if success:
            self.log(f"  >> 投递成功: {job_info.get('title', '未知')} - {job_info.get('company', '未知')}")
        else:
            self.log(f"  >> 投递失败: {job_info.get('title', '未知')} - {job_info.get('company', '未知')} - {reason}")

    # ═══════════════════════════════════════════════════════
    #  岗位卡片获取
    # ═══════════════════════════════════════════════════════

    def get_job_cards(self, page=None):
        """从页面获取岗位卡片列表

        Args:
            page: 指定页面实例，默认使用self.page

        Returns:
            List: 岗位卡片DOM元素列表
        """
        cards = []
        current_page = page or self.page
        try:
            self.log("正在获取岗位卡片...")

            # 尝试多种CSS选择器找到岗位卡片
            job_card_selectors = [
                '.job-primary',
                '.job-card',
                '.job-item'
            ]

            job_cards = []
            for selector in job_card_selectors:
                try:
                    cards = current_page.eles(selector, timeout=3)
                    if cards:
                        job_cards = cards
                        self.log(f"使用选择器 {selector} 找到 {len(job_cards)} 个岗位卡片")
                        break
                except Exception:
                    continue

            if not job_cards:
                # 备选方案：遍历所有<a>链接，筛选job_detail链接
                try:
                    all_as = current_page.eles('tag:a', timeout=3)
                    self.log(f"页面a元素总数: {len(all_as)}")

                    # 诊断：打印前15个含job_detail的链接详情
                    debug_count = 0
                    for idx, a in enumerate(all_as):
                        try:
                            href = a.attr('href') or ''
                            if 'job_detail' in href:
                                if debug_count < 15:
                                    raw_text = a.text
                                    # 尝试通过js获取innerText
                                    try:
                                        js_text = a.run_js('return this.innerText || "";')
                                    except Exception:
                                        js_text = ""
                                    self.log(f"  [调试{debug_count+1}] idx={idx}, href={href[:120]}")
                                    self.log(f"           a.text={repr(raw_text)}, innerText={repr(js_text[:80])}")
                                    debug_count += 1
                        except Exception:
                            continue

                    filtered_links = []
                    seen_urls = set()

                    for idx, a in enumerate(all_as):
                        try:
                            href = a.attr('href') or ''
                            if 'job_detail' in href:
                                job_url = href
                                if not job_url.startswith('http'):
                                    job_url = f"https://www.zhipin.com{job_url}"

                                if job_url in seen_urls:
                                    continue
                                seen_urls.add(job_url)

                                # 尝试多种方式提取文本
                                title = ""
                                try:
                                    title = a.run_js('return this.innerText || "";').strip()
                                except Exception:
                                    pass
                                if not title:
                                    title = (a.text or "").strip()

                                # 跳过明显的非岗位链接
                                skip_titles = ["查看更多信息", "职位搜索", "", "未知"]
                                if title in skip_titles:
                                    continue

                                if job_url and "job_detail" in job_url:
                                    self.log(f"  岗位链接 {len(filtered_links) + 1}: {title[:30]} - {job_url[:100]}")
                                    filtered_links.append(a)
                        except Exception:
                            continue

                    cards = filtered_links[:30]
                    self.log(f"找到 {len(cards)} 个岗位链接")
                    return cards
                except Exception as e:
                    self.log(f"获取a元素失败: {e}")
                    return []
            else:
                # 从卡片中提取去重后的有效卡片
                filtered_cards = []
                seen_urls = set()

                for idx, card in enumerate(job_cards):
                    try:
                        job_links = card.eles('tag:a')
                        job_link = None
                        job_url = None
                        title = "未知"

                        for link in job_links:
                            href = link.attr('href') or ''
                            if 'job_detail' in href:
                                job_link = link
                                job_url = href
                                if not job_url.startswith('http'):
                                    job_url = f"https://www.zhipin.com{job_url}"
                                title = "未知"
                                try:
                                    title = link.run_js('return this.innerText || "";').strip()
                                except Exception:
                                    pass
                                if not title:
                                    title = (link.text or "").strip() or "未知"
                                break

                        if job_url and job_url not in seen_urls:
                            seen_urls.add(job_url)
                            if title and title not in ["查看更多信息", "职位搜索", "", "未知"]:
                                self.log(f"  岗位卡片 {idx + 1}: {job_url} - {title}")
                                filtered_cards.append(card)
                    except Exception:
                        continue

                cards = filtered_cards[:30]
                self.log(f"找到 {len(cards)} 个岗位卡片")
                return cards

        except Exception as e:
            self.log(f"获取岗位卡片失败: {e}")
            import traceback
            traceback.print_exc()

        return cards

    # ═══════════════════════════════════════════════════════
    #  岗位信息提取
    # ═══════════════════════════════════════════════════════

    def extract_job_info_from_card(self, card):
        """从卡片DOM元素提取岗位基本信息

        Args:
            card: 岗位卡片DOM元素

        Returns:
            Optional[Dict]: 包含 title / company / salary / location / publish_time / url
        """
        try:
            title = "未知"
            company = "未知"
            salary = "面议"
            location = "未知"
            publish_time = "未知"
            job_url = None

            # 获取岗位链接
            if card.tag == 'a':
                job_link = card
            else:
                job_link = None
                all_links = card.eles('tag:a')
                for link in all_links:
                    href = link.attr('href') or ''
                    if 'job_detail' in href:
                        job_link = link
                        break

            if job_link:
                job_url = job_link.attr('href')
                if job_url and not job_url.startswith('http'):
                    job_url = f"https://www.zhipin.com{job_url}"
                # 优先用innerText提取嵌套元素文本
                title = "未知"
                try:
                    title = job_link.run_js('return this.innerText || "";').strip()
                except Exception:
                    pass
                if not title:
                    title = (job_link.text or "").strip() or "未知"

            # 提取公司名称
            try:
                company_selectors = [
                    '.company-name',
                    '.company',
                    '.company-text'
                ]
                for selector in company_selectors:
                    try:
                        company_elements = card.eles(selector, timeout=1)
                        if company_elements:
                            company = company_elements[0].text.strip() if company_elements[0].text else "未知"
                            if company != "未知":
                                break
                    except:
                        pass

                if company == "未知":
                    company_elements = card.eles('tag:span', timeout=1)
                    for elem in company_elements:
                        text = elem.text.strip() if elem.text else ""
                        if text and len(text) > 2 and len(text) < 50:
                            if "公司" in text or "科技" in text or "集团" in text or "有限公司" in text:
                                company = text
                                break
            except:
                pass

            if title == "未知" and not job_url:
                return None

            return {
                'title': title,
                'company': company,
                'salary': salary,
                'location': location,
                'publish_time': publish_time,
                'url': job_url
            }
        except:
            return None

    # ═══════════════════════════════════════════════════════
    #  岗位详情 & HR 提取
    # ═══════════════════════════════════════════════════════

    def get_job_detail_and_hr(self, job_info, page=None):
        """打开新标签页，提取岗位详情文本和HR姓名

        Args:
            job_info: 岗位信息字典（必须包含url）
            page: 指定页面实例

        Returns:
            tuple: (detail_text, hr_name)
        """
        if not job_info.get('url'):
            return None, None

        current_page = page or self.page

        try:
            self.log(f"       >> 访问详情页...")
            new_tab = current_page.new_tab(job_info['url'])

            try:
                self.wait_for_element(new_tab, '.job-name', timeout=3)
            except:
                pass

            detail_parts = []
            hr_name = ""

            # 提取岗位名称
            try:
                title_elem = self.wait_for_element(new_tab, '.job-name, .name, h1', timeout=2)
                if title_elem and title_elem.text:
                    detail_parts.append(f"岗位名称: {title_elem.text.strip()}")
            except:
                pass

            # 提取薪资
            try:
                salary_elem = self.wait_for_element(new_tab, '.salary, .job-salary', timeout=2)
                if salary_elem and salary_elem.text:
                    detail_parts.append(f"薪资: {salary_elem.text.strip()}")
            except:
                pass

            # 提取公司名称
            try:
                company_elem = self.wait_for_element(new_tab, '.company-name, .name, .company-title', timeout=2)
                if company_elem and company_elem.text:
                    detail_parts.append(f"公司: {company_elem.text.strip()}")
            except:
                pass

            # 提取HR姓名
            try:
                hr_selectors = [
                    '.boss-name',
                    '.recruiter-name',
                    '.hr-name',
                    '.name'
                ]
                for selector in hr_selectors:
                    try:
                        hr_elem = new_tab.ele(selector, timeout=1)
                        if hr_elem and hr_elem.text:
                            hr_text = hr_elem.text.strip()
                            if hr_text and len(hr_text) > 1 and len(hr_text) < 10:
                                hr_name = hr_text
                                self.log(f"       >> 提取到HR姓名: {hr_name}")
                                break
                    except:
                        continue
            except:
                pass

            # 提取岗位详情
            try:
                detail_selectors = [
                    '.job-detail-section',
                    '.job-detail',
                    '.job-sec',
                    '.job-description'
                ]
                for selector in detail_selectors:
                    try:
                        detail_elem = self.wait_for_element(new_tab, selector, timeout=1)
                        if detail_elem and detail_elem.text:
                            detail_text = detail_elem.text.strip()
                            if len(detail_text) > 50:
                                detail_parts.append(f"岗位详情:\n{detail_text}")
                                break
                    except:
                        pass
            except:
                pass

            self.log(f"       >> 返回列表页...")
            try:
                new_tab.close()
            except:
                pass

            detail_text = "\n\n".join(detail_parts) if detail_parts else "无详情"
            return detail_text, hr_name

        except Exception as e:
            self.log(f"       >> 获取详情失败: {e}")
            try:
                if 'new_tab' in locals():
                    new_tab.close()
            except:
                pass
            return None, None

    # ═══════════════════════════════════════════════════════
    #  投递（沟通 + 招呼语 + 发送）
    # ═══════════════════════════════════════════════════════

    def deliver_job(self, job_info, greeting=None, page=None):
        """执行投递：打开详情页 → 点击沟通 → 输入招呼语 → 发送

        Args:
            job_info: 岗位信息字典（必须包含 title/company/url）
            greeting: 自定义打招呼语（可选，不传则尝试AI生成或使用默认）
            page: 指定页面实例

        Returns:
            bool: 是否投递成功
        """
        self.log(f"       >> 开始投递: {job_info.get('url')}")
        self.log(f"       >> 当前投递数: {self.delivery_count}/{self.max_delivery}")

        if self.delivery_count >= self.max_delivery:
            self.log(f"       >> 已达到单次最大投递数")
            return False

        current_page = page or self.page
        send_success = False
        job_title = job_info.get('title', '')
        company = job_info.get('company', '')

        try:
            if not job_info.get('url'):
                self.log(f"       >> 没有岗位URL")
                return False

            self.log(f"       >> 访问岗位投递...")
            delivery_tab = current_page.new_tab(job_info['url'])

            try:
                self.wait_for_element(delivery_tab, '.start-chat-btn', timeout=3)
            except:
                pass

            # 查找沟通按钮（多种选择器）
            chat_btn = None
            chat_selectors = [
                '.start-chat-btn',
                '.btn-startchat',
                '[ka="chat-start"]',
                '.op-btn',
                '.chat-btn',
                '.contact-btn',
                '.btn-primary',
                'text:立即沟通',
                'text:打招呼',
                'text:沟通'
            ]

            for sel in chat_selectors:
                try:
                    chat_btn = delivery_tab.ele(sel, timeout=1)
                    if chat_btn:
                        self.log(f"       >> 找到沟通按钮: {sel}")
                        break
                except:
                    continue

            if chat_btn:
                self.log(f"       >> 点击沟通...")
                try:
                    chat_btn.scroll.to_see()
                except:
                    pass
                chat_btn.click()

                # 确定招呼语
                job_detail = job_info.get('job_detail', '')
                if greeting:
                    final_greeting = greeting
                elif self.resume_analyzer and self.resume_analyzer.resume_text:
                    self.log(f"       >> 正在生成个性化打招呼语...")
                    final_greeting = self.resume_analyzer.generate_greeting_message(
                        job_title, company, self.resume_analyzer.resume_text, job_detail)
                    self.log(f"       >> 打招呼语: {final_greeting[:50]}...")
                else:
                    final_greeting = DEFAULT_GREETING

                self.log(f"       >> 等待聊天页面加载...")
                time.sleep(2)

                try:
                    delivery_tab.scroll.to_bottom()
                    time.sleep(0.5)
                except:
                    pass

                self.log(f"       >> 使用JavaScript输入打招呼语...")

                # JavaScript注入打招呼语
                input_success = False
                try:
                    js_input = """
                    let inputBox = document.querySelector('.chat-input') ||
                                  document.querySelector('textarea') ||
                                  document.querySelector('[contenteditable="true"]') ||
                                  document.querySelector('.message-input') ||
                                  document.querySelector('#chat-input');

                    if (inputBox) {
                        if (inputBox.getAttribute('contenteditable') === 'true') {
                            inputBox.innerText = arguments[0];
                        } else {
                            inputBox.value = arguments[0];
                        }

                        inputBox.dispatchEvent(new Event('input', { bubbles: true }));
                        inputBox.dispatchEvent(new Event('change', { bubbles: true }));
                        inputBox.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
                        inputBox.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', bubbles: true }));

                        return '输入成功';
                    } else {
                        return '未找到输入框';
                    }
                    """

                    input_result = delivery_tab.run_js(js_input, final_greeting)
                    self.log(f"       >> JavaScript输入结果: {input_result}")
                    input_success = (input_result == '输入成功')
                except Exception as e:
                    self.log(f"       >> JavaScript输入失败: {e}")

                if input_success:
                    self.log(f"       >> 等待按钮激活并发送...")
                    time.sleep(1)

                    # JavaScript点击发送按钮
                    try:
                        js_send = """
                        const buttons = document.querySelectorAll('button');
                        for (let btn of buttons) {
                            if (btn.innerText && btn.innerText.includes('发送') && !btn.disabled) {
                                btn.click();
                                return '已点击发送按钮';
                            }
                        }

                        let sendBtn = document.querySelector('.send-btn:not([disabled])') ||
                                      document.querySelector('.btn-send:not([disabled])') ||
                                      document.querySelector('[ka="chat-send"]:not([disabled])') ||
                                      document.querySelector('.btn-primary:not([disabled])');

                        if (sendBtn) {
                            sendBtn.click();
                            return '已点击发送按钮';
                        }

                        return '未找到发送按钮';
                        """
                        send_result = delivery_tab.run_js(js_send)
                        self.log(f"       >> JavaScript发送结果: {send_result}")

                        if send_result == '已点击发送按钮':
                            send_success = True
                            self.delivery_count += 1
                            self.log(f"       >> 投递成功，总投递数: {self.delivery_count}")
                            self.log_delivery(job_info, success=True)
                        else:
                            # 备用：使用DrissionPage原生方法查找发送按钮
                            self.log(f"       >> JavaScript未找到按钮，尝试DrissionPage...")
                            send_selectors = [
                                'text:发送',
                                '.send-btn',
                                '.btn-send',
                                '.send-button',
                                '[ka="chat-send"]'
                            ]
                            for sel in send_selectors:
                                try:
                                    elem = delivery_tab.ele(sel, timeout=2)
                                    if elem:
                                        elem.click()
                                        self.log(f"       >> 使用DrissionPage点击发送按钮: {sel}")
                                        send_success = True
                                        self.delivery_count += 1
                                        self.log(f"       >> 投递成功，总投递数: {self.delivery_count}")
                                        self.log_delivery(job_info, success=True)
                                        break
                                except:
                                    continue
                            if not send_success:
                                self.log_delivery(job_info, success=False, reason="未找到发送按钮")
                    except Exception as e:
                        self.log(f"       >> 发送失败: {e}")
                        self.log_delivery(job_info, success=False, reason=f"发送失败: {e}")
                else:
                    self.log_delivery(job_info, success=False, reason="输入失败")

                self.log(f"       >> 等待发送完成...")
                time.sleep(2)

                try:
                    delivery_tab.close()
                except:
                    pass

                return send_success
            else:
                self.log(f"       >> 未找到沟通按钮")
                self.log_delivery(job_info, success=False, reason="未找到沟通按钮")
                try:
                    delivery_tab.close()
                except:
                    pass
                return False
        except Exception as e:
            self.log(f"       >> 投递失败: {e}")
            try:
                if 'delivery_tab' in locals():
                    delivery_tab.close()
            except:
                pass
            self.log_delivery(job_info, success=False, reason=str(e))
            return False


# ==================== UI 标签页 ====================

class AccountTab(QWidget):
    """账号管理页签 — 登录/注册/激活"""

    login_success = pyqtSignal(dict)

    def __init__(self, db: AccountDatabase, parent=None):
        super().__init__(parent)
        self.db = db
        self.card_mgr = CardManager(db)
        self.user_info = None
        self._init_ui()

    def _init_ui(self):
        # 外层滚动区域
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer_layout.addWidget(scroll)

        content = QWidget()
        content.setMinimumWidth(420)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 标题
        title = QLabel("账号管理")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #1e293b;")
        layout.addWidget(title)

        # 用户信息显示区
        self.info_group = QGroupBox("用户状态")
        info_layout = QFormLayout(self.info_group)
        self.user_name_label = QLabel("未登录")
        self.user_name_label.setStyleSheet("color: #ef4444; font-weight: bold;")
        info_layout.addRow("用户名：", self.user_name_label)
        self.license_label = QLabel("-")
        info_layout.addRow("许可证：", self.license_label)
        self.expiry_label = QLabel("-")
        info_layout.addRow("到期时间：", self.expiry_label)
        layout.addWidget(self.info_group)

        # 登录区
        login_group = QGroupBox("登录")
        login_layout = QFormLayout(login_group)
        self.login_username = QLineEdit()
        self.login_username.setPlaceholderText("请输入用户名")
        self.login_username.setMinimumWidth(200)
        login_layout.addRow("用户名：", self.login_username)
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.Password)
        self.login_password.setPlaceholderText("请输入密码")
        self.login_password.setMinimumWidth(200)
        login_layout.addRow("密码：", self.login_password)
        login_btn_row = QHBoxLayout()
        self.login_btn = QPushButton("登录")
        self.login_btn.setStyleSheet("background-color: #4a6cf7; color: white; border: none; border-radius: 4px; padding: 8px 20px;")
        self.login_btn.clicked.connect(self._on_login)
        login_btn_row.addWidget(self.login_btn)
        self.register_btn = QPushButton("注册新账号")
        self.register_btn.setStyleSheet("background-color: #64748b; color: white; border: none; border-radius: 4px; padding: 8px 20px;")
        self.register_btn.clicked.connect(self._on_register)
        login_btn_row.addWidget(self.register_btn)
        login_btn_row.addStretch()
        login_layout.addRow("", login_btn_row)
        layout.addWidget(login_group)

        # 激活区
        activate_group = QGroupBox("卡密激活")
        activate_layout = QFormLayout(activate_group)
        self.card_input = QLineEdit()
        self.card_input.setPlaceholderText("请输入16位卡密（格式：XXXX-XXXX-XXXX-XXXX）")
        self.card_input.setMinimumWidth(200)
        activate_layout.addRow("卡密：", self.card_input)
        self.activate_btn = QPushButton("激活卡密")
        self.activate_btn.setStyleSheet("background-color: #10b981; color: white; border: none; border-radius: 4px; padding: 8px 20px;")
        self.activate_btn.clicked.connect(self._on_activate)
        activate_layout.addRow("", self.activate_btn)
        layout.addWidget(activate_group)

        layout.addStretch()

        # 加载已保存的登录凭证
        creds = load_user_credentials()
        if creds.get("username"):
            self.login_username.setText(creds["username"])
        if creds.get("password"):
            self.login_password.setText(creds["password"])

    def _on_login(self):
        username = self.login_username.text().strip()
        password = self.login_password.text().strip()
        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return

        success, result = self.db.validate_login(username, password)
        if success:
            self.user_info = result
            self.user_name_label.setText(result['username'])
            self.user_name_label.setStyleSheet("color: #10b981; font-weight: bold;")
            self._refresh_license()
            self.login_success.emit(result)
            save_user_credentials(username, password)
            QMessageBox.information(self, "成功", f"登录成功！欢迎 {result['username']}")
        else:
            QMessageBox.warning(self, "登录失败", result)

    def _on_register(self):
        username = self.login_username.text().strip()
        password = self.login_password.text().strip()
        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return
        if len(password) < 6:
            QMessageBox.warning(self, "提示", "密码长度至少6位")
            return

        success, msg = self.db.register_user(username, password)
        if success:
            QMessageBox.information(self, "注册成功", msg)
            self._on_login()
        else:
            QMessageBox.warning(self, "注册失败", msg)

    def _on_activate(self):
        if not self.user_info:
            QMessageBox.warning(self, "提示", "请先登录后再激活卡密")
            return
        card_key = self.card_input.text().strip().upper()
        if not card_key:
            QMessageBox.warning(self, "提示", "请输入卡密")
            return

        machine_fp = get_machine_fingerprint()
        success, msg = self.card_mgr.verify_and_activate(card_key, self.user_info['id'], machine_fp)
        if success:
            QMessageBox.information(self, "激活成功", msg)
            self._refresh_license()
            self.card_input.clear()
        else:
            QMessageBox.warning(self, "激活失败", msg)

    def _refresh_license(self):
        if not self.user_info:
            return
        lic = self.card_mgr.check_license(self.user_info['id'])
        if lic['active']:
            self.license_label.setText(f"{lic.get('card_type', '')} - {lic['reason']}")
            self.license_label.setStyleSheet("color: #10b981;")
            exp_text = get_expiry_text(lic.get('expires_at'))
            self.expiry_label.setText(exp_text)
        else:
            self.license_label.setText(f"未激活 - {lic['reason']}")
            self.license_label.setStyleSheet("color: #ef4444;")
            self.expiry_label.setText(lic['reason'])

    def is_logged_in(self) -> bool:
        return self.user_info is not None

    def is_licensed(self) -> bool:
        if not self.user_info:
            return False
        try:
            lic = self.card_mgr.check_license(self.user_info['id'])
            return lic.get('active', False)
        except Exception:
            return False


class ResumeTab(QWidget):
    """简历管理页签 — 上传/分析"""

    def __init__(self, analyzer: ResumeAnalyzer, parent=None):
        super().__init__(parent)
        self.analyzer = analyzer
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("简历管理")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #1e293b;")
        layout.addWidget(title)

        # 上传区
        upload_group = QGroupBox("简历文件")
        upload_layout = QVBoxLayout(upload_group)
        btn_row = QHBoxLayout()
        self.upload_btn = QPushButton("选择简历文件（PDF）")
        self.upload_btn.setStyleSheet("background-color: #4a6cf7; color: white; border: none; border-radius: 4px; padding: 10px;")
        self.upload_btn.clicked.connect(self._on_upload)
        btn_row.addWidget(self.upload_btn)
        upload_layout.addLayout(btn_row)
        self.resume_path_label = QLabel("未选择文件")
        self.resume_path_label.setStyleSheet("color: #94a3b8;")
        upload_layout.addWidget(self.resume_path_label)
        layout.addWidget(upload_group)

        # 分析结果区
        analysis_group = QGroupBox("AI 分析结果")
        analysis_layout = QVBoxLayout(analysis_group)
        self.analyze_btn = QPushButton("开始AI分析")
        self.analyze_btn.setStyleSheet("background-color: #10b981; color: white; border: none; border-radius: 4px; padding: 10px;")
        self.analyze_btn.clicked.connect(self._on_analyze)
        self.analyze_btn.setEnabled(False)
        analysis_layout.addWidget(self.analyze_btn)
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setPlaceholderText("AI分析结果将显示在这里...")
        self.analysis_text.setMinimumHeight(200)
        analysis_layout.addWidget(self.analysis_text)
        layout.addWidget(analysis_group)

        layout.addStretch()

    def _on_upload(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择简历", "", "PDF文件 (*.pdf)")
        if path:
            self.resume_path_label.setText(path)
            try:
                text = self.analyzer.extract_text_from_pdf(path)
                self.analyzer.resume_text = text
                self.resume_path_label.setText(f"{path}\n已提取 {len(text)} 字")
                self.analyze_btn.setEnabled(True)
            except Exception as e:
                QMessageBox.warning(self, "解析失败", f"PDF解析失败: {e}")

    def _on_analyze(self):
        if not self.analyzer.resume_text:
            QMessageBox.warning(self, "提示", "请先上传简历文件")
            return
        self.analyze_btn.setEnabled(False)
        self.analysis_text.setText("正在分析中，请稍候...")
        QApplication.processEvents()
        try:
            result = self.analyzer.analyze_resume()
            if result:
                lines = []
                skills = result.get('skills', [])
                positions = result.get('recommended_positions', [])
                keywords = result.get('search_keywords', [])
                industries = result.get('recommended_industries', [])
                if skills:
                    lines.append(f"技能优势：{', '.join(skills)}")
                if positions:
                    lines.append(f"推荐岗位：{', '.join(positions)}")
                if keywords:
                    lines.append(f"搜索关键词：{', '.join(keywords)}")
                if industries:
                    lines.append(f"行业方向：{', '.join(industries)}")
                self.analysis_text.setText('\n\n'.join(lines) if lines else str(result))
                # 自动保存简历文本，下次启动自动恢复
                save_resume_text(self.analyzer.resume_text)
            else:
                self.analysis_text.setText("分析失败，请检查网络连接和API密钥")
        except Exception as e:
            self.analysis_text.setText(f"分析出错: {e}")
        finally:
            self.analyze_btn.setEnabled(True)


# ==================== 自动投递 Worker（双模式） ====================

class AutoDeliverWorker(QThread):
    """自动投递工作线程 — 支持API模式和浏览器模式"""
    progress = pyqtSignal(int, int, str)
    job_result = pyqtSignal(str, bool)
    job_found = pyqtSignal(str, dict)
    job_enriched = pyqtSignal(str, dict)
    all_done = pyqtSignal(int, int)
    log_signal = pyqtSignal(str)
    daily_limit_reached = pyqtSignal()

    def __init__(self, api_client: BOSSApiClient, db: JobDatabase,
                 analyzer: ResumeAnalyzer, keyword: str, location: str,
                 min_score: int, target_count: int, use_ai_greeting: bool,
                 delivery_mode: str = "api",
                 platforms: list = None,
                 delay_min: int = MIN_DELAY_SECONDS, delay_max: int = MAX_DELAY_SECONDS,
                 browser_deliverer: BossBrowserDeliverer = None):
        super().__init__()
        self.api_client = api_client
        self.db = db
        self.analyzer = analyzer
        self.keyword = keyword
        self.location = location
        self.min_score = min_score
        self.target_count = target_count
        self.use_ai_greeting = use_ai_greeting and delivery_mode == "browser"
        self.delivery_mode = delivery_mode
        self.platforms = platforms or ['boss']
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.browser_deliverer = browser_deliverer
        self._stop_flag = False
        self._platform_counts = {'boss': 0}

    def stop(self):
        self._stop_flag = True
        if self.browser_deliverer:
            self.browser_deliverer.stop()

    def run(self):
        if self.delivery_mode == "browser":
            self._run_browser_delivery()
        else:
            self._run_api_delivery()

    def _run_api_delivery(self):
        """API模式投递（现有逻辑）"""
        self.log_signal.emit(_log_fmt("投递",
            f"[API模式] 开始自动投递 → 目标{self.target_count}个 间隔{self.delay_min}~{self.delay_max}秒"
        ))

        DETAIL_DELAY = 3
        delivered_count = 0
        failed_count = 0
        enriched_count = 0
        skipped_count = 0
        nodetail_count = 0
        api_lock = threading.Lock()
        batch_lock = threading.Lock()
        batch_counter = [0]
        count_lock = threading.Lock()
        has_resume = self.analyzer and self.analyzer.resume_text

        def deliver_one(url: str, job: dict) -> tuple:
            nonlocal delivered_count, failed_count
            if self._stop_flag:
                return url, False
            delay = random.uniform(self.delay_min, self.delay_max)
            self.log_signal.emit(_log_fmt("投递", f"等待{delay:.0f}秒 → {job.get('title')}@{job.get('company')}"))
            for _ in range(int(delay * 10)):
                if self._stop_flag:
                    return url, False
                time.sleep(0.1)

            greeting = DEFAULT_GREETING
            if self.use_ai_greeting and has_resume and job.get('job_detail'):
                try:
                    greeting = self.analyzer.generate_greeting_message(
                        job_title=job.get('title', ''),
                        company_name=job.get('company', ''),
                        resume_text=self.analyzer.resume_text,
                        job_detail=job.get('job_detail', '')
                    )
                except Exception:
                    pass

            with api_lock:
                if self._stop_flag or self.api_client.daily_limit_reached:
                    return url, False
                success = self.api_client.deliver_job(url, greeting, job_data=job)

            with count_lock:
                if success:
                    delivered_count += 1
                    job['status'] = 1
                    if 'boss' in self._platform_counts:
                        self._platform_counts['boss'] += 1
                else:
                    failed_count += 1
                    job['status'] = 2

            self.db.add_job(
                job_url=url,
                title=job.get("title", ""),
                company=job.get("company", ""),
                status=job.get("status", 0),
                match_score=job.get("match_score", 0),
                active_time=job.get("active_time", 0),
                active_time_desc=job.get("active_time_desc", ""))
            self.job_result.emit(url, success)
            self.progress.emit(delivered_count, self.target_count,
                             f"已投递 {delivered_count}/{self.target_count}")

            with batch_lock:
                batch_counter[0] += 1
                if batch_counter[0] % BATCH_SIZE == 0:
                    pause_seconds = BATCH_PAUSE_MINUTES * 60 + random.randint(-30, 30)
                    self.log_signal.emit(_log_fmt("投递",
                        f"已投递{batch_counter[0]}个，休息{pause_seconds // 60}分钟"))
                    for _ in range(int(pause_seconds)):
                        if self._stop_flag:
                            break
                        time.sleep(1)
            return url, success

        executor = ThreadPoolExecutor(max_workers=1)
        futures = []

        try:
            self.log_signal.emit(_log_fmt("投递", "正在刷新Cookie准备投递环境..."))
            self.api_client.refresh_cookies_from_browser()
            self.api_client._cookie_refresh_count = 0

            page = 1
            while delivered_count < self.target_count and not self._stop_flag:
                self.progress.emit(delivered_count, self.target_count, f"正在搜索第{page}页岗位...")
                raw_jobs = self.api_client.fetch_jobs(
                    keyword=self.keyword, location=self.location, page=page)
                if not raw_jobs:
                    if page == 1:
                        self.log_signal.emit(_log_fmt("投递", "第1页无结果，请检查关键词或登录状态"))
                        break
                    self.log_signal.emit(_log_fmt("投递", f"第{page}页无结果，搜索完成"))
                    break

                new_jobs = self.db.filter_new_jobs(raw_jobs)
                if not new_jobs:
                    self.log_signal.emit(_log_fmt("投递", f"第{page}页均为已投递岗位，翻页"))
                    page += 1
                    time.sleep(1)
                    continue

                self.log_signal.emit(_log_fmt("投递",
                    f"第{page}页: {len(new_jobs)}个新岗位 → 开始逐条分析投递"))

                for idx, (url, job) in enumerate(new_jobs.items()):
                    if self._stop_flag or delivered_count >= self.target_count:
                        break

                    self.progress.emit(delivered_count, self.target_count,
                        f"分析岗位 (第{page}页 {idx+1}/{len(new_jobs)}): {job.get('title', '')}")

                    job.setdefault("platform", "boss")
                    job.setdefault("active_time", 0)
                    job.setdefault("active_time_desc", "")
                    job.setdefault("delivery_mode", "api")
                    self.job_found.emit(url, job)

                    security_id = job.get("_security_id", "")
                    lid = job.get("_lid", "")
                    detail_ok = False

                    if security_id:
                        detail = self.api_client._get_job_detail_real(security_id, lid)
                        if detail:
                            job["job_detail"] = detail.get("description", "")
                            job["active_time"] = detail.get("active_time", 0)
                            job["active_time_desc"] = detail.get("active_time_desc", "")
                            detail_ok = True

                    if has_resume and job.get("job_detail"):
                        try:
                            result = self.analyzer.calculate_match_score(
                                resume_text=self.analyzer.resume_text,
                                job_title=job.get("title", ""),
                                job_detail=job.get("job_detail", ""),
                                company_name=job.get("company", ""))
                            job["match_score"] = result.get("score", 50)
                            job["_match_detail"] = result
                        except Exception as e:
                            self.log_signal.emit(_log_fmt("投递", f"AI匹配度计算失败: {e}"))
                            job["match_score"] = 50

                    enriched_count += 1
                    self.db.add_job(
                        job_url=url,
                        title=job.get("title", ""),
                        company=job.get("company", ""),
                        status=job.get("status", 0),
                        match_score=job.get("match_score", 0),
                        active_time=job.get("active_time", 0),
                        active_time_desc=job.get("active_time_desc", ""))
                    self.job_enriched.emit(url, job)

                    if has_resume and not detail_ok:
                        nodetail_count += 1
                        job['status'] = 3
                        self.log_signal.emit(_log_fmt("投递",
                            f"⊙ {job.get('title')}@{job.get('company')} 无详情数据 → 跳过"))
                    elif has_resume and job.get('match_score', 0) < self.min_score:
                        skipped_count += 1
                        job['status'] = 4
                        self.log_signal.emit(_log_fmt("投递",
                            f"跳过({job.get('match_score')}分) {job.get('title')}@{job.get('company')}"))
                    else:
                        futures.append(executor.submit(deliver_one, url, job))
                        self.log_signal.emit(_log_fmt("投递",
                            f"✓ {job.get('title')}@{job.get('company')} [{job.get('match_score')}分] → 入队"))

                    if not self._stop_flag and delivered_count < self.target_count:
                        time.sleep(DETAIL_DELAY)

                page += 1
                if not self._stop_flag and delivered_count < self.target_count:
                    time.sleep(1)

            remaining = len(futures)
            if remaining > 0:
                self.log_signal.emit(_log_fmt("投递",
                    f"搜索完成(分析{enriched_count}个 跳过{skipped_count}个)，等待{remaining}个投递任务..."))
                for future in as_completed(futures):
                    if self._stop_flag or delivered_count >= self.target_count:
                        break
                    if self.api_client.daily_limit_reached:
                        self.log_signal.emit(_log_fmt("投递",
                            "达到每日120次沟通上限，请先在BOSS直聘APP中手动点击'开聊'，再继续投递"))
                        self.daily_limit_reached.emit()
                        self._stop_flag = True
                        break

        finally:
            executor.shutdown(wait=False)

        self.log_signal.emit(_log_fmt("投递",
            f"[API模式] 结束 → 投递{delivered_count} 失败{failed_count} 跳过{skipped_count}"))
        self.all_done.emit(delivered_count, failed_count)

    def _run_browser_delivery(self):
        """浏览器模式投递 — 使用 DrissionPage"""
        if not self.browser_deliverer or not HAS_DRISSION:
            self.log_signal.emit(_log_fmt("投递", "[浏览器模式] DrissionPage未安装或浏览器未初始化"))
            self.all_done.emit(0, 0)
            return

        self.log_signal.emit(_log_fmt("投递",
            f"[浏览器模式] 开始自动投递 → 目标{self.target_count}个"))

        city_code = resolve_city_code(self.location)
        city_name = city_code_to_name(city_code)
        delivered_count = 0
        failed_count = 0
        has_resume = self.analyzer and self.analyzer.resume_text

        try:
            search_url = self.browser_deliverer.build_search_url(city_code, self.keyword)
            self.log_signal.emit(_log_fmt("投递", f"[浏览器模式] 搜索: {search_url}"))
            self.browser_deliverer.navigate(search_url)

            scroll_count = 0
            while delivered_count < self.target_count and not self._stop_flag and scroll_count < 5:
                self.log_signal.emit(_log_fmt("投递", f"第{scroll_count + 1}轮获取岗位卡片..."))
                cards = self.browser_deliverer.get_job_cards()
                self.log_signal.emit(_log_fmt("投递", f"发现{len(cards)}个岗位卡片"))

                for i, card in enumerate(cards):
                    if self._stop_flag or delivered_count >= self.target_count:
                        break

                    job_info = self.browser_deliverer.extract_job_info_from_card(card)
                    if not job_info or not job_info.get('url'):
                        continue

                    job_url = job_info['url']
                    title = job_info.get('title', '')
                    company = job_info.get('company', '')

                    # 去重
                    if self.db.is_delivered(job_url) or self.db.is_skipped(job_url):
                        continue

                    job_info.setdefault("delivery_mode", "browser")
                    self.job_found.emit(job_url, job_info)

                    self.progress.emit(delivered_count, self.target_count,
                                     f"分析: {title}@{company}")

                    # 获取详情
                    job_detail, hr_name = self.browser_deliverer.get_job_detail_and_hr(job_info)
                    if not job_detail:
                        continue

                    job_info['job_detail'] = job_detail
                    job_info['hr_name'] = hr_name

                    # AI匹配度（与API模式保持一致）
                    if has_resume and job_detail:
                        try:
                            result = self.analyzer.calculate_match_score(
                                resume_text=self.analyzer.resume_text,
                                job_title=title, job_detail=job_detail,
                                company_name=company)
                            job_info["match_score"] = result.get("score", 50)
                            job_info["_match_detail"] = result
                        except Exception as e:
                            self.log_signal.emit(_log_fmt("投递", f"AI匹配度计算失败: {e}"))
                            job_info["match_score"] = 50
                    else:
                        job_info["match_score"] = 50

                    match_score = job_info["match_score"]

                    # 保存到数据库
                    job_url_safe = job_url[:500]
                    self.db.add_job(job_url_safe, title=title, company=company,
                                    status=0, match_score=match_score,
                                    platform="boss", delivery_mode="browser")
                    self.job_enriched.emit(job_url_safe, job_info)

                    # 筛选
                    if has_resume and match_score < self.min_score:
                        self.db.update_status(job_url_safe, 4, match_score)
                        self.log_signal.emit(_log_fmt("投递",
                            f"跳过({match_score}分) {title}@{company}"))
                        continue

                    # 生成招呼语
                    greeting = DEFAULT_GREETING
                    if self.use_ai_greeting and has_resume:
                        try:
                            greeting = self.analyzer.generate_greeting_message(
                                job_title=title, company_name=company,
                                resume_text=self.analyzer.resume_text,
                                job_detail=job_detail)
                        except Exception:
                            pass

                    # 投递
                    self.log_signal.emit(_log_fmt("投递",
                        f"✓ {title}@{company} [{match_score}分] → 浏览器投递"))
                    success = self.browser_deliverer.deliver_job(job_info, greeting=greeting)

                    if success:
                        delivered_count += 1
                        self.db.update_status(job_url_safe, 1, match_score)
                    else:
                        failed_count += 1
                        self.db.update_status(job_url_safe, 2, match_score)

                    self.job_result.emit(job_url_safe, success)
                    self.progress.emit(delivered_count, self.target_count,
                                     f"已投递 {delivered_count}/{self.target_count}")

                    # 投递间隔
                    delay = random.uniform(self.delay_min, self.delay_max)
                    for _ in range(int(delay)):
                        if self._stop_flag:
                            break
                        time.sleep(1)

                if not self.browser_deliverer.load_more_content():
                    self.log_signal.emit(_log_fmt("投递", "没有更多内容可加载"))
                    break
                scroll_count += 1

        except Exception as e:
            self.log_signal.emit(_log_fmt("投递", f"[浏览器模式] 出错: {e}"))
            import traceback
            traceback.print_exc()

        self.log_signal.emit(_log_fmt("投递",
            f"[浏览器模式] 结束 → 投递{delivered_count} 失败{failed_count}"))
        self.all_done.emit(delivered_count, failed_count)


# ==================== 岗位列表页签 ====================

class JobListTab(QWidget):
    """岗位列表独立页签 — 展示本次搜索到的岗位及投递状态"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._job_row_map: Dict[str, int] = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # 岗位列表（11列）
        self.job_table = QTableWidget()
        self.job_table.setColumnCount(11)
        self.job_table.setHorizontalHeaderLabels([
            "岗位名称", "公司", "地区", "薪资", "活跃时间", "活跃描述",
            "匹配度", "原因", "岗位详情", "投递模式", "状态"
        ])
        self.job_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.job_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.job_table.setAlternatingRowColors(True)
        header = self.job_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        header.setSectionResizeMode(8, QHeaderView.Stretch)
        header.setSectionResizeMode(9, QHeaderView.Fixed)
        header.setSectionResizeMode(10, QHeaderView.Fixed)
        header.setStretchLastSection(False)
        self.job_table.setColumnWidth(1, 80)
        self.job_table.setColumnWidth(2, 50)
        self.job_table.setColumnWidth(3, 65)
        self.job_table.setColumnWidth(4, 65)
        self.job_table.setColumnWidth(5, 55)
        self.job_table.setColumnWidth(6, 48)
        self.job_table.setColumnWidth(7, 70)
        self.job_table.setColumnWidth(9, 50)
        self.job_table.setColumnWidth(10, 50)
        self.job_table.setMinimumHeight(180)
        self.job_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.job_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.job_table)

    def clear(self):
        """清空岗位列表"""
        self.job_table.setRowCount(0)
        self._job_row_map.clear()

    def add_job(self, url: str, job: dict):
        """添加新岗位到列表"""
        row = self.job_table.rowCount()
        self.job_table.insertRow(row)
        self._fill_row(row, url, job)

    def update_job(self, url: str, job: dict):
        """更新已有岗位信息（如匹配度、详情等）"""
        if url in self._job_row_map:
            row = self._job_row_map[url]
        else:
            row = self.job_table.rowCount()
            self.job_table.insertRow(row)
        self._fill_row(row, url, job)

    def update_result(self, url: str, success: bool):
        """更新投递结果状态"""
        if url in self._job_row_map:
            row = self._job_row_map[url]
            status_text = "已投递" if success else "投递失败"
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor("#27ae60" if success else "#e74c3c"))
            self.job_table.setItem(row, 10, status_item)

    def _fill_row(self, row: int, url: str, job: dict):
        self._job_row_map[url] = row

        title = job.get('title', '')
        title_item = QTableWidgetItem(title)
        title_item.setToolTip(title)
        self.job_table.setItem(row, 0, title_item)

        company = job.get('company', '未知')
        company_item = QTableWidgetItem(company)
        company_item.setToolTip(f"{company}\n{job.get('company_scale', '')} | {job.get('company_stage', '')} | {job.get('company_industry', '')}")
        self.job_table.setItem(row, 1, company_item)

        location = job.get('location', job.get('city', ''))
        district = job.get('district', '')
        loc_text = f"{location} {district}".strip() if district else location
        loc_item = QTableWidgetItem(loc_text)
        loc_item.setToolTip(loc_text)
        self.job_table.setItem(row, 2, loc_item)

        salary_item = QTableWidgetItem(job.get('salary', ''))
        salary_item.setToolTip(job.get('salary', ''))
        self.job_table.setItem(row, 3, salary_item)

        active_time = job.get('active_time', 0)
        if active_time > 0:
            active_dt = datetime.fromtimestamp(active_time / 1000.0)
            active_date_str = active_dt.strftime("%Y-%m-%d")
            active_tip = active_dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            active_date_str = ''
            active_tip = ''
        at_item = QTableWidgetItem(active_date_str)
        at_item.setToolTip(active_tip)
        self.job_table.setItem(row, 4, at_item)

        active_desc = job.get('active_time_desc', '')
        ad_item = QTableWidgetItem(active_desc)
        ad_item.setToolTip(active_desc)
        self.job_table.setItem(row, 5, ad_item)

        score_val = job.get('match_score', 0)
        score_item = QTableWidgetItem(str(score_val))
        if score_val >= 80:
            score_item.setForeground(QColor("#27ae60"))
        elif score_val >= 60:
            score_item.setForeground(QColor("#f39c12"))
        else:
            score_item.setForeground(QColor("#e74c3c"))
        self.job_table.setItem(row, 6, score_item)

        match_detail = job.get('_match_detail', {}) or {}
        reasons = match_detail.get('reasons', [])
        reason_text = reasons[0] if reasons else '-'
        reason_item = QTableWidgetItem(reason_text)
        tip_lines = [f"综合匹配度: {score_val}分"]
        if reasons:
            for r in reasons:
                tip_lines.append(f"  + {r}")
        reason_item.setToolTip('\n'.join(tip_lines))
        self.job_table.setItem(row, 7, reason_item)

        detail = job.get('job_detail', '')
        detail_short = detail[:60].replace('\n', ' ') + ('...' if len(detail) > 60 else '')
        detail_item = QTableWidgetItem(detail_short if detail_short else '（待获取）')
        if detail:
            detail_item.setToolTip(detail)
        else:
            detail_item.setForeground(QColor("#bdc3c7"))
        self.job_table.setItem(row, 8, detail_item)

        mode = job.get('delivery_mode', 'api')
        mode_item = QTableWidgetItem("API" if mode == "api" else "浏览器")
        self.job_table.setItem(row, 9, mode_item)

        status_map = {0: "待投递", 1: "已投递", 2: "投递失败", 3: "无需投递", 4: "匹配不足", 5: "时间不符"}
        status_text = status_map.get(job.get('status', 0), "待投递")
        status_item = QTableWidgetItem(status_text)
        colors = {"已投递": "#27ae60", "投递失败": "#e74c3c", "无需投递": "#f39c12",
                  "匹配不足": "#e67e22", "时间不符": "#95a5a6"}
        status_item.setForeground(QColor(colors.get(status_text, "#7f8c8d")))
        self.job_table.setItem(row, 10, status_item)


# ==================== 自动投递页签 ====================

class AutoDeliveryTab(QWidget):
    """自动投递页签 — 支持API/浏览器双模式"""

    def __init__(self, api_client: BOSSApiClient, db: JobDatabase,
                 analyzer: ResumeAnalyzer, job_list_tab: JobListTab = None,
                 account_tab: AccountTab = None, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.db = db
        self.analyzer = analyzer
        self.job_list_tab = job_list_tab
        self.account_tab = account_tab
        self._auto_worker: Optional[AutoDeliverWorker] = None
        self._browser_deliverer: Optional[BossBrowserDeliverer] = None
        self._init_ui()

    def _init_ui(self):
        # 外层滚动区域 —— 窗口缩窄时出现滚动条而非压缩控件
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer_layout.addWidget(scroll)

        content = QWidget()
        content.setMinimumWidth(880)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # ---- 参数设置 ----
        param_group = QGroupBox("自动投递参数设置")
        param_grid = QGridLayout(param_group)
        param_grid.setVerticalSpacing(6)
        param_grid.setHorizontalSpacing(8)
        param_grid.setColumnStretch(0, 0)
        param_grid.setColumnStretch(1, 1)
        param_grid.setColumnMinimumWidth(0, 60)
        FIELD_MIN_W = 200

        row = 0

        # --- 投递模式 ---
        param_grid.addWidget(QLabel("模式："), row, 0)
        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(16)
        self.api_mode_radio = QRadioButton("API接口")
        self.api_mode_radio.setToolTip("快速投递，通过API接口直接投递，不使用打招呼语")
        self.api_mode_radio.setChecked(True)
        self.browser_mode_radio = QRadioButton("浏览器投递")
        self.browser_mode_radio.setToolTip("通过浏览器模拟操作投递，支持AI个性化招呼语，需先在账号管理页登录")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.api_mode_radio, 1)
        self.mode_group.addButton(self.browser_mode_radio, 2)
        self.mode_group.buttonClicked.connect(self._on_mode_changed)
        mode_row.addWidget(self.api_mode_radio)
        mode_row.addWidget(self.browser_mode_radio)
        mode_row.addStretch()
        param_grid.addLayout(mode_row, row, 1)
        row += 1

        # --- 岗位关键字 ---
        param_grid.addWidget(QLabel("关键字："), row, 0)
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("多关键字空格分隔，需同时匹配 如：软件测试 Python")
        self.keyword_input.setMinimumWidth(FIELD_MIN_W)
        self.keyword_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        param_grid.addWidget(self.keyword_input, row, 1)
        row += 1

        # --- 工作地区 ---
        param_grid.addWidget(QLabel("地区："), row, 0)
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("留空=不限地区，如：北京、上海")
        self.location_input.setMinimumWidth(FIELD_MIN_W)
        self.location_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        param_grid.addWidget(self.location_input, row, 1)
        row += 1

        # --- 最低匹配度 ---
        param_grid.addWidget(QLabel("匹配度："), row, 0)
        self.score_spin = QSpinBox()
        self.score_spin.setRange(0, 100)
        self.score_spin.setValue(60)
        self.score_spin.setSuffix(" 分")
        self.score_spin.setMinimumWidth(FIELD_MIN_W)
        param_grid.addWidget(self.score_spin, row, 1)
        row += 1

        # --- 目标投递数量 ---
        param_grid.addWidget(QLabel("目标数量："), row, 0)
        self.target_spin = QSpinBox()
        self.target_spin.setRange(1, 500)
        self.target_spin.setValue(10)
        self.target_spin.setSuffix(" 个")
        self.target_spin.setMinimumWidth(FIELD_MIN_W)
        param_grid.addWidget(self.target_spin, row, 1)
        row += 1

        # --- 投递延迟 ---
        param_grid.addWidget(QLabel("延迟："), row, 0)
        delay_row = QHBoxLayout()
        delay_row.setContentsMargins(0, 0, 0, 0)
        delay_row.setSpacing(8)
        self.delay_min_spin = QSpinBox()
        self.delay_min_spin.setRange(3, 120)
        self.delay_min_spin.setValue(MIN_DELAY_SECONDS)
        self.delay_min_spin.setSuffix(" 秒")
        self.delay_min_spin.setMinimumWidth(90)
        delay_row.addWidget(self.delay_min_spin)
        delay_row.addWidget(QLabel("~"))
        self.delay_max_spin = QSpinBox()
        self.delay_max_spin.setRange(5, 180)
        self.delay_max_spin.setValue(MAX_DELAY_SECONDS)
        self.delay_max_spin.setSuffix(" 秒")
        self.delay_max_spin.setMinimumWidth(90)
        delay_row.addWidget(self.delay_max_spin)
        delay_row.addStretch()
        param_grid.addLayout(delay_row, row, 1)
        row += 1

        # --- 招呼语 ---
        param_grid.addWidget(QLabel("招呼语："), row, 0)
        self.greeting_check = QCheckBox("使用 AI 个性化招呼语")
        self.greeting_check.setChecked(False)
        self.greeting_check.setEnabled(False)  # API模式默认禁用，切换浏览器模式时启用
        param_grid.addWidget(self.greeting_check, row, 1)

        layout.addWidget(param_group)

        # 按钮
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始自动投递")
        self.start_btn.setFont(QFont("Microsoft YaHei", 11))
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.start_btn.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; border: none; border-radius: 6px; padding: 10px 30px; font-weight: bold; }
            QPushButton:hover { background-color: #059669; }
            QPushButton:pressed { background-color: #047857; }
            QPushButton:disabled { background-color: #cbd5e1; color: #94a3b8; }
        """)
        self.start_btn.clicked.connect(self._on_start)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止投递")
        self.stop_btn.setFont(QFont("Microsoft YaHei", 11))
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.stop_btn.setStyleSheet("""
            QPushButton { background-color: #ef4444; color: white; border: none; border-radius: 6px; padding: 10px 30px; font-weight: bold; }
            QPushButton:hover { background-color: #dc2626; }
            QPushButton:pressed { background-color: #b91c1c; }
            QPushButton:disabled { background-color: #cbd5e1; color: #94a3b8; }
        """)
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        # 进度
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪，点击「开始自动投递」启动")
        self.status_label.setFont(QFont("Microsoft YaHei", 10))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #94a3b8;")
        layout.addWidget(self.status_label)

        # 统计信息
        stats_group = QGroupBox("投递统计")
        stats_layout = QFormLayout(stats_group)
        session_row = QHBoxLayout()
        self.boss_session_label = QLabel("BOSS本次：0")
        self.session_total_label = QLabel("本次合计：0")
        session_row.addWidget(self.boss_session_label)
        session_row.addWidget(self.session_total_label)
        session_row.addStretch()
        stats_layout.addRow("本次：", session_row)
        daily_row = QHBoxLayout()
        self.api_daily_label = QLabel("API模式今日：0")
        self.browser_daily_label = QLabel("浏览器模式今日：0")
        self.daily_total_label = QLabel("今日合计：0")
        daily_row.addWidget(self.api_daily_label)
        daily_row.addWidget(self.browser_daily_label)
        daily_row.addWidget(self.daily_total_label)
        daily_row.addStretch()
        stats_layout.addRow("今日：", daily_row)
        layout.addWidget(stats_group)

        # 加载上次投递配置
        self._load_config()
        # 加载今日投递统计
        self._load_daily_stats()

    def _load_config(self):
        """从 config.json 恢复上次投递配置"""
        cfg = load_delivery_config()
        if not cfg:
            return
        if cfg.get("keyword"):
            self.keyword_input.setText(cfg["keyword"])
        if cfg.get("location"):
            self.location_input.setText(cfg["location"])
        if cfg.get("min_score", 0) > 0:
            self.score_spin.setValue(cfg["min_score"])
        if cfg.get("target", 0) > 0:
            self.target_spin.setValue(cfg["target"])
        if cfg.get("delay_min", 0) > 0:
            self.delay_min_spin.setValue(cfg["delay_min"])
        if cfg.get("delay_max", 0) > 0:
            self.delay_max_spin.setValue(cfg["delay_max"])
        if cfg.get("delivery_mode") == "browser":
            self.browser_mode_radio.setChecked(True)
            self.greeting_check.setEnabled(True)
        if cfg.get("use_greeting") and cfg.get("delivery_mode") == "browser":
            self.greeting_check.setChecked(True)

    def _save_config(self, keyword: str, location: str, min_score: int,
                     target: int, delay_min: int, delay_max: int,
                     delivery_mode: str, use_greeting: bool):
        """保存当前投递配置到 config.json"""
        save_delivery_config(
            keyword=keyword, location=location, min_score=min_score,
            target=target, delay_min=delay_min, delay_max=delay_max,
            delivery_mode=delivery_mode, use_greeting=use_greeting)

    def _on_mode_changed(self, btn):
        is_browser = (btn == self.browser_mode_radio)
        self.greeting_check.setEnabled(is_browser)
        if not is_browser:
            self.greeting_check.setChecked(False)

    def _on_start(self):
        is_browser = self.browser_mode_radio.isChecked()
        delivery_mode = "browser" if is_browser else "api"

        # 统一卡密验证（API模式和浏览器模式都需要）
        if self.account_tab:
            if not self.account_tab.is_logged_in():
                QMessageBox.warning(self, "提示",
                    "请先在「账号管理」页签登录并激活卡密后再开始投递")
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                return
            if not self.account_tab.is_licensed():
                QMessageBox.warning(self, "提示",
                    "卡密未激活或已过期，请在「账号管理」页签激活卡密后再开始投递")
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                return

        # 浏览器模式额外检查
        if is_browser:
            if not HAS_DRISSION:
                QMessageBox.warning(self, "提示", "浏览器模式需要 DrissionPage 库\n请执行: pip install DrissionPage")
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                return

        keyword = self.keyword_input.text().strip()
        location = self.location_input.text().strip()
        min_score = self.score_spin.value()
        target = self.target_spin.value()
        dmin = self.delay_min_spin.value()
        dmax = self.delay_max_spin.value()
        use_greeting = self.greeting_check.isChecked() and is_browser

        # 简历文本检查
        if not self.analyzer or not self.analyzer.resume_text:
            _log_emitter.log_signal.emit(_log_fmt("警告",
                "未检测到简历文本！将使用默认匹配度50分，所有岗位均低于筛选线可能被跳过。"
                "请先在「简历管理」页签上传简历并点击「开始AI分析」"))

        # 保存投递配置
        self._save_config(keyword=keyword, location=location, min_score=min_score,
                          target=target, delay_min=dmin, delay_max=dmax,
                          delivery_mode=delivery_mode, use_greeting=use_greeting)

        mode_desc = "浏览器模式" if is_browser else "API模式"
        _log_emitter.log_signal.emit(_log_fmt(
            "投递", f"点击「开始自动投递」→ {mode_desc} 关键词={keyword} 地区={location} "
            f"最低{min_score}分 目标{target}个 延迟{dmin}~{dmax}秒"
        ))

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(target)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"正在自动投递（{mode_desc}）...")
        self.status_label.setStyleSheet("color: #f59e0b;")
        if self.job_list_tab:
            self.job_list_tab.clear()

        # 浏览器模式：初始化DrissionPage
        browser_deliverer = None
        if is_browser:
            try:
                co = ChromiumOptions()
                co.set_argument('--no-sandbox')
                co.set_argument('--disable-blink-features=AutomationControlled')
                co.set_argument('--disable-dev-shm-usage')
                co.set_argument('--disable-gpu')
                co.set_argument('--remote-allow-origins=*')
                co.set_argument('--window-position=100,100')  # 窗口在可见位置，方便用户观察/操作
                co.set_argument('--window-size=1280,800')
                page = ChromiumPage(co)
                browser_deliverer = BossBrowserDeliverer(page, self.analyzer,
                    log_callback=lambda msg: _log_emitter.log_signal.emit(msg))
                self._browser_deliverer = browser_deliverer
            except Exception as e:
                _log_emitter.log_signal.emit(_log_fmt("投递", f"浏览器初始化失败: {e}"))
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                return

        self._auto_worker = AutoDeliverWorker(
            self.api_client, self.db, self.analyzer,
            keyword, location, min_score, target,
            use_greeting, delivery_mode=delivery_mode,
            delay_min=dmin, delay_max=dmax,
            browser_deliverer=browser_deliverer
        )
        self._auto_worker.progress.connect(self._on_progress)
        self._auto_worker.job_found.connect(self._on_auto_job_found)
        self._auto_worker.job_enriched.connect(self._on_auto_job_enriched)
        self._auto_worker.job_result.connect(self._on_auto_job_result)
        self._auto_worker.log_signal.connect(
            lambda msg: _log_emitter.log_signal.emit(msg))
        self._auto_worker.all_done.connect(self._on_done)
        self._auto_worker.daily_limit_reached.connect(self._on_daily_limit)
        self._auto_worker.start()

    def _on_auto_job_found(self, url, job):
        if self.job_list_tab:
            self.job_list_tab.add_job(url, job)

    def _on_auto_job_enriched(self, url, job):
        if self.job_list_tab:
            self.job_list_tab.update_job(url, job)

    def _on_auto_job_result(self, url, success):
        if self.job_list_tab:
            self.job_list_tab.update_result(url, success)

    def _on_progress(self, current, total, status):
        self.progress_bar.setValue(current)
        self.status_label.setText(status)
        self._update_session_stats()

    def _on_done(self, success_count, fail_count):
        _log_emitter.log_signal.emit(_log_fmt("投递", f"投递完成 — 成功{success_count} 失败{fail_count}"))
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"投递完成！成功: {success_count}, 失败: {fail_count}")
        self.status_label.setStyleSheet("color: #10b981;")
        self._update_session_stats()
        self._auto_worker = None
        # 清理浏览器实例
        if self._browser_deliverer:
            try:
                self._browser_deliverer.stop()
            except Exception:
                pass
            self._browser_deliverer = None

    def _on_stop(self):
        if self._auto_worker and self._auto_worker.isRunning():
            _log_emitter.log_signal.emit(_log_fmt("投递", "点击「停止投递」→ 发送停止信号"))
            self._auto_worker.stop()
            self.stop_btn.setEnabled(False)
            self.status_label.setText("正在停止...")
            self.status_label.setStyleSheet("color: #ef4444;")

    def _on_daily_limit(self):
        """每日沟通上限触发：停止投递，弹窗提示"""
        if self._auto_worker:
            self._auto_worker.stop()
        _log_emitter.log_signal.emit(_log_fmt("投递", "触发每日沟通上限，停止投递"))
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("每日上限已达，请手动处理")
        self.status_label.setStyleSheet("color: #ef4444;")
        self._update_session_stats()
        self._auto_worker = None
        QMessageBox.warning(
            self, "每日沟通上限",
            "已达到BOSS直聘每日120次沟通上限！\n\n"
            "请在BOSS直聘网页/APP中手动点击「开聊」按钮，\n"
            "完成验证后可继续使用本工具投递。")

    def _update_session_stats(self):
        if not self._auto_worker:
            return
        boss_count = self._auto_worker._platform_counts.get('boss', 0)
        self.boss_session_label.setText(f"BOSS本次：{boss_count}")
        self.session_total_label.setText(f"本次合计：{boss_count}")
        self._load_daily_stats()

    def _load_daily_stats(self):
        try:
            stats = self.db.get_daily_stats()
            self.api_daily_label.setText(f"API模式今日：{stats.get('api', 0)}")
            self.browser_daily_label.setText(f"浏览器模式今日：{stats.get('browser', 0)}")
            self.daily_total_label.setText(f"今日合计：{stats.get('total', 0)}")
        except Exception:
            pass


# ==================== 主窗口 ====================

class MainWindow(QMainWindow):
    """主窗口 — 多标签页容器"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BOSS直聘智能投递助手 v2.0")
        self.setGeometry(100, 100, 1100, 750)
        self.setMinimumSize(1050, 700)

        # 初始化数据库
        self.account_db = AccountDatabase()
        try:
            self.account_db.init_tables()
        except Exception as e:
            print(f"数据库初始化失败: {e}")

        self.job_db = JobDatabase()

        # 初始化AI分析器（连接日志回调，确保AI日志写入文件）
        self.analyzer = ResumeAnalyzer()
        self.analyzer.log_callback = lambda msg: _log_emitter.log_signal.emit(msg)

        # 自动恢复简历文本（上次AI分析时保存的）
        try:
            cfg = load_delivery_config()
            if cfg.get("resume_text"):
                self.analyzer.resume_text = cfg["resume_text"]
                self.analyzer.resume_content = cfg["resume_text"]
                print(f"[系统] 已从配置恢复简历文本 ({len(cfg['resume_text'])}字符)")
        except Exception:
            pass

        # 初始化API客户端（连接日志回调，确保API日志写入文件）
        self.api_client = BOSSApiClient(
            log_callback=lambda msg: _log_emitter.log_signal.emit(msg))

        # 自动提取Cookie
        self._auto_login()

        # 构建UI
        self._init_ui()

    def _auto_login(self):
        """尝试自动从浏览器提取Cookie登录"""
        try:
            auth = BrowserAuthHelper(
                log_callback=lambda msg: _log_emitter.log_signal.emit(msg))
            cookies = auth.extract_cookies()
            if cookies:
                cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
                self.api_client.login(cookie_str)
                _log_emitter.log_signal.emit(_log_fmt("系统", "已自动提取BOSS直聘Cookie"))
            else:
                _log_emitter.log_signal.emit(_log_fmt("系统", "未找到BOSS直聘Cookie，请在API模式下手动设置"))
        except Exception as e:
            _log_emitter.log_signal.emit(_log_fmt("系统", f"自动登录失败: {e}"))

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)
        central.setStyleSheet("background-color: #f5f6fa;")

        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("Microsoft YaHei", 10))

        # Tab 0: 账号管理
        self.account_tab = AccountTab(self.account_db)
        self.tab_widget.addTab(self.account_tab, "账号管理")

        # Tab 1: 简历管理
        self.resume_tab = ResumeTab(self.analyzer)
        self.tab_widget.addTab(self.resume_tab, "简历管理")

        # 岗位列表（先创建实例供自动投递引用）
        self.job_list_tab = JobListTab()

        # Tab 2: 自动投递（核心）
        self.auto_tab = AutoDeliveryTab(self.api_client, self.job_db, self.analyzer,
                                        job_list_tab=self.job_list_tab,
                                        account_tab=self.account_tab)
        self.tab_widget.addTab(self.auto_tab, "自动投递")

        # Tab 3: 岗位列表
        self.tab_widget.addTab(self.job_list_tab, "岗位列表")

        main_layout.addWidget(self.tab_widget)

        # 日志区
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_group)

        # 连接日志信号
        _log_emitter.log_signal.connect(self._on_log)

    def _on_log(self, msg: str):
        self.log_text.append(msg)
        # 限制日志行数
        if self.log_text.document().blockCount() > 500:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, 100)
            cursor.removeSelectedText()


def main():
    """应用入口"""
    import os
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
    setup_file_logging()  # 运行日志写入脚本目录
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 全局字体
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)

    # ── 全局 QSS 样式表 ──
    app.setStyleSheet("""
    /* QGroupBox — 白底卡片 */
    QGroupBox {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        margin-top: 10px;
        padding: 10px 6px 6px 6px;
        font-weight: bold;
        color: #1e293b;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 14px;
        padding: 0 6px;
    }

    /* QPushButton */
    QPushButton {
        background-color: #4a6cf7;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 7px 16px;
        font-weight: bold;
    }
    QPushButton:hover { background-color: #3b5de7; }
    QPushButton:pressed { background-color: #2d4ecc; }
    QPushButton:disabled { background-color: #cbd5e1; color: #94a3b8; }

    /* QTableWidget */
    QTableWidget {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        gridline-color: #f1f5f9;
        alternate-background-color: #f8fafc;
    }
    QTableWidget::item { padding: 3px 6px; }
    QTableWidget::item:selected { background: #eef2ff; color: #1e293b; }
    QHeaderView::section {
        background: #f1f5f9;
        border: none;
        border-bottom: 2px solid #e2e8f0;
        padding: 4px 6px;
        font-weight: bold;
        color: #475569;
    }

    /* QLineEdit / QSpinBox / QDateEdit */
    QLineEdit, QSpinBox, QDateEdit {
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        padding: 3px 6px;
        background: #ffffff;
        color: #1e293b;
    }
    QLineEdit:focus, QSpinBox:focus, QDateEdit:focus {
        border-color: #4a6cf7;
    }

    /* QTabWidget */
    QTabWidget::pane {
        border: 1px solid #e2e8f0;
        border-radius: 0 0 8px 8px;
        background: #f5f6fa;
    }
    QTabBar::tab {
        background: #e2e8f0;
        color: #64748b;
        padding: 6px 16px;
        margin-right: 2px;
        border-radius: 6px 6px 0 0;
        font-weight: bold;
    }
    QTabBar::tab:selected {
        background: #f5f6fa;
        color: #4a6cf7;
        border-bottom: 2px solid #4a6cf7;
    }
    QTabBar::tab:hover { color: #4a6cf7; }

    /* QProgressBar */
    QProgressBar {
        border: none;
        border-radius: 4px;
        background: #e2e8f0;
        height: 8px;
        text-align: center;
    }
    QProgressBar::chunk {
        background: #4a6cf7;
        border-radius: 4px;
    }

    /* QCheckBox / QRadioButton */
    QCheckBox, QRadioButton { color: #1e293b; spacing: 6px; }
    """)

    window = MainWindow()
    window.resize(1000, 680)
    window.setMinimumSize(1000, 680)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

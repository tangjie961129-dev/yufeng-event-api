"""
屿风会员分层评分 v3 — 简化版
维度：收入(35%) + 城市(30%) + 年龄(15%) + 独居(20%)
"""
import re


def parse_income(raw) -> int:
    """收入 → 0-100 分"""
    if not raw:
        return 20
    raw = str(raw).strip()

    TABLE = {
        "5万以上": 100,
        "3w-5w": 85,
        "1w-3w": 70,
        "8000-10000": 55,
        "5000-8000": 35,
        "3000-5000": 20,
        "3000以下": 5,
        "未工作/在读": 0,
        "30000以上": 100,
        "20000以上": 80,
        "15000-20000": 75,
        "10000-15000": 65,
    }
    if raw in TABLE:
        return TABLE[raw]

    nums = re.findall(r'\d+', raw)
    if nums:
        val = int(nums[0])
        if val >= 50000: return 100
        if val >= 30000: return 85
        if val >= 10000: return 65
        if val >= 5000: return 35
        if val >= 3000: return 20
        return 5
    return 20


# 二线及以上城市列表（一线100, 新一线+二线90）
TIER1 = {"北京", "上海", "广州", "深圳"}
TIER2 = {
    "成都", "杭州", "重庆", "武汉", "西安", "苏州", "南京", "天津",
    "长沙", "东莞", "宁波", "佛山", "合肥", "青岛",
    "沈阳", "昆明", "大连", "厦门", "无锡", "福州", "济南",
    "哈尔滨", "温州", "长春", "石家庄", "常州", "泉州", "南宁",
    "贵阳", "南昌", "太原", "烟台", "嘉兴", "南通", "金华",
    "珠海", "惠州", "徐州", "海口", "乌鲁木齐", "绍兴",
    "中山", "台州", "兰州", "潍坊",
}


def city_score(city: str) -> int:
    """城市 → 0-100 分"""
    if not city:
        return 15
    city = city.strip()

    # 处理级联格式 "省/市/区"
    parts = re.split(r"[/·\s]", city)
    city_name = ""
    # 1. 精选匹配：找第一个已知城市名
    for p in parts:
        p_clean = p.strip().replace("市", "")
        if p_clean in TIER1 or p_clean in TIER2:
            city_name = p_clean
            break
    # 2. 直辖市处理：北京/上海/天津/重庆 直接取
    if not city_name:
        for p in parts:
            p_clean = p.strip().replace("市", "")
            if p_clean in ("北京", "上海", "天津", "重庆"):
                city_name = p_clean
                break
    # 3. 兜底：取第一个非省部分
    if not city_name:
        for p in parts:
            p_clean = p.strip().replace("市", "").replace("省", "").replace("区", "").replace("县", "")
            if p_clean and p_clean not in ("北京", "上海", "天津", "重庆"):
                city_name = p_clean
                break
    if not city_name:
        city_name = parts[0].replace("市", "").strip() if parts else city

    if city_name in TIER1:
        return 100
    # 模糊匹配二线
    for t2 in TIER2:
        if t2 in city_name or city_name in t2:
            return 90
    # 直辖市但非一线（天津、重庆）
    if city_name in ("天津", "重庆"):
        return 90
    return 30


def age_score(age_val) -> int:
    """年龄 → 0-100 分（25-45满分）"""
    if age_val is None:
        return 30
    try:
        age_val = int(age_val)
    except:
        return 30
    if 25 <= age_val <= 45:
        return 100
    if 18 <= age_val <= 24:
        return 70
    if age_val >= 46:
        return 30
    return 30


def age_group(age_val) -> str:
    """年龄组：18-24 / 25-35 / 35+"""
    if age_val is None:
        return ""
    try:
        age_val = int(age_val)
    except (ValueError, TypeError):
        return ""
    if 18 <= age_val <= 24:
        return "18-24"
    if 25 <= age_val <= 35:
        return "25-35"
    if age_val >= 36:
        return "35+"
    return ""


def alone_score(attitude_live: str) -> int:
    """独居 → 0-100 分"""
    if not attitude_live:
        return 50
    al = attitude_live.strip()

    if al in ("租房独居", "已购房独居", "独居"):
        return 100
    if al in ("合租",):
        return 50
    if al in ("父母同居", "非独居", "与父母同住"):
        return 20

    # 旧表单文本模糊匹配
    if "独居" in al or "自己住" in al or "一个人住" in al:
        return 100
    if "父母" in al or "家人" in al or "家庭" in al:
        return 20
    if "同居" in al or "合租" in al:
        return 50
    return 50


def score_member(profile):
    """
    给一个会员打分（接受 dict 或 ORM 对象）
    Returns: (level, total_score, details)
    """
    if not isinstance(profile, dict):
        try:
            profile = {c.key: getattr(profile, c.key) for c in profile.__table__.columns}
        except:
            pass

    weights = {"income": 0.35, "city": 0.30, "age": 0.15, "alone": 0.20}

    inc = parse_income(profile.get("income", "") or "")
    cit = city_score(profile.get("city", "") or "")

    age_raw = profile.get("age")
    if age_raw is None:
        bi = profile.get("birth_info", "") or ""
        nums = re.findall(r'\d+', str(bi))
        age_raw = int(nums[0]) if nums else None
    ag = age_score(age_raw)

    al = alone_score(profile.get("attitude_live", "") or "")

    total = inc * weights["income"] + cit * weights["city"] + \
            ag * weights["age"] + al * weights["alone"]
    total = round(total, 1)

    if total >= 80:
        level = "S"
    elif total >= 60:
        level = "A"
    elif total >= 40:
        level = "B"
    else:
        level = "C"

    details = {
        "income": {"score": inc, "weighted": round(inc * weights["income"], 1)},
        "city": {"score": cit, "weighted": round(cit * weights["city"], 1)},
        "age": {"score": ag, "weighted": round(ag * weights["age"], 1)},
        "alone": {"score": al, "weighted": round(al * weights["alone"], 1)},
    }

    return level, total, details

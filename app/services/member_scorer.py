"""
屿风会员分层评分 v3 — 简化版
维度：收入(30%) + 城市(30%) + 年龄(20%) + 独居(20%)
"""
import re


def parse_income(raw) -> int:
    """收入 → 0-100 分"""
    if not raw:
        return 20
    raw = str(raw).strip()

    # 新表单下拉值
    TABLE = {
        "5万以上": 100,
        "3w-5w": 85,
        "1w-3w": 70,
        "8000-10000": 55,
        "5000-8000": 35,
        "3000-5000": 20,
        "3000以下": 5,
        "未工作/在读": 0,
        # 旧值兼容
        "30000以上": 100,
        "20000以上": 80,
        "15000-20000": 75,
        "10000-15000": 65,
    }
    if raw in TABLE:
        return TABLE[raw]

    # 模糊匹配数字
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


def city_score(city: str) -> int:
    """城市 → 0-100 分"""
    if not city:
        return 15
    city = city.strip()

    # 处理级联格式 "省/市/区"
    parts = re.split(r"[/·\s]", city)
    # 取市名（例：江苏省/扬州市/邗江区 → 扬州）
    city_name = ""
    for p in parts:
        p = p.strip().replace("市", "")
        if p and p not in ("北京", "上海", "天津", "重庆"):  # 直辖市直接保留
            city_name = p
        elif p in ("北京", "上海"):
            city_name = p
    if not city_name:
        city_name = parts[0].replace("市", "").strip() if parts else city

    SCORE_MAP = {
        "北京": 100, "上海": 100, "广州": 100, "深圳": 100,
        "杭州": 90, "成都": 90, "重庆": 80,
        "南京": 80, "西安": 80, "武汉": 80, "长沙": 80,
        "苏州": 70, "天津": 70, "东莞": 70, "佛山": 70,
    }

    if city_name in SCORE_MAP:
        return SCORE_MAP[city_name]
    # 模糊匹配
    for key, score in SCORE_MAP.items():
        if key in city_name or city_name in key:
            return score
    return 30


def age_score(age_val) -> int:
    """年龄 → 0-100 分"""
    if age_val is None:
        try:
            age_val = int(age_val)
        except:
            return 30
    age_val = int(age_val)
    if 25 <= age_val <= 35:
        return 100
    if 20 <= age_val <= 24 or 36 <= age_val <= 40:
        return 70
    if 18 <= age_val <= 19 or 41 <= age_val <= 45:
        return 40
    if age_val >= 46:
        return 10
    return 30


def alone_score(attitude_live: str) -> int:
    """独居 → 0-100 分"""
    if not attitude_live:
        return 50  # 未填→中性分，不惩罚
    al = attitude_live.strip()

    # 新表单下拉值
    if al in ("租房独居", "已购房独居", "独居"):
        return 100
    if al in ("合租",):
        return 50
    if al in ("父母同居", "非独居", "与父母同住"):
        return 20

    # 旧表单文本字段 — 模糊匹配
    if "独居" in al or "自己住" in al or "一个人住" in al:
        return 100
    if "父母" in al or "家人" in al or "家庭" in al:
        return 20
    if "同居" in al or "合租" in al:
        return 50
    if "独居" not in al and "同居" not in al and "合租" not in al and "父母" not in al:
        # 有填内容但无法判断居住情况 → 中性
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

    weights = {"income": 0.30, "city": 0.30, "age": 0.20, "alone": 0.20}

    # 1. 收入
    inc_raw = profile.get("income", "") or ""
    inc = parse_income(inc_raw)

    # 2. 城市
    c_raw = profile.get("city", "") or ""
    cit = city_score(c_raw)

    # 3. 年龄
    age_raw = profile.get("age")
    if age_raw is None:
        bi = profile.get("birth_info", "") or ""
        nums = re.findall(r'\d+', str(bi))
        age_raw = int(nums[0]) if nums else None
    ag = age_score(age_raw)

    # 4. 独居
    al_raw = profile.get("attitude_live", "") or ""
    al = alone_score(al_raw)

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
        "income": {"raw": inc_raw, "score": inc, "weighted": round(inc * weights["income"], 1)},
        "city": {"raw": c_raw, "score": cit, "weighted": round(cit * weights["city"], 1)},
        "age": {"raw": age_raw, "score": ag, "weighted": round(ag * weights["age"], 1)},
        "alone": {"raw": al_raw, "score": al, "weighted": round(al * weights["alone"], 1)},
    }

    return level, total, details

"""
屿风会员分层评分服务 v3
- 适配 member_profiles 26 个实际字段
- 收入新增 3 万以上档
- 使用 self_tags/ideal_type_tags/ideal_desc/marriage 等字段做更精准评分
- 评分函数接受 ORM 对象或 dict
"""
import re


WEIGHTS = {
    "income": 0.25,
    "completeness": 0.20,
    "match_potential": 0.25,
    "responsiveness": 0.15,
    "long_term_value": 0.15,
}


def parse_income(raw):
    """收入 → 0-25 分，新增 3 万以上 40 分（唯一超过满点的维度）"""
    if not raw:
        return 5
    raw = str(raw).strip()
    static = {
        "30000以上": 40, "20000以上": 25, "15000-20000": 22,
        "10000-15000": 20, "8000-10000": 18, "5000-8000": 12,
        "3000-5000": 5, "3000以下": 0, "未工作/在读": 0,
    }
    if raw in static:
        return static[raw]
    # 模糊匹配
    nums = re.findall(r'\d+', raw)
    if nums:
        val = int(nums[0])
        if val >= 30000: return 40
        if val >= 20000: return 25
        if val >= 15000: return 22
        if val >= 10000: return 20
        if val >= 8000: return 18
        if val >= 5000: return 12
        if val >= 3000: return 5
        return 0
    return 5


def guess_age(profile):
    """从 birth_info 或 age 字段猜测年龄"""
    bi = profile.get("birth_info", "") or ""
    if bi:
        years = re.findall(r'(19\d{2}|20\d{2})', str(bi))
        if years:
            return 2026 - int(years[0])
        ages = re.findall(r'(\d+)\s*岁', str(bi))
        if ages:
            return int(ages[0])
    # fallback: 直接 age 字段
    age = profile.get("age")
    if age:
        return int(age) if str(age).isdigit() else None
    return None


def age_score(age):
    if age is None: return 1
    if 25 <= age <= 35: return 5
    if 20 <= age <= 24 or 36 <= age <= 45: return 3
    return 1


def role_score(role_self):
    role = (role_self or "").strip()
    if role in ("0", "1"): return 10
    if any(k in role for k in ("0.5", "偏0", "偏1")):
        return 5
    return 0


def ideal_role_score(ideal_role):
    ir = (ideal_role or "").strip()
    if ir in ("0", "1"): return 5
    if "0.5" in ir: return 3
    return 0


CITY_SCORE = {
    "北京": 10, "上海": 10, "广州": 10, "深圳": 10,
    "杭州": 9, "成都": 9, "重庆": 8,
    "南京": 8, "西安": 8, "武汉": 8, "长沙": 8,
    "苏州": 7, "天津": 7, "东莞": 7, "佛山": 7,
}


def city_score(city):
    if not city: return 2
    city = city.strip()
    if city in CITY_SCORE: return CITY_SCORE[city]
    for key, score in CITY_SCORE.items():
        if key in city or city in key: return score
    return 4


def completeness_score(profile):
    """
    资料完整度 0-20 分
    使用 26 个字段中的核心字段
    """
    core = [
        "nickname", "city", "income", "height", "weight",
        "role_self", "body_type", "job", "education",
        "self_tags", "ideal_desc", "dealbreaker",
        "attitude_live", "out_status",
    ]
    filled = sum(1 for f in core if profile.get(f) and str(profile.get(f, "")).strip())
    
    # 追加字段加分
    extras = ["ideal_body_type", "ideal_type_tags", "love_habits", "why_together",
              "extra_message", "social_info", "single_duration", "marriage", "experience"]
    extra_filled = sum(1 for f in extras if profile.get(f) and str(profile.get(f, "")).strip())
    filled += extra_filled * 0.5  # 每个追加字段算 0.5 分
    
    # 照片加分
    photos = profile.get("photos", "") or ""
    photo_path = profile.get("photo_path", "") or ""
    if (photos and str(photos).strip("[] ")) or photo_path:
        filled += 2
    
    if filled >= 16: return 20
    if filled >= 12: return 17
    if filled >= 8: return 12
    if filled >= 4: return 6
    return 0


def long_term_score(profile):
    """
    长期价值 0-15 分
    使用 marriage(形婚考虑), dealbreaker(雷区), ideal_desc(理想描述),
    why_together(长久因素), attitude_live(脱单态度/同居) 等字段
    """
    fields_to_check = [
        profile.get("ideal_desc", ""),
        profile.get("why_together", ""),
        profile.get("attitude_live", ""),
        profile.get("expectation", ""),
        profile.get("dealbreaker", ""),
        profile.get("marriage", ""),
        profile.get("love_habits", ""),
    ]
    combined = " ".join(str(f or "") for f in fields_to_check)
    
    long_sigs = ["结婚", "婚姻", "长久", "长期", "稳定", "一辈子",
                 "相伴", "生活", "一起", "同居", "认真", "真诚",
                 "关系", "伴侣", "陪伴", "过日"]
    short_sigs = ["试试", "看看", "随便", "聊天", "交友", "约"]
    negative = ["骗", "已婚", "有对象"]
    
    if any(s in combined for s in negative): return 0
    if any(s in combined for s in long_sigs): return 15
    if any(s in combined for s in short_sigs): return 3
    # 有详细描述但不明确提及长期
    has_detail = sum(1 for f in fields_to_check if f and len(str(f).strip()) > 15)
    if has_detail >= 2: return 10
    if has_detail >= 1: return 8
    return 5


def score_member(profile):
    """
    给一个会员打分（接受 dict 或 ORM 对象）
    profile: dict with member_profiles fields
    Returns: (level, score, details)
    """
    # 如果是 ORM 对象，转 dict
    if not isinstance(profile, dict):
        try:
            profile = {c.key: getattr(profile, c.key) for c in profile.__table__.columns}
        except:
            pass

    details = {}

    # 1. 收入 (0-100, 3万以上可到160→加权后仍合规)
    income_raw = profile.get("income", "") or ""
    income_points = parse_income(income_raw)
    income_score = income_points * 4  # 3万以上 = 40*4 = 160分，但权重25% = 40分
    # 但最终总分可能超过100，需要 cap
    details["income"] = {"score": income_score, "weighted": income_score * WEIGHTS["income"]}

    # 2. 资料完整度 (0-100)
    comp_score = completeness_score(profile) * 5
    details["completeness"] = {"score": comp_score, "weighted": comp_score * WEIGHTS["completeness"]}

    # 3. 匹配潜力 (0-100)
    rv = role_score(profile.get("role_self", ""))
    iv = ideal_role_score(profile.get("ideal_role", ""))
    cv = city_score(profile.get("city", ""))
    av = age_score(guess_age(profile))
    raw_match = rv + iv + cv + av  # max ~30
    match_score = (raw_match / 30) * 100
    details["match_potential"] = {
        "score": round(match_score, 1),
        "weighted": match_score * WEIGHTS["match_potential"],
    }

    # 4. 配合度 (0-100)
    resp = 50
    photos = profile.get("photos", "") or ""
    photo_path = profile.get("photo_path", "") or ""
    if (photos and str(photos).strip("[] ")) or photo_path:
        resp = 80
    # 如果有微信/手机号也加分
    wechat = profile.get("wechat", "") or ""
    phone = profile.get("phone", "") or ""
    if wechat and phone:
        resp = min(resp + 10, 100)
    details["responsiveness"] = {"score": resp, "weighted": resp * WEIGHTS["responsiveness"]}

    # 5. 长期价值 (0-100)
    ltv_raw = long_term_score(profile)
    ltv_score = (ltv_raw / 15) * 100
    details["long_term_value"] = {"score": round(ltv_score, 1), "weighted": ltv_score * WEIGHTS["long_term_value"]}

    total = sum(v["weighted"] for v in details.values())
    total = round(total, 1)

    if total >= 80:
        level = "S"
    elif total >= 60:
        level = "A"
    elif total >= 40:
        level = "B"
    else:
        level = "C"

    return level, total, details

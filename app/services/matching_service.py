"""匹配服务 v2 — 支持新表单双向角色+体型偏好+标签交叉+共同爱好+异地惩罚"""

import re
from datetime import datetime
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.member_profile import MemberProfile
from app.models.huxuan_profile import HuxuanProfile

# ─── 角色兼容性矩阵 ──────────────────────────────────────────
ROLE_COMPAT = {
    ("1", "0"): 100,
    ("1", "0.5"): 60,
    ("1", "side"): 10,
    ("1", "双"): 30,
    ("0", "1"): 100,
    ("0", "0.5"): 60,
    ("0", "side"): 10,
    ("0", "双"): 30,
    ("0.5", "1"): 60,
    ("0.5", "0"): 60,
    ("0.5", "0.5"): 80,
    ("0.5", "side"): 20,
    ("0.5", "双"): 50,
    ("side", "1"): 10,
    ("side", "0"): 10,
    ("side", "0.5"): 20,
    ("side", "side"): 100,
    ("side", "双"): 30,
    ("双", "1"): 30,
    ("双", "0"): 30,
    ("双", "0.5"): 50,
    ("双", "side"): 30,
    ("双", "双"): 60,
}

ROLE_NORMALIZE = {
    "纯0": "0", "偏0": "0", "0.5/皆可": "0.5",
    "纯1": "1", "偏1": "1",
    "SIDE": "side", "side": "side",
    "双": "双",
}


def _norm_role(r: str) -> str:
    r = r.strip()
    return ROLE_NORMALIZE.get(r, r)


def _role_score_single(role_a: str, role_b: str) -> int:
    """单方向角色兼容性"""
    key = (_norm_role(role_a), _norm_role(role_b))
    return ROLE_COMPAT.get(key, 0)


def _parse_role_vals(val: str) -> list[str]:
    """解析角色字段（可能是逗号分隔的多个值，如 '1，0.5'）"""
    if not val:
        return []
    # 兼容中英文逗号+空格
    parts = re.split(r"[，,、\s]+", val.strip())
    return [p.strip() for p in parts if p.strip()]


def _best_role_match(my_roles: list[str], their_roles: list[str]) -> int:
    """两组角色列表间的最佳匹配分数"""
    if not my_roles or not their_roles:
        return 0
    best = 0
    for mr in my_roles:
        for tr in their_roles:
            s = _role_score_single(mr, tr)
            if s > best:
                best = s
    return best


def _expectation_match(actual_role: str, expected_roles: str) -> int:
    """我/对方是否满足对方的角色期待
    
    actual_role: 实际角色（如 '1'）
    expected_roles: 期待角色字符串，可能多值如 '1，0.5'
    返回 0（不满足）或 100（满足）
    """
    parsed = _parse_role_vals(expected_roles)
    if not parsed:
        return 50  # 没填写期待 → 中等分
    return 100 if actual_role in parsed else 0


def _role_score(my_role_self: str, my_ideal_role: str,
                their_role_self: str, their_ideal_role: str) -> int:
    """双向角色匹配：三个方向取加权平均"""
    # 方向1：双方role_self直接兼容（原有逻辑）
    s1 = _role_score_single(my_role_self, their_role_self)

    # 方向2：我是否符合对方的期待（my_role_self vs their_ideal_role）
    s2 = _expectation_match(my_role_self, their_ideal_role)

    # 方向3：对方是否符合我的期待（their_role_self vs my_ideal_role）
    s3 = _expectation_match(their_role_self, my_ideal_role)

    # 加权：直接兼容 40%，双向期待各 30%
    return int(s1 * 0.4 + s2 * 0.3 + s3 * 0.3)


# ─── 体型偏好 ──────────────────────────────────────────────

# 新旧体型归一化映射
BODY_TYPE_NORM = {
    "偏瘦": "偏瘦", "精瘦": "偏瘦",
    "匀称": "匀称",
    "薄肌": "薄肌",
    "肌肉": "肌肉", "壮实": "肌肉", "微壮": "肌肉",
    "脂包肌": "脂包肌", "微胖": "脂包肌",
    "熊": "熊", "壮": "熊",
    "猪": "猪",
    "丰满": "匀称",  # 折中
}

BODY_SIMILAR_GROUPS = [
    {"偏瘦", "匀称"},
    {"匀称", "薄肌"},
    {"薄肌", "肌肉"},
    {"脂包肌", "熊"},
    {"熊", "猪"},
]


def _norm_body(bt: str) -> str:
    return BODY_TYPE_NORM.get(bt.strip(), bt.strip())


def _body_pref_score(actual: str, ideal: str) -> int:
    """体型偏好匹配：实际 vs 期望"""
    actual = _norm_body(actual)
    ideal = _norm_body(ideal)
    if not ideal:
        return 50
    if ideal == "不限" or ideal == "不限（均可）":
        return 100
    if actual == ideal:
        return 100
    # 相近体型组
    for group in BODY_SIMILAR_GROUPS:
        if actual in group and ideal in group:
            return 70
    return 20


# ─── 城市匹配 ──────────────────────────────────────────────

def _city_score(city_a: str, city_b: str) -> int:
    a = city_a.strip()
    b = city_b.strip()
    if not a or not b:
        return 50
    a_short = re.split(r"[/·\s]", a)[-2] if "/" in a or "·" in a else a
    b_short = re.split(r"[/·\s]", b)[-2] if "/" in b or "·" in b else b
    if a == b:
        return 100
    if a_short == b_short:
        return 95
    return 40


# ─── 异地惩罚 ──────────────────────────────────────────────

def _long_distance_penalty(city_s: int, ld_a: str, ld_b: str) -> float:
    """异地惩罚系数：不接受异地且城市不同 → 大幅降分"""
    a_cant = (ld_a or "").strip() == "不接受"
    b_cant = (ld_b or "").strip() == "不接受"
    if (a_cant or b_cant) and city_s < 80:
        return 0.3  # ×0.3 惩罚
    return 1.0


# ─── 年龄 ──────────────────────────────────────────────────

def _age_score(age_a: int | None, age_b: int | None) -> int:
    if age_a is None or age_b is None:
        return 50
    diff = abs(age_a - age_b)
    if diff <= 3:
        return 100
    elif diff <= 6:
        return 80
    elif diff <= 10:
        return 60
    else:
        return 20


def _get_age(profile) -> int | None:
    age_attr = getattr(profile, "age", None)
    if age_attr is not None:
        return int(age_attr) if age_attr else None
    if hasattr(profile, "年龄"):
        try:
            val = re.sub(r"[^0-9]", "", profile.年龄 or "0")
            return int(val) if val else None
        except:
            return None
    bi = getattr(profile, "birth_info", "") or ""
    m = re.search(r"(\d{4})", bi)
    if m:
        return datetime.now().year - int(m.group(1))
    m = re.search(r"(\d+)\s*岁", bi)
    if m:
        return int(m.group(1))
    return None


# ─── 标签交叉匹配 ──────────────────────────────────────────

def _parse_tags(tags_str: str) -> set[str]:
    """解析逗号分隔的标签列表"""
    if not tags_str:
        return set()
    parts = re.split(r"[，,、\s]+", tags_str.strip())
    return set(p.strip() for p in parts if p.strip())


def _tags_cross_score(my_self_tags: str, my_ideal_tags: str,
                      their_self_tags: str, their_ideal_tags: str) -> int:
    """标签交叉：我的自我标签 vs 对方的理想标签 + 对方的自我标签 vs 我的理想标签"""
    my_self = _parse_tags(my_self_tags)
    my_ideal = _parse_tags(my_ideal_tags)
    their_self = _parse_tags(their_self_tags)
    their_ideal = _parse_tags(their_ideal_tags)

    if not my_self and not my_ideal and not their_self and not their_ideal:
        return 50  # 全未填 → 中性
    if not my_ideal or not their_self:
        return 50  # 有一方未填(s1方向无效) → 中性
    if not my_self or not their_ideal:
        return 50  # 有一方未填(s2方向无效) → 中性

    # 方向1：我的自我标签 ∩ 对方的理想标签
    s1 = len(my_self & their_ideal) / max(len(my_self | their_ideal), 1) if my_self and their_ideal else 0
    # 方向2：对方的自我标签 ∩ 我的理想标签
    s2 = len(their_self & my_ideal) / max(len(their_self | my_ideal), 1) if their_self and my_ideal else 0

    avg = (s1 + s2) / 2
    return int(avg * 100)


# ─── 共同爱好 ──────────────────────────────────────────────

def _hobbies_score(hobbies_a: str, hobbies_b: str) -> int:
    """共同爱好得分"""
    h_a = _parse_tags(hobbies_a)
    h_b = _parse_tags(hobbies_b)
    if not h_a or not h_b:
        return 0
    common = h_a & h_b
    if len(common) >= 2:
        return 100
    elif len(common) == 1:
        return 60
    return 0


# ─── 匹配描述 ──────────────────────────────────────────────

def _describe_match(profile: MemberProfile, scores: dict) -> str:
    reasons = []
    role_desc = profile.role_self or "未知"
    age_val = _get_age(profile)
    age_desc = f"{age_val}岁" if age_val else "未知年龄"
    city_desc = profile.city or "未知城市"
    job_desc = profile.job or ""

    base = f"{profile.nickname or '匿名'} · {role_desc} · {age_desc}"
    if city_desc != "未知城市":
        base += f" · {city_desc}"
    if job_desc:
        base += f" · {job_desc}"
    reasons.append(base)

    if scores.get("role", 0) >= 80:
        reasons.append(f"✅ 角色匹配 ({scores['role']}分)")
    if scores.get("city", 0) >= 90:
        reasons.append(f"📍 同城 ({city_desc})")
    if scores.get("age", 0) >= 80:
        reasons.append(f"🎂 年龄相仿 ({age_desc})")
    if scores.get("body", 0) >= 80:
        reasons.append(f"💪 体型偏好 ({scores['body']}分)")
    if scores.get("tags", 0) >= 70:
        reasons.append(f"🏷 标签契合 ({scores['tags']}分)")
    if scores.get("hobbies", 0) >= 60:
        reasons.append(f"🎯 共同爱好")

    body = f"体型·{profile.body_type}" if profile.body_type else ""
    income = f"收入·{profile.income}" if profile.income else ""
    extra = "、".join(filter(None, [body, income]))
    if extra:
        reasons.append(f"🏷 {extra}")

    hobby = (profile.hobbies or "")[:30]
    if hobby:
        reasons.append(f"💬 {hobby}")

    return "\n".join(reasons)


def _describe_huxuan_match(hp: HuxuanProfile, scores: dict) -> str:
    reasons = []
    role_desc = hp.属性 or "未知"
    city_desc = hp.城市 or "未知城市"
    job_desc = hp.职业 or ""
    age_str = hp.年龄 or "未知年龄"

    base = f"{hp.昵称 or '匿名'} · {role_desc} · {age_str}"
    if city_desc != "未知城市":
        base += f" · {city_desc}"
    if job_desc:
        base += f" · {job_desc}"
    reasons.append(base)

    if scores.get("role", 0) >= 80:
        reasons.append(f"✅ 角色匹配 ({scores['role']}分)")
    if scores.get("city", 0) >= 90:
        reasons.append(f"📍 同城 ({city_desc})")
    if scores.get("age", 0) >= 80:
        reasons.append(f"🎂 年龄相仿 ({age_str})")
    if scores.get("body", 0) >= 80:
        reasons.append(f"💪 体型偏好 ({scores['body']}分)")

    body = f"体型·{hp.体型}" if hp.体型 else ""
    if body:
        reasons.append(f"🏷 {body}")

    return "\n".join(reasons)


def _find_scored(db: Session, my_profile: MemberProfile,
                 candidates: list, is_huxuan: bool = False) -> list[dict]:
    """通用评分函数：对候选人列表打分排序
    
    Args:
        candidates: MemberProfile 或 HuxuanProfile 列表
        is_huxuan: 是否是煎面外部数据（使用中文列名）
    """
    scored = []

    for c in candidates:
        # 提取字段（兼容 MemberProfile 和 HuxuanProfile）
        if is_huxuan:
            their_role_self = getattr(c, "属性", "") or ""
            their_ideal_role = ""  # 煎面没有理想角色
            their_city = getattr(c, "城市", "") or ""
            their_body_type = getattr(c, "体型", "") or ""
            their_ideal_body = ""  # 煎面没有理想体型
            their_ld = ""  # 煎面没有异地字段
            their_self_tags = ""  # 煎面没有标签
            their_ideal_tags = ""
            their_hobbies = ""
        else:
            their_role_self = c.role_self or ""
            their_ideal_role = c.ideal_role or ""
            their_city = c.city or ""
            their_body_type = c.body_type or ""
            their_ideal_body = c.ideal_body_type or ""
            their_ld = c.long_distance or ""
            their_self_tags = c.self_tags or ""
            their_ideal_tags = c.ideal_type_tags or ""
            their_hobbies = c.hobbies or ""

        # ── 各维度评分 ──
        # 1. 角色双向匹配 (30%)
        r_score = _role_score(
            my_profile.role_self or "", my_profile.ideal_role or "",
            their_role_self, their_ideal_role
        )

        # 2. 城市 + 异地惩罚 (20%)
        c_score = _city_score(my_profile.city or "", their_city)
        ld_penalty = _long_distance_penalty(
            c_score, my_profile.long_distance or "", their_ld
        )
        c_score_adj = int(c_score * ld_penalty)

        # 3. 年龄 (20%)
        if is_huxuan:
            try:
                hp_age = int(re.sub(r"[^0-9]", "", getattr(c, "年龄", "0") or "0")) if getattr(c, "年龄", None) else None
            except:
                hp_age = None
            a_score = _age_score(_get_age(my_profile), hp_age)
        else:
            a_score = _age_score(_get_age(my_profile), _get_age(c))

        # 4. 体型偏好 (10%)
        b_score = _body_pref_score(their_body_type, my_profile.ideal_body_type or "")

        # 5. 标签交叉 (10%)
        t_score = _tags_cross_score(
            my_profile.self_tags or "", my_profile.ideal_type_tags or "",
            their_self_tags, their_ideal_tags
        ) if not is_huxuan else 50  # 煎面没标签，给中等分

        # 6. 共同爱好 (5%)
        h_score = _hobbies_score(my_profile.hobbies or "", their_hobbies)

        # ── 同城优先 Bonus ──
        city_bonus = 0
        if c_score_adj >= 95:
            city_bonus = 20  # 同城 +20
        elif c_score_adj >= 70:
            city_bonus = 10  # 同省 +10

        # ── 总分 ──
        total = (r_score * 0.30 + c_score_adj * 0.30 + a_score * 0.20 +
                 b_score * 0.10 + t_score * 0.05 + h_score * 0.05) + city_bonus

        # 如果角色完全不兼容（<20分）且城市也远不匹配 → 剔除
        if r_score < 20 and c_score < 40:
            continue

        scores = {
            "role": r_score, "city": c_score_adj, "age": a_score,
            "body": b_score, "tags": t_score, "hobbies": h_score,
            "city_bonus": city_bonus, "total": round(total, 1),
        }
        description = _describe_huxuan_match(c, scores) if is_huxuan else _describe_match(c, scores)

        scored.append({"profile": c, "scores": scores, "description": description})

    return scored


def find_matches(
    db: Session,
    profile: MemberProfile,
    limit: int = 5,
) -> list[dict]:
    """增强匹配：从 member_profiles + huxuan_profiles 找候选人"""
    if not profile.id:
        return []

    # ── 1. MemberProfile 候选人 ──
    candidates = (
        db.query(MemberProfile)
        .filter(
            MemberProfile.id != profile.id,
            MemberProfile.nickname != "",
        )
        .all()
    )
    scored = _find_scored(db, profile, candidates, is_huxuan=False)

    # ── 2. HuxuanProfile 补充 ──
    seen_nicknames = {c.nickname.strip() for c in candidates if c.nickname}

    huxuan_all = db.query(HuxuanProfile).filter(
        HuxuanProfile.昵称 != "",
        HuxuanProfile.昵称.isnot(None),
    ).all()

    huxuan_new = [hp for hp in huxuan_all
                  if (hp.昵称 or "").strip() not in seen_nicknames]
    scored += _find_scored(db, profile, huxuan_new, is_huxuan=True)
    seen_nicknames.update((hp.昵称 or "").strip() for hp in huxuan_new)

    # ── 排序 & 截取 ──
    scored.sort(key=lambda x: x["scores"]["total"], reverse=True)
    return scored[:limit]

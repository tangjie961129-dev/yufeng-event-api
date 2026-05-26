"""匹配服务 — 从 member_profiles 表中找合适的候选人"""
import re
from datetime import datetime
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.member_profile import MemberProfile

# ─── 角色兼容性矩阵 ──────────────────────────────────────────
# 值: 0-100，越高越兼容
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


def _role_score(role_a: str, role_b: str) -> int:
    key = (role_a.strip(), role_b.strip())
    return ROLE_COMPAT.get(key, 0)


def _city_score(city_a: str, city_b: str) -> int:
    a = city_a.strip()
    b = city_b.strip()
    if not a or not b:
        return 50  # 未知城市给中等分
    # 从完整路径中提取城市名（如 "广东省/广州市/番禺区" → "广州"）
    a_short = re.split(r"[/·\s]", a)[-2] if "/" in a or "·" in a else a
    b_short = re.split(r"[/·\s]", b)[-2] if "/" in b or "·" in b else b
    if a == b:
        return 100
    if a_short == b_short:
        return 95
    return 40


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


def _describe_match(profile: MemberProfile, scores: dict) -> str:
    """生成匹配理由"""
    reasons = []

    role_desc = profile.role_self or "未知"
    age_desc = f"{profile.age}岁" if profile.age else "未知年龄"
    city_desc = profile.city or "未知城市"
    job_desc = profile.job or ""

    # 基础信息
    base = f"{profile.nickname or '匿名'} · {role_desc} · {age_desc}"
    if city_desc != "未知城市":
        base += f" · {city_desc}"
    if job_desc:
        base += f" · {job_desc}"
    reasons.append(base)

    # 匹配理由
    if scores.get("role", 0) >= 80:
        reasons.append(f"✅ 角色匹配 ({scores['role']}分)")
    if scores.get("city", 0) >= 90:
        reasons.append(f"📍 同城 ({city_desc})")
    if scores.get("age", 0) >= 80:
        reasons.append(f"🎂 年龄相仿 ({age_desc})")

    body = f"体型·{profile.body_type}" if profile.body_type else ""
    income = f"收入·{profile.income}" if profile.income else ""
    extra = "、".join(filter(None, [body, income]))
    if extra:
        reasons.append(f"🏷 {extra}")

    # 爱好/状态简述
    hobby = (profile.hobbies or "")[:30]
    if hobby:
        reasons.append(f"💬 {hobby}")

    return "\n".join(reasons)


def find_matches(
    db: Session,
    profile: MemberProfile,
    limit: int = 5,
) -> list[dict]:
    """从 member_profiles 中为指定档案找匹配候选人

    返回已按总分降序排列的 [(profile, score, reasons), ...]
    """
    if not profile.id:
        return []

    # 排除自己
    candidates = (
        db.query(MemberProfile)
        .filter(
            MemberProfile.id != profile.id,
            MemberProfile.nickname != "",  # 有昵称才算有效数据
        )
        .all()
    )

    scored_candidates = []
    for c in candidates:
        r_score = _role_score(profile.role_self or "", c.role_self or "")
        c_score = _city_score(profile.city or "", c.city or "")
        a_score = _age_score(profile.age, c.age)

        # 如果角色完全不兼容（<30 分），剔除
        if r_score < 30 and c_score < 50:
            continue

        # 权重：角色 40%，城市 30%，年龄 30%
        total = r_score * 0.4 + c_score * 0.3 + a_score * 0.3

        scores = {"role": r_score, "city": c_score, "age": a_score, "total": round(total, 1)}
        description = _describe_match(c, scores)

        scored_candidates.append({
            "profile": c,
            "scores": scores,
            "description": description,
        })

    # 按总分降序排列
    scored_candidates.sort(key=lambda x: x["scores"]["total"], reverse=True)

    return scored_candidates[:limit]

"""User-main-table matching service for Yufeng.

All channels should converge into users. This service reads users as the
canonical candidate pool and only uses source/raw tables for enrichment.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.models.user import User


ROLE_COMPAT = {
    ("1", "0"): 100,
    ("0", "1"): 100,
    ("1", "0.5"): 65,
    ("0.5", "1"): 65,
    ("0", "0.5"): 65,
    ("0.5", "0"): 65,
    ("0.5", "0.5"): 80,
    ("side", "side"): 100,
    ("双", "双"): 70,
    ("双", "1"): 45,
    ("双", "0"): 45,
    ("1", "双"): 45,
    ("0", "双"): 45,
}


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _short_city(city: str) -> str:
    city = _norm(city).replace("省", "省/").replace("市", "市/") if "/" not in _norm(city) else _norm(city)
    parts = [p for p in re.split(r"[/·\s]+", city) if p]
    if not parts:
        return ""
    for p in reversed(parts):
        if p.endswith("市") or p.endswith("区") or p.endswith("县"):
            return p.replace("市", "")
    return parts[-1].replace("市", "")


def _province(city: str) -> str:
    parts = [p for p in re.split(r"[/·\s]+", _norm(city)) if p]
    return parts[0] if parts else ""


def _parse_json_list(v: str | None) -> list[str]:
    if not v:
        return []
    try:
        data = json.loads(v)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except Exception:
        pass
    return [x.strip() for x in re.split(r"[,，、/\s]+", v or "") if x.strip()]


def _role_score(a: str, b: str) -> int:
    a = _norm(a).lower().replace("０", "0").replace("１", "1")
    b = _norm(b).lower().replace("０", "0").replace("１", "1")
    if not a or not b:
        return 55
    return ROLE_COMPAT.get((a, b), 30 if a != b else 60)


def _city_score(a: str, b: str, long_distance: str = "") -> int:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 50
    if a == b or _short_city(a) == _short_city(b):
        return 100
    if _province(a) and _province(a) == _province(b):
        return 70
    if "接受" in _norm(long_distance) or "异地也可" in _norm(long_distance):
        return 55
    if "不接受" in _norm(long_distance) or "仅同城" in _norm(long_distance):
        return 20
    return 40


def _age_score(a: int | None, b: int | None) -> int:
    if a is None or b is None:
        return 50
    diff = abs(int(a) - int(b))
    if diff <= 3:
        return 100
    if diff <= 6:
        return 80
    if diff <= 10:
        return 60
    return 30


def _text_overlap_score(source: User, cand: User) -> tuple[int, list[str]]:
    s_tags = set(_parse_json_list(source.hobby_tags) + _parse_json_list(source.personality_tags))
    c_tags = set(_parse_json_list(cand.hobby_tags) + _parse_json_list(cand.personality_tags))
    common = sorted(x for x in s_tags & c_tags if x)
    score = min(100, 45 + len(common) * 18) if common else 45
    reasons = [f"共同标签：{'、'.join(common[:4])}"] if common else []
    s_text = " ".join([_norm(source.match_preferences), _norm(source.expectation), _norm(source.bio)])
    c_text = " ".join([_norm(cand.bio), _norm(cand.expectation), _norm(cand.match_preferences)])
    for kw in ["健身", "运动", "稳定", "真诚", "成熟", "同城", "旅行", "生活", "长期", "结婚", "形婚"]:
        if kw in s_text and kw in c_text and kw not in common:
            score = min(100, score + 10)
            reasons.append(f"文本偏好都提到：{kw}")
            break
    return score, reasons


def _profile_quality(u: User) -> int:
    fields = [u.nickname, u.city, u.age, u.role_self, u.body_type, u.job, u.income_range, u.bio, u.match_preferences, u.expectation]
    filled = sum(1 for x in fields if _norm(x))
    return min(100, filled * 10)


def _candidate_card(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "nickname": u.nickname or f"会员{u.id}",
        "city": u.city or "未知",
        "age": u.age,
        "height": getattr(u, "height", None),
        "weight": getattr(u, "weight", None),
        "role_self": getattr(u, "role_self", "") or "未知",
        "body_type": getattr(u, "body_type", "") or "未知",
        "job": getattr(u, "job", "") or "未知",
        "income_range": u.income_range or "未知",
        "education": u.education or "未知",
        "bio": (u.bio or "")[:260],
        "match_preferences": (u.match_preferences or u.expectation or "")[:260],
        "source_channel": getattr(u, "source_channel", "") or "",
    }


def find_user(db: Session, *, user_id: int | None = None, nickname: str | None = None) -> User | None:
    if user_id:
        u = db.query(User).filter(User.id == user_id).first()
        if u:
            return u
    name = _norm(nickname)
    if not name:
        return None
    return (
        db.query(User)
        .filter(User.nickname.ilike(f"%{name}%"))
        .order_by(User.updated_at.desc().nullslast(), User.id.desc())
        .first()
    )


def find_matches_for_user(db: Session, *, user_id: int | None = None, nickname: str | None = None, limit: int = 8) -> dict[str, Any]:
    source = find_user(db, user_id=user_id, nickname=nickname)
    if not source:
        return {"found": False, "message": f"未在 users 主表命中会员：{nickname or user_id}", "source": None, "matches": []}

    candidates = (
        db.query(User)
        .filter(
            User.id != source.id,
            User.match_status == "ready",
            User.nickname != "",
            User.age.isnot(None),
            User.city != "",
        )
        .limit(3000)
        .all()
    )
    scored: list[dict[str, Any]] = []
    for c in candidates:
        r_score = _role_score(getattr(source, "role_self", "") or "", getattr(c, "role_self", "") or "")
        c_score = _city_score(source.city or "", c.city or "", getattr(source, "long_distance", "") or source.match_preferences or "")
        a_score = _age_score(source.age, c.age)
        text_score, text_reasons = _text_overlap_score(source, c)
        quality = _profile_quality(c)
        total = round(r_score * 0.25 + c_score * 0.30 + a_score * 0.15 + text_score * 0.20 + quality * 0.10, 1)
        reasons = []
        if c_score >= 95:
            reasons.append(f"同城/同区域：{c.city}")
        elif c_score >= 70:
            reasons.append("同省，距离成本相对低")
        if a_score >= 80:
            reasons.append(f"年龄相近：{c.age}岁")
        if r_score >= 80:
            reasons.append("属性/角色兼容度高")
        elif r_score >= 60:
            reasons.append("属性/角色可兼容")
        if getattr(c, "body_type", ""):
            reasons.append(f"体型：{c.body_type}")
        if c.job:
            reasons.append(f"职业：{c.job}")
        reasons.extend(text_reasons[:2])
        if not reasons:
            reasons.append("基础资料完整，可作为备选进一步人工核查")
        scored.append({"score": total, "scores": {"city": c_score, "age": a_score, "role": r_score, "text": text_score, "quality": quality}, "member": _candidate_card(c), "reasons": reasons[:6]})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"found": True, "source": _candidate_card(source), "total_candidates": len(candidates), "matches": scored[:limit]}


def format_match_result(result: dict[str, Any]) -> str:
    if not result.get("found"):
        return result.get("message") or "未命中会员。"
    src = result["source"]
    lines = [
        f"✅ 已走 users 主表快速匹配：{src['nickname']}（ID {src['id']}）",
        f"资料：{src['city']}｜{src.get('age') or '未知'}岁｜{src.get('height') or '-'}cm/{src.get('weight') or '-'}kg｜属性{src.get('role_self') or '未知'}｜{src.get('body_type') or '体型未知'}｜{src.get('job') or '职业未知'}",
        f"候选池：users 主表 ready 会员 {result.get('total_candidates', 0)} 人；以下按综合分排序。",
        "",
    ]
    for i, item in enumerate(result.get("matches") or [], 1):
        m = item["member"]
        lines.append(f"{i}. {m['nickname']}（ID {m['id']}）｜{item['score']}分")
        lines.append(f"   {m['city']}｜{m.get('age') or '未知'}岁｜{m.get('height') or '-'}cm/{m.get('weight') or '-'}kg｜属性{m.get('role_self') or '未知'}｜{m.get('body_type') or '体型未知'}｜{m.get('job') or '职业未知'}")
        lines.append("   推荐依据：" + "；".join(item.get("reasons") or []))
        if m.get("match_preferences"):
            lines.append(f"   期待/偏好：{m['match_preferences'][:120]}")
    lines.append("\n说明：以上为内部匹配建议，公开对客户沟通时不要直接暴露属性/角色和隐私联系方式。")
    return "\n".join(lines)[:1800]


def lookup_user_profile_text(db: Session, nickname: str) -> str:
    u = find_user(db, nickname=nickname)
    if not u:
        return f"未在 users 主表命中会员：{nickname}"
    card = _candidate_card(u)
    rows = db.execute(text("""
        select source_type, source_record_id, raw_json::text as raw_json_text, last_synced_at
        from member_sync_sources where user_id=:uid order by updated_at desc limit 3
    """), {"uid": u.id}).mappings().all()
    contact = db.execute(text("""
        select source_type, phone, wechat_id from member_contact_methods where user_id=:uid order by updated_at desc limit 3
    """), {"uid": u.id}).mappings().all()
    def mask(v: str | None) -> str:
        v = _norm(v)
        return (v[:3] + "***" + v[-2:]) if len(v) > 6 else ("已留" if v else "无")
    lines = [
        f"✅ users 主表会员档案：{card['nickname']}（ID {card['id']}）",
        f"城市/年龄：{card['city']}｜{card.get('age') or '未知'}岁",
        f"身高体重：{card.get('height') or '-'}cm / {card.get('weight') or '-'}kg",
        f"属性/体型：{card.get('role_self') or '未知'}｜{card.get('body_type') or '未知'}",
        f"职业/收入/学历：{card.get('job') or '未知'}｜{card.get('income_range') or '未知'}｜{card.get('education') or '未知'}",
        f"自我介绍：{card.get('bio') or '无'}",
        f"择偶/期待：{card.get('match_preferences') or '无'}",
        f"来源渠道：{getattr(u, 'source_channel', '') or '未标记'}｜状态：{u.match_status}",
    ]
    if contact:
        lines.append("联系方式状态（已脱敏）：" + "；".join([f"{r['source_type']} 微信{mask(r['wechat_id'])} 手机{mask(r['phone'])}" for r in contact]))
    if rows:
        lines.append("来源记录：" + "；".join([f"{r['source_type']}#{r['source_record_id']}" for r in rows]))
    return "\n".join(lines)[:1800]

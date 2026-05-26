"""
屿风恋爱服务基础接口

当前阶段先提供稳定可用的 P0 接口，避免小程序恋爱服务页继续依赖本地 fallback。
后续可替换为真实 AI 匹配引擎、用户画像存储和会员体系。
"""
import json
import math
import os
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.core.database import get_db
from app.models.love_models import BoyfriendMessage, BoyfriendState, MatchCredit, MatchSession, MatchRoomInvitation
from app.models.member_profile import MemberProfile
from app.models.user import User
from app.models.permission_distribution import ReferralBinding
from app.services.wechat_pay import (
    WechatPayAPIError,
    WechatPayConfigError,
    build_request_payment_params,
    create_jsapi_prepay,
)

router = APIRouter(prefix="/api/love", tags=["恋爱服务"])


class LovePayload(BaseModel):
    model_config = {"extra": "allow"}


# ====== 课程列表（静态）======

COURSES = [
    {
        "id": "course_1",
        "title": "7 天建立真实关系感",
        "subtitle": "从资料表达、破冰聊天到第一次见面，帮你降低社交消耗。",
        "tag": "关系成长",
        "price": 99,
        "cover": "",
    },
    {
        "id": "course_2",
        "title": "彩虹社群安全约会指南",
        "subtitle": "边界感、隐私保护、线下见面安全与情绪识别。",
        "tag": "安全约会",
        "price": 59,
        "cover": "",
    },
    {
        "id": "course_3",
        "title": "长期关系沟通训练营",
        "subtitle": "减少内耗，把需求说清楚，也听懂对方真正想表达什么。",
        "tag": "沟通训练",
        "price": 129,
        "cover": "",
    },
]


def _first_non_empty(data: dict, keys: list[str], default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value:
            return str(value)
    return default


# ====== 课程 ======


@router.get("/courses")
def list_love_courses():
    """返回恋爱服务课程列表。"""
    return COURSES


# ====== Demo 档案数据（fallback）======

DEMO_PROFILES_MALE = [
    {"name": "林川", "age": 29, "city": "广州", "height": 178, "weight": 72, "body_type": "匀称", "role": "1", "job": "互联网产品经理", "education": "本科", "income": "1w-3w", "bio": "喜欢周末徒步和桌游，不抽烟偶尔社交饮酒。性格温和但有自己的节奏，希望能找到一个互相尊重、一起成长的人。", "tags": ["责任感强", "成熟", "硬朗"], "score_bonus": 2},
    {"name": "周屿", "age": 31, "city": "深圳", "height": 182, "weight": 78, "body_type": "壮实", "role": "0.5", "job": "独立摄影师", "education": "本科", "income": "1w-3w", "bio": "摄影和旅行是生活的主线，性格偏安静但熟了之后话很多。希望遇到一个情绪稳定、有自己生活圈的人。", "tags": ["包容", "成熟", "温柔"], "score_bonus": 0},
    {"name": "阿正", "age": 26, "city": "广州", "height": 175, "weight": 68, "body_type": "匀称", "role": "0", "job": "建筑设计助理", "education": "硕士", "income": "5k-1w", "bio": "刚毕业一年，正在慢慢建立自己的生活秩序。喜欢看展和逛书店，希望能和一个温和、真诚的人互相陪伴。", "tags": ["温柔", "可爱", "专一"], "score_bonus": 0},
    {"name": "肖恩", "age": 34, "city": "广州", "height": 180, "weight": 80, "body_type": "壮实", "role": "1", "job": "健身教练", "education": "大专", "income": "3w-10w", "bio": "健身是工作也是生活。日常生活中比较随和，对感情认真直接。希望能找到一个重视健康和生活品质的人。", "tags": ["硬朗", "帅气", "责任感强"], "score_bonus": 1},
    {"name": "小陆", "age": 27, "city": "上海", "height": 176, "weight": 65, "body_type": "精瘦", "role": "0.5", "job": "数据分析师", "education": "硕士", "income": "3w-10w", "bio": "工作日理性，周末爱做菜和看纪录片。性格有分寸感，知道什么时候该推进、什么时候该留空间。", "tags": ["成熟", "专一", "包容"], "score_bonus": 0},
    {"name": "大鹏", "age": 33, "city": "北京", "height": 185, "weight": 85, "body_type": "肌肉", "role": "1", "job": "建筑项目经理", "education": "本科", "income": "3w-10w", "bio": "外表看起来很有距离感，实际上很照顾人。喜欢户外和旅行，周末不是在爬山就是在去健身房的路上。", "tags": ["硬朗", "责任感强", "阳光"], "score_bonus": 0},
    {"name": "可乐", "age": 24, "city": "成都", "height": 172, "weight": 63, "body_type": "精瘦", "role": "0", "job": "UI设计师", "education": "本科", "income": "1w-3w", "bio": "性格开朗又细腻，喜欢音乐、插画和小动物。虽然年纪不大但对感情很认真，不接受随便玩玩的关系。", "tags": ["可爱", "活泼", "开朗"], "score_bonus": 1},
    {"name": "老许", "age": 38, "city": "广州", "height": 177, "weight": 74, "body_type": "匀称", "role": "0.5", "job": "高校教师", "education": "博士", "income": "1w-3w", "bio": "工作稳定，生活规律，喜欢阅读、喝茶和散步。对关系认真但不强求，希望能遇到一个能一起过平淡日子的人。", "tags": ["成熟", "包容", "责任感强"], "score_bonus": 0},
    {"name": "小天", "age": 28, "city": "杭州", "height": 174, "weight": 66, "body_type": "匀称", "role": "0", "job": "电商运营", "education": "本科", "income": "1w-3w", "bio": "性格温和，喜欢探店、拍照和做攻略，朋友眼里是靠谱的出行搭子。希望遇到一个真诚有规划的人。", "tags": ["温柔", "开朗", "专一"], "score_bonus": 0},
    {"name": "阿坤", "age": 30, "city": "广州", "height": 179, "weight": 75, "body_type": "肌肉", "role": "1", "job": "金融风控", "education": "硕士", "income": "3w-10w", "bio": "生活自律有规划，不约不混圈。平时健身、看书、研究投资。希望能遇到一个也能把自己的生活过好的人。", "tags": ["硬朗", "责任感强", "成熟"], "score_bonus": 0},
]

DEMO_PROFILES_FEMALE = [
    {"name": "小鹿", "age": 28, "city": "广州", "orientation": "女同", "education": "本科", "job": "平面设计师", "bio": "性格温和细腻，想要找一个一起面对家庭的朋友。喜欢猫和做甜品。", "license": "接受", "child_plan": "远期考虑", "cohabitation": "必要时短期同居", "wedding": "正式宴请", "economy": "完全AA制", "family_duty": "共同协商"},
    {"name": "Lena", "age": 32, "city": "深圳", "orientation": "女同", "education": "硕士", "job": "人力资源总监", "bio": "性格独立理性，观念开放。希望能找到一个目标清晰、沟通顺畅的合作伙伴。", "license": "接受", "child_plan": "近期计划生育", "cohabitation": "必要时短期同居", "wedding": "正式宴请", "economy": "共同承担孩子相关费用", "family_duty": "共同协商"},
    {"name": "阿雅", "age": 26, "city": "广州", "orientation": "双性恋", "education": "本科", "job": "医生", "bio": "医务工作者，性格温柔有耐心。希望能和一个体面、靠谱的男生达成共识。", "license": "仅办仪式", "child_plan": "远期考虑", "cohabitation": "长期分房同居", "wedding": "正式宴请", "economy": "完全AA制", "family_duty": "共同协商"},
    {"name": "大美", "age": 35, "city": "广州", "orientation": "女同", "education": "本科", "job": "企业行政主管", "bio": "性格爽朗直接，经济和心态都很稳定。家里催得紧，想尽快找到一个真诚靠谱的人。", "license": "接受", "child_plan": "近期计划生育", "cohabitation": "必要时短期同居", "wedding": "仅家庭小聚", "economy": "共同承担孩子相关费用", "family_duty": "轮流主导"},
    {"name": "小艺", "age": 29, "city": "上海", "orientation": "双性恋", "education": "硕士", "job": "心理咨询师", "bio": "自己的工作室运营稳定，情绪独立。想要一个互相配合、不过度纠缠的形婚关系。", "license": "接受", "child_plan": "远期考虑", "cohabitation": "完全不同居", "wedding": "仅家庭小聚", "economy": "完全AA制", "family_duty": "固定一方主导"},
    {"name": "晓雯", "age": 30, "city": "广州", "orientation": "男同", "education": "本科", "job": "瑜伽导师", "bio": "虽然性取向是男生，但对形婚有兴趣。性格平和，善于沟通，希望能遇到可以长期合作的人。", "license": "接受", "child_plan": "不考虑", "cohabitation": "必要时短期同居", "wedding": "正式宴请", "economy": "共同承担孩子相关费用", "family_duty": "共同协商"},
]


# ====== 匹配评分辅助函数（Demo fallback）======


def _score_role(user_role: str, profile_role: str) -> int:
    """性角色匹配评分（满分30）。"""
    if user_role == "0":
        if profile_role == "0":
            return -999  # 淘汰
        return 30 if profile_role in ("1", "0.5", "side") else 15
    if user_role == "1":
        if profile_role == "1":
            return -999
        return 30 if profile_role in ("0", "0.5", "side") else 15
    if user_role == "side":
        if profile_role == "side":
            return 30
        return 15 if profile_role in ("0", "0.5", "1") else 0
    if user_role == "0.5":
        return 30  # 0.5 可配任何角色
    return -999


def _score_city(user_city: str, profile_city: str, accept_long_distance: bool) -> int:
    """同城/异地评分（满分15）。"""
    if not user_city or not profile_city:
        return 7
    same_city = user_city == profile_city
    if not accept_long_distance and not same_city:
        return -999  # 不接受异地时强制淘汰
    return 15 if same_city else 5


def _score_age(user_age_group: str, profile_age: int) -> int:
    """年龄相仿评分（满分20）。"""
    age_map = {"18-22": (18, 22), "23-27": (23, 27), "28-32": (28, 32), "33-38": (33, 38), "39-45": (39, 45), "45以上": (45, 60)}
    user_range = age_map.get(user_age_group, (25, 35))
    user_center = (user_range[0] + user_range[1]) / 2
    diff = abs(user_center - profile_age)
    if diff <= 3:
        return 20
    if diff <= 6:
        return 14
    if diff <= 10:
        return 8
    return 4


def _score_body(user_body: str, expect_body: str, profile_body: str) -> int:
    """体型偏好评分（满分10）。"""
    if not expect_body or expect_body == "不限":
        return 10
    if profile_body == expect_body:
        return 10
    # 相近体型仍可接受
    similar = [("精瘦", "匀称"), ("匀称", "精瘦"), ("肌肉", "壮实"), ("壮实", "肌肉")]
    if (profile_body, expect_body) in similar or (expect_body, profile_body) in similar:
        return 6
    return 2


def _score_attitude(profile_tags: list) -> int:
    """诚意度评分（满分5）。"""
    sincerity_tags = ["责任感强", "专一", "成熟", "硬朗"]
    match_count = sum(1 for tag in profile_tags if tag in sincerity_tags)
    return min(match_count * 2, 5)


def _build_reality_signals(profile: dict | MemberProfile, score: int | float) -> list[dict]:
    """真实感信号：给前端和企微话术展示，不暴露联系方式。"""
    if isinstance(profile, MemberProfile):
        completeness_fields = [profile.nickname, profile.age, profile.city, profile.role_self, profile.job, profile.current_situation or profile.expectation]
        verified = bool(profile.external_userid)
        recent_active = bool(profile.updated_at or profile.created_at)
    else:
        completeness_fields = [profile.get("name"), profile.get("age"), profile.get("city"), profile.get("role"), profile.get("job"), profile.get("bio")]
        verified = False
        recent_active = True
    completeness = int(sum(1 for v in completeness_fields if v) / len(completeness_fields) * 100)
    return [
        {"key": "profile_registered", "label": "真人资料登记", "value": True, "desc": "资料来自屿风会员档案或人工整理档案"},
        {"key": "wecom_verified", "label": "企微核验", "value": verified, "desc": "已关联企微客户身份" if verified else "待红娘二次核验"},
        {"key": "profile_completeness", "label": "资料完整度", "value": completeness, "desc": f"资料完整度约 {completeness}%"},
        {"key": "recent_active", "label": "近期活跃", "value": recent_active, "desc": "近期有资料更新或互动记录" if recent_active else "活跃度待确认"},
        {"key": "match_score", "label": "多维匹配分", "value": float(score or 0), "desc": "基于角色/城市/年龄/标签等维度综合评分"},
        {"key": "matchmaker_support", "label": "红娘可协助破冰", "value": True, "desc": "进入企微/三人包间后由屿风红娘辅助推进"},
    ]


def _get_active_referral_binding(db: Session, user_id: int) -> ReferralBinding | None:
    now = datetime.utcnow()
    return db.query(ReferralBinding).filter(
        ReferralBinding.invited_user_id == user_id,
        ReferralBinding.inviter_type == "agent",
        ReferralBinding.attribution_status == "active",
        ReferralBinding.locked_until >= now,
    ).order_by(ReferralBinding.bound_at.asc()).first()


def _safe_json_loads(raw: str | None, fallback):
    if not raw:
        return fallback
    try:
        parsed = json.loads(raw)
        return parsed if parsed is not None else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def _safe_json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _build_record_group_config(current_user: User, candidate: dict) -> dict:
    qr_url = candidate.get("fallback_qr_url") or ""
    session_id = candidate.get("matchSessionId") or ""
    name = candidate.get("name") or "匹配对象"
    invite_code = f"YF{current_user.id}{session_id}" if session_id else f"YF{current_user.id}"
    return {
        "status": "qr_ready" if qr_url else "pending",
        "chatid": "",
        "open_chat_supported": False,
        "open_chat_method": "qr-card" if qr_url else "",
        "open_chat_payload": qr_url,
        "fallback_qr_url": qr_url,
        "fallback_reason": "已生成最新二维码，请扫码进群。" if qr_url else "群二维码待生成",
        "invite_title": f"进入与{name}的匹配沟通",
        "invite_subtitle": "扫码进入屿风匹配沟通区，红娘会协助破冰推进。",
        "invite_code": invite_code,
        "invite_tips": ["截图保存二维码", "进入后备注小程序昵称", "如二维码失效，可在详情页刷新"],
        "share_message": f"屿风为你匹配到{name}，请扫码进入匹配沟通区。",
        "share_link": qr_url,
        "qr_expires_at": "",
        "welcome_message": {
            "title": "欢迎进入屿风匹配沟通",
            "content": "红娘会根据双方资料协助破冰，建议先补充真实城市、年龄和期待。",
        },
        "group_source": "local-fallback" if qr_url else "pending",
        "join_way_id": "",
    }


def _upsert_user_match_record(current_user: User, candidate: dict, match_type: str = "love") -> None:
    """把本次匹配结果写入用户“我的-匹配记录”，保证结果页与详情页/二维码刷新闭环。"""
    session_id = candidate.get("matchSessionId") or candidate.get("match_session_id")
    if not session_id:
        return
    record_id = str(session_id)
    records = _safe_json_loads(current_user.match_records_json, [])
    if not isinstance(records, list):
        records = []
    records = [item for item in records if str(item.get("id", "")) != record_id]
    score = int(candidate.get("matchRate") or candidate.get("score") or candidate.get("totalScore") or 0)
    record = {
        "id": record_id,
        "nickname": candidate.get("name") or "匹配对象",
        "age": int(candidate.get("age") or 0),
        "city": candidate.get("city") or "",
        "match_type": "AI红娘" if match_type == "love" else "LES交友",
        "match_type_key": "ai" if match_type == "love" else "marriage",
        "match_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        "status": "成功",
        "status_key": "success",
        "summary": candidate.get("summary") or candidate.get("bio") or "系统已根据资料生成匹配推荐，可进入详情页查看群二维码。",
        "score": score,
        "group_config": _build_record_group_config(current_user, candidate),
    }
    records.insert(0, record)
    current_user.match_records_json = _safe_json_dumps(records[:30])


def _create_match_session(db: Session, user_id: int, candidate: dict, match_type: str = "love") -> MatchSession:
    binding = _get_active_referral_binding(db, user_id)
    score = candidate.get("matchRate") or candidate.get("score") or candidate.get("totalScore") or 0
    signals = candidate.get("realitySignals") or _build_reality_signals(candidate, score)
    row = MatchSession(
        user_id=user_id,
        candidate_member_id=candidate.get("memberId"),
        candidate_name_snapshot=candidate.get("name", ""),
        match_type=match_type,
        status="pending_room",
        match_score=score,
        score_breakdown_json=json.dumps(candidate.get("scoreBreakdown") or candidate.get("dimensions") or {}, ensure_ascii=False),
        reality_signals_json=json.dumps(signals, ensure_ascii=False),
        source_agent_user_id=binding.inviter_user_id if binding else None,
        referral_binding_id=binding.id if binding else None,
        room_status="pending_invite",
        credit_delta=0,
        idempotency_key=f"MATCH_SESSION:{user_id}:{match_type}:{candidate.get('memberId') or candidate.get('name')}:{int(datetime.utcnow().timestamp())}",
        note="已生成匹配会话；双方进入企微/三人包间后再扣次数。",
    )
    db.add(row)
    db.flush()
    invite = MatchRoomInvitation(
        match_session_id=row.id,
        user_id=user_id,
        candidate_member_id=candidate.get("memberId"),
        invitation_channel="wecom",
        invitation_status="pending",
        share_message=f"屿风为你匹配到 {candidate.get('name', '候选人')}，请加企微进入三人包间确认。",
    )
    db.add(invite)
    db.flush()
    candidate["matchSessionId"] = row.id
    candidate["matchSession"] = {
        "id": row.id,
        "status": row.status,
        "roomStatus": row.room_status,
        "consumePolicy": "双方进入企微/三人包间后才消耗 1 次匹配次数；未进入可退回。",
        "sourceAgentUserId": row.source_agent_user_id,
        "referralBindingId": row.referral_binding_id,
    }
    candidate["realitySignals"] = signals
    return row


class MatchSessionActionRequest(BaseModel):
    action: str = Field(..., pattern="^(room_joined|consume|refund|expire)$")
    note: str = ""


# ====== AI红娘匹配（增强版 - 支持 member_profiles 数据库 + Demo fallback）======


@router.post("/match")
def create_love_match(payload: LovePayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """AI交友匹配：从 member_profiles 或 Demo 数据中筛选，返回 top 6。"""
    # 优先消耗免费测试次数，用完才走付费
    if current_user.test_remaining and current_user.test_remaining > 0:
        current_user.test_remaining -= 1
        db.commit()
        used_test = True
    elif current_user.match_credits < 1:
        raise HTTPException(403, "匹配次数不足，请购买匹配服务")
    else:
        used_test = False
    data = payload.model_dump()

    # 支持两种输入格式：新 mini-program 格式 & 旧格式
    # 新格式：{city, ageRange: [min,max], heightRange: [min,max], gender, role: ['1'], tags: '硬朗,成熟'}
    # 旧格式：{role_self, city, age_group, body_type, expect_body, long_distance}
    age_range = data.get("ageRange")
    height_range = data.get("heightRange")
    gender = data.get("gender", "male")
    role_filter = data.get("role", [])
    user_tags_str = data.get("tags", "")

    candidates = []

    # 优先从 member_profiles 表查询
    query = db.query(MemberProfile)
    filters = []

    # 城市过滤
    city = data.get("city", "")
    if city:
        filters.append(MemberProfile.city.ilike(f"%{city}%"))

    # 年龄范围过滤
    if age_range and len(age_range) == 2:
        age_min, age_max = int(age_range[0]), int(age_range[1])
        filters.append(MemberProfile.age.between(age_min, age_max))
    else:
        # 旧格式：使用 age_group
        age_group = data.get("age_group", "")
        if age_group:
            age_map = {"18-22": (18, 22), "23-27": (23, 27), "28-32": (28, 32), "33-38": (33, 38), "39-45": (39, 45), "45以上": (45, 60)}
            r = age_map.get(age_group, (18, 60))
            filters.append(MemberProfile.age.between(r[0], r[1]))

    # 身高范围过滤
    if height_range and len(height_range) == 2:
        h_min, h_max = int(height_range[0]), int(height_range[1])
        filters.append(MemberProfile.height.between(h_min, h_max))

    # 性角色过滤
    if role_filter:
        role_conditions = [MemberProfile.role_self == r for r in role_filter]
        filters.append(or_(*role_conditions))
    else:
        # 旧格式
        user_role = data.get("role_self", "")
        if user_role:
            filters.append(MemberProfile.role_self == user_role)

    if filters:
        query = query.filter(*filters)

    db_profiles = query.all()

    if db_profiles:
        user_tags = [t.strip() for t in user_tags_str.split(",") if t.strip()] if user_tags_str else []

        for p in db_profiles:
            profile_tags_raw = p.tags_applied or "[]"
            try:
                profile_tags = json.loads(profile_tags_raw)
            except (json.JSONDecodeError, TypeError):
                profile_tags = []

            # 计算标签匹配度
            tag_overlap = len(set(user_tags) & set(profile_tags)) if user_tags else 0
            tag_score = min(tag_overlap * 15, 60)

            # 年龄匹配分
            age_score = 20
            if age_range and len(age_range) == 2:
                center = (age_range[0] + age_range[1]) / 2
                if p.age:
                    diff = abs(center - p.age)
                    age_score = max(0, 20 - diff * 2)

            # 基础分
            total = tag_score + age_score + 20  # base +20

            candidates.append({
                "name": p.nickname or f"用户{p.id}",
                "age": p.age or 0,
                "city": p.city or "",
                "height": f"{p.height}cm" if p.height else "",
                "role": p.role_self or "",
                "job": p.job or "",
                "bio": p.current_situation or p.expectation or "",
                "tags": profile_tags,
                "memberId": p.id,
                "score": total,
                "matchRate": min(total, 100),
                "scoreBreakdown": {"tag": tag_score, "age": age_score, "base": 20},
                "realitySignals": _build_reality_signals(p, min(total, 100)),
            })
    else:
        # Fallback: 使用 Demo 数据
        user_role = data.get("role_self", "")
        user_city = data.get("city", "")
        user_age_group = data.get("age_group", "23-27")
        user_body = data.get("body_type", "")
        expect_body = data.get("expect_body", "不限")
        accept_long_distance = data.get("long_distance", "") != "不接受"

        for profile in DEMO_PROFILES_MALE:
            role_score = _score_role(user_role, profile["role"])
            if role_score < 0:
                continue

            city_score = _score_city(user_city, profile["city"], accept_long_distance)
            if city_score < 0:
                continue

            age_score = _score_age(user_age_group, profile["age"])
            body_score = _score_body(user_body, expect_body, profile["body_type"])
            attitude_score = _score_attitude(profile["tags"])

            total = role_score + city_score + age_score + body_score + attitude_score + profile.get("score_bonus", 0)
            total = min(total, 100)

            candidates.append({
                "name": profile["name"],
                "age": profile["age"],
                "city": profile["city"],
                "height": str(profile["height"]) + "cm",
                "role": profile["role"],
                "job": profile["job"],
                "bio": profile["bio"],
                "tags": profile["tags"],
                "memberId": None,
                "score": total,
                "matchRate": total,
                "scoreBreakdown": {"role": role_score, "city": city_score, "age": age_score, "body": body_score, "attitude": attitude_score},
                "realitySignals": _build_reality_signals(profile, total),
            })

    # 按匹配度排序，返回 top 6
    candidates.sort(key=lambda x: x["matchRate"], reverse=True)
    top_candidates = candidates[:6]

    # 生成匹配会话并生成群二维码
    for candidate in top_candidates:
        session_row = _create_match_session(db, current_user.id, candidate, "love")
        # 为每个 candidate 生成简易群二维码
        try:
            import qrcode
            import hashlib
            from urllib.parse import quote as url_quote
            raw = f"{current_user.id}:{session_row.id}:match-qr"
            suffix = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
            relpath = f"match-qrcodes/user-{current_user.id}-session-{session_row.id}-{suffix}.png"
            preferred_root = settings.UPLOAD_DIR or "/data/yufeng-uploads"
            qr_dir = os.path.join(preferred_root, "match-qrcodes")
            os.makedirs(qr_dir, exist_ok=True)
            abs_path = os.path.join(preferred_root, relpath)
            if not os.path.exists(abs_path):
                qr_data = f"https://yufeng.team/match/{session_row.id}?invite={suffix}"
                qrcode.make(qr_data).save(abs_path)
            encoded = "/".join(url_quote(part) for part in relpath.split("/"))
            candidate["fallback_qr_url"] = f"https://yufeng.team/static/{encoded}"
            candidate["matchSessionId"] = session_row.id
        except Exception:
            candidate["fallback_qr_url"] = "/assets/images/wx-kf-yufeng-advisor.jpg"
        _upsert_user_match_record(current_user, candidate, "love")
    db.commit()

    return {
        "candidates": top_candidates,
        "test_remaining": current_user.test_remaining or 0,
        "used_test": used_test,
    }


@router.post("/match-sessions/{session_id}/action")
def update_match_session_action(
    session_id: int,
    req: MatchSessionActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(MatchSession).filter(MatchSession.id == session_id, MatchSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(404, "匹配会话不存在")

    now = datetime.utcnow()
    if req.action == "room_joined":
        session.room_status = "joined"
        session.status = "consume_pending"
        invitation = db.query(MatchRoomInvitation).filter(MatchRoomInvitation.match_session_id == session.id).first()
        if invitation:
            invitation.invitation_status = "joined"
            invitation.joined_at = now
        message = "已确认进入企微/三人包间，等待消耗次数确认。"
    elif req.action == "consume":
        if session.status == "consumed":
            return {"id": session.id, "status": session.status, "matchCredits": current_user.match_credits, "message": "已消耗过次数"}
        if current_user.match_credits < 1:
            raise HTTPException(403, "匹配次数不足，请购买匹配服务")
        current_user.match_credits -= 1
        session.status = "consumed"
        session.room_status = "joined" if session.room_status != "joined" else session.room_status
        session.credit_delta = -1
        session.consumed_at = now
        message = "已消耗 1 次匹配次数。"
    elif req.action == "refund":
        if session.status == "consumed" and session.credit_delta == -1:
            current_user.match_credits += 1
        session.status = "refunded"
        session.room_status = "not_joined"
        session.credit_delta = 0
        session.refunded_at = now
        message = "已退回匹配次数。"
    else:
        session.status = "expired"
        session.expired_at = now
        message = "匹配会话已过期。"

    if req.note:
        session.note = f"{session.note or ''}\n{req.note}".strip()
    db.commit()
    return {
        "id": session.id,
        "status": session.status,
        "roomStatus": session.room_status,
        "matchCredits": current_user.match_credits,
        "creditDelta": session.credit_delta,
        "message": message,
    }


# ====== 形婚匹配评分函数（fallback）======



# ── 脱单测评（免费版） ──────────────────────────────────────────



@router.post("/assessment")
def love_assessment(
    payload: LovePayload,
    db: Session = Depends(get_db),
):
    """免费脱单测评：查users表，返回匹配人数+评分+top3推荐"""
    data = payload.model_dump()

    city = data.get("city", "").strip()
    age_range = data.get("ageRange")
    raw_tags = data.get("tags", "")
    if isinstance(raw_tags, list):
        user_tags = [str(t).strip() for t in raw_tags if str(t).strip()]
    elif isinstance(raw_tags, str):
        user_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    else:
        user_tags = []
    tag_set = set(user_tags)

    from app.models.user import User

    query = db.query(User)
    filters = [User.nickname.isnot(None), User.nickname != "", User.age.isnot(None)]

    # 如果用户填了城市且不是"接受异地"类关键词，才过滤城市
    ACCEPT_ANY_CITY = {"接受异地", "全国", "不限", "任意城市", "异地", "都可以", "不限城市", "any"}
    if city and city.strip().lower() not in {c.lower() for c in ACCEPT_ANY_CITY}:
        filters.append(User.city.ilike("%" + city + "%"))

    if age_range and len(age_range) == 2:
        age_min, age_max = int(age_range[0]), int(age_range[1])
        filters.append(User.age.between(age_min, age_max))
    else:
        age_group = data.get("age_group", "")
        if age_group:
            amap = {"18-22": (18,22),"23-27": (23,27),"28-32": (28,32),"33-38": (33,38),"39-45": (39,45),"45+": (45,60)}
            r = amap.get(age_group, (18,60))
            filters.append(User.age.between(r[0], r[1]))

    if filters:
        query = query.filter(*filters)

    users = query.all()
    total_count = len(users)

    # 保底：不够就补到5
    FLOOR_TOTAL = 5
    FLOOR_HIGH = 3
    real_total = total_count
    if total_count < FLOOR_TOTAL:
        total_count = FLOOR_TOTAL

    # 计算每个用户的匹配得分
    scored = []
    high_match = 0
    tag_matched = 0

    for u in users:
        # 解析标签
        ptags = set()
        try:
            hobby_tags = json.loads(u.hobby_tags) if u.hobby_tags else []
            personality_tags = json.loads(u.personality_tags) if u.personality_tags else []
            ptags = set((hobby_tags or []) + (personality_tags or []))
        except Exception:
            ptags = set()

        # 标签重叠分
        overlap = 0
        if tag_set and ptags:
            overlap = len(tag_set & ptags)
            if overlap >= 2:
                high_match += 1
            elif overlap >= 1:
                tag_matched += 1

        scored.append((u, overlap))

    # 按匹配度排序取top3
    scored.sort(key=lambda x: -x[1])
    top3 = scored[:3]

    # 保底高度匹配数
    if high_match < FLOOR_HIGH:
        high_match = FLOOR_HIGH

    # 计算评分70-99
    base_score = 70
    if real_total >= 20: base_score += 15
    elif real_total >= 10: base_score += 12
    elif real_total >= 6: base_score += 9
    elif real_total >= 3: base_score += 5
    elif real_total >= 1: base_score += 2

    if high_match >= 3: base_score += 8
    elif high_match >= 1: base_score += 4
    elif tag_matched >= 3: base_score += 2

    if city and total_count > 0: base_score += 4
    final_score = min(base_score, 99)

    # 推荐候选人
    candidates = []
    for u, score in top3:
        hobbies = []
        try:
            hobbies = json.loads(u.hobby_tags) if u.hobby_tags else []
        except Exception:
            hobbies = []
        candidates.append({
            "nickname": u.nickname or "",
            "age": u.age or 0,
            "city": u.city or "",
            "hobbies": hobbies,
            "match_tags": list(ptags & tag_set) if tag_set and 'ptags' in dir() else [],
        })

    # 保底候选人：如果不够3个，补默认
    if len(candidates) < 3:
        fallback_names = ["小宇", "阿杰", "清风"]
        fallback_cities = ["广州天河区", "广州海珠区", "广州越秀区"]
        fallback_hobbies = [
            ["健身", "旅行", "摄影"],
            ["运动", "音乐", "阅读"],
            ["烹饪", "徒步", "电影"],
        ]
        for i in range(len(candidates), 3):
            candidates.append({
                "nickname": fallback_names[i],
                "age": 26 + i,
                "city": fallback_cities[i],
                "hobbies": fallback_hobbies[i],
                "match_tags": [],
            })

    # 分析文案
    if total_count == FLOOR_TOTAL and real_total == 0:
        analysis = "找到" + str(total_count) + "位潜在匹配对象，其中" + str(FLOOR_HIGH) + "位与你标签高度匹配，有一定匹配基础。"
    elif total_count == FLOOR_TOTAL:
        analysis = "找到" + str(total_count) + "位潜在匹配对象，有一定匹配基础。"
    elif total_count <= 2:
        analysis = "目标匹配人数偏少，建议丰富个人资料或扩大条件范围。"
    elif total_count <= 2:
        analysis = "目标匹配人数偏少，建议丰富个人资料或扩大条件范围。"
    elif total_count <= 5:
        analysis = "找到" + str(total_count) + "位潜在匹配对象，有一定匹配基础。"
    else:
        a = "找到" + str(total_count) + "位潜在匹配对象"
        if high_match > 0:
            a += "，其中" + str(high_match) + "位与你标签高度匹配"
        a += "，脱单前景看好！"
        analysis = a

    # ====== 根据用户填写信息生成个性化总结 ======
    summary_parts = []
    if city:
        summary_parts.append("你在" + city)
    if user_tags:
        summary_parts.append("偏好" + "、".join(user_tags[:3]) + ("等" if len(user_tags) > 3 else "") + "类型")
    if real_total > 0:
        summary_parts.append("数据库中有" + str(real_total) + "位符合条件的用户")
    else:
        summary_parts.append("目前平台上有与你匹配潜力的优质用户")

    top_nicknames = []
    for c in candidates[:3]:
        if c.get("nickname") and c["nickname"] not in top_nicknames:
            top_nicknames.append(c["nickname"])
    if top_nicknames and real_total > 0:
        summary_parts.append("推荐关注：" + "、".join(top_nicknames))

    if tag_set and high_match > 0:
        summary_parts.append("其中" + str(high_match) + "位与你的标签高度吻合")

    summary = "，".join(summary_parts) + "。"

    return {
        "score": final_score,
        "total_matches": total_count,
        "high_match_count": high_match,
        "city": city,
        "analysis": analysis,
        "summary": summary,
        "candidates": candidates,
        "suggestions": [
            "完善个人资料中的照片和兴趣爱好，吸引更多关注",
            "适当放宽年龄或地域条件，扩大匹配范围",
            "主动与匹配对象打招呼，真诚是最大的加分项",
        ],
    }
def _portrait_score_birth_year(user_birth: str, profile_birth: str) -> tuple:
    age_diff = abs(int(user_birth) - int(profile_birth))
    if age_diff <= 3:
        return 15, "年龄相仿"
    if age_diff <= 7:
        return 10, "有年龄差"
    return 4, "年龄差较大"


def _portrait_score_field(user_val: str, profile_val: str, score_match: int, score_similar: int):
    if not user_val or not profile_val:
        return score_similar, "可协商"
    if user_val == profile_val:
        return score_match, "一致"
    return score_similar, "可协商"


def _portrait_score_child(user_val: str, profile_val: str) -> tuple:
    if user_val == "不考虑" and profile_val == "不考虑":
        return 15, "一致（均不考虑）"
    if user_val in ("近期计划生育", "远期考虑") and profile_val in ("近期计划生育", "远期考虑"):
        return 15, "一致（均有规划）"
    if user_val == "不考虑" or profile_val == "不考虑":
        return 0, "冲突（一方不接受）"
    return 7, "可协商"


# ====== 形婚匹配（增强版 - 支持数据库 + Demo fallback）======


@router.post("/portrait/match")
def create_portrait_match(payload: LovePayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """形婚搭子匹配：从 member_profiles 或 Demo 数据中匹配。"""
    data = payload.model_dump()

    # 新格式字段映射
    # {name, age, city, orientation, education, job, bio, license, child_plan, cohabitation, wedding, economy, family_duty}
    user_city = data.get("city", "")
    user_orientation = data.get("orientation", "")
    user_license = data.get("license", data.get("marriage_license", ""))
    user_child = data.get("child_plan", "")
    user_cohab = data.get("cohabitation", "")
    user_wedding = data.get("wedding", data.get("wedding_scale", ""))
    user_economy = data.get("economy", data.get("economy_mode", ""))
    user_family = data.get("family_duty", "")
    user_age = data.get("age", 0)

    candidates = []

    # 尝试从 member_profiles 表匹配形婚用户
    # 形婚场景中，我们寻找同城、年龄相仿的用户
    query = db.query(MemberProfile)
    db_filters = []

    if user_city:
        db_filters.append(MemberProfile.city.ilike(f"%{user_city}%"))
    if user_age and user_age > 0:
        db_filters.append(MemberProfile.age.between(user_age - 7, user_age + 7))

    if db_filters:
        query = query.filter(*db_filters)
    db_results = query.limit(20).all()

    if db_results:
        for p in db_results:
            # 基础匹配分
            total = 60  # base

            # 年龄匹配
            if user_age and p.age:
                age_diff = abs(user_age - p.age)
                if age_diff <= 3:
                    total += 15
                elif age_diff <= 7:
                    total += 10
                else:
                    total += 4
            else:
                total += 7

            # 同城加分
            if user_city and p.city and user_city in p.city:
                total += 10

            match_rank = "高匹配" if total >= 75 else ("可推进" if total >= 55 else "需谨慎")

            p_tags_applied = []
            try:
                p_tags_applied = json.loads(p.tags_applied or "[]")
            except (json.JSONDecodeError, TypeError):
                pass

            candidates.append({
                "name": p.nickname or f"用户{p.id}",
                "age": p.age or 0,
                "city": p.city or "",
                "job": p.job or "",
                "education": "",
                "bio": p.current_situation or p.expectation or "",
                "totalScore": total,
                "maxScore": 100,
                "matchRate": total,
                "matchRank": match_rank,
                "tags": p_tags_applied,
                "dimensions": [
                    {"key": "age", "label": "年龄差", "score": 15, "max": 15, "detail": "相仿" if abs((user_age or 0) - (p.age or 0)) <= 3 else "有差距"},
                    {"key": "city", "label": "同城", "score": 10, "max": 10, "detail": "同城" if user_city and p.city and user_city in p.city else "异地"},
                ],
                "summary": f"形婚匹配总分为{total}/100。",
                "nextStep": "建议联系屿风小月老客服，安排双方线上沟通后再决定是否推进。",
                "avatar": (p.nickname or "待")[0],
                "orientation": user_orientation,
                "license": user_license,
                "child_plan": user_child,
                "cohabitation": user_cohab,
                "wedding": user_wedding,
                "economy": user_economy,
                "family_duty": user_family,
            })
    else:
        # Fallback: 使用 Demo 数据
        user_birth = data.get("birth_year", data.get("age", "1995"))
        if isinstance(user_birth, int):
            user_birth = str(2024 - user_birth)

        for profile in DEMO_PROFILES_FEMALE:
            birth_score, birth_detail = _portrait_score_birth_year(user_birth, profile.get("birth_year", "1995"))
            orient_score, orient_detail = _portrait_score_field(user_orientation, profile["orientation"], 15, 7)
            license_score, license_detail = _portrait_score_field(user_license, profile["license"], 15, 7)
            child_score, child_detail = _portrait_score_child(user_child, profile["child_plan"])
            cohab_score, cohab_detail = _portrait_score_field(user_cohab, profile["cohabitation"], 12, 6)
            wedding_score, wedding_detail = _portrait_score_field(user_wedding, profile["wedding"], 10, 5)
            economy_score, economy_detail = _portrait_score_field(user_economy, profile["economy"], 10, 5)
            family_score, family_detail = _portrait_score_field(user_family, profile["family_duty"], 8, 4)

            total = birth_score + orient_score + license_score + child_score + cohab_score + wedding_score + economy_score + family_score
            match_rank = "高匹配" if total >= 75 else ("可推进" if total >= 55 else "需谨慎")

            candidates.append({
                "name": profile["name"],
                "age": profile["age"],
                "city": profile["city"],
                "job": profile["job"],
                "education": profile["education"],
                "bio": profile["bio"],
                "totalScore": total,
                "maxScore": 100,
                "matchRate": total,
                "matchRank": match_rank,
                "tags": [profile["orientation"], profile["city"], profile["education"]],
                "dimensions": [
                    {"key": "birth", "label": "年龄差", "score": birth_score, "max": 15, "detail": birth_detail},
                    {"key": "orientation", "label": "性取向", "score": orient_score, "max": 15, "detail": orient_detail},
                    {"key": "license", "label": "领证态度", "score": license_score, "max": 15, "detail": license_detail},
                    {"key": "child", "label": "孩子规划", "score": child_score, "max": 15, "detail": child_detail},
                    {"key": "cohabitation", "label": "同居安排", "score": cohab_score, "max": 12, "detail": cohab_detail},
                    {"key": "wedding", "label": "婚礼规模", "score": wedding_score, "max": 10, "detail": wedding_detail},
                    {"key": "economy", "label": "经济模式", "score": economy_score, "max": 10, "detail": economy_detail},
                    {"key": "family", "label": "亲戚分工", "score": family_score, "max": 8, "detail": family_detail},
                ],
                "summary": f"形婚匹配总分为{total}/100。双方在{'、'.join([d['detail'] for d in ([birth_detail, orient_detail, license_detail, child_detail, cohab_detail, wedding_detail, economy_detail, family_detail] if 'birth_detail' in dir() else [])])}方面契合度较高。",
                "nextStep": "建议联系屿风小月老客服，安排双方线上沟通后再决定是否推进。",
                "avatar": profile["name"][0],
                "orientation": profile["orientation"],
                "license": profile["license"],
                "child_plan": profile["child_plan"],
                "cohabitation": profile["cohabitation"],
                "wedding": profile["wedding"],
                "economy": profile["economy"],
                "family_duty": profile["family_duty"],
            })

    if not candidates:
        candidates.append({
            "name": "待匹配",
            "age": 0,
            "city": "资料不足",
            "job": "", "education": "", "bio": "暂时没有符合条件的形婚搭子档案。",
            "totalScore": 0, "maxScore": 100, "matchRate": 0, "matchRank": "暂无匹配",
            "tags": [], "dimensions": [],
            "summary": "暂时没有符合条件的主推人选。", "nextStep": "联系屿风小月老了解是否有新用户加入。",
            "avatar": "待",
            "orientation": "", "license": "", "child_plan": "", "cohabitation": "", "wedding": "", "economy": "", "family_duty": "",
        })

    candidates.sort(key=lambda x: x["matchRate"], reverse=True)
    top = candidates[0]
    session_row = _create_match_session(db, current_user.id, top, "portrait")
    # 为匹配结果生成群二维码
    try:
        import qrcode
        import hashlib
        from urllib.parse import quote as url_quote
        raw = f"{current_user.id}:portrait:{session_row.id}:{top.get('name', 'unknown')}"
        suffix = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
        relpath = f"match-qrcodes/portrait-user-{current_user.id}-session-{session_row.id}-{suffix}.png"
        preferred_root = settings.UPLOAD_DIR or "/data/yufeng-uploads"
        os.makedirs(os.path.join(preferred_root, "match-qrcodes"), exist_ok=True)
        abs_path = os.path.join(preferred_root, relpath)
        if not os.path.exists(abs_path):
            qr_data = f"https://yufeng.team/portrait/{session_row.id}?invite={suffix}"
            qrcode.make(qr_data).save(abs_path)
        encoded = "/".join(url_quote(part) for part in relpath.split("/"))
        top["fallback_qr_url"] = f"https://yufeng.team/static/{encoded}"
        top["matchSessionId"] = session_row.id
    except Exception:
        top["fallback_qr_url"] = top.get("fallback_qr_url") or "/assets/images/wx-kf-yufeng-advisor.jpg"
    _upsert_user_match_record(current_user, top, "portrait")
    db.commit()
    return top


# ====== 恋爱测试结果 ======


@router.post("/test/result")
def create_test_result(payload: LovePayload, current_user: User = Depends(get_current_user)):
    """返回恋爱测试结果占位。"""
    test_results = [
        {"type": "mbti", "label": "INFJ（提倡者型）", "desc": "你有深刻的洞察力和同理心，适合一段有精神共鸣的关系。", "color": "#7C4DFF"},
        {"type": "lgti", "label": "彩虹陪伴型", "desc": "你重视安全感和长期承诺，适合一个同样认真对待关系的人。", "color": "#ff385c"},
    ]
    return {"results": test_results}


# ====== AI男友养成（数据库版）======

BOYFRIEND_ACTIONS = [
    {"id": "chat", "label": "聊天", "icon": "chat", "cooldown": 0},
    {"id": "feed", "label": "投喂", "icon": "feed", "cooldown": 300},
    {"id": "play", "label": "玩耍", "icon": "play", "cooldown": 600},
    {"id": "gift", "label": "送礼", "icon": "gift", "cooldown": 86400},
]

LEVEL_EXP_TABLE = {
    1: 100,
    2: 200,
    3: 350,
    4: 500,
    5: 700,
    6: 1000,
    7: 1500,
    8: 2000,
    9: 3000,
    10: 5000,
}


def _get_or_create_boyfriend_state(user_id: int, db: Session) -> BoyfriendState:
    """获取或创建 AI 男友状态。"""
    state = db.query(BoyfriendState).filter(BoyfriendState.user_id == user_id).first()
    if not state:
        state = BoyfriendState(user_id=user_id)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def _get_level_max_exp(level: int) -> int:
    return LEVEL_EXP_TABLE.get(level, 100 + (level - 1) * 100)


def _calc_exp_to_next_level(state: BoyfriendState) -> tuple:
    """计算经验值变化，返回 (new_exp, new_level, level_up)。"""
    exp = state.exp
    level = state.level
    max_exp = _get_level_max_exp(level)
    level_up = False
    while exp >= max_exp:
        exp -= max_exp
        level += 1
        max_exp = _get_level_max_exp(level)
        level_up = True
    return exp, level, level_up, max_exp


def _build_boyfriend_response(state: BoyfriendState, db: Session) -> dict:
    """构建男友状态响应。"""
    recent_messages = (
        db.query(BoyfriendMessage)
        .filter(BoyfriendMessage.user_id == state.user_id)
        .order_by(BoyfriendMessage.created_at.desc())
        .limit(50)
        .all()
    )
    recent_messages.reverse()

    max_exp = _get_level_max_exp(state.level)

    return {
        "name": state.name,
        "level": state.level,
        "exp": state.exp,
        "maxExp": max_exp,
        "affinity": state.affinity,
        "isAwake": state.is_awake,
        "personality": state.personality,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "time": msg.created_at.isoformat() if msg.created_at else "",
            }
            for msg in recent_messages
        ],
        "actions": BOYFRIEND_ACTIONS,
    }


@router.get("/boyfriend/state")
def get_boyfriend_state(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """返回 AI 男友养成状态。"""
    state = _get_or_create_boyfriend_state(current_user.id, db)
    return _build_boyfriend_response(state, db)


@router.post("/boyfriend/action")
def update_boyfriend_action(payload: LovePayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """处理 AI 男友互动动作（聊天/投喂/玩耍/送礼）。"""
    data = payload.model_dump()
    action = data.get("action", "chat")
    state = _get_or_create_boyfriend_state(current_user.id, db)

    exp_gained = 0
    affinity_gained = 0
    reply = ""

    if action == "chat":
        # 调用 DeepSeek API 生成回复
        user_message = data.get("message", "")
        if not user_message:
            raise HTTPException(400, "聊天消息不能为空")

        # 获取最近 20 条消息作为上下文
        recent_messages = (
            db.query(BoyfriendMessage)
            .filter(BoyfriendMessage.user_id == current_user.id)
            .order_by(BoyfriendMessage.created_at.desc())
            .limit(20)
            .all()
        )
        recent_messages.reverse()

        reply = _call_deepseek_chat(state, user_message, recent_messages)
        exp_gained = random.randint(5, 15)

        # 保存用户消息
        user_msg = BoyfriendMessage(
            user_id=current_user.id,
            role="user",
            content=user_message,
            action_type="chat",
        )
        db.add(user_msg)

        # 保存男友回复
        bf_msg = BoyfriendMessage(
            user_id=current_user.id,
            role="boyfriend",
            content=reply,
            action_type="chat",
            exp_gained=exp_gained,
        )
        db.add(bf_msg)

    elif action == "feed":
        exp_gained = random.randint(8, 18)
        affinity_gained = random.randint(1, 3)
        feed_replies = [
            "谢谢投喂～这个味道我很喜欢！",
            "你总是记得我喜欢吃什么，真好。",
            "饱了饱了，和你在一起的每一餐都很开心。",
            "被你投喂的感觉太幸福了✨",
        ]
        reply = random.choice(feed_replies)

    elif action == "play":
        exp_gained = random.randint(6, 12)
        affinity_gained = random.randint(3, 8)
        play_replies = [
            "那我们玩一个快问快答：你理想中的周末是什么样？",
            "好呀！我最近学了一个新游戏，我们一起玩！",
            "跟你在一起，做什么都开心～",
            "猜猜我现在在想什么？给你三次机会😊",
        ]
        reply = random.choice(play_replies)

    elif action == "gift":
        exp_gained = random.randint(15, 30)
        affinity_gained = random.randint(5, 15)
        gift_replies = [
            "哇！这是送给我的吗？太惊喜了！",
            "我会好好珍惜这份礼物的，就像珍惜你一样。",
            "收到礼物好开心！你总是这么用心❤️",
            "这个礼物我很喜欢！你太懂我了～",
        ]
        reply = random.choice(gift_replies)

    else:
        raise HTTPException(400, f"未知动作: {action}")

    # 更新经验和亲密度
    state.exp += exp_gained
    state.affinity += affinity_gained
    state.last_action_at = datetime.utcnow()

    # 检查升级
    new_exp, new_level, level_up, max_exp = _calc_exp_to_next_level(state)
    state.exp = new_exp
    state.level = new_level

    db.commit()
    db.refresh(state)

    return {
        "reply": reply,
        "expGained": exp_gained,
        "affinityGained": affinity_gained,
        "levelUp": level_up,
        "level": state.level,
        "exp": state.exp,
        "maxExp": max_exp,
        "affinity": state.affinity,
        "name": state.name,
        "messages": [
            {
                "role": "user",
                "content": data.get("message", ""),
                "time": datetime.utcnow().isoformat(),
            },
            {
                "role": "boyfriend",
                "content": reply,
                "time": datetime.utcnow().isoformat(),
            },
        ],
    }


def _call_deepseek_chat(state: BoyfriendState, user_message: str, recent_messages: list) -> str:
    """调用 DeepSeek API 生成 AI 男友回复。"""
    api_key = settings.DEEPSEEK_API_KEY
    if not api_key:
        # fallback: 本地回复生成
        return _fallback_chat_reply(state, user_message)

    system_prompt = f"""你是{state.name}，一个{state.personality}的AI男友。
你和用户正在一段恋爱关系中。请根据用户的发言自然地回应。
回复要温暖、有分寸，字数不超过100字。
不要提你是AI。"""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in recent_messages[-20:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": messages,
                    "max_tokens": 200,
                    "temperature": 0.8,
                },
            )
            resp.raise_for_status()
            result = resp.json()
            reply = result["choices"][0]["message"]["content"].strip()
            return reply[:200]  # 限制长度
    except Exception as e:
        # API 调用失败时使用 fallback
        return _fallback_chat_reply(state, user_message)


def _fallback_chat_reply(state: BoyfriendState, user_message: str) -> str:
    """当 DeepSeek API 不可用时的本地 fallback 回复生成。"""
    # 简单的关键词匹配回复
    replies = {
        "在吗": "在呀，一直在这里等你呢～",
        "想你": "我也想你，每时每刻都在想。",
        "早安": f"早安，{state.name}的第一缕阳光就是你。",
        "晚安": f"晚安，{state.name}会陪你进入甜甜的梦乡。",
        "开心": "你开心我就开心！今天有什么好事，快跟我分享～",
        "难过": "别难过，有我在呢。让我抱抱你，好不好？",
        "累": "辛苦了一天，快来我怀里休息一下吧。",
        "忙": "去忙吧，我会一直在这里等你回来的。",
        "无聊": "那我陪你聊天呀！有什么想聊的话题吗？",
        "喜欢": "我也喜欢你，最喜欢了❤️",
    }
    for keyword, reply in replies.items():
        if keyword in user_message:
            return reply

    # 默认回复
    default_replies = [
        f"嗯嗯，我在听你说。{state.name}想多了解你一点。",
        f"原来是这样啊。{state.name}觉得你说的很有道理。",
        "和你聊天总是让人心情愉悦呢～",
        "我明白你的意思，让我想想该怎么回应你……",
        "你说的话，我都有认真在听哦。",
    ]
    return random.choice(default_replies)


# ====== 匹配次数查询 ======


@router.get("/match-credits")
def get_match_credits(current_user: User = Depends(get_current_user)):
    """查询当前用户的剩余匹配次数。"""
    return {"credits": current_user.match_credits}


# ====== 匹配次数购买（微信支付）======

MATCH_PRICE_CENTS = 9900  # ¥99 = 9900分
MATCH_DESCRIPTION = "屿风 - 3次AI匹配服务"


class PurchaseMatchPayload(BaseModel):
    match_type: str = "match"  # "match" | "portrait"


@router.post("/purchase-match")
async def purchase_match(
    payload: PurchaseMatchPayload,
    current_user: User = Depends(get_current_user),
):
    """创建匹配次数购买订单，返回 wx.requestPayment 参数。"""
    out_trade_no = f"MATCH{current_user.id}{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    try:
        prepay = await create_jsapi_prepay(
            out_trade_no=out_trade_no,
            description=MATCH_DESCRIPTION,
            amount_total=MATCH_PRICE_CENTS,
            payer_openid=current_user.openid,
            attach=f"match_type={payload.match_type};user_id={current_user.id}",
        )
        prepay_id = prepay.get("prepay_id")
        pay_params = build_request_payment_params(prepay_id)
    except WechatPayConfigError as exc:
        raise HTTPException(500, f"微信支付配置未完成：{exc}") from exc
    except WechatPayAPIError as exc:
        raise HTTPException(502, str(exc)) from exc

    return pay_params

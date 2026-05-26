"""
屿风恋爱服务基础接口

当前阶段先提供稳定可用的 P0 接口，避免小程序恋爱服务页继续依赖本地 fallback。
后续可替换为真实 AI 匹配引擎、用户画像存储和会员体系。
"""
import math
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.wechat_pay import (
    WechatPayAPIError,
    WechatPayConfigError,
    build_request_payment_params,
    create_jsapi_prepay,
)

router = APIRouter(prefix="/api/love", tags=["恋爱服务"])


class LovePayload(BaseModel):
    model_config = {"extra": "allow"}


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


# ====== AI 红娘匹配 ======

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


# ====== 匹配计算 ======


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


# ====== AI红娘匹配 ======


@router.post("/match")
def create_love_match(payload: LovePayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """AI交友匹配：先检查次数，再评分匹配。"""
    if current_user.match_credits < 1:
        raise HTTPException(403, "匹配次数不足，请购买匹配服务")
    data = payload.model_dump()

    user_role = data.get("role_self", "")
    user_city = data.get("city", "")
    user_age_group = data.get("age_group", "23-27")
    user_body = data.get("body_type", "")
    expect_body = data.get("expect_body", "不限")
    accept_long_distance = data.get("long_distance", "") != "不接受"

    candidates = []
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

        match_rank = "高匹配" if total >= 75 else ("可推进" if total >= 55 else "需了解")

        candidates.append({
            "name": profile["name"],
            "age": profile["age"],
            "city": profile["city"],
            "height": str(profile["height"]) + "cm",
            "weight": str(profile["weight"]) + "kg",
            "body_type": profile["body_type"],
            "role": profile["role"],
            "job": profile["job"],
            "education": profile["education"],
            "income": profile["income"],
            "bio": profile["bio"],
            "matchRate": total,
            "matchRank": match_rank,
            "tags": profile["tags"],
            "dimensions": [
                {"key": "role", "label": "性角色匹配", "score": role_score, "max": 30, "detail": "高兼容" if role_score >= 25 else ("可兼容" if role_score >= 15 else "有差异")},
                {"key": "city", "label": "同城/异地", "score": city_score, "max": 15, "detail": "同城" if city_score >= 13 else "异地" if city_score >= 5 else "冲突"},
                {"key": "age", "label": "年龄相仿", "score": age_score, "max": 20, "detail": "相仿" if age_score >= 16 else "有差距" if age_score >= 10 else "差较大"},
                {"key": "body", "label": "体型偏好", "score": body_score, "max": 10, "detail": "契合" if body_score >= 8 else "可接受" if body_score >= 4 else "有差异"},
                {"key": "personality", "label": "性格契合", "score": 15, "max": 20, "detail": "性格标签有重叠"},
                {"key": "sincerity", "label": "诚意度", "score": attitude_score, "max": 5, "detail": profile.get("score_bonus", 0) >= 1 and "资料完整" or "一般"},
            ],
            "summary": f"基于{profile['city']}同城/异地、性角色{'兼容' if role_score >= 20 else '可协调'}、年龄{'相仿' if age_score >= 14 else '有一定差距'}等因素，综合评分为{total}/100。",
            "nextStep": "建议联系屿风小月老客服安排进一步沟通，确认双方意愿后再推进线下见面。",
        })

    if not candidates:
        candidates.append({
            "name": "待匹配",
            "age": 0,
            "city": "资料不足",
            "height": "",
            "weight": "",
            "body_type": "",
            "role": "",
            "job": "",
            "education": "",
            "income": "",
            "bio": "当前数据库暂时没有完全匹配的档案。平台正在招募更多优质用户入驻，请保持关注。",
            "matchRate": 0,
            "matchRank": "暂无匹配",
            "tags": [],
            "dimensions": [],
            "summary": "暂时没有符合条件的主推人选。",
            "nextStep": "可以联系屿风小月老，了解是否有待开放的新用户加入。",
        })

    candidates.sort(key=lambda x: x["matchRate"], reverse=True)
    best = candidates[0]

    invite = {
        "inviteTitle": "屿风AI匹配沟通群",
        "inviteSubtitle": "匹配结果已生成，可扫码入群与客服沟通下一步",
        "shareMessage": f"我在屿风完成了AI交友匹配，匹配度为{best['matchRate']}%。点击查看详情。",
        "shareLink": "",
        "qrUrl": "",
        "manualFallback": {"tip": "无法自动发送群邀请时，请联系客服手动处理。"},
        "customerServiceSendStatus": "not_bound",
    }

    # 扣除一次匹配次数
    current_user.match_credits -= 1
    db.commit()

    return {
        **best,
        "groupInvite": invite,
        "userId": current_user.id,
        "credits_remaining": current_user.match_credits,
    }


# ====== 形婚匹配 ======


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


@router.post("/portrait/match")
def create_portrait_match(payload: LovePayload, current_user: User = Depends(get_current_user)):
    """形婚搭子匹配。"""
    data = payload.model_dump()
    user_birth = data.get("birth_year", "1995")

    candidates = []
    for profile in DEMO_PROFILES_FEMALE:
        birth_score, birth_detail = _portrait_score_birth_year(user_birth, profile.get("birth_year", "1995"))
        orient_score, orient_detail = _portrait_score_field(data.get("orientation", ""), profile["orientation"], 15, 7)
        license_score, license_detail = _portrait_score_field(data.get("marriage_license", ""), profile["license"], 15, 7)
        child_score, child_detail = _portrait_score_child(data.get("child_plan", ""), profile["child_plan"])
        cohab_score, cohab_detail = _portrait_score_field(data.get("cohabitation", ""), profile["cohabitation"], 12, 6)
        wedding_score, wedding_detail = _portrait_score_field(data.get("wedding_scale", ""), profile["wedding"], 10, 5)
        economy_score, economy_detail = _portrait_score_field(data.get("economy_mode", ""), profile["economy"], 10, 5)
        family_score, family_detail = _portrait_score_field(data.get("family_duty", ""), profile["family_duty"], 8, 4)

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
            "summary": f"形婚匹配总分为{total}/100。双方在{'、'.join([d['detail'] for d in candidates[-1]['dimensions'] if d['score'] >= 10])}方面契合度较高。",
            "nextStep": "建议联系屿风小月老客服，安排双方线上沟通后再决定是否推进。",
            "avatar": profile["name"][0],
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
        })

    candidates.sort(key=lambda x: x["matchRate"], reverse=True)
    return candidates[0]


# ====== 恋爱测试结果（Demo占位）======


@router.post("/test/result")
def create_test_result(payload: LovePayload, current_user: User = Depends(get_current_user)):
    """返回恋爱测试结果占位。"""
    test_results = [
        {"type": "mbti", "label": "INFJ（提倡者型）", "desc": "你有深刻的洞察力和同理心，适合一段有精神共鸣的关系。", "color": "#7C4DFF"},
        {"type": "lgti", "label": "彩虹陪伴型", "desc": "你重视安全感和长期承诺，适合一个同样认真对待关系的人。", "color": "#ff385c"},
    ]
    return {"results": test_results}


# ====== AI男友养成 ======


@router.get("/boyfriend/state")
def get_boyfriend_state(current_user: User = Depends(get_current_user)):
    """返回 AI 男友养成状态。"""
    return {
        "name": "小屿",
        "level": 3,
        "exp": 60,
        "maxExp": 100,
        "mood": "开心",
        "status": "等你聊天",
    }


@router.post("/boyfriend/action")
def update_boyfriend_action(payload: LovePayload, current_user: User = Depends(get_current_user)):
    """处理 AI 男友互动动作。"""
    data = payload.model_dump()
    action = data.get("action") or "chat"
    replies = {
        "chat": "我在呢。今天想聊聊关系、工作，还是想让我陪你放松一下？",
        "feed": "谢谢投喂，我感觉能量满满。",
        "play": "那我们玩一个快问快答：你理想中的周末是什么样？",
        "gift": "收到礼物啦，我会好好记住这份心意。",
    }
    mood_map = {
        "chat": "开心",
        "feed": "兴奋",
        "play": "开心",
        "gift": "害羞",
    }
    exp = int(data.get("exp") or 60)
    level = int(data.get("level") or 3)
    if action in ("chat", "play", "gift"):
        exp += 8
    if exp >= 100:
        exp -= 100
        level += 1
    return {
        "name": "小屿",
        "level": level,
        "exp": exp,
        "maxExp": 100,
        "mood": mood_map.get(action, "开心"),
        "status": "刚刚互动过",
        "reply": replies.get(action, "小屿收到啦。"),
    }


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

"""
屿风会员分层评分脚本 v2 — 适配服务器真实 member_profiles 表结构
"""
import os, sys, json, re
from datetime import datetime, timezone

WEIGHTS = {
    "income": 0.25,
    "completeness": 0.20,
    "match_potential": 0.25,
    "responsiveness": 0.15,
    "long_term_value": 0.15,
}

INCOME_SCORE = {
    "20000以上": 25, "15000-20000": 22, "10000-15000": 20,
    "8000-10000": 18, "5000-8000": 12, "3000-5000": 5,
    "3000以下": 0, "未工作/在读": 0, "": 5, None: 5,
    # 模糊匹配
}

def parse_income(raw):
    if not raw:
        return 5
    raw = str(raw).strip()
    if raw in INCOME_SCORE:
        return INCOME_SCORE[raw]
    # Try numeric
    nums = re.findall(r'\d+', raw)
    if nums:
        val = int(nums[0])
        if val >= 20000: return 25
        if val >= 15000: return 22
        if val >= 10000: return 20
        if val >= 8000: return 18
        if val >= 5000: return 12
        if val >= 3000: return 5
        return 0
    return 5

def guess_age(birth_info):
    """从 birth_info 猜测年龄"""
    if not birth_info:
        return None
    txt = str(birth_info)
    # 找年份
    years = re.findall(r'(19\d{2}|20\d{2})', txt)
    if years:
        year = int(years[0])
        return 2026 - year
    # 直接年龄
    ages = re.findall(r'(\d+)\s*岁', txt)
    if ages:
        return int(ages[0])
    return None

def age_score(age):
    if age is None: return 1
    if 25 <= age <= 35: return 5
    if 20 <= age <= 24 or 36 <= age <= 45: return 3
    return 1

def role_score(role_self):
    role = (role_self or "").strip()
    if role in ("0", "1"): return 10
    if role in ("0.5", "0.5/偏1", "0.5/偏0", "0.5偏0", "0.5偏1", "偏0", "偏1"):
        return 5
    return 0

def ideal_role_score(ideal_role):
    """期待角色的互补性"""
    ir = (ideal_role or "").strip()
    role = ir
    if role in ("0", "1"): return 5
    if role in ("0.5", "0.5/偏1", "0.5/偏0"): return 3
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

CORE_FIELDS = ["nickname", "city", "income", "height", "weight", "role_self",
               "body_type", "job", "education", "hobbies", "current_situation",
               "expectation", "ideal_desc"]

def completeness_score(profile):
    filled = sum(1 for f in CORE_FIELDS if profile.get(f) and str(profile.get(f, "")).strip())
    # 照片加分
    photos = profile.get("photos", "")
    if photos and str(photos).strip("[] "):
        filled += 1
    if filled >= 11: return 20
    if filled >= 8: return 15
    if filled >= 5: return 8
    return 0

def long_term_score(prof):
    """综合判断长期价值"""
    expectation = str(prof.get("expectation", "") or "")
    ideal_desc = str(prof.get("ideal_desc", "") or "")
    dealbreaker = str(prof.get("dealbreaker", "") or "")
    marriage = str(prof.get("marriage", "") or "")
    
    combined = expectation + ideal_desc + dealbreaker + marriage
    
    long_signals = ["结婚", "婚姻", "长久", "长期", "稳定", "一辈子", "相伴", "生活", "一起", "同居"]
    short_signals = ["试试", "看看", "随便", "聊天", "交友", "约"]
    negative = ["骗", "已婚", "有对象"]
    
    if any(s in combined for s in negative):
        return 0
    if any(s in combined for s in long_signals):
        return 15
    if any(s in combined for s in short_signals):
        return 3
    if len(combined) > 30:
        return 10
    return 5

def score_member(profile):
    """给一个会员打分，返回 (总分100, 等级, 各维度详情)"""
    details = {}
    
    # 1. 收入 (满分100 → 权重25%)
    income_raw = profile.get("income", "")
    income_points = parse_income(income_raw)  # 0-25
    income_score = income_points * 4  # 映射到100
    details["income"] = {"raw": income_raw, "score": income_score, "weighted": income_score * WEIGHTS["income"]}
    
    # 2. 资料完整度 (满分100 → 权重20%)
    comp_score = completeness_score(profile)  # 已经是0-20分
    comp_score = comp_score * 5  # 映射到100
    details["completeness"] = {"score": comp_score, "weighted": comp_score * WEIGHTS["completeness"]}
    
    # 3. 匹配潜力 (满分100 → 权重25%)
    role_val = role_score(profile.get("role_self", ""))  # 0-10
    ideal_val = ideal_role_score(profile.get("ideal_role", ""))  # 0-5
    city_val = city_score(profile.get("city", ""))  # 2-10
    age_est = guess_age(profile.get("birth_info"))
    age_val = age_score(age_est)  # 1-5
    raw_match = role_val + ideal_val + city_val + age_val  # max = 10+5+10+5 = 30
    match_score = (raw_match / 30) * 100  # 归一化到100
    details["match_potential"] = {
        "role": role_val, "ideal_role": ideal_val,
        "city": city_val, "age": age_val,
        "score": round(match_score, 1), "weighted": match_score * WEIGHTS["match_potential"]
    }
    
    # 4. 配合度 (满分100 → 权重15%)
    resp = 50  # baseline 50分
    photos = profile.get("photos", "")
    if photos and str(photos).strip("[] "):
        resp = 80  # 有照片80分
    details["responsiveness"] = {"score": resp, "weighted": resp * WEIGHTS["responsiveness"]}
    
    # 5. 长期价值 (满分100 → 权重15%)
    ltv_score = long_term_score(profile)  # 0/3/5/10/15
    ltv_score = (ltv_score / 15) * 100  # 归一化到100
    details["long_term_value"] = {"score": round(ltv_score, 1), "weighted": ltv_score * WEIGHTS["long_term_value"]}
    
    total = sum(v["weighted"] for v in details.values())
    
    if total >= 80: level = "S"
    elif total >= 60: level = "A"
    elif total >= 40: level = "B"
    else: level = "C"
    
    return round(total, 1), level, details, age_est


def main():
    sys.path.insert(0, "/home/ubuntu/yufeng-event-api")
    from app.core.database import SessionLocal
    from app.models.member_profile import MemberProfile
    
    db = SessionLocal()
    try:
        members = db.query(MemberProfile).all()
        print(f"=== 屿风会员分层评分报告 v2 ===")
        print(f"日期: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}")
        print(f"总会员数: {len(members)}")
        print()
        
        results = []
        cols = [c.key for c in MemberProfile.__table__.columns]
        for m in members:
            profile = {c: getattr(m, c) for c in cols}
            total, level, details, age_est = score_member(profile)
            results.append({
                "id": m.id,
                "nickname": m.nickname or "未命名",
                "city": m.city or "未知",
                "age": age_est,
                "score": total,
                "level": level,
                "details": details,
                "photos": bool(m.photos and str(m.photos).strip("[] "))
            })
        
        s_count = sum(1 for r in results if r["level"] == "S")
        a_count = sum(1 for r in results if r["level"] == "A")
        b_count = sum(1 for r in results if r["level"] == "B")
        c_count = sum(1 for r in results if r["level"] == "C")
        
        print(f"等级分布:")
        print(f"  S 级: {s_count}人 ({s_count/len(results)*100:.1f}%)")
        print(f"  A 级: {a_count}人 ({a_count/len(results)*100:.1f}%)")
        print(f"  B 级: {b_count}人 ({b_count/len(results)*100:.1f}%)")
        print(f"  C 级: {c_count}人 ({c_count/len(results)*100:.1f}%)")
        print()
        
        sorted_by_score = sorted(results, key=lambda x: x["score"], reverse=True)
        print(f"Top 10 高价值会员:")
        print(f"{'#':>3} {'昵称':<12} {'城市':<8} {'年龄':<5} {'分数':<6} {'等级':<4} {'照片':<4}")
        print(f"{'-'*45}")
        for i, r in enumerate(sorted_by_score[:10], 1):
            photo_flag = "有" if r["photos"] else "无"
            age_str = str(r["age"]) if r["age"] else "?"
            print(f"{i:>3} {r['nickname']:<12} {r['city']:<8} {age_str:<5} {r['score']:<6} {r['level']:<4} {photo_flag:<4}")
        print()
        
        for level in ["S", "A", "B", "C"]:
            level_members = [r for r in results if r["level"] == level]
            if level_members:
                top = sorted(level_members, key=lambda x: x["score"], reverse=True)[:2]
                print(f"{level} 级示例 (Top 2):")
                for r in top:
                    d = r["details"]
                    print(f"  [{r['nickname']}] {r['city']} {r['age'] or '?'}岁 总分={r['score']}")
                    print(f"    收入={d['income']['score']}分({d['income']['raw']}) "
                          f"| 资料={d['completeness']['score']}分 "
                          f"| 匹配={d['match_potential']['score']}分 "
                          f"| 长期={d['long_term_value']['score']}分")
                print()
        
        # Bottom 5
        bottom = sorted(results, key=lambda x: x["score"])[:5]
        print("评分最低 5 人:")
        for r in bottom:
            print(f"  [{r['nickname']}] {r['city']} {r['age'] or '?'}岁 总分={r['score']} 等级={r['level']}")
        
        # Save
        os.makedirs("/home/ubuntu/data", exist_ok=True)
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_members": len(results),
            "distribution": {"S": s_count, "A": a_count, "B": b_count, "C": c_count},
            "members": [{
                "id": r["id"], "nickname": r["nickname"],
                "city": r["city"], "age": r["age"],
                "score": r["score"], "level": r["level"]
            } for r in sorted_by_score]
        }
        with open("/home/ubuntu/data/member_scores.json", "w") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n评分结果已保存到 /home/ubuntu/data/member_scores.json")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()

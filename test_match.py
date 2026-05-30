#!/usr/bin/env python3
"""Test the new match display format"""
import sys
sys.path.insert(0, "/home/ubuntu/yufeng-event-api")

from app.database import SessionLocal
from app.models.member_profile import MemberProfile
from app.services.matching_service import find_matches

db = SessionLocal()
profile = db.query(MemberProfile).filter(MemberProfile.id == 31).first()
matches = find_matches(db, profile, limit=5)
db.close()

for i, m in enumerate(matches, 1):
    p = m['profile']
    s = m['scores']
    name = getattr(p, "nickname", getattr(p, "昵称", "?"))
    city = getattr(p, "city", getattr(p, "城市", ""))
    role_actual = getattr(p, "role_self", getattr(p, "属性", "?"))
    age_actual = getattr(p, "age", getattr(p, "年龄", "?"))
    body_actual = getattr(p, "body_type", getattr(p, "体型", "?"))
    print(f"{i}. {name} | {s['total']}%")
    print(f"   {city} - 角色{role_actual} - {age_actual}岁 - 体型{body_actual}")
    bonus = s.get("city_bonus", 0)
    if bonus:
        print(f"   同城") if bonus >= 20 else print(f"   同省")
    print()

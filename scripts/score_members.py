"""
屿风会员分层评分脚本 v3
维度：收入35% + 城市30% + 年龄15% + 独居20%
"""
import os, sys, json
from datetime import datetime, timezone

sys.path.insert(0, "/home/ubuntu/yufeng-event-api")


def main():
    from app.core.database import SessionLocal
    from app.models.member_profile import MemberProfile
    from app.services.member_scorer import score_member

    db = SessionLocal()
    try:
        members = db.query(MemberProfile).all()
        print("=== 屿风会员分层评分报告 v3 ===")
        print(f"日期: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}")
        print(f"总会员数: {len(members)}")
        print()
        print("评分维度: 收入35% + 城市30% + 年龄15% + 独居20%")
        print()

        cols = [c.key for c in MemberProfile.__table__.columns]
        results = []
        for m in members:
            profile = {c: getattr(m, c) for c in cols}
            level, total, details = score_member(profile)
            results.append({
                "id": m.id, "nickname": m.nickname or "未命名",
                "city": m.city or "未知", "age": m.age or profile.get("birth_info", ""),
                "score": total, "level": level, "details": details,
            })

        s = sum(1 for r in results if r["level"] == "S")
        a = sum(1 for r in results if r["level"] == "A")
        b = sum(1 for r in results if r["level"] == "B")
        c = sum(1 for r in results if r["level"] == "C")
        print(f"等级分布:  S:{s}({s/len(results)*100:.1f}%)  A:{a}({a/len(results)*100:.1f}%)  B:{b}({b/len(results)*100:.1f}%)  C:{c}({c/len(results)*100:.1f}%)")
        print()

        sorted_r = sorted(results, key=lambda x: -x["score"])
        print(f"{'#':>3} {'昵称':<14} {'城市':<14} {'年龄':<5} {'分数':<6} {'等级':<4}")
        print("-" * 50)
        for i, r in enumerate(sorted_r[:15], 1):
            age_str = str(r["age"]) if r["age"] else "?"
            print(f"{i:>3} {r['nickname']:<14} {r['city']:<14} {age_str:<5} {r['score']:<6} {r['level']:<4}")

        for lv in ["S", "A", "B", "C"]:
            mems = [r for r in results if r["level"] == lv]
            if mems:
                top = sorted(mems, key=lambda x: -x["score"])[:2]
                print(f"\n{lv} 级示例:")
                for r in top:
                    d = r["details"]
                    print(f"  [{r['nickname']}] {r['city']} {r['age'] or '?'} 总分={r['score']}")
                    print(f"    收入={d['income']['score']}分 | 城市={d['city']['score']}分 | 年龄={d['age']['score']}分 | 独居={d['alone']['score']}分")

        # Save
        os.makedirs("/home/ubuntu/data", exist_ok=True)
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": "v3",
            "dimensions": "income35_city30_age15_alone20",
            "total_members": len(results),
            "distribution": {"S": s, "A": a, "B": b, "C": c},
            "members": [{
                "id": r["id"], "nickname": r["nickname"],
                "city": r["city"], "age": str(r["age"]),
                "score": r["score"], "level": r["level"],
            } for r in sorted_r],
        }
        with open("/home/ubuntu/data/member_scores.json", "w") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n评分结果已保存到 /home/ubuntu/data/member_scores.json")

    finally:
        db.close()


if __name__ == "__main__":
    main()

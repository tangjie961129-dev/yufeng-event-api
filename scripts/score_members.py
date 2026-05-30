"""
屿风会员分层评分脚本 v3 — 简化版：收入30%+城市30%+年龄20%+独居20%
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
        print(f"=== 屿风会员分层评分报告 v3 === ")
        print(f"日期: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}")
        print(f"总会员数: {len(members)}")
        print()
        print("评分维度: 收入30% + 城市30% + 年龄20% + 独居20%")
        print()

        results = []
        cols = [c.key for c in MemberProfile.__table__.columns]
        for m in members:
            profile = {c: getattr(m, c) for c in cols}
            level, total, details = score_member(profile)
            results.append({
                "id": m.id,
                "nickname": m.nickname or "未命名",
                "city": m.city or "未知",
                "age": m.age or profile.get("birth_info", ""),
                "score": total,
                "level": level,
                "details": details,
            })

        s_count = sum(1 for r in results if r["level"] == "S")
        a_count = sum(1 for r in results if r["level"] == "A")
        b_count = sum(1 for r in results if r["level"] == "B")
        c_count = sum(1 for r in results if r["level"] == "C")

        print(f"等级分布:")
        print(f"  S 级: {s_count}人 ({s_count/len(results)*100:.1f}%)" if s_count else "  S 级: 0人")
        print(f"  A 级: {a_count}人 ({a_count/len(results)*100:.1f}%)" if a_count else "  A 级: 0人")
        print(f"  B 级: {b_count}人 ({b_count/len(results)*100:.1f}%)" if b_count else "  B 级: 0人")
        print(f"  C 级: {c_count}人 ({c_count/len(results)*100:.1f}%)" if c_count else "  C 级: 0人")
        print()

        sorted_by_score = sorted(results, key=lambda x: x["score"], reverse=True)
        print(f"{'#':>3} {'昵称':<14} {'城市':<14} {'年龄':<5} {'分数':<6} {'等级':<4}")
        print(f"{'-'*50}")
        for i, r in enumerate(sorted_by_score[:15], 1):
            age_str = str(r["age"]) if r["age"] else "?"
            print(f"{i:>3} {r['nickname']:<14} {r['city']:<14} {age_str:<5} {r['score']:<6} {r['level']:<4}")
        print()

        for level in ["S", "A", "B", "C"]:
            level_members = [r for r in results if r["level"] == level]
            if level_members:
                top = sorted(level_members, key=lambda x: x["score"], reverse=True)[:2]
                print(f"{level} 级示例 (Top 2):")
                for r in top:
                    d = r["details"]
                    print(f"  [{r['nickname']}] {r['city']} {r['age'] or '?'} 总分={r['score']}")
                    print(f"    收入={d['income']['score']}分({d['income']['raw']}) "
                          f"| 城市={d['city']['score']}分 "
                          f"| 年龄={d['age']['score']}分 "
                          f"| 独居={d['alone']['score']}分")
                print()

        # Save
        os.makedirs("/home/ubuntu/data", exist_ok=True)
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": "v3",
            "dimensions": "income30_city30_age20_alone20",
            "total_members": len(results),
            "distribution": {"S": s_count, "A": a_count, "B": b_count, "C": c_count},
            "members": [{
                "id": r["id"], "nickname": r["nickname"],
                "city": r["city"], "age": str(r["age"]),
                "score": r["score"], "level": r["level"],
            } for r in sorted_by_score],
        }
        with open("/home/ubuntu/data/member_scores.json", "w") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"评分结果已保存到 /home/ubuntu/data/member_scores.json")

    finally:
        db.close()


if __name__ == "__main__":
    main()

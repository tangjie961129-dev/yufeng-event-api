#!/usr/bin/env python3
"""每日推荐生成 · 仅文本版（跳过生图，后续单独处理）"""
import asyncio, json, os, sys, random, re, requests, time
from datetime import datetime, date
from pathlib import Path

BASE_DIR = os.path.expanduser("~/yufeng-event-api")
REF_DIR = os.path.join(BASE_DIR, "references")
OUTPUT_DIR = os.path.join(BASE_DIR, "daily_recommendation")
os.makedirs(REF_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

USED_FILE = os.path.join(REF_DIR, "used_recommendations.json")
PREVIEW_FILE = os.path.join(OUTPUT_DIR, "preview_queue.json")

sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
from level_scorer import evaluate_level

def load_used():
    if os.path.exists(USED_FILE):
        with open(USED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"S": [], "A": [], "B": [], "C": []}

def save_used(used):
    with open(USED_FILE, "w", encoding="utf-8") as f:
        json.dump(used, f, ensure_ascii=False, indent=2)

def get_conn():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return None
    with open(env_path) as f:
        for line in f:
            if line.startswith("DATABASE_URL"):
                import psycopg2
                return psycopg2.connect(line.strip().replace("DATABASE_URL=", ""))
    return None

def load_all_members():
    conn = get_conn()
    if not conn:
        print("  ❌ DB 连接失败", file=sys.stderr)
        return []
    members = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT "昵称","城市","年龄","职业","身高","学历","体重","体型","属性",
                   "个人特点","理想型描述","恋爱历史","恋爱癖好","最重要因素",
                   "其他想说的话","单身多久","出柜对象","形婚考虑","星座MBTI",
                   "异地接受度","理想伴侣关系","交友方式","屿风编号"
            FROM huxuan_profiles ORDER BY id
        """)
        for row in cur.fetchall():
            name = str(row[0] or "").strip()
            if not name:
                continue
            members.append({
                "name": name,
                "city": str(row[1] or "").strip(),
                "age": str(row[2] or "").strip(),
                "job": str(row[3] or "").strip(),
                "height": str(row[4] or "").strip(),
                "education": str(row[5] or "").strip(),
                "weight": str(row[6] or "").strip(),
                "body_type": str(row[7] or "").strip(),
                "role": str(row[8] or "").strip(),
                "self_tags": str(row[9] or "").strip(),
                "ideal_desc": str(row[10] or "").strip(),
                "experience": str(row[11] or "").strip(),
                "love_habits": str(row[12] or "").strip(),
                "priority": str(row[13] or "").strip(),
                "extra": str(row[14] or "").strip(),
                "single_duration": str(row[15] or "").strip(),
                "out_status": str(row[16] or "").strip(),
                "marriage": str(row[17] or "").strip(),
                "mbti": str(row[18] or "").strip(),
                "long_distance": str(row[19] or "").strip(),
                "ideal_relation": str(row[20] or "").strip(),
                "social_info": str(row[21] or "").strip(),
            })
    conn.close()
    return members

def pick_members_by_level(all_members, used):
    result = {}
    already_used = {lv: set(names) for lv, names in used.items()}
    scored = []
    for m in all_members:
        level, score = evaluate_level(m)
        scored.append((m, level, score))
    level_pool = {"S": [], "A": [], "B": [], "C": []}
    for m, lv, sc in scored:
        if m["name"] not in already_used.get(lv, set()):
            level_pool[lv].append((m, sc))
    for lv in ["S", "A", "B", "C"]:
        pool = level_pool.get(lv, [])
        if not pool:
            fallback_order = {"S": "A", "A": "B", "B": "C", "C": "S"}
            fallback = fallback_order.get(lv)
            if fallback and level_pool.get(fallback):
                pool = sorted(level_pool[fallback], key=lambda x: -x[1])
                print(f"  ⚠️ {lv}级候选池空，从{fallback}级借调: {pool[0][0]['name']}")
                result[lv] = pool[0][0]
                level_pool[fallback] = [x for x in level_pool[fallback] if x[0]["name"] != pool[0][0]["name"]]
                continue
            print(f"  ⚠️ {lv}级无人可选，跳过")
            continue
        pool.sort(key=lambda x: -x[1])
        chosen = pool[0][0]
        result[lv] = chosen
        print(f"  ✅ {lv}级: {chosen['name']} | {chosen.get('city','')} | {chosen.get('age','')}岁 | 评分{pool[0][1]}")
    return result

def generate_text(member, level):
    name = member.get("name", "")
    city = member.get("city", "")
    age = member.get("age", "")
    job = member.get("job", "")
    height = member.get("height", "")
    edu = member.get("education", "")
    tags = member.get("self_tags", "")
    ideal = member.get("ideal_desc", "")
    extra = member.get("extra", "")

    prompt = (
        f"以屿风创始人阿杰的语气，写一段像私聊一样推荐一位{level}级会员的文字。\n\n"
        f"会员信息：{name} | {city} | {age}岁 | {job} | {height} | {edu}\n"
        f"个人特点：{tags}\n理想型：{ideal}\n其他：{extra}\n\n"
        f"要求：\n"
        f"1. 语气像朋友私下推荐，不是官方文案\n"
        f"2. 开头自然（如「跟你说个事」「刚看到个会员」）\n"
        f"3. 结合真实信息写，有具体细节\n"
        f"4. 80-150字\n"
        f"5. 结尾像「有兴趣我帮你牵个线」\n"
        f"只输出正文。"
    )
    try:
        hermes_key = os.environ.get("HERMES_API_KEY", "")
        resp = requests.post(
            "http://127.0.0.1:8642/v1/chat/completions",
            headers={"Authorization": f"Bearer {hermes_key}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是屿风创始人阿杰，说话真诚有温度，像朋友在认真推荐一个人。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 500, "temperature": 0.95
            },
            timeout=180
        )
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  WARN: LLM failed: {e}", file=sys.stderr)
        return f"跟你说个事，我这边有个会员叫{name}，{city}的，{age}岁做{job}的，条件挺好的，你有兴趣我帮你牵个线。"

def save_preview(level_items, today_str):
    preview = {
        "date": today_str,
        "generated_at": datetime.now().isoformat(),
        "items": level_items,
        "status": "pending",
    }
    with open(PREVIEW_FILE, "w", encoding="utf-8") as f:
        json.dump(preview, f, ensure_ascii=False, indent=2)
    print(f"  💾 预览队列已保存: {PREVIEW_FILE}")

def mark_used(level_items):
    used = load_used()
    for item in level_items:
        lv = item["level"]
        name = item["member"]["name"]
        if name not in used.get(lv, []):
            used.setdefault(lv, []).append(name)
    save_used(used)
    print(f"  ✅ 已推荐列表已更新")

def main():
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    print(f"\n📢 每日推荐生成(仅文本) - {today_str}")
    print("=" * 40)

    all_members = load_all_members()
    if not all_members:
        print("❌ 互选库为空")
        return
    print(f"  互选库: {len(all_members)} 人")

    used = load_used()
    for lv in ["S","A","B","C"]:
        count = len(used.get(lv, []))
        print(f"  {lv}级已推荐: {count} 人")

    print(f"\n  🔍 按等级挑人...")
    chosen = pick_members_by_level(all_members, used)
    if not chosen:
        print("❌ 无可推荐的会员")
        return

    level_items = []
    for lv in ["S", "A", "B", "C"]:
        member = chosen.get(lv)
        if not member:
            continue
        print(f"\n  ━━ {lv}级 · {member['name']} ━━")
        print(f"     {member.get('city','')} | {member.get('age','')}岁 | {member.get('job','')}")

        print(f"    ✍️ 生成文案...")
        text = generate_text(member, lv)

        level_items.append({
            "level": lv,
            "member": member,
            "text": text,
            "image_url": "",
            "confirmed": False,
        })
        print(f"    ✅ {lv}级完成")

    if not level_items:
        print("❌ 无可推荐的会员")
        return

    save_preview(level_items, today_str)
    mark_used(level_items)

    print(f"\n{'='*40}")
    print(f"📋 今日推荐预览（文本已生成，配图待补充）")
    for item in level_items:
        lv = item["level"]
        m = item["member"]
        print(f"\n── {lv}级 · {m['name']} ──")
        print(f"  {m.get('city','')} | {m.get('age','')}岁 | {m.get('job','')} | {m.get('height','')}")
        print(f"  📝 {item['text'][:100]}...")

    print(f"\n💡 回应「确认全发」→ 18:00群发所有")
    print(f"💡 回应「发{level_items[0]['level']}」→ 只发该等级")
    print(f"💡 回应「补充配图」→ 单独生成配图")

if __name__ == "__main__":
    main()

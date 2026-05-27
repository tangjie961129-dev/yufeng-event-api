#!/usr/bin/env python3
"""每日推荐生成（修复版 v2）
每天早上10:00生成4条推荐（S/A/B/C各1条），保存到预览队列
用 self-contained scorer，不依赖 app.services 的 import
"""
import asyncio, json, os, sys, random, re, requests, time, base64
from datetime import datetime, date
from pathlib import Path

# ─── 路径 ───
BASE_DIR = os.path.expanduser("~/yufeng-event-api")
REF_DIR = os.path.join(BASE_DIR, "references")
OUTPUT_DIR = os.path.join(BASE_DIR, "daily_recommendation")
os.makedirs(REF_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

USED_FILE = os.path.join(REF_DIR, "used_recommendations.json")
PREVIEW_FILE = os.path.join(OUTPUT_DIR, "preview_queue.json")

AV_KEY = os.environ.get("AVEMUJICA_API_KEY", "")
AV_BASE = os.environ.get("AVEMUJICA_BASE_URL", "https://api.avemujica.moe").rstrip("/v1")

# ─── 导入自建评分器 ───
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
from level_scorer import evaluate_level

# ─── 已推荐管理（按等级独立） ───
def load_used():
    if os.path.exists(USED_FILE):
        with open(USED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"S": [], "A": [], "B": [], "C": []}

def save_used(used):
    with open(USED_FILE, "w", encoding="utf-8") as f:
        json.dump(used, f, ensure_ascii=False, indent=2)

# ─── DB ───
def get_conn():
    """读取 .env 连 PG"""
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
    """从 huxuan_profiles 加载所有会员，转为统一 dict"""
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

# ─── 选人（按等级 + 去重） ───
def pick_members_by_level(all_members, used):
    """为每个等级挑1个没推荐过的会员，确保等级匹配"""
    result = {}
    already_used = {lv: set(names) for lv, names in used.items()}

    # 先对所有会员评分定级
    scored = []
    for m in all_members:
        level, score = evaluate_level(m)
        scored.append((m, level, score))

    # 按等级分组排序
    level_pool = {"S": [], "A": [], "B": [], "C": []}
    for m, lv, sc in scored:
        if m["name"] not in already_used.get(lv, set()):
            level_pool[lv].append((m, sc))

    for lv in ["S", "A", "B", "C"]:
        pool = level_pool.get(lv, [])
        if not pool:
            # 备用：本等级无人可选，从相邻等级选（降级选）
            fallback_order = {"S": "A", "A": "B", "B": "C", "C": "S"}
            fallback = fallback_order.get(lv)
            if fallback and level_pool.get(fallback):
                pool = sorted(level_pool[fallback], key=lambda x: -x[1])
                print(f"  ⚠️ {lv}级候选池空，从{fallback}级借调: {pool[0][0]['name']}", file=sys.stderr)
                result[lv] = pool[0][0]
                # 从原等级池移除
                level_pool[fallback] = [x for x in level_pool[fallback] if x[0]["name"] != pool[0][0]["name"]]
                continue
            print(f"  ⚠️ {lv}级无人可选，跳过", file=sys.stderr)
            continue
        # 排序取最优
        pool.sort(key=lambda x: -x[1])
        chosen = pool[0][0]
        result[lv] = chosen
        print(f"  ✅ {lv}级: {chosen['name']} | {chosen.get('city','')} | {chosen.get('age','')}岁 | 评分{pool[0][1]}")

    return result

# ─── 生图 ───
def generate_photo(member):
    name = member.get("name", "")
    age = member.get("age", "")
    city = member.get("city", "")
    prompt = (
        f"高端男性肖像写真，{age}岁中国男性，帅气有型，"
        f"五官立体，自然微笑，暖调自然光，生活照质感，中景构图，干净背景，"
        f"真实人像摄影质感，毛孔可见，超写实。不要过度美化。"
    )
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{AV_BASE}/v1/images/generations",
                headers={"Authorization": f"Bearer {AV_KEY}", "Content-Type": "application/json"},
                json={"model": "gpt-image-2", "prompt": prompt, "n": 1, "size": "1024x1792"},
                timeout=180
            )
            if resp.status_code == 200:
                data = resp.json()['data'][0]
                if 'url' in data and data['url']:
                    return data['url']
                if 'b64_json' in data and data['b64_json']:
                    img_bytes = base64.b64decode(data['b64_json'])
                    tmp = f"/tmp/rec_{name}_{int(time.time())}.png"
                    with open(tmp, 'wb') as f: f.write(img_bytes)
                    return tmp
        except Exception as e:
            print(f"  WARN: img attempt {attempt+1}: {e}", file=sys.stderr)
            if attempt == 0: time.sleep(5)
    return None

# ─── 文案 ───
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

# ─── 保存预览队列 ───
def save_preview(level_items, today_str):
    preview = {
        "date": today_str,
        "generated_at": datetime.now().isoformat(),
        "items": level_items,
        "status": "pending",  # pending | partial_confirmed | all_confirmed | sent
    }
    with open(PREVIEW_FILE, "w", encoding="utf-8") as f:
        json.dump(preview, f, ensure_ascii=False, indent=2)
    print(f"  💾 预览队列已保存: {PREVIEW_FILE}")

# ─── 更新已推荐字典 ───
def mark_used(level_items):
    used = load_used()
    for item in level_items:
        lv = item["level"]
        name = item["member"]["name"]
        if name not in used.get(lv, []):
            used.setdefault(lv, []).append(name)
    save_used(used)
    print(f"  ✅ 已推荐列表已更新")

# ─── 主流程 ───
def main():
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    print(f"\n📢 每日推荐生成 - {today_str}")
    print("=" * 40)

    all_members = load_all_members()
    if not all_members:
        print("❌ 互选库为空")
        return
    print(f"  互选库: {len(all_members)} 人")

    used = load_used()
    # 打印当前已推荐统计
    for lv in ["S","A","B","C"]:
        count = len(used.get(lv, []))
        print(f"  {lv}级已推荐: {count} 人")

    # 选人
    print(f"\n  🔍 按等级挑人...")
    chosen = pick_members_by_level(all_members, used)
    if not chosen:
        print("❌ 无可推荐的会员")
        return

    # 生成文案 + 配图
    level_items = []
    for lv in ["S", "A", "B", "C"]:
        member = chosen.get(lv)
        if not member:
            continue

        print(f"\n  ━━ {lv}级 · {member['name']} ━━")
        print(f"     {member.get('city','')} | {member.get('age','')}岁 | {member.get('job','')}")

        # 生图
        print(f"    📸 生成形象照...")
        img_url = generate_photo(member)

        # 文案
        print(f"    ✍️ 生成文案...")
        text = generate_text(member, lv)

        level_items.append({
            "level": lv,
            "member": member,
            "text": text,
            "image_url": str(img_url) if img_url else "",
            "confirmed": False,
        })
        print(f"    ✅ {lv}级完成")

    if not level_items:
        print("❌ 无可推荐的会员")
        return

    # 保存预览队列
    save_preview(level_items, today_str)

    # 更新已推荐（无论是否确认，先占位）
    mark_used(level_items)

    # 输出摘要到 stdout（cron会输出给我看）
    print(f"\n{'='*40}")
    print(f"📋 今日推荐预览")
    for item in level_items:
        lv = item["level"]
        m = item["member"]
        print(f"\n── {lv}级 · {m['name']} ──")
        print(f"  {m.get('city','')} | {m.get('age','')}岁 | {m.get('job','')} | {m.get('height','')}")
        print(f"  📝 {item['text'][:100]}...")
        print(f"  {'📷 有配图' if item['image_url'] else '❌ 无配图'}")

    print(f"\n💡 回复「确认全发」→ 18:00群发所有")
    print(f"💡 回复「发{level_items[0]['level']}」→ 只发该等级")
    print(f"💡 回复「重做{level_items[0]['level']}图片」→ 重新生成配图")
    print(f"💡 回复「改{level_items[0]['level']}文案为xxx」→ 修改文案")

if __name__ == "__main__":
    main()

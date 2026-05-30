#!/usr/bin/env python3
"""群发队列生成 - 独立于每日推荐，独立去重"""
import json, os, sys, requests, time, base64
from datetime import datetime, date

BASE_DIR = os.path.expanduser("~/yufeng-event-api")
REF_DIR = os.path.join(BASE_DIR, "references")
QUEUE_DIR = os.path.join(BASE_DIR, "mass_queue")
PREVIEW_DIR = "/var/www/yufeng/queue"
IMAGE_DIR = os.path.join(PREVIEW_DIR, "images")
os.makedirs(QUEUE_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
from level_scorer import evaluate_level

USED_FILE = os.path.join(REF_DIR, "used_mass_send.json")
QUEUE_FILE = os.path.join(QUEUE_DIR, "pending_queue.json")

# Mass send reference corpus
MASS_SAMPLES_FILE = os.path.join(os.path.expanduser("~/yufeng-daily"), "references", "mass-send-samples", "1.txt")

def load_mass_samples():
    try:
        with open(MASS_SAMPLES_FILE, "r", encoding="utf-8") as f:
            return f.read()[:3000]
    except:
        return ""

# Ton API config
TON_API_KEY = None
TON_API_BASE = "https://api.sgyer.cn"
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("TON_API_KEY="):
                TON_API_KEY = line.split("=", 1)[1]
            if line.startswith("TON_API_BASE_URL="):
                TON_API_BASE = line.split("=", 1)[1]


def load_used():
    if os.path.exists(USED_FILE):
        with open(USED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"S": [], "A": [], "B": [], "C": []}


def save_used(used):
    with open(USED_FILE, "w", encoding="utf-8") as f:
        json.dump(used, f, ensure_ascii=False, indent=2)


def get_conn():
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


def generate_mass_text(member):
    name = member.get("name", "")
    age = member.get("age", "")
    job = member.get("job", "")
    height = member.get("height", "")
    education = member.get("education", "")
    body_type = member.get("body_type", "")
    role = member.get("role", "")
    tags = member.get("self_tags", "")
    ideal = member.get("ideal_desc", "")
    experience = member.get("experience", "")
    love_habits = member.get("love_habits", "")
    priority = member.get("priority", "")
    extra = member.get("extra", "")
    single_duration = member.get("single_duration", "")
    out_status = member.get("out_status", "")
    mbti = member.get("mbti", "")
    ideal_relation = member.get("ideal_relation", "")

    prompt = (
        f"以屿风创始人阿杰的语气，写一段群发推荐文案，用'宝子'开头。\n\n"
        f"要推荐的会员信息如下（注意：role/属性字段仅供你理解背景，绝对不能出现在文案中）：\n"
        f"年龄：{age}岁 | 职业：{job} | 身高：{height} | 学历：{education}\n"
        f"体型：{body_type} | 属性：{role} | 单身时长：{single_duration}\n"
        f"个人特点：{tags}\n"
        f"恋爱历史：{experience}\n"
        f"恋爱癖好：{love_habits}\n"
        f"最重要的因素：{priority}\n"
        f"理想型：{ideal}\n"
        f"理想伴侣关系：{ideal_relation}\n"
        f"出柜情况：{out_status}\n"
        f"MBTI：{mbti}\n"
        f"其他：{extra}\n\n"
        f"要求：\n"
        f"1. 开头用'宝子'，这是一条群发给多个客户的消息\n"
        f"2. 语气像阿杰私下推荐，真诚有温度，像朋友在认真介绍一个人\n"
        f"3. 结合会员的真实信息，用具体细节让人有画面感，显得资料很详实\n"
        f"4. 不用提该会员的真实昵称，用'咱们这位会员'之类描述\n"
        f"5. 80-130字，信息量要足，让人感觉这个会员资料很详细很靠谱\n"
        f"6. 结尾自然收束，如'有意向跟我说'\n"
        f"7. 绝对不要出现城市、地名或地域信息\n"
        f"8. 会员都是男性，只能用'他'不用'她'\n"
        f"9. 文案中绝对不能出现任何属性相关描述，包括但不限于：偏1、偏0、0.5、SIDE、皆可、偏S、纯S、偏0.5等任何形式（包括缩写、代称、谐音）——role字段仅供你理解背景\n"
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
                    {"role": "system", "content": "你是屿风创始人阿杰，说话真诚有温度，像朋友在认真推荐一个人。文案要有信息量，用具体的细节让人感受到这个会员的真实和靠谱。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 600, "temperature": 0.9
            },
            timeout=180
        )
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  WARN: LLM failed: {e}", file=sys.stderr)
        return f"宝子，咱们这位会员{age}岁做{job}的，条件挺不错的，有意向跟我说。"


def generate_images(level_items):
    """为每个会员生成配图（独立步骤，失败不影响文案）
    每日清旧图重新生成，6场景随机轮换，30%不露脸身材照
    """
    import random, hashlib

    # ===== 1. 清空旧图，确保每天重新生成 =====
    for old in os.listdir(IMAGE_DIR):
        old_path = os.path.join(IMAGE_DIR, old)
        if os.path.isfile(old_path) and old[0] in "SABC":
            os.remove(old_path)
            print(f"  🗑️ 已清除旧图: {old}")

    # ===== 2. 6个场景轮换 =====
    SCENES = [
        ("gym", "at the gym, doing a light workout, gym equipment in background, tank top or athletic wear"),
        ("basketball", "on a basketball court, holding a basketball, sportswear, outdoor court, sunny day"),
        ("running", "on a running track, athleisure wear, after a run, slightly sweaty, fitness vibe"),
        ("home", "in a cozy living room, sitting on a sofa, natural home setting, casual t-shirt"),
        ("coffee", "at a coffee shop, holding a cup, casual urban style, streetwear, relaxed vibe"),
        ("yoga", "stretching in a bright room, fitness wear, peaceful atmosphere, warm sunlight"),
    ]

    # ===== 3. Avemujica fallback =====
    AVEMUJICA_BASE = "https://api.avemujica.moe/v1"
    avemujica_key = ""
    for k, v in [(line.strip().split("=", 1)) for line in open(env_path) if "=" in line.strip()]:
        if k == "AVEMUJICA_API_KEY":
            avemujica_key = v

    for item in level_items:
        lv = item["level"]
        m = item["member"]
        img_path = os.path.join(IMAGE_DIR, f"{lv}.png")

        # 确定性场景分配（同一会员每次生成同场景）
        seed_str = m.get("name", "") + m.get("job", "")
        scene_idx = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % len(SCENES)
        scene_name, scene_desc = SCENES[scene_idx]

        # 30%不露脸身材照
        no_face = int(hashlib.md5((seed_str + "face").encode()).hexdigest(), 16) % 100 < 30

        # 体型判断
        body = m.get("body_type", "")
        is_athletic = any(kw in body for kw in ["肌肉", "健身", "运动", "偏壮", "运动型"])

        top_desc = "athletic fit, shirtless or tank top showing chest and abs naturally" if is_athletic else "medium shot from chest up, wearing casual t-shirt or sweater"

        face_desc = ""
        if no_face:
            face_desc = ", 拍摄不露脸, only body visible, back view or side view, face not in frame"
        else:
            face_desc = ", handsome young Chinese man, clear face visible, natural smile, approachable expression"

        prompt_text = (
            f"手机随手拍生活质感照片, {face_desc}, "
            f"{top_desc}, {scene_desc}, "
            f"warm natural lighting, photorealistic, "
            f"手机随手拍画质, 低清压缩感, 不修图不锐化, 生活化照片, "
            f"no studio lighting, no fashion shoot style, no text, no logos"
        )

        # ===== 双通道 API 生成 =====
        api_endpoints = [
            {"name": "Ton", "base": TON_API_BASE, "key": TON_API_KEY},
            {"name": "Avemujica", "base": AVEMUJICA_BASE, "key": avemujica_key},
        ]

        generated = False
        for ep in api_endpoints:
            name, base, key = ep["name"], ep["base"], ep["key"]
            if not key:
                continue
            for attempt in range(2):
                try:
                    api_url = base.rstrip("/")
                    if not api_url.endswith("/v1"):
                        api_url += "/v1"
                    resp = requests.post(
                        f"{api_url}/images/generations",
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        json={
                            "model": "gpt-image-2",
                            "prompt": prompt_text,
                            "n": 1,
                            "size": "1024x1024",
                            "response_format": "b64_json",
                        },
                        timeout=120
                    )
                    data = resp.json()
                    b64 = data.get("data", [{}])[0].get("b64_json", "")
                    if b64:
                        raw_bytes = base64.b64decode(b64)

                        # 缩放+转JPEG压缩
                        from PIL import Image as PILImage
                        import io
                        buf = io.BytesIO(raw_bytes)
                        img = PILImage.open(buf).convert("RGB")
                        w, h = img.size
                        if w > 600:
                            ratio = 600.0 / w
                            img = img.resize((600, int(h * ratio)))

                        # 有脸 → 脸部打码
                        if not no_face:
                            fx, fy = int(w * 0.30), int(h * 0.08)
                            fw2, fh2 = int(w * 0.40), int(h * 0.30)
                            face_region = img.crop((fx, fy, fx + fw2, fy + fh2))
                            rw2, rh2 = face_region.size
                            small = face_region.resize((max(rw2 // 28, 10), max(rh2 // 28, 10)), PILImage.NEAREST)
                            img.paste(small.resize((rw2, rh2), PILImage.NEAREST), (fx, fy))

                        out_buf = io.BytesIO()
                        img.save(out_buf, format="JPEG", quality=75)
                        with open(img_path, "wb") as f:
                            f.write(out_buf.getvalue())
                        print(f"  🖼️ {lv} [{name}] {scene_name} {'🔒不露脸' if no_face else '👤露脸'} "
                              f"{img_path} {os.path.getsize(img_path)//1024}KB")
                        item["image"] = img_path
                        generated = True
                        break
                    else:
                        print(f"  ⚠️ {lv} [{name}] 无b64 (attempt {attempt+1})")
                except KeyError as e:
                    print(f"  ⚠️ {lv} [{name}] JSON结构异常: {e} (attempt {attempt+1})")
                except Exception as e:
                    print(f"  ⚠️ {lv} [{name}] 失败: {type(e).__name__} (attempt {attempt+1})")
                time.sleep(2)
            if generated:
                break

        if not generated:
            print(f"  ⚠️ {lv} 配图跳过（所有通道失败）")


def save_queue(level_items, today_str):
    queue = {
        "date": today_str,
        "generated_at": datetime.now().isoformat(),
        "items": level_items,
        "status": "pending",
        "sender": "",
    }
    # 如果同一天的队列已确认过，保留确认状态（避免重跑覆盖用户确认）
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("date") == today_str and existing.get("status") == "confirmed":
                queue["status"] = "confirmed"
                queue["sender"] = existing.get("sender", "TangJieSiRenHao")
                for new_item in queue["items"]:
                    for old_item in existing.get("items", []):
                        if new_item["level"] == old_item["level"] and old_item.get("confirmed"):
                            new_item["confirmed"] = True
                            break
                print(f"  🔄 保留已有确认状态")
        except:
            pass
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
    print(f"  💾 待群发列表已保存: {QUEUE_FILE}")


def generate_mass_preview_html(level_items, today_str):
    count_by_level = {}
    for item in level_items:
        lv = item["level"]
        count_by_level[lv] = count_by_level.get(lv, 0) + 1

    slots_html = ""
    for item in level_items:
        lv = item["level"]
        m = item["member"]
        text = item["text"]
        img_path = item.get("image", "")
        img_html = ""
        if img_path and os.path.exists(img_path):
            img_rel = os.path.join("..", "images", os.path.basename(img_path))
            img_html = f'<img src="{img_rel}" class="member-photo" alt="{lv}">'
        slots_html += f'''
<div class="msg-item level-{lv.lower()}">
  <div class="msg-header">
    <span class="level-badge level-{lv.lower()}">{lv}</span>
    <span class="member-name">{m.get('name','?')}</span>
    <span class="member-meta">{m.get('age','?')}岁 · {m.get('job','?')} · {m.get('height','?')}</span>
  </div>
  {img_html}
  <div class="msg-content">{text}</div>
</div>'''

    total = len(level_items)
    level_summary = " | ".join([f"{lv}: {count_by_level.get(lv,0)}条" for lv in ["S","A","B","C"]])

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>屿风群发预览 - {today_str}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#f5f0eb;font-family:-apple-system,'PingFang SC','Helvetica Neue',sans-serif;color:#2d2a27;padding:20px}}
.container{{max-width:600px;margin:0 auto}}
.header{{text-align:center;padding:24px 0 16px}}
.header h1{{font-size:20px;font-weight:600;color:#DFA9AC}}
.header .date{{font-size:14px;color:#999;margin-top:4px}}
.summary-bar{{text-align:center;padding:12px;margin-bottom:16px;background:#fff8f0;border-radius:12px;font-size:13px;color:#666;border:1px solid #f0e0d0}}
.summary-bar strong{{color:#DFA9AC}}
.msg-item{{background:#fff;border-radius:12px;margin-bottom:12px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,0.06);border-left:4px solid #ccc}}
.level-s{{border-left-color:#e74c3c}} .level-a{{border-left-color:#e67e22}} .level-b{{border-left-color:#f1c40f}} .level-c{{border-left-color:#95a5a6}}
.msg-header{{display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap}}
.level-badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;color:#fff}}
.level-s{{background:#e74c3c}} .level-a{{background:#e67e22}} .level-b{{background:#d4a017}} .level-c{{background:#95a5a6}}
.member-name{{font-weight:600;font-size:14px}}
.member-meta{{font-size:12px;color:#999}}
.member-photo{{width:100%;border-radius:8px;margin-bottom:10px;max-height:300px;object-fit:cover}}
.msg-content{{font-size:14px;line-height:1.7;color:#444;white-space:pre-wrap}}
.footer{{text-align:center;padding:24px 0;font-size:12px;color:#bbb}}
</style>
</head><body>
<div class="container">
  <div class="header">
    <h1>📨 今日群发预览</h1>
    <div class="date">{today_str}</div>
  </div>
  <div class="summary-bar">
    总计 <strong>{total}条</strong> | {level_summary}<br>
    发送账号：TangJieSiRenHao（私人号）
  </div>
  {slots_html}
  <div class="footer">在飞书回复「确认所有」后执行群发</div>
</div>
</body></html>'''
    return html


def mark_used(level_items):
    used = load_used()
    for item in level_items:
        lv = item["level"]
        name = item["member"]["name"]
        if name not in used.get(lv, []):
            used.setdefault(lv, []).append(name)
    save_used(used)
    print(f"  ✅ 群发已推荐列表已更新")


def main():
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    print(f"\n📢 每日群发队列生成 - {today_str}")
    print("=" * 40)

    all_members = load_all_members()
    if not all_members:
        print("❌ 互选库为空")
        return
    print(f"  互选库: {len(all_members)} 人")

    used = load_used()
    for lv in ["S","A","B","C"]:
        count = len(used.get(lv, []))
        print(f"  {lv}级已群发推荐过: {count} 人")

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
        print(f"     {member.get('age','')}岁 | {member.get('job','')} | {member.get('height','')}")

        print(f"    ✍️ 生成群发文案...")
        text = generate_mass_text(member)

        level_items.append({
            "level": lv,
            "member": member,
            "text": text,
            "image": "",
            "confirmed": False,
        })
        print(f"    ✅ {lv}级完成")

    if not level_items:
        print("❌ 无可用文案")
        return

    save_queue(level_items, today_str)
    mark_used(level_items)

    # 生成配图（独立步骤）
    print(f"\n  🖼️ 生成配图...")
    generate_images(level_items)

    # 重新保存队列（补充配图路径）
    save_queue(level_items, today_str)

    # 生成预览网页
    preview_html = generate_mass_preview_html(level_items, today_str)
    preview_dir = os.path.join(PREVIEW_DIR, today_str)
    os.makedirs(preview_dir, exist_ok=True)
    with open(os.path.join(preview_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(preview_html)
    preview_url = f"https://yufeng.team/queue/{today_str}/"

    print(f"\n{'='*40}")
    print(f"📋 今日群发待发送列表")
    for item in level_items:
        lv = item["level"]
        m = item["member"]
        has_img = "🖼️" if item.get("image") else "🚫"
        print(f"\n── {lv}级 · {m['name']} {has_img}──")
        print(f"  {m.get('age','')}岁 | {m.get('job','')} | {m.get('height','')}")
        print(f"  📝 {item['text'][:150]}...")

    print(f"\n🌐 预览链接: {preview_url}")
    print(f"💡 回应「确认所有」→ 推送至待群发列表等待发送")
    print(f"💡 回应「改S文案为...」→ 修改某条")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
每日群发话术生成 + 待发送列表 + 群发预览网页
每天跑一次（凌晨3:00），按 S/A/B/C 生成不同话术并推送到待发送队列
同时生成群发预览网页 /var/www/yufeng/queue/{日期}/index.html
"""
import sys, json, asyncio, os, random
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "/home/ubuntu/yufeng-event-api")

from app.core.database import SessionLocal
from app.models.member_profile import MemberProfile
from app.services.wecom import _get_access_token
from sqlalchemy.sql import text
import httpx

WECOM_API_BASE = "https://qyapi.weixin.qq.com"

# 群发固定话术模板（配图 + 文案）
MASS_IMAGE_PARAMS = {
    "size": "1024x1792",
    "prompt_type": "member",  # 复用朋友圈会员人像生图逻辑
}

# 按等级的话术模板
MESSAGE_TEMPLATES = {
    "S": [
        "宝子，这边给你推荐一位优质新会员，可以看一下合不合适，我把大概情况发给你，先稍微了解一下子哈\n\n{age}岁的{job}，{height}，他平常常驻在{city}。{personality}。然后他的理想型是{expectation}\n\n你可以先看一下有没有兴趣，感觉不合适也没事的，后续还会推荐其他会员的，要是感觉有意向的话跟我说就行。",
    ],
    "A": [
        "宝子，这边给你推荐一位优质新会员，可以看一下合不合适，我把大概情况发给你，先稍微了解一下子哈\n\n{age}岁的{job}，{height}，他平常常驻在{city}。{personality}。然后他的理想型是{expectation}\n\n你可以先看一下有没有兴趣，感觉不合适也没事的，后续还会推荐其他会员的，要是感觉有意向的话跟我说就行。",
    ],
    "B": [
        "宝子，这边给你推荐一位优质新会员，可以看一下合不合适，我把大概情况发给你，先稍微了解一下子哈\n\n{age}岁的{job}，{height}，他平常常驻在{city}。{personality}。然后他的理想型是{expectation}\n\n你可以先看一下有没有兴趣，感觉不合适也没事的，后续还会推荐其他会员的，要是感觉有意向的话跟我说就行。",
    ],
    "C": [
        "宝子，这边给你推荐一位优质新会员，可以看一下合不合适，我把大概情况发给你，先稍微了解一下子哈\n\n{age}岁的{job}，{height}，他平常常驻在{city}。{personality}。然后他的理想型是{expectation}\n\n你可以先看一下有没有兴趣，感觉不合适也没事的，后续还会推荐其他会员的，要是感觉有意向的话跟我说就行。",
    ],
}


def build_member_context(mp) -> dict:
    """从 MemberProfile 提取群发所需的字段"""
    ls = mp.lifestyle_status or ""
    lines_map = {}
    if ls:
        for line in ls.split("\n"):
            if "：" in line:
                k, v = line.split("：", 1)
                lines_map[k.strip()] = v.strip()

    age = mp.age or lines_map.get("年龄", "未知")
    job = mp.job or lines_map.get("职业", "未知")
    height = mp.height or lines_map.get("身高", "未知")
    city = mp.city or lines_map.get("现居城市", "未知")

    # 性格描述 - 从多个字段拼
    personality_parts = []
    for key in ["目前状况", "日常状态", "爱好与习惯", "自我标签"]:
        val = lines_map.get(key, "")
        if val:
            personality_parts.append(val)
    personality = "，".join(personality_parts[:2]) if personality_parts else "性格很好"

    expectation = lines_map.get("期待的你", lines_map.get("择偶标准", "认真相处的人"))

    return {
        "age": str(age),
        "job": str(job),
        "height": str(height),
        "city": str(city),
        "personality": str(personality)[:80],
        "expectation": str(expectation)[:60],
        "nickname": mp.nickname or "",
    }


async def generate_daily_queue(db):
    """生成今天待发送的消息队列"""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    # 第一步：从企微API获取所有客户及其等级标签
    token = await _get_access_token()
    all_contacts = {}  # ext_id -> {name, level, employee_userid}

    async with httpx.AsyncClient() as client:
        for emp in ["TangZengRong", "TangJieSiRenHao"]:
            resp = await client.post(
                f"{WECOM_API_BASE}/cgi-bin/externalcontact/batch/get_by_user",
                params={"access_token": token},
                json={"userid_list": [emp], "limit": 100},
                timeout=10,
            )
            data = resp.json()
            if data.get("errcode") == 0:
                for item in data.get("external_contact_list", []):
                    c = item.get("external_contact", {})
                    f = item.get("follow_info", {})
                    name = c.get("name", "")
                    ext_id = c.get("external_userid", "")
                    remark = (f.get("remark", "") or "").strip()
                    if ext_id:
                        level = "C"
                        parts = remark.split("｜")
                        if len(parts) >= 5:
                            last = parts[-1].strip()
                            if last in ("S", "A", "B", "C"):
                                level = last
                        all_contacts[ext_id] = {
                            "name": name,
                            "remark": remark,
                            "level": level,
                            "employee_userid": f.get("userid", emp),
                        }

    # 第二步：从 member_profiles 获取等级（优先于备注提取）
    members = db.execute(text("""
        SELECT mp.nickname, mp.level, mp.level_score, mp.last_contact_at
        FROM member_profiles mp
        WHERE mp.level IS NOT NULL AND mp.level != ''
        ORDER BY 
          CASE mp.level WHEN 'S' THEN 1 WHEN 'A' THEN 2 WHEN 'B' THEN 3 WHEN 'C' THEN 4 END,
          mp.level_score DESC
    """)).fetchall()

    nickname_level = {m[0]: m[1] for m in members if m[0]}

    # 第三步：从 member_profiles 获取会员详细资料用于生成话术
    all_mps = db.query(MemberProfile).filter(
        MemberProfile.nickname.isnot(None),
        MemberProfile.nickname != "",
    ).all()
    mp_by_nick = {}
    for mp in all_mps:
        n = (mp.nickname or "").strip()
        if n:
            mp_by_nick[n] = mp

    # 第四步：对每个企微客户生成群发消息
    used_nicknames = set()
    used_names_file = os.path.expanduser("~/yufeng-daily/references/used_mass_send.json")
    try:
        with open(used_names_file, "r", encoding="utf-8") as f:
            used_data = json.load(f)
            used_nicknames = set(used_data.get("used", []))
    except: pass

    queue = []
    for ext_id, info in all_contacts.items():
        name = info["name"]
        level = nickname_level.get(name, info["level"])

        # 获取该等级对应的推荐会员
        eligible_mps = []
        for mp in all_mps:
            n = (mp.nickname or "").strip()
            if n and n not in used_nicknames:
                eligible_mps.append(mp)

        if not eligible_mps:
            continue

        # 选一个会员推荐
        chosen = random.choice(eligible_mps)
        ctx = build_member_context(chosen)
        used_nicknames.add(chosen.nickname)

        template = random.choice(MESSAGE_TEMPLATES.get(level, MESSAGE_TEMPLATES["C"]))
        content = template.format(**ctx)

        queue.append({
            "nickname": name,
            "level": level,
            "external_userid": ext_id,
            "employee_userid": info["employee_userid"],
            "content": content,
            "recommend_member": {
                "name": chosen.nickname,
                "age": ctx["age"],
                "job": ctx["job"],
                "height": ctx["height"],
                "city": ctx["city"],
            },
        })

    # 保存已使用记录
    with open(used_names_file, "w", encoding="utf-8") as f:
        json.dump({"used": list(used_nicknames)}, f, ensure_ascii=False)

    return queue


def generate_preview_html(queue: list, today_str: str) -> str:
    """生成群发预览网页"""
    count_by_level = {}
    for msg in queue:
        lv = msg["level"]
        count_by_level[lv] = count_by_level.get(lv, 0) + 1

    slots_html = ""
    for i, msg in enumerate(queue):
        lv = msg["level"]
        rm = msg.get("recommend_member", {})
        slots_html += f'''
<div class="msg-item level-{lv.lower()}">
  <div class="msg-header">
    <span class="level-badge level-{lv.lower()}">{lv}级</span>
    <span class="customer-name">{msg["nickname"]}</span>
    <span class="employee-name">→ {msg["employee_userid"]}</span>
  </div>
  <div class="member-info">
    推荐会员：{rm.get("name","?")} · {rm.get("age","?")}岁 · {rm.get("job","?")} · {rm.get("city","?")}
  </div>
  <div class="msg-content">{msg["content"]}</div>
</div>'''

    total = len(queue)
    level_summary = " | ".join([f"{lv}级: {count_by_level.get(lv,0)}条" for lv in ["S","A","B","C"]])

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
.header h1{{font-size:20px;font-weight:600;color:#c0392b}}
.header .date{{font-size:14px;color:#999;margin-top:4px}}
.summary-bar{{text-align:center;padding:12px;margin-bottom:16px;background:#fff8f0;border-radius:12px;font-size:13px;color:#666;border:1px solid #f0e0d0}}
.summary-bar strong{{color:#c0392b}}
.msg-item{{background:#fff;border-radius:12px;margin-bottom:12px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,0.06);border-left:4px solid #ccc}}
.level-s{{border-left-color:#e74c3c}} .level-a{{border-left-color:#e67e22}} .level-b{{border-left-color:#f1c40f}} .level-c{{border-left-color:#95a5a6}}
.msg-header{{display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap}}
.level-badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;color:#fff}}
.level-s{{background:#e74c3c}} .level-a{{background:#e67e22}} .level-b{{background:#d4a017}} .level-c{{background:#95a5a6}}
.customer-name{{font-weight:600;font-size:14px}}
.employee-name{{font-size:12px;color:#999}}
.member-info{{font-size:13px;color:#666;margin-bottom:8px;padding:6px 10px;background:#f9f6f2;border-radius:6px}}
.msg-content{{font-size:14px;line-height:1.7;color:#444;white-space:pre-wrap}}
.approve-section{{text-align:center;padding:20px 0 12px}}
.approve-title{{font-size:13px;color:#999;margin-bottom:12px}}
.approve-buttons{{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}}
.approve-btn{{padding:10px 20px;border:none;border-radius:8px;font-size:14px;cursor:pointer}}
.approve-btn:hover{{opacity:0.85}}
.approve-ok{{background:#27ae60;color:#fff}}
.approve-skip{{background:#e67e22;color:#fff}}
.approve-cancel{{background:#95a5a6;color:#fff}}
.approve-msg{{margin-top:10px;font-size:13px;font-weight:500}}
.approve-success{{color:#27ae60}} .approve-error{{color:#c0392b}}
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
    推送至：TangJieSiRenHao + romanYu
  </div>
  {slots_html}
  <div class="approve-section">
    <div class="approve-title">审批操作</div>
    <div class="approve-buttons">
      <button class="approve-btn approve-ok" onclick="doApprove('queue_approve')">✅ 确认群发</button>
      <button class="approve-btn approve-skip" onclick="doApprove('queue_skip')">⏭️ 今天不群发</button>
      <button class="approve-btn approve-cancel" onclick="doApprove('queue_unapprove')">↩️ 撤回审批</button>
    </div>
    <div class="approve-msg" id="approve-msg"></div>
  </div>
  <div class="footer">如需修改请回复 Hermes 对话</div>
</div>
<script>
function doApprove(a){{var m=document.getElementById("approve-msg");m.textContent="⏳...";var p=prompt("请输入管理密码：");if(!p)return;var fd=new FormData();fd.append("password",p);fd.append("action",a);fetch("/api/approve",{{method:"POST",body:fd}}).then(function(r){{return r.json()}}).then(function(d){{if(d.success){{m.textContent="✅ "+d.message;setTimeout(function(){{location.reload()}},1500)}}else{{m.textContent="❌ "+d.detail}}}}).catch(function(){{m.textContent="❌ 网络错误"}});}}
</script>
</body></html>'''
    return html


def main():
    db = SessionLocal()
    try:
        queue = asyncio.run(generate_daily_queue(db))

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        output = {
            "date": today_str,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(queue),
            "by_level": {},
            "messages": [],
            "queue_approved": False,
            "queue_skip": False,
        }

        for msg in queue:
            level = msg["level"]
            output["by_level"][level] = output["by_level"].get(level, 0) + 1
            output["messages"].append({
                "nickname": msg["nickname"],
                "level": level,
                "content": msg["content"],
                "employee": msg["employee_userid"],
                "recommend_member": msg.get("recommend_member", {}),
            })

        # 保存队列文件
        output_dir = "/home/ubuntu/data/queue"
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"queue_{today_str}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        # 生成群发预览网页
        preview_html = generate_preview_html(queue, today_str)
        preview_dir = f"/var/www/yufeng/queue/{today_str}"
        os.makedirs(preview_dir, exist_ok=True)
        with open(os.path.join(preview_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(preview_html)

        # 输出摘要到控制台（供 cron agent 感知）
        summary = (
            f"📋 今日群发待发送队列\n"
            f"日期: {today_str}\n"
            f"总计: {len(queue)} 条消息\n"
        )
        for level in ["S", "A", "B", "C"]:
            count = output["by_level"].get(level, 0)
            if count:
                summary += f"  {level} 级: {count} 条\n"

        summary += f"\n✅ 群发预览: https://yufeng.team/queue/{today_str}/\n"
        summary += f"✅ 队列文件: {filepath}\n"
        summary += "⏳ 等待审批中（queue_approved=false）\n"
        summary += "💡 在 Hermes 对话中输入「确认群发」批准后 18:00 自动推送"

        print(summary)

    finally:
        db.close()


if __name__ == "__main__":
    main()

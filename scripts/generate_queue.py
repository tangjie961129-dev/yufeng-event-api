"""
每日群发话术生成 + 待发送列表
每天跑一次，按 S/A/B/C 生成不同话术并推送到待发送队列
"""
import sys, json, asyncio, os
from datetime import datetime, timezone, timedelta
sys.path.insert(0, "/home/ubuntu/yufeng-event-api")

from app.core.database import SessionLocal
from app.models.member_profile import MemberProfile
from app.services.wecom import _get_access_token
from sqlalchemy.sql import text
import httpx

WECOM_API_BASE = "https://qyapi.weixin.qq.com"

# 按等级的话术模板
MESSAGE_TEMPLATES = {
    "S": [
        "Hi {nickname}，我是阿杰。看到你的资料觉得条件很好，最近我们有几位新加入的优质会员，条件跟你很匹配，要不要先看看？",
        "{nickname}，最近屿风来了几位跟你同样注重品质的会员，我帮你初步筛选了几个，方便的话我发给你看看？",
    ],
    "A": [
        "你好{nickname}，屿风最近脱单喜报又增加了！有很多跟你条件匹配的新会员加入，要不要看看有没有合适的？",
        "{nickname}，屿风最近在做会员活动，符合条件的会员可以免费获取一次深度匹配报告，要不要了解一下？",
    ],
    "B": [
        "嗨{nickname}，屿风最近新增了好几位优质会员，有空来看看有没有合眼缘的~",
        "{nickname}，最近有会员反馈说在屿风遇到了不错的人，希望下一个好消息是你哦~",
    ],
    "C": [
        "好久不见{nickname}，屿风最近又上新人啦，有空来看看~",
        "{nickname}，最近怎么样？屿风一直在更新匹配库，说不定已经有适合你的人出现了~",
    ],
}

# 节假日/特殊日期的特制话术
SPECIAL_MESSAGES = {}  # 可以扩展

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
                    tags = f.get("tag_id", [])
                    if ext_id:
                        # 从备注提取等级（格式: XXX｜XX｜XX｜XX｜A）
                        level = "C"  # 默认
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
    
    # 按昵称匹配
    nickname_level = {m[0]: m[1] for m in members if m[0]}
    
    # 第三步：对每个企微客户，用 member_profiles 的等级覆盖
    queue = []
    for ext_id, info in all_contacts.items():
        name = info["name"]
        # 用数据库等级
        level = nickname_level.get(name, info["level"])
        
        # 用备注名也尝试匹配
        remark = info["remark"]
        for nick, lv in nickname_level.items():
            if nick in remark or remark in nick:
                level = lv
                break
        
        # 选话术
        templates = MESSAGE_TEMPLATES.get(level, MESSAGE_TEMPLATES["C"])
        import random
        template = random.choice(templates)
        content = template.format(nickname=name)
        
        queue.append({
            "nickname": name,
            "level": level,
            "external_userid": ext_id,
            "employee_userid": info["employee_userid"],
            "content": content,
        })
    
    return queue


def main():
    """每次运行时：生成待发送队列 → 保存到文件 → 输出到控制台"""
    import asyncio
    
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
        }
        
        for msg in queue:
            level = msg["level"]
            output["by_level"][level] = output["by_level"].get(level, 0) + 1
            output["messages"].append({
                "nickname": msg["nickname"],
                "level": level,
                "content": msg["content"],
                "employee": msg["employee_userid"],
            })
        
        # 保存到文件
        output_dir = "/home/ubuntu/data/queue"
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"queue_{today_str}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        # 推送摘要到企微
        summary = (
            f"📋 今日群发待发送队列\n"
            f"日期: {today_str}\n"
            f"总计: {len(queue)} 条消息\n"
        )
        for level in ["S", "A", "B", "C"]:
            count = output["by_level"].get(level, 0)
            if count:
                summary += f"  {level} 级: {count} 条\n"
        
        if queue:
            summary += "\n预览 (前5条):\n"
            for msg in queue[:5]:
                summary += f"  [{msg['level']}] {msg['nickname']}: {msg['content'][:30]}...\n"
        
        summary += f"\n完整列表已保存到服务器: {filepath}"
        summary += "\n💡 打开 Hermes 对话输入「处理群发队列」进行修改和发送"
        
        print(summary)
        print("=" * 60)
        print("✅ 已完成。请查看上方摘要，然后在对话中告诉我怎么处理。")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()

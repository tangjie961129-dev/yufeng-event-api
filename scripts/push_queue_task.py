#!/usr/bin/env python3
"""
群发任务推送脚本
18:00 执行：读 queue_{日期}.json → 调企微 add_msg_template API → 推送到员工
员工在企微「群发助手」中看到任务，点一下即可发送
"""
import sys, json, os, asyncio
from datetime import datetime, timezone

sys.path.insert(0, "/home/ubuntu/yufeng-event-api")
from app.services.wecom import _get_access_token
import httpx

WECOM_API_BASE = "https://qyapi.weixin.qq.com"

# 推送目标员工
EMPLOYEES = ["TangJieSiRenHao", "romanYu"]


def load_queue(date_str: str = None) -> dict:
    """读取今日队列"""
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filepath = f"/home/ubuntu/data/queue/queue_{date_str}.json"
    if not os.path.exists(filepath):
        print(f"❌ 队列文件不存在: {filepath}")
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


async def push_mass_task():
    """推群发任务到企微"""
    queue = load_queue()
    today = queue["date"]

    # 检查审批
    if queue.get("queue_skip", False):
        print(f"⏭️ 今日群发已标记跳过（queue_skip=true），不推送")
        return
    if not queue.get("queue_approved", False):
        print(f"⏳ 群发待审批（queue_approved=false），已拦截")
        return

    messages = queue.get("messages", [])
    total = len(messages)
    if total == 0:
        print("⚠️ 队列为空，无消息可推")
        return

    token = await _get_access_token()

    async with httpx.AsyncClient(timeout=30) as client:
        # 按员工分组
        for emp in EMPLOYEES:
            emp_msgs = [m for m in messages if m.get("employee", "").startswith(emp) or True]
            # 如果按employee分不够，就全部分配给两个员工各一半
            if not emp_msgs:
                emp_msgs = messages[:total // 2]

            for msg in emp_msgs:
                ext_id = msg.get("external_userid", "")
                if not ext_id:
                    print(f"  ⚠️ 跳过 {msg.get('nickname','?')}: 无 external_userid")
                    continue

                content = msg.get("content", "")
                if not content:
                    continue

                # 调用企微创建群发任务 add_msg_template
                payload = {
                    "chat_type": "single",
                    "external_userid": [ext_id],
                    "sender": emp,
                    "text": {
                        "content": content
                    },
                }

                resp = await client.post(
                    f"{WECOM_API_BASE}/cgi-bin/externalcontact/add_msg_template",
                    params={"access_token": token},
                    json=payload,
                    timeout=15,
                )
                data = resp.json()
                if data.get("errcode") == 0:
                    print(f"  ✅ [{emp}] {msg['nickname']} ({msg['level']}) → 群发任务已创建 (fail_list: {data.get('fail_list', [])})")
                else:
                    print(f"  ❌ [{emp}] {msg['nickname']}: {data.get('errmsg', '未知错误')} (errcode={data.get('errcode')})")

    print(f"\n✅ 群发推送完成: {total} 条 → {len(EMPLOYEES)} 位员工")
    print(f"💡 员工已打开企微 → 群发助手 → 点「发送」即可")    


def main():
    asyncio.run(push_mass_task())


if __name__ == "__main__":
    main()

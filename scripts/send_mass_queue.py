#!/usr/bin/env python3
"""群发待发送列表 → 执行群发
从 mass_queue/pending_queue.json 读取已确认的群发任务，
按等级筛选 TangJieSiRenHao 的客户，群发对应文案。
"""
import json, os, sys, time, urllib.request
from datetime import datetime

BASE_DIR = os.path.expanduser("~/yufeng-event-api")
QUEUE_FILE = os.path.join(BASE_DIR, "mass_queue/pending_queue.json")

WECOM_CORP_ID = "wwf6496c5297e21b7d"
WECOM_SECRET = "W86CRfulOpbAAapBTtF0G9TATw8HIEkU1GWpOK1AtJU"
API_BASE = "https://qyapi.weixin.qq.com"

_token_cache = {"token": None, "expires_at": 0}

def get_token():
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    try:
        url = f"{API_BASE}/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if data.get("errcode") != 0:
            raise Exception(f"token failed: {data}")
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + data["expires_in"]
        return data["access_token"]
    except Exception as e:
        print(f"  ❌ get_token: {e}", file=sys.stderr)
        return None

def get_customers(employee_userid):
    """获取某员工的客户列表，返回 [{external_userid, name, level}]"""
    token = get_token()
    if not token:
        return []
    customers = []
    cursor = ""
    while True:
        try:
            payload = {"userid_list": [employee_userid], "limit": 100}
            if cursor:
                payload["cursor"] = cursor
            req = urllib.request.Request(
                f"{API_BASE}/cgi-bin/externalcontact/batch/get_by_user?access_token={token}",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            if data.get("errcode") != 0:
                print(f"  WARN: get_customers failed: {data}", file=sys.stderr)
                break
            for item in data.get("external_contact_list", []):
                c = item.get("external_contact", {})
                f = item.get("follow_info", {})
                ext_id = c.get("external_userid", "")
                name = c.get("name", "")
                remark = (f.get("remark", "") or "").strip()
                # 从备注提取等级（格式: XXX｜XX｜XX｜XX｜A）
                level = "C"
                parts = remark.split("｜")
                if len(parts) >= 5:
                    last = parts[-1].strip()
                    if last in ("S", "A", "B", "C"):
                        level = last
                if ext_id:
                    customers.append({
                        "external_userid": ext_id,
                        "name": name,
                        "level": level,
                    })
            cursor = data.get("next_cursor", "")
            if not cursor:
                break
        except Exception as e:
            print(f"  WARN: get_customers batch: {e}", file=sys.stderr)
            break
    return customers

def send_group_msg(external_userids, text, sender):
    """通过 add_msg_template 群发文本消息"""
    if not external_userids:
        return True
    token = get_token()
    if not token:
        return False

    batch_size = 100
    success = True
    for i in range(0, len(external_userids), batch_size):
        batch = external_userids[i:i+batch_size]
        payload = {
            "chat_type": "single",
            "external_userid": batch,
            "sender": sender,
            "text": {"content": text},
        }
        try:
            req = urllib.request.Request(
                f"{API_BASE}/cgi-bin/externalcontact/add_msg_template?access_token={token}",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            if data.get("errcode") == 0:
                print(f"  ✅ 已群发 {len(batch)} 人, msgid={data.get('msgid','')}")
            else:
                print(f"  ❌ 群发失败: {data}", file=sys.stderr)
                success = False
        except Exception as e:
            print(f"  ❌ 群发异常: {e}", file=sys.stderr)
            success = False
        time.sleep(1)
    return success

def main():
    print(f"\n📢 执行群发 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 40)

    if not os.path.exists(QUEUE_FILE):
        print("❌ 待群发列表不存在")
        return

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

    status = queue.get("status", "")
    sender = queue.get("sender", "TangJieSiRenHao")

    if status != "confirmed":
        print(f"⚠️ 状态为 {status}，不是 confirmed，跳过")
        return

    items = queue.get("items", [])
    confirmed = [it for it in items if it.get("confirmed", False)]
    if not confirmed:
        print("⚠️ 无已确认条目")
        return

    print(f"  发送员工: {sender}")
    print(f"  待发条目: {len(confirmed)} 条\n")

    # 获取客户列表
    print(f"  🔍 获取 {sender} 的客户列表...")
    all_customers = get_customers(sender)
    print(f"  共 {len(all_customers)} 个客户")

    total_sent = 0
    for item in confirmed:
        lv = item["level"]
        text = item["text"]
        member_name = item["member"]["name"]

        level_customers = [c for c in all_customers if c["level"] == lv]
        if not level_customers:
            print(f"\n  ⚠️ {lv}级: 无客户，跳过")
            continue

        ext_ids = [c["external_userid"] for c in level_customers]
        print(f"\n  ━━ {lv}级 · {member_name} ━━")
        print(f"     目标: {len(ext_ids)} 个客户")
        print(f"     文案: {text[:60]}...")

        ok = send_group_msg(ext_ids, text, sender)
        if ok:
            total_sent += len(ext_ids)
            print(f"  ✅ {lv}级 群发成功")
        else:
            print(f"  ❌ {lv}级 群发失败")

    # 更新状态
    queue["status"] = "sent"
    queue["sent_at"] = datetime.now().isoformat()
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*40}")
    print(f"✅ 群发完成: 共 {total_sent} 条消息")

if __name__ == "__main__":
    main()

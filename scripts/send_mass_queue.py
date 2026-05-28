#!/usr/bin/env python3
"""群发待发送列表 → 执行群发（文字+配图）
从 mass_queue/pending_queue.json 读取已确认的群发任务，
按等级筛选员工的客户，群发对应文案+配图。
支持多员工逗号分隔发送。
"""
import json, os, sys, time, urllib.request, urllib.parse
from datetime import datetime

BASE_DIR = os.path.expanduser("~/yufeng-event-api")
QUEUE_FILE = os.path.join(BASE_DIR, "mass_queue/pending_queue.json")
IMAGE_DIR = "/var/www/yufeng/queue/images"

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


def upload_image_to_wecom(image_path):
    """上传图片到企微临时素材，返回 media_id（有效期3天，够发群发）"""
    token = get_token()
    if not token:
        return None
    try:
        boundary = "----WebKitFormBoundary" + os.urandom(16).hex()
        with open(image_path, "rb") as f:
            img_data = f.read()
        filename = os.path.basename(image_path)
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode() + img_data + f"\r\n--{boundary}--\r\n".encode()
        url = f"{API_BASE}/cgi-bin/media/upload?type=image&access_token={token}"
        req = urllib.request.Request(url, data=body)
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        if data.get("errcode") == 0:
            print(f"    📤 图片上传成功, media_id={data['media_id'][:20]}...")
            return data["media_id"]
        else:
            print(f"    ❌ 图片上传失败: {data}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"    ❌ 图片上传异常: {e}", file=sys.stderr)
        return None


def send_text(ext_ids, text, sender):
    """纯文本群发"""
    if not ext_ids:
        return True
    token = get_token()
    if not token:
        return False
    batch_size = 100
    success = True
    for i in range(0, len(ext_ids), batch_size):
        batch = ext_ids[i:i+batch_size]
        payload = {
            "chat_type": "single", "external_userid": batch, "sender": sender,
            "text": {"content": text},
        }
        try:
            req = urllib.request.Request(
                f"{API_BASE}/cgi-bin/externalcontact/add_msg_template?access_token={token}",
                data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            if data.get("errcode") == 0:
                print(f"  ✅ 纯文本群发 {len(batch)} 人, msgid={data.get('msgid','')}")
            else:
                print(f"  ❌ 纯文本群发失败: {data}", file=sys.stderr)
                success = False
        except Exception as e:
            print(f"  ❌ 纯文本群发异常: {e}", file=sys.stderr)
            success = False
        time.sleep(1)
    return success


def send_image(ext_ids, media_id, sender):
    """单独群发图片消息"""
    if not ext_ids or not media_id:
        return True
    token = get_token()
    if not token:
        return False
    batch_size = 100
    success = True
    for i in range(0, len(ext_ids), batch_size):
        batch = ext_ids[i:i+batch_size]
        payload = {
            "chat_type": "single", "external_userid": batch, "sender": sender,
            "msgtype": "image",
            "image": {"media_id": media_id},
        }
        try:
            req = urllib.request.Request(
                f"{API_BASE}/cgi-bin/externalcontact/add_msg_template?access_token={token}",
                data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            if data.get("errcode") == 0:
                print(f"  ✅ 图片群发 {len(batch)} 人, msgid={data.get('msgid','')}")
            else:
                print(f"  ❌ 图片群发失败: {data}", file=sys.stderr)
                success = False
        except Exception as e:
            print(f"  ❌ 图片群发异常: {e}", file=sys.stderr)
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
    senders_str = queue.get("sender", "TangJieSiRenHao")
    senders = [s.strip() for s in senders_str.split(",") if s.strip()]

    if status != "confirmed":
        print(f"⚠️ 状态为 {status}，不是 confirmed，跳过")
        return

    items = queue.get("items", [])
    confirmed = [it for it in items if it.get("confirmed", False)]
    if not confirmed:
        print("⚠️ 无已确认条目")
        return

    print(f"  发送员工: {senders}")
    print(f"  待发条目: {len(confirmed)} 条\n")

    total_sent = 0
    for sender in senders:
        print(f"\n━━ 员工 {sender} ━━")
        print(f"  🔍 获取 {sender} 的客户列表...")
        all_customers = get_customers(sender)
        print(f"  共 {len(all_customers)} 个客户")

        for item in confirmed:
            lv = item["level"]
            text = item["text"]
            member_name = item["member"]["name"]

            level_customers = [c for c in all_customers if c["level"] == lv]
            if not level_customers:
                print(f"  ⚠️ {lv}级: 无客户，跳过")
                continue

            ext_ids = [c["external_userid"] for c in level_customers]
            print(f"\n  ━━ {lv}级 · {member_name} ━━")
            print(f"     目标: {len(ext_ids)} 个客户")

            # 准备图片
            img_path = item.get("image", "")
            has_img = img_path and os.path.exists(img_path)

            if has_img:
                print(f"    📤 上传配图...")
                media_id = upload_image_to_wecom(img_path)
                # 先发文字
                ok_text = send_text(ext_ids, text, sender)
                if ok_text:
                    total_sent += len(ext_ids)
                    print(f"  ✅ {lv}级 文字完成")
                else:
                    print(f"  ❌ {lv}级 文字失败")
                # 再发图片
                if media_id:
                    ok_img = send_image(ext_ids, media_id, sender)
                    if ok_img:
                        print(f"  ✅ {lv}级 配图完成")
                    else:
                        print(f"  ❌ {lv}级 配图失败")
                else:
                    print(f"  ⚠️ {lv}级 配图上传失败，跳过")
                ok = ok_text  # 用于外部计数
            else:
                ok = send_text(ext_ids, text, sender)

            if ok:
                sent_count = len(ext_ids)
                total_sent += sent_count
                print(f"  ✅ {lv}级 完成 ({sent_count}人)")
            else:
                print(f"  ❌ {lv}级 失败")

    # 更新状态
    queue["status"] = "sent"
    queue["sent_at"] = datetime.now().isoformat()
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*40}")
    print(f"✅ 群发完成: 共 {total_sent} 条消息")


if __name__ == "__main__":
    main()

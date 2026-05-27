#!/usr/bin/env python3
"""每日推荐 · 18:00群发脚本
从 preview_queue.json 读取已确认的推荐项，按等级群发给客户
"""
import asyncio, json, sys, os, random, time, base64, urllib.request
from datetime import datetime, date
from pathlib import Path

BASE_DIR = os.path.expanduser("~/yufeng-event-api")
OUTPUT_DIR = os.path.join(BASE_DIR, "daily_recommendation")
PREVIEW_FILE = os.path.join(OUTPUT_DIR, "preview_queue.json")
LOG_FILE = os.path.join(OUTPUT_DIR, "send_log.txt")

WECOM_CORP_ID = "wwf6496c5297e21b7d"
WECOM_SECRET = "W86CRfulOpbAAapBTtF0G9TATw8HIEkU1GWpOK1AtJU"
API_BASE = "https://qyapi.weixin.qq.com"

# ─── Token ───
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

# ─── 上传图片到企微 ───
def upload_image(filepath):
    """返回 media_id"""
    if not filepath or not os.path.exists(filepath):
        return None
    try:
        import http.client
        token = get_token()
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        with open(filepath, "rb") as f:
            file_data = f.read()
        filename = os.path.basename(filepath)
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

        url = f"{API_BASE}/cgi-bin/media/upload?access_token={token}&type=image"
        req = urllib.request.Request(url, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        if data.get("errcode") == 0:
            return data["media_id"]
        print(f"  WARN: upload_image failed: {data}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  WARN: upload_image: {e}", file=sys.stderr)
        return None

# ─── 获取客户列表（按员工） ───
def get_customers(employee_userid):
    """返回 [{external_userid, name, remark, level}]"""
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
                data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
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
                # 从备注提取等级（格式：XXX｜XX｜XX｜XX｜A）
                level = "C"
                parts = remark.split("｜")
                if len(parts) >= 5:
                    last = parts[-1].strip()
                    if last in ("S", "A", "B", "C"):
                        level = last
                # 也查标签
                tag_ids = f.get("tag_id", [])
                if ext_id:
                    customers.append({
                        "external_userid": ext_id,
                        "name": name,
                        "remark": remark,
                        "level": level,
                        "tag_ids": tag_ids,
                    })
            cursor = data.get("next_cursor", "")
            if not cursor:
                break
        except Exception as e:
            print(f"  WARN: get_customers batch: {e}", file=sys.stderr)
            break
    return customers

# ─── 获取标签 ID（按名称） ───
def get_tag_id(tag_name):
    """从企微查标签组，返回 tag_id"""
    token = get_token()
    if not token:
        return None
    try:
        req = urllib.request.Request(
            f"{API_BASE}/cgi-bin/externalcontact/get_corp_tag_list?access_token={token}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if data.get("errcode") != 0:
            return None
        for group in data.get("tag_group", []):
            for tag in group.get("tag", []):
                if tag["name"] == tag_name:
                    return tag["id"]
        return None
    except:
        return None

# ─── 群发消息（通过 add_msg_template） ───
def send_group_msg(external_userids, text, media_id=None, sender="TangZengRong"):
    """向指定客户列表群发消息"""
    if not external_userids:
        return True
    token = get_token()
    if not token:
        return False

    # 分批次（每批最多100人）
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

    # 如果有图片，再发一次图片
    if media_id and success:
        for i in range(0, len(external_userids), batch_size):
            batch = external_userids[i:i+batch_size]
            payload = {
                "chat_type": "single",
                "external_userid": batch,
                "sender": sender,
                "image": {"media_id": media_id},
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
                    print(f"  ✅ 图片群发 {len(batch)} 人")
                else:
                    print(f"  ❌ 图片群发失败: {data}", file=sys.stderr)
            except Exception as e:
                print(f"  ❌ 图片群发异常: {e}", file=sys.stderr)
            time.sleep(1)

    return success

# ─── 日志 ───
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(msg)

# ─── 主流程 ───
def main():
    print(f"\n📢 每日推荐 · 18:00群发")
    print("=" * 40)

    # 读取预览队列
    if not os.path.exists(PREVIEW_FILE):
        print("❌ 预览队列不存在，跳过群发")
        return

    with open(PREVIEW_FILE, "r", encoding="utf-8") as f:
        preview = json.load(f)

    today_str = preview.get("date", "")
    status = preview.get("status", "pending")
    items = preview.get("items", [])

    print(f"  日期: {today_str}")
    print(f"  状态: {status}")
    print(f"  条目: {len(items)} 条")

    # 筛选已确认的
    confirmed = [it for it in items if it.get("confirmed", False)]
    if not confirmed:
        print("⚠️ 无已确认的推荐项，跳过群发")
        return

    # 获取所有客户
    print(f"\n  🔍 获取企微客户列表...")
    employees = ["TangZengRong", "TangJieSiRenHao"]
    all_customers = []
    for emp in employees:
        customers = get_customers(emp)
        print(f"  员工 {emp}: {len(customers)} 个客户")
        all_customers.extend(customers)

    if not all_customers:
        print("❌ 客户列表为空")
        return

    total_sent = 0
    for item in confirmed:
        lv = item["level"]
        member = item["member"]
        text = item["text"]
        img_url = item.get("image_url", "")

        print(f"\n  ━━ {lv}级 · {member['name']} ━━")

        # 找该等级的客户
        level_customers = [c for c in all_customers if c["level"] == lv]
        if not level_customers:
            print(f"  没有 {lv} 级客户，跳过")
            continue

        ext_ids = [c["external_userid"] for c in level_customers]
        print(f"  目标: {len(ext_ids)} 个客户 ({lv}级)")

        # 上传图片（如果有）
        media_id = None
        if img_url and img_url.startswith("http"):
            # 下载临时图片
            tmp_path = f"/tmp/send_{lv}_{int(time.time())}.jpg"
            try:
                import subprocess
                subprocess.run(["wget", "-q", "-O", tmp_path, img_url, "--timeout=60"], timeout=120)
                if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 50000:
                    media_id = upload_image(tmp_path)
                    print(f"  {'📷 图片已上传' if media_id else '❌ 图片上传失败'}")
            except:
                pass
        elif img_url and os.path.exists(img_url):
            media_id = upload_image(img_url)
            print(f"  {'📷 图片已上传' if media_id else '❌ 图片上传失败'}")

        # 群发
        ok = send_group_msg(ext_ids, text, media_id=media_id)
        if ok:
            total_sent += len(ext_ids)
            log(f"✅ {lv}级 '{member['name']}' → {len(ext_ids)} 人已群发")
            item["sent"] = True
        else:
            log(f"⚠️ {lv}级 '{member['name']}' 群发异常")

    # 更新状态
    preview["status"] = "sent"
    preview["sent_at"] = datetime.now().isoformat()
    with open(PREVIEW_FILE, "w", encoding="utf-8") as f:
        json.dump(preview, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*40}")
    print(f"✅ 群发完成: {total_sent} 条消息")

if __name__ == "__main__":
    main()

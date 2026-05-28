
"""
屿风截图上传 API
用于朋友圈预览网页上传聊天截图
POST /api/upload-screenshot 保存图片到 output/ / 更新 today_posts.json
返回HTML触发iframe刷新父页面
"""
import json, os, shutil, uuid
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse

router = APIRouter(prefix="/api", tags=["截图上传"])

YUFENG_DAILY_DIR = os.path.expanduser("~/yufeng-daily")
PUBLIC_DIR = "/var/www/yufeng/posts"


@router.post("/upload-screenshot")
async def upload_screenshot(
    file: UploadFile = File(...),
    slot: str = Form(...),
    date: str = Form(...),
):
    if slot not in ("10:00", "14:00", "20:00"):
        raise HTTPException(status_code=400, detail=f"Invalid slot: {slot}")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    today_dir = os.path.join(YUFENG_DAILY_DIR, "output", date)
    os.makedirs(today_dir, exist_ok=True)

    slot_key_map = {"10:00": "member", "14:00": "content", "20:00": "story"}
    key = slot_key_map.get(slot, "story")

    ext = os.path.splitext(file.filename or ".jpg")[1] or ".jpg"
    filename = f"{key}.jpg"
    filepath = os.path.join(today_dir, filename)

    content_data = await file.read()
    with open(filepath, "wb") as f:
        f.write(content_data)

    pub_dir = os.path.join(PUBLIC_DIR, date)
    os.makedirs(pub_dir, exist_ok=True)
    pub_path = os.path.join(pub_dir, filename)
    try:
        if os.path.exists(pub_path):
            os.remove(pub_path)
    except:
        pass
    try:
        shutil.copy2(filepath, pub_path)
    except PermissionError:
        import subprocess
        subprocess.run(["sudo", "cp", filepath, pub_path], check=True)
        subprocess.run(["sudo", "chown", "ubuntu:ubuntu", pub_path], check=True)

    json_path = os.path.join(today_dir, "today_posts.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if slot in data.get("slots", {}):
                data["slots"][slot]["image"] = f"output/{date}/{filename}"
                data["slots"][slot]["image_ready"] = True
                data["slots"][slot]["image_source"] = "screenshot"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return HTMLResponse(
        content="<html><body><script>parent.location.reload()</script></body></html>",
        status_code=200,
    )

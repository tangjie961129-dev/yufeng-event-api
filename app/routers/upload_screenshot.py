"""
屿风截图上传 API
用于朋友圈预览网页上传聊天截图
POST /api/upload-screenshot → 保存图片到 output/{日期}/ → 更新 today_posts.json
"""
import json, os, shutil, uuid
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["截图上传"])

YUFENG_DAILY_DIR = os.path.expanduser("~/yufeng-daily")
PUBLIC_DIR = "/var/www/yufeng/posts"


@router.post("/upload-screenshot")
async def upload_screenshot(
    file: UploadFile = File(...),
    slot: str = Form(...),
    date: str = Form(...),
):
    """接收朋友圈截图上传，保存并更新 today_posts.json"""
    # 参数验证
    if slot not in ("10:00", "14:00", "20:00"):
        raise HTTPException(status_code=400, detail=f"Invalid slot: {slot}")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # 路径
    today_dir = os.path.join(YUFENG_DAILY_DIR, "output", date)
    os.makedirs(today_dir, exist_ok=True)

    # slot → key 映射
    slot_key_map = {"10:00": "member", "14:00": "content", "20:00": "story"}
    key = slot_key_map.get(slot, "story")

    # 保存文件
    ext = os.path.splitext(file.filename or ".jpg")[1] or ".jpg"
    filename = f"{key}.jpg"
    filepath = os.path.join(today_dir, filename)

    # 写入文件
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # 复制到公共目录（先移除旧文件避免权限冲突）    pub_dir = os.path.join(PUBLIC_DIR, date)    os.makedirs(pub_dir, exist_ok=True)    pub_path = os.path.join(pub_dir, filename)    try:        if os.path.exists(pub_path):            os.remove(pub_path)    except:        pass    try:        shutil.copy2(filepath, pub_path)    except PermissionError:        import subprocess        subprocess.run(["sudo", "cp", filepath, pub_path], check=True)        subprocess.run(["sudo", "chown", "ubuntu:ubuntu", pub_path], check=True)

    # 更新 today_posts.json
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
        except Exception as e:
            return JSONResponse(
                content={"success": True, "warning": f"JSON update failed: {e}", "image_url": f"/posts/{date}/{filename}"},
            )

    return JSONResponse(content={
        "success": True,
        "image_url": f"/posts/{date}/{filename}",
        "slot": slot,
        "date": date,
    })

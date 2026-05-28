"""
屿风审批 API
POST /api/approve 接收密码+指令，修改 today_posts.json 审批标记
"""
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
import json, os, subprocess

router = APIRouter(prefix="/api", tags=["审批"])

APPROVE_PASSWORD="yufeng2026"
YUFENG_DAILY = os.path.expanduser("~/yufeng-daily")
QUEUE_DIR = "/home/ubuntu/data/queue"


def _get_today_str():
    from datetime import date
    return date.today().strftime("%Y-%m-%d")


@router.post("/approve")
async def approve_action(
    password: str = Form(...),
    action: str = Form(...),
    date: str = Form(None),
):
    """审批操作
    action 可选:
      posts_approve   - 确认发圈
      posts_skip      - 今天不发圈
      queue_approve   - 确认群发
      queue_skip      - 今天不群发
      posts_unapprove - 取消审批（回退到待审批状态）
      queue_unapprove - 取消群发审批
    """
    if password != APPROVE_PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")

    today = date or _get_today_str()

    valid_actions = {
        "posts_approve": ("posts_approved", True, "posts_skip", False),
        "posts_skip": ("posts_skip", True, "posts_approved", False),
        "posts_unapprove": ("posts_approved", False, None, None),
        "queue_approve": ("queue_approved", True, "queue_skip", False),
        "queue_skip": ("queue_skip", True, "queue_approved", False),
        "queue_unapprove": ("queue_approved", False, None, None),
    }

    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"未知操作: {action}，可选: {list(valid_actions.keys())}")

    results = []

    # 朋友圈操作
    if action.startswith("posts"):
        posts_path = os.path.join(YUFENG_DAILY, "output", today, "today_posts.json")
        if os.path.exists(posts_path):
            with open(posts_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            key1, val1, key2, val2 = valid_actions[action]
            data[key1] = val1
            if key2:
                data[key2] = val2
            with open(posts_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            results.append(f"朋友圈: {key1}={val1}")
        else:
            results.append(f"⚠️ 朋友圈 today_posts.json 不存在（{posts_path}）")

        # 重建预览网页
        preview_path = os.path.join(YUFENG_DAILY, "output", today, "preview.html")
        if os.path.exists(posts_path) and not os.path.exists(preview_path):
            try:
                subprocess.run(
                    ["python3", os.path.join(YUFENG_DAILY, "scripts", "finalize_posts.py")],
                    cwd=YUFENG_DAILY, timeout=300, capture_output=True
                )
                results.append("预览网页已重建")
            except Exception as e:
                results.append(f"⚠️ 重建预览网页失败: {e}")

    # 群发操作
    if action.startswith("queue"):
        queue_path = os.path.join(QUEUE_DIR, f"queue_{today}.json")
        if os.path.exists(queue_path):
            with open(queue_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            key1, val1, key2, val2 = valid_actions[action]
            data[key1] = val1
            if key2:
                data[key2] = val2
            with open(queue_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            results.append(f"群发: {key1}={val1}")
        else:
            results.append(f"⚠️ 群发队列文件不存在（{queue_path}）")

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/posts/{today}/", status_code=303)
"""
屿风 GBrain HTTP API
通过主服务器 FastAPI 暴露 gbrain 读写接口，供备用机和本地 WSL 调用
POST /api/gbrain 接收指令，本地执行 gbrain binary，返回结果
"""
import json, subprocess, os
from datetime import date
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["GBrain"])

GBRAIN_BIN = "/home/ubuntu/gbrain/bin/gbrain"
GBRAIN_TOKEN = "yufeng2026"  # 简单鉴权，跟管理密码一致
GBRAIN_ENV = {**os.environ, "HOME": "/home/ubuntu"}


def _run_gbrain(args: list[str], stdin: str = None) -> tuple[str, str, int]:
    """执行 gbrain 命令，返回 (stdout, stderr, exit_code)"""
    try:
        result = subprocess.run(
            [GBRAIN_BIN] + args,
            input=stdin,
            capture_output=True, text=True, timeout=30,
            cwd="/home/ubuntu",
            env=GBRAIN_ENV,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "命令超时（30秒）", 124
    except FileNotFoundError:
        return "", f"gbrain binary not found: {GBRAIN_BIN}", 1
    except Exception as e:
        return "", str(e), 1


@router.post("/gbrain")
async def gbrain_api(
    token: str = Form(...),
    action: str = Form(...),
    slug: str = Form(None),
    content: str = Form(None),
    query: str = Form(None),
    date_str: str = Form(None),
    text: str = Form(None),
):
    """GBrain HTTP 接口

    action 可选:
      put <slug>       — 写入/更新页面 (需要 content)
      get <slug>       — 读取页面
      search <query>   — 搜索
      query <query>    — 混合搜索
      delete <slug>    — 删除页面
      list             — 列出页面
      timeline <slug>  — 查看时间线
      timeline-add <slug> <date> <text> — 添加时间线条目
      stats            — 统计
      put-briefing     — 快捷写入每日简报 (需要 content, slug 可选)
    """
    if token != GBRAIN_TOKEN:
        raise HTTPException(status_code=403, detail="token 错误")

    try:
        if action == "put":
            if not slug:
                raise HTTPException(status_code=400, detail="put 需要 slug 参数")
            stdout, stderr, rc = _run_gbrain(["put", slug], stdin=content or "")

        elif action == "get":
            if not slug:
                raise HTTPException(status_code=400, detail="get 需要 slug 参数")
            stdout, stderr, rc = _run_gbrain(["get", slug])

        elif action == "search":
            if not query:
                raise HTTPException(status_code=400, detail="search 需要 query 参数")
            stdout, stderr, rc = _run_gbrain(["search", query])

        elif action == "query":
            if not query:
                raise HTTPException(status_code=400, detail="query 需要 query 参数")
            stdout, stderr, rc = _run_gbrain(["query", query])

        elif action == "delete":
            if not slug:
                raise HTTPException(status_code=400, detail="delete 需要 slug 参数")
            stdout, stderr, rc = _run_gbrain(["delete", slug])

        elif action == "list":
            stdout, stderr, rc = _run_gbrain(["list", "-n", "50"])

        elif action == "timeline":
            if not slug:
                raise HTTPException(status_code=400, detail="timeline 需要 slug 参数")
            stdout, stderr, rc = _run_gbrain(["timeline", slug])

        elif action == "timeline-add":
            if not slug or not date_str or not text:
                raise HTTPException(status_code=400, detail="timeline-add 需要 slug, date_str, text 参数")
            stdout, stderr, rc = _run_gbrain(["timeline-add", slug, date_str, text])

        elif action == "stats":
            stdout, stderr, rc = _run_gbrain(["stats"])

        elif action == "put-briefing":
            today = date.today().strftime("%Y-%m-%d")
            target_slug = slug or "daily-briefing"
            exist_stdout, _, _ = _run_gbrain(["get", target_slug])
            if "error" not in exist_stdout.lower() and exist_stdout.strip():
                new_content = exist_stdout + "\n---\n## " + today + "\n" + (content or "")
            else:
                new_content = "---\n{}\n---\n\n## " + today + "\n" + (content or "")

            stdout, stderr, rc = _run_gbrain(["put", target_slug], stdin=new_content)
            if rc == 0:
                _run_gbrain(["timeline-add", target_slug, today, content or ""])
        else:
            raise HTTPException(status_code=400, detail=f"未知 action: {action}")

        return JSONResponse(content={
            "success": rc == 0,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": rc,
        })

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": 1,
        })

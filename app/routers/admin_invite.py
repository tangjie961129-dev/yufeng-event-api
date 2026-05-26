"""抖音引流渠道管理 — 归因数据统计

路径: /api/admin/invite/channels
功能: 查看各渠道点击数据 + 管理渠道配置
"""
import json
import os
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.invite_router import InviteClick, CHANNEL_NAMES

router = APIRouter(prefix="/api/admin/invite", tags=["引流渠道管理"])

# 管理密码（跟规则管理共用）
PASSWORD = os.environ.get("RULES_PASSWORD", "yufeng2026")


# ─── API: 渠道统计数据 ──────────────────────────────────────


@router.get("/stats")
def invite_stats(
    password: str = Query(...),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """获取渠道点击统计数据"""
    if password != PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")

    since = date.today() - timedelta(days=days)

    # 按渠道分组统计
    channel_stats = (
        db.query(
            InviteClick.channel,
            func.count(InviteClick.id).label("total"),
            func.count(func.distinct(InviteClick.ip)).label("unique_ips"),
        )
        .filter(func.date(InviteClick.created_at) >= since)
        .group_by(InviteClick.channel)
        .order_by(func.count(InviteClick.id).desc())
        .all()
    )

    # 按日期统计总点击
    daily_stats = (
        db.query(
            func.date(InviteClick.created_at).label("day"),
            func.count(InviteClick.id).label("count"),
        )
        .filter(func.date(InviteClick.created_at) >= since)
        .group_by(func.date(InviteClick.created_at))
        .order_by(func.date(InviteClick.created_at).desc())
        .limit(30)
        .all()
    )

    channels = []
    for ch, total, unique in channel_stats:
        name = CHANNEL_NAMES.get(ch, ch)
        channels.append({
            "channel": ch,
            "name": name,
            "total": total,
            "unique_ips": unique,
            "link": f"https://go.yufeng.team/invite/{ch}",
        })

    daily = [{"day": str(d), "count": c} for d, c in daily_stats]
    total_all = sum(c["total"] for c in channels)

    return {
        "channels": channels,
        "daily": daily,
        "total": total_all,
        "days": days,
    }


# ─── 管理页面 ────────────────────────────────────────────────


def _check_password(password: str) -> bool:
    return password == PASSWORD


@router.get("/admin", response_class=HTMLResponse)
def invite_admin_page():
    """渠道管理页面"""
    return HTMLResponse(content=_PAGE_HTML)


_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>屿风 · 引流渠道统计</title>
<style>
  :root {
    --bg: #1a1a2e;
    --card: #16213e;
    --accent: #e94560;
    --accent2: #0f3460;
    --text: #e8e8e8;
    --muted: #8892b0;
    --border: #233554;
    --success: #64ffda;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg); color: var(--text);
    padding: 20px;
  }
  .container { max-width: 800px; margin: 0 auto; }
  .card {
    background: var(--card);
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 20px;
    border: 1px solid var(--border);
  }
  h1 { font-size: 20px; color: var(--accent); margin-bottom: 16px; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th { text-align: left; color: var(--muted); padding: 10px 8px; border-bottom: 1px solid var(--border); font-weight: 500; }
  td { padding: 12px 8px; border-bottom: 1px solid rgba(255,255,255,0.05); }
  tr:last-child td { border-bottom: none; }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 8px;
    background: var(--accent2);
    font-size: 11px;
  }
  .num { font-weight: 600; color: var(--accent); }
  .link-input {
    width: 100%;
    background: #0d1b2a;
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 11px;
    font-family: monospace;
  }
  .stat-row { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
  .stat-item {
    flex: 1; min-width: 120px;
    background: rgba(255,255,255,0.03);
    border-radius: 12px;
    padding: 16px;
    text-align: center;
  }
  .stat-num { font-size: 24px; font-weight: 700; color: var(--accent); }
  .stat-label { font-size: 12px; color: var(--muted); margin-top: 4px; }
  .bar-container { height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; margin-top: 8px; }
  .bar-fill { height: 100%; background: var(--accent); border-radius: 3px; }
  .login-form { text-align: center; padding: 40px; }
  .login-form input {
    background: #0d1b2a; color: var(--text);
    border: 1px solid var(--border); border-radius: 8px;
    padding: 12px; font-size: 16px; width: 100%; max-width: 300px;
    text-align: center; margin: 16px 0;
  }
  .login-form input:focus { outline: none; border-color: var(--accent); }
  .btn {
    padding: 10px 28px; border: none; border-radius: 8px;
    font-size: 14px; cursor: pointer;
    background: var(--accent); color: white;
  }
  .btn:hover { background: #d63850; }
  .footer { text-align: center; color: var(--muted); font-size: 11px; margin-top: 20px; }
</style>
</head>
<body>
<div class="container" id="app"></div>

<script>
const API = '/api/admin/invite';
let password = localStorage.getItem('invite_pwd') || '';

function escapeHtml(t) {
  const d = document.createElement('div');
  d.textContent = t;
  return d.innerHTML;
}

async function loadStats() {
  const app = document.getElementById('app');
  if (!password) { renderLogin(); return; }

  try {
    const r = await fetch(`${API}/stats?password=${encodeURIComponent(password)}&days=30`);
    if (r.status === 403) { password = ''; localStorage.removeItem('invite_pwd'); renderLogin(); return; }
    const data = await r.json();
    renderStats(data);
  } catch(e) {
    app.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

function renderLogin() {
  document.getElementById('app').innerHTML = `
    <div class="card login-form">
      <h1>🔐 引流渠道统计</h1>
      <p style="color:var(--muted)">输入管理密码</p>
      <input type="password" id="pwd" placeholder="管理密码" autofocus
             onkeydown="if(event.key==='Enter') doLogin()" />
      <div><button class="btn" onclick="doLogin()">进入</button></div>
    </div>
  `;
}

function doLogin() {
  password = document.getElementById('pwd').value.trim();
  if (!password) return;
  localStorage.setItem('invite_pwd', password);
  loadStats();
}

function renderStats(data) {
  const channels = data.channels || [];
  const daily = data.daily || [];
  const maxTotal = Math.max(...channels.map(c => c.total), 1);

  let rows = channels.map(c => {
    const pct = (c.total / maxTotal * 100).toFixed(0);
    return `<tr>
      <td><strong>${escapeHtml(c.name)}</strong><br><span class="badge">${c.channel}</span></td>
      <td class="num">${c.total}</td>
      <td>${c.unique_ips}</td>
      <td><input class="link-input" value="${escapeHtml(c.link)}" readonly onclick="this.select()" /></td>
      <td><div class="bar-container"><div class="bar-fill" style="width:${pct}%"></div></div></td>
    </tr>`;
  }).join('');

  let dailyRows = daily.map(d =>
    `<tr><td>${d.day}</td><td class="num">${d.count}</td></tr>`
  ).join('');

  document.getElementById('app').innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <h1>📊 引流渠道统计</h1>
      <button class="btn" onclick="logout()" style="font-size:12px;padding:6px 16px">退出</button>
    </div>

    <div class="card">
      <div class="stat-row">
        <div class="stat-item">
          <div class="stat-num">${data.total}</div>
          <div class="stat-label">近${data.days}天总点击</div>
        </div>
        <div class="stat-item">
          <div class="stat-num">${channels.length}</div>
          <div class="stat-label">渠道数</div>
        </div>
        <div class="stat-item">
          <div class="stat-num">${data.daily?.[0]?.count || 0}</div>
          <div class="stat-label">今日点击</div>
        </div>
      </div>
    </div>

    <div class="card">
      <h1>📡 各渠道数据</h1>
      <table>
        <tr><th>渠道</th><th>点击</th><th>独立IP</th><th>跳转链接</th><th></th></tr>
        ${rows || '<tr><td colspan="5" style="text-align:center;color:var(--muted)">暂无数据</td></tr>'}
      </table>
    </div>

    <div class="card">
      <h1>📅 每日趋势（近30天）</h1>
      <table>
        <tr><th>日期</th><th>点击</th></tr>
        ${dailyRows || '<tr><td colspan="2" style="text-align:center;color:var(--muted)">暂无数据</td></tr>'}
      </table>
    </div>

    <div class="card">
      <h1>🔗 渠道链接速查</h1>
      ${channels.map(c => `<p style="margin:6px 0;font-size:13px">
        <strong>${escapeHtml(c.name)}</strong>：
        <code style="color:var(--accent);font-size:12px">${escapeHtml(c.link)}</code>
      </p>`).join('')}
      <p style="margin-top:12px;color:var(--muted);font-size:12px">
        💡 在抖音视频简介/评论放对应的链接，即可追踪来源
      </p>
    </div>

    <div class="footer">屿风 · 引流渠道归因系统</div>
  `;
}

function logout() {
  password = '';
  localStorage.removeItem('invite_pwd');
  renderLogin();
}

// 启动
loadStats();
</script>
</body>
</html>"""

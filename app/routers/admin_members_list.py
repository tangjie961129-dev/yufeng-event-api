"""会员列表页面 — 密码保护，查看 member_profiles 全表"""
import os

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text

from app.core.database import SessionLocal

router = APIRouter(prefix="/api/admin/members", tags=["会员管理"])

PASSWORD = os.environ.get("ADMIN_PASSWORD", "yufeng2026")

_ADMIN_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>屿风 · 会员列表</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #faf5ee; color: #3d3d3d; padding: 16px; min-height: 100vh;
}
h1 { font-size: 22px; color: #e94560; margin-bottom: 16px; text-align: center; }
.pwd-bar {
    background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04); text-align: center;
}
.pwd-bar input {
    border: 1px solid #e8ddd0; border-radius: 8px; padding: 10px 14px;
    font-size: 15px; width: 200px; outline: none; margin-right: 8px;
    background: #f8f4ee; color: #3d3d3d;
}
.pwd-bar input:focus { border-color: #e94560; box-shadow: 0 0 0 3px rgba(233,69,96,.08); }
.pwd-bar button {
    background: #e94560; color: #fff; border: none; border-radius: 8px;
    padding: 10px 20px; font-size: 15px; cursor: pointer;
}
.pwd-bar button:hover { background: #d43d55; }
.stats {
    display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px;
}
.stat-card {
    background: #fff; border-radius: 10px; padding: 12px 16px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04); flex: 1; min-width: 80px; text-align: center;
}
.stat-card .num { font-size: 24px; font-weight: bold; color: #e94560; }
.stat-card .label { font-size: 12px; color: #8a7a6a; margin-top: 4px; }
.table-wrap {
    background: #fff; border-radius: 12px; overflow-x: auto;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 600px; }
th {
    background: #f8f4ee; color: #5a4a3a; padding: 10px 8px; text-align: left;
    font-weight: 600; white-space: nowrap; position: sticky; top: 0;
}
td { padding: 8px; border-top: 1px solid #f0ebe3; vertical-align: top; }
tr:hover td { background: #faf5ee; }
.level-S { color: #e94560; font-weight: bold; }
.level-A { color: #d48a5a; font-weight: bold; }
.level-B { color: #8a7a6a; }
.level-C { color: #b8a898; }
.loading { text-align: center; padding: 40px; color: #8a7a6a; font-size: 14px; }
.error { text-align: center; padding: 20px; color: #e94560; font-size: 14px; }
.empty { text-align: center; padding: 40px; color: #8a7a6a; }
.footer { text-align: center; margin-top: 16px; font-size: 12px; color: #b8a898; }
</style>
</head>
<body>

<h1>📋 会员列表</h1>

<div class="pwd-bar">
    <input type="password" id="pwd" placeholder="管理密码" onkeydown="if(event.key==='Enter')load()">
    <button onclick="load()">查询</button>
</div>

<div id="stats" class="stats" style="display:none"></div>
<div id="table-area"><div class="loading">请输入密码查询</div></div>
<div class="footer" id="footer" style="display:none"></div>

<script>
async function load() {
    const pwd = document.getElementById('pwd').value;
    if (!pwd) { alert('请输入管理密码'); return; }
    document.getElementById('table-area').innerHTML = '<div class="loading">加载中...</div>';
    document.getElementById('stats').style.display = 'none';
    document.getElementById('footer').style.display = 'none';

    try {
        const r = await fetch('/api/admin/members/data?password=' + encodeURIComponent(pwd));
        if (!r.ok) {
            const txt = await r.text();
            document.getElementById('table-area').innerHTML = '<div class="error">' + txt + '</div>';
            return;
        }
        const json = await r.json();
        if (json.error) {
            document.getElementById('table-area').innerHTML = '<div class="error">' + json.error + '</div>';
            return;
        }
        render(json);
    } catch(e) {
        document.getElementById('table-area').innerHTML = '<div class="error">请求失败: ' + e.message + '</div>';
    }
}

function render(json) {
    const rows = json.rows || [];
    const total = json.total || 0;

    const stats = json.stats || {};
    document.getElementById('stats').style.display = 'flex';
    document.getElementById('stats').innerHTML =
        '<div class="stat-card"><div class="num">' + total + '</div><div class="label">总计</div></div>' +
        '<div class="stat-card"><div class="num">' + (stats.S||0) + '</div><div class="label">S级</div></div>' +
        '<div class="stat-card"><div class="num">' + (stats.A||0) + '</div><div class="label">A级</div></div>' +
        '<div class="stat-card"><div class="num">' + (stats.B||0) + '</div><div class="label">B级</div></div>' +
        '<div class="stat-card"><div class="num">' + (stats.C||0) + '</div><div class="label">C级</div></div>' +
        '<div class="stat-card"><div class="num">' + (stats.has_photo||0) + '</div><div class="label">有照片</div></div>';

    if (rows.length === 0) {
        document.getElementById('table-area').innerHTML = '<div class="empty">暂无数据</div>';
        return;
    }

    let html = '<div class="table-wrap"><table><thead><tr>' +
        '<th>ID</th><th>昵称</th><th>年龄</th><th>城市</th><th>属性</th>' +
        '<th>职业</th><th>收入</th><th>身高</th><th>体重</th><th>层级</th><th>注册时间</th></tr></thead><tbody>';

    for (const r of rows) {
        const levelClass = 'level-' + (r.level || '');
        const levelStr = r.level || '-';
        const ageStr = r.age != null ? r.age : (r.birth_info || '');
        html += '<tr>' +
            '<td>' + (r.id || '') + '</td>' +
            '<td>' + esc(r.nickname) + '</td>' +
            '<td>' + esc(ageStr) + '</td>' +
            '<td>' + esc(r.city) + '</td>' +
            '<td>' + esc(r.role_self) + '</td>' +
            '<td>' + esc(r.job) + '</td>' +
            '<td>' + esc(r.income) + '</td>' +
            '<td>' + (r.height || '') + '</td>' +
            '<td>' + (r.weight || '') + '</td>' +
            '<td class="' + levelClass + '">' + levelStr + '</td>' +
            '<td>' + (r.created_at || '').slice(0,10) + '</td>' +
            '</tr>';
    }

    html += '</tbody></table></div>';
    document.getElementById('table-area').innerHTML = html;
    document.getElementById('footer').style.display = 'block';
    document.getElementById('footer').textContent = '共 ' + total + ' 条记录 · 屿风会员档案';
}

function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
</script>
</body>
</html>'''

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def admin_members_page():
    return HTMLResponse(content=_ADMIN_HTML)

@router.get("/data")
def admin_members_data(password: str = Query(...)):
    if password != PASSWORD:
        return JSONResponse({"error": "密码错误"}, status_code=403)

    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT id, nickname, city, age, role_self, income, job,
                   height, weight, body_type, education, birth_info,
                   level, level_score, source, created_at, updated_at,
                   CASE WHEN photo_path != '' AND photo_path IS NOT NULL THEN 1 ELSE 0 END as has_photo
            FROM member_profiles
            ORDER BY id DESC
        """)).fetchall()

        total = len(rows)

        stats = db.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE level = 'S') as s,
                COUNT(*) FILTER (WHERE level = 'A') as a,
                COUNT(*) FILTER (WHERE level = 'B') as b,
                COUNT(*) FILTER (WHERE level = 'C') as c,
                COUNT(*) FILTER (WHERE photo_path != '' AND photo_path IS NOT NULL) as has_photo
            FROM member_profiles
        """)).fetchone()

        result = {
            "total": total,
            "rows": [dict(r._mapping) for r in rows],
            "stats": {
                "S": stats.s, "A": stats.a, "B": stats.b, "C": stats.c,
                "has_photo": stats.has_photo,
            },
        }
        return result
    finally:
        db.close()

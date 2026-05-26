"""朋友圈规则管理页面 — 密码保护

路径: /admin/rules (在 Nginx 中代理为 /api/admin/rules)
功能: 查看/编辑 moments_config.json 中的所有 Prompt 规则
安全: 密码登录 + 连续失败5次限频5分钟
"""
import json
import os
import time
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, HTTPException, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter(prefix="/api/admin/rules", tags=["朋友圈规则管理"])

# 配置文件路径
CONFIG_PATH = "/home/ubuntu/yufeng-daily/config/moments_config.json"
PASSWORD = os.environ.get("RULES_PASSWORD", "yufeng2026")

# ─── 限频保护 ────────────────────────────────────────────────

_fail_counts: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 5     # 连续失败次数
_RATE_WINDOW = 300  # 限频窗口（秒）


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    fails = _fail_counts[ip]
    # 清理过期记录
    _fail_counts[ip] = [t for t in fails if now - t < _RATE_WINDOW]
    if len(_fail_counts[ip]) >= _RATE_LIMIT:
        retry_after = int(_RATE_WINDOW - (now - _fail_counts[ip][0]))
        if retry_after > 0:
            raise HTTPException(
                status_code=429,
                detail=f"密码错误次数过多，请 {retry_after} 秒后再试"
            )


def _record_fail(ip: str) -> None:
    _fail_counts[ip].append(time.time())


def _record_success(ip: str) -> None:
    # 成功后清除记录
    _fail_counts.pop(ip, None)


# ─── 密码验证 ────────────────────────────────────────────────


def _check_password(password: str, ip: str = "") -> bool:
    _check_rate_limit(ip)
    if password == PASSWORD:
        _record_success(ip)
        return True
    _record_fail(ip)
    return False


# ─── 读取/写入配置 ────────────────────────────────────────────


def _read_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, OSError):
        return {}


def _write_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


# ─── API: 获取规则（需密码） ────────────────────────────────


@router.get("/data")
def get_rules(
    password: str = Query(...),
    request: Request = None,
):
    """获取当前所有规则（需密码验证）"""
    ip = request.client.host if request else ""
    if not _check_password(password, ip):
        raise HTTPException(status_code=403, detail="密码错误")
    config = _read_config()
    prompts = config.get("prompts", {})
    rules_list = [
        {"key": "member_image_suffix", "label": "📷 会员配图提示词后缀",
         "value": prompts.get("member_image_suffix", ""),
         "hint": "拼在用户配图prompt末尾，控制配图风格细节"},
        {"key": "member_comment_instruction", "label": "✍️ 会员点评文案规则",
         "value": prompts.get("member_comment_instruction", ""),
         "hint": "DeepSeek生成会员点评时使用的system提示"},
        {"key": "match_copy_rule", "label": "💕 配对喜报文案规则",
         "value": prompts.get("match_copy_rule", ""),
         "hint": "配对成功推送的文案风格要求"},
        {"key": "match_image_rule", "label": "📱 配对配图提示词规则",
         "value": prompts.get("match_image_rule", ""),
         "hint": "配对喜报配图的prompt模板，{skin}{scene}会被自动替换"},
        {"key": "tip_copy_rule", "label": "💡 恋爱技巧文案规则",
         "value": prompts.get("tip_copy_rule", ""),
         "hint": "每日恋爱技巧/人格观察文案风格"},
        {"key": "tip_image_rule", "label": "🎨 Tips海报图片生成规则",
         "value": prompts.get("tip_image_rule", ""),
         "hint": "MBTI/人格观察海报的完整prompt模板，{scene}{title}自动替换"},
        {"key": "deepseek_system", "label": "🤖 DeepSeek 系统提示词",
         "value": prompts.get("deepseek_system", ""),
         "hint": "AI模型的整体角色设定，影响所有文案风格"},
        {"key": "assistant_sanitize_note", "label": "🔒 发送前脱敏规则",
         "value": prompts.get("assistant_sanitize_note", ""),
         "hint": "推送到企微前的自动处理规则"},
    ]
    return {"rules": rules_list, "updated_at": config.get("updated_at", "")}


# ─── API: 保存规则（需密码） ────────────────────────────────


@router.post("/save")
def save_rule(
    password: str = Form(...),
    key: str = Form(...),
    value: str = Form(...),
    request: Request = None,
):
    """保存单条规则（需密码验证）"""
    ip = request.client.host if request else ""
    if not _check_password(password, ip):
        raise HTTPException(status_code=403, detail="密码错误")

    config = _read_config()
    prompts = config.setdefault("prompts", {})
    old_value = prompts.get(key, "")
    prompts[key] = value
    config["updated_at"] = date.today().isoformat()
    _write_config(config)

    return {"success": True, "key": key, "old_value": old_value[:80], "new_value": value[:80]}


# ─── 前端页面 ────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def rules_page():
    """朋友圈规则管理页面"""
    return HTMLResponse(content=_PAGE_HTML)


_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>屿风 · 朋友圈规则管理</title>
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
    --error: #ff6b6b;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  .container {
    width: 100%;
    max-width: 720px;
  }
  .card {
    background: var(--card);
    border-radius: 16px;
    padding: 32px;
    margin-bottom: 20px;
    border: 1px solid var(--border);
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  }
  h1 {
    font-size: 20px;
    color: var(--accent);
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .subtitle {
    color: var(--muted);
    font-size: 13px;
    margin-bottom: 24px;
  }
  .rule-item {
    margin-bottom: 20px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border);
  }
  .rule-item:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
  .rule-label {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 4px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .rule-hint {
    font-size: 11px;
    color: var(--muted);
    margin-bottom: 8px;
  }
  textarea {
    width: 100%;
    background: #0d1b2a;
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    font-size: 13px;
    line-height: 1.5;
    font-family: 'SF Mono', 'Fira Code', monospace;
    resize: vertical;
    min-height: 60px;
    transition: border-color 0.2s;
  }
  textarea:focus {
    outline: none;
    border-color: var(--accent);
  }
  textarea.large { min-height: 100px; }
  .btn-row {
    display: flex;
    gap: 8px;
    margin-top: 8px;
    justify-content: flex-end;
  }
  .btn {
    padding: 8px 20px;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-primary {
    background: var(--accent);
    color: white;
  }
  .btn-primary:hover { background: #d63850; }
  .btn-primary:disabled {
    background: #5a1f2a;
    color: #888;
    cursor: not-allowed;
  }
  .btn-secondary {
    background: var(--accent2);
    color: var(--text);
  }
  .btn-secondary:hover { background: #1a4a7a; }
  .toast {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 13px;
    z-index: 1000;
    transition: all 0.3s;
    opacity: 0;
    transform: translateY(-10px);
  }
  .toast.show { opacity: 1; transform: translateY(0); }
  .toast.success { background: #1b4332; color: var(--success); border: 1px solid var(--success); }
  .toast.error { background: #3d0c11; color: var(--error); border: 1px solid var(--error); }
  .login-form { text-align: center; }
  .login-form h1 { justify-content: center; }
  .password-input {
    background: #0d1b2a;
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 16px;
    width: 100%;
    max-width: 300px;
    font-size: 16px;
    text-align: center;
    margin: 16px 0;
  }
  .password-input:focus { outline: none; border-color: var(--accent); }
  .footer {
    text-align: center;
    color: var(--muted);
    font-size: 12px;
    margin-top: 16px;
  }
  .updated-at {
    text-align: right;
    color: var(--muted);
    font-size: 11px;
  }
  .badge {
    display: inline-block;
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 10px;
    background: var(--accent2);
    color: var(--muted);
  }
  @media (max-width: 480px) {
    .card { padding: 20px; }
  }
</style>
</head>
<body>
<div class="container" id="app"></div>
<div id="toast" class="toast"></div>

<script>
const API = '/api/admin/rules';

// ─── 状态 ───
let state = { password: localStorage.getItem('rules_pwd') || '' };

// ─── 工具 ───
function toast(msg, type = 'success') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type} show`;
  setTimeout(() => el.classList.remove('show'), 3000);
}

// ─── 页面渲染 ───
function render() {
  const app = document.getElementById('app');

  if (!state.loggedIn) {
    app.innerHTML = `
      <div class="card login-form">
        <h1>🔐 屿风规则管理</h1>
        <p class="subtitle">输入管理密码进入</p>
        <input type="password" class="password-input" id="pwdInput"
               placeholder="管理密码" autofocus
               onkeydown="if(event.key==='Enter') doLogin()" />
        <div>
          <button class="btn btn-primary" onclick="doLogin()">进入管理</button>
        </div>
      </div>
    `;
    if (state.password) document.getElementById('pwdInput').value = state.password;
    return;
  }

  // 已登录：加载规则
  loadRules();
}

async function doLogin() {
  const pwd = document.getElementById('pwdInput').value.trim();
  if (!pwd) { toast('请输入密码', 'error'); return; }

  // 验证密码
  try {
    const r = await fetch(`${API}/data?password=${encodeURIComponent(pwd)}`);
    if (!r.ok) { toast('密码错误', 'error'); return; }
    state.password = pwd;
    state.loggedIn = true;
    localStorage.setItem('rules_pwd', pwd);
    render();
  } catch(e) {
    toast('网络错误: ' + e.message, 'error');
  }
}

async function loadRules() {
  const app = document.getElementById('app');
  app.innerHTML = `<div class="card" style="text-align:center;padding:60px"><p>加载中...</p></div>`;

  try {
    const r = await fetch(`${API}/data?password=${encodeURIComponent(state.password)}`);
    if (r.status === 403) {
      state.loggedIn = false;
      localStorage.removeItem('rules_pwd');
      render();
      return;
    }
    const data = await r.json();
    renderRules(data);
  } catch(e) {
    app.innerHTML = `<div class="card" style="text-align:center;padding:60px"><p style="color:var(--error)">加载失败: ${e.message}</p></div>`;
  }
}

function renderRules(data) {
  const app = document.getElementById('app');
  const rules = data.rules || [];

  let itemsHtml = '';
  let savingState = {};

  rules.forEach((rule, idx) => {
    const isLong = rule.key === 'deepseek_system' || rule.key === 'member_image_suffix';
    itemsHtml += `
      <div class="rule-item">
        <div class="rule-label">
          <span>${rule.label}</span>
          <span class="badge">${rule.key}</span>
        </div>
        <div class="rule-hint">${rule.hint}</div>
        <textarea class="${isLong ? 'large' : ''}" id="ta_${idx}"
          placeholder="暂无内容">${escapeHtml(rule.value)}</textarea>
        <div class="btn-row">
          <button class="btn btn-secondary" onclick="resetRule(${idx})">重置</button>
          <button class="btn btn-primary" id="save_${idx}" onclick="saveRule(${idx})">保存</button>
        </div>
      </div>
    `;
    savingState[idx] = { original: rule.value, key: rule.key };
  });

  app.innerHTML = `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <h1>📝 朋友圈规则管理</h1>
          <p class="subtitle">修改后保存，下次朋友圈生成自动生效</p>
        </div>
        <button class="btn btn-secondary" onclick="logout()" style="font-size:12px">退出</button>
      </div>
      ${data.updated_at ? `<div class="updated-at">上次更新: ${data.updated_at}</div>` : ''}
    </div>
    <div class="card">
      ${itemsHtml}
    </div>
    <div class="card" style="text-align:center">
      <button class="btn btn-primary" onclick="saveAll()" style="padding:10px 40px;font-size:15px">💾 保存全部修改</button>
      <p style="color:var(--muted);font-size:11px;margin-top:8px">修改后请到企微点「朋友圈预览」确认效果</p>
    </div>
    <div class="footer">屿风 · moments_config.json 在线编辑</div>
  `;

  window.__savingState = savingState;
  window.__rulesCount = rules.length;
  window.__ruleKeys = rules.map(r => r.key);
}

async function saveRule(idx) {
  const ta = document.getElementById(`ta_${idx}`);
  const btn = document.getElementById(`save_${idx}`);
  const key = window.__ruleKeys[idx];
  const value = ta.value.trim();

  btn.disabled = true;
  btn.textContent = '保存中...';

  try {
    const form = new URLSearchParams();
    form.append('password', state.password);
    form.append('key', key);
    form.append('value', value);

    const r = await fetch(`${API}/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    });
    if (r.ok) {
      toast('✅ 保存成功');
      window.__savingState[idx].original = value;
    } else {
      const err = await r.json();
      toast('❌ ' + (err.detail || '保存失败'), 'error');
    }
  } catch(e) {
    toast('❌ 网络错误: ' + e.message, 'error');
  }

  btn.disabled = false;
  btn.textContent = '保存';
}

async function saveAll() {
  const count = window.__rulesCount;
  for (let i = 0; i < count; i++) {
    const ta = document.getElementById(`ta_${i}`);
    const key = window.__ruleKeys[i];
    const value = ta.value.trim();

    const form = new URLSearchParams();
    form.append('password', state.password);
    form.append('key', key);
    form.append('value', value);

    try {
      await fetch(`${API}/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form.toString(),
      });
    } catch(e) {
      toast(`保存 "${key}" 失败: ${e.message}`, 'error');
      return;
    }
  }
  toast('✅ 全部保存成功');
}

function resetRule(idx) {
  const original = window.__savingState[idx].original;
  document.getElementById(`ta_${idx}`).value = escapeHtml(original);
}

function logout() {
  state.loggedIn = false;
  state.password = '';
  localStorage.removeItem('rules_pwd');
  render();
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

// ─── 启动 ───
render();
</script>
</body>
</html>
"""

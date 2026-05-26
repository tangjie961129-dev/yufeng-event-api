"""抖音引流中间页 — 渠道归因 + 企微跳转

路径: go.yufeng.team/xxx
功能: 品牌展示 + 记录渠道点击 + 引导加企微
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import Session

from app.core.database import get_db, Base

router = APIRouter(prefix="/invite", tags=["抖音引流归因"])

# ─── 数据库模型 ──────────────────────────────────────────────


class InviteClick(Base):
    """渠道点击记录"""
    __tablename__ = "invite_clicks"

    id = Column(Integer, primary_key=True, index=True)
    click_id = Column(String(32), unique=True, index=True, default=lambda: uuid.uuid4().hex[:16])
    channel = Column(String(50), default="", index=True, comment="渠道标识")
    ip = Column(String(50), default="")
    user_agent = Column(String(500), default="")
    referer = Column(String(500), default="")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# 表会在 main.py startup 时自动创建（已有 Base.metadata.create_all）


# ─── 配置 ────────────────────────────────────────────────────

# 企微联系我跳转 URL Scheme（从企微后台获取）
# 格式: weixin://dl/business/?t=XXXXX
# 你可以从这里获取: 企微后台 → 客户联系 → 加客户 → 联系我二维码 → 生成URL Scheme
WECOM_URL_SCHEME = "weixin://dl/business/?t=YOUR_TICKET_HERE"

# 各渠道的企微跳转链接（不同渠道可以配不同ticket，实现精确归因）
CHANNEL_WECOM_URLS = {
    "default": "weixin://dl/business/?t=YOUR_TICKET_HERE",
}

# 渠道名称映射（展示用）
CHANNEL_NAMES = {
    "dy_a": "抖音号A",
    "dy_b": "抖音号B",
    "dy_c": "抖音号C",
}


def _get_channel_wecom_url(channel: str) -> str:
    return CHANNEL_WECOM_URLS.get(channel) or CHANNEL_WECOM_URLS["default"]


def _get_channel_name(channel: str) -> str:
    return CHANNEL_NAMES.get(channel, f"渠道:{channel}")


# ─── 记录点击 ────────────────────────────────────────────────


def _record_click(db: Session, channel: str, request: Request) -> str:
    """记录渠道点击，返回 click_id"""
    click = InviteClick(
        click_id=uuid.uuid4().hex[:16],
        channel=channel,
        ip=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", "")[:500],
        referer=request.headers.get("referer", "")[:500],
    )
    db.add(click)
    db.commit()
    return click.click_id


# ─── 引流中间页 ──────────────────────────────────────────────


@router.get("/{channel:str}", response_class=HTMLResponse)
def invite_page(channel: str, request: Request, db: Session = Depends(get_db)):
    """渠道引流中间页

    访问: go.yufeng.team/invite/dy_a
    功能: 记录点击 + 展示品牌 + 引导加企微
    """
    click_id = _record_click(db, channel, request)
    channel_name = _get_channel_name(channel)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>屿风 · 彩虹相亲</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    color: #e8e8e8;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px;
    overflow: hidden;
  }}
  .bg-circle {{
    position: fixed;
    border-radius: 50%;
    opacity: 0.08;
    pointer-events: none;
  }}
  .bg-circle.c1 {{ width: 400px; height: 400px; background: #e94560; top: -100px; right: -100px; }}
  .bg-circle.c2 {{ width: 300px; height: 300px; background: #533483; bottom: -50px; left: -80px; }}
  .card {{
    background: rgba(22, 33, 62, 0.85);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(233, 69, 96, 0.2);
    border-radius: 24px;
    padding: 40px 32px;
    width: 100%;
    max-width: 400px;
    text-align: center;
    position: relative;
    z-index: 1;
    box-shadow: 0 20px 60px rgba(0,0,0,0.4);
  }}
  .logo {{
    width: 72px;
    height: 72px;
    border-radius: 18px;
    background: linear-gradient(135deg, #e94560, #533483);
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 16px;
    font-size: 32px;
    font-weight: bold;
    color: white;
    box-shadow: 0 8px 24px rgba(233, 69, 96, 0.3);
  }}
  h1 {{ font-size: 22px; margin-bottom: 8px; font-weight: 600; }}
  .subtitle {{ color: #8892b0; font-size: 14px; margin-bottom: 28px; line-height: 1.6; }}
  .feature-list {{ text-align: left; margin-bottom: 28px; }}
  .feature-item {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 0;
    font-size: 14px;
    color: #ccd6f6;
    border-bottom: 1px solid rgba(255,255,255,0.05);
  }}
  .feature-item:last-child {{ border-bottom: none; }}
  .feature-icon {{ font-size: 18px; width: 28px; text-align: center; }}
  .btn {{
    display: block;
    width: 100%;
    padding: 16px;
    border: none;
    border-radius: 14px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
    text-decoration: none;
  }}
  .btn-primary {{
    background: linear-gradient(135deg, #e94560, #d63850);
    color: white;
    margin-bottom: 12px;
    box-shadow: 0 8px 24px rgba(233, 69, 96, 0.4);
  }}
  .btn-primary:active {{ transform: scale(0.97); opacity: 0.9; }}
  .btn-secondary {{
    background: rgba(255,255,255,0.06);
    color: #8892b0;
    font-size: 13px;
    padding: 12px;
  }}
  .btn-secondary:active {{ background: rgba(255,255,255,0.1); }}
  .tag {{
    display: inline-block;
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 10px;
    background: rgba(233, 69, 96, 0.15);
    color: #e94560;
    margin-bottom: 20px;
  }}
  .footer {{ margin-top: 20px; font-size: 11px; color: #495670; }}
  .toast {{
    position: fixed;
    top: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: #1b4332;
    color: #64ffda;
    padding: 12px 24px;
    border-radius: 10px;
    font-size: 13px;
    z-index: 999;
    opacity: 0;
    transition: opacity 0.3s;
    pointer-events: none;
  }}
  .toast.show {{ opacity: 1; }}
</style>
</head>
<body>
<div class="bg-circle c1"></div>
<div class="bg-circle c2"></div>
<div class="card">
  <div class="logo">屿</div>
  <h1>屿风 · 彩虹相亲</h1>
  <p class="subtitle">为男同群体打造的真诚交友平台<br>真实资料 · 精准匹配 · 认真脱单</p>

  <div class="tag">🤝 {channel_name} · 专属通道</div>

  <div class="feature-list">
    <div class="feature-item">
      <span class="feature-icon">✅</span>
      <span>实名认证，真实资料可查</span>
    </div>
    <div class="feature-item">
      <span class="feature-icon">🎯</span>
      <span>AI智能匹配，多维度推荐</span>
    </div>
    <div class="feature-item">
      <span class="feature-icon">🔒</span>
      <span>隐私保护，敏感信息隐藏</span>
    </div>
    <div class="feature-item">
      <span class="feature-icon">💬</span>
      <span>专业红娘1对1牵线服务</span>
    </div>
  </div>

  <button class="btn btn-primary" onclick="showQR()">
    💬 添加企业微信了解详情
  </button>
</div>

<div id="qrOverlay" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.85);z-index:99;align-items:center;justify-content:center;flex-direction:column;font-family:sans-serif">
  <div style="background:#fff;border-radius:20px;padding:32px 28px;text-align:center;max-width:320px;width:90%">
    <p style="font-size:17px;color:#1a1a1a;font-weight:600;margin-bottom:20px">长按识别添加屿风企微</p>
    <img src="/static/wecom-qr.png" style="width:200px;height:200px;border-radius:12px;display:block;margin:0 auto" alt="屿风企微二维码" />
    <p style="font-size:13px;color:#999;margin-top:14px">打开微信或企业微信扫一扫</p>
    <button onclick="hideQR()" style="margin-top:18px;padding:12px 48px;border:none;background:#e94560;color:#fff;border-radius:12px;font-size:15px;font-weight:600;cursor:pointer">关闭</button>
  </div>
</div>

<div class="footer">
  © 2026 屿风 · {channel_name}<br>
  已在 {datetime.now().strftime("%H:%M")} 记录您的访问
</div>

<script>
function jumpWecom() {{
</script>

<!-- 渠道统计像素 -->
<img src="/invite/_pixel/{channel}?cid={click_id}" style="display:none" />
</body>
</html>"""
    return HTMLResponse(content=html)


# ─── 统计像素（用于记录页面展示） ──────────────────────────


@router.get("/_pixel/{channel}")
def pixel(channel: str, cid: str = Query(""), db: Session = Depends(get_db)):
    """1x1 透明像素，用于统计页面浏览量"""
    return HTMLResponse(
        content="<svg xmlns='http://www.w3.org/2000/svg' width='1' height='1'/>",
        media_type="image/svg+xml",
    )


# ─── 根路径跳转 ──────────────────────────────────────────────


@router.get("")
def invite_root(db: Session = Depends(get_db)):
    """不带渠道参数时，跳转到默认渠道"""
    return RedirectResponse(url="/invite/default")

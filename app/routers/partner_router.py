import os
"""渠道主分销体系 — 群主/博主合作引流

模式：渠道主发链接 → 客户填表 → 佣金自动记录
- 填表佣金：2元/人
- 成交分润：后续付费的20%
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import Column, Integer, String, DateTime, Text, DECIMAL, ForeignKey, func
from sqlalchemy.orm import Session

from app.core.database import get_db, Base

router = APIRouter(prefix="/partner", tags=["渠道主分销"])


# ─── 数据库模型 ──────────────────────────────────────────────


class ChannelPartner(Base):
    """渠道主"""
    __tablename__ = "channel_partners"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(String(32), unique=True, index=True, default=lambda: uuid.uuid4().hex[:16])
    name = Column(String(50), default="", comment="渠道主称呼")
    phone = Column(String(20), default="", comment="手机号")
    wechat = Column(String(50), default="", comment="微信号")
    source = Column(String(30), default="wechat", comment="渠道来源：wechat/xiaohongshu/douyin")
    status = Column(String(20), default="active", index=True, comment="active/disabled")
    total_registers = Column(Integer, default=0, comment="累计填表数")
    total_deals = Column(Integer, default=0, comment="累计成交数")
    total_commission = Column(DECIMAL(10, 2), default=0, comment="累计佣金")
    withdrawable = Column(DECIMAL(10, 2), default=0, comment="可提现余额")
    password_hash = Column(String(100), default="", comment="简易密码")
    qr_code = Column(Text, default="", comment="企微联系我二维码URL")
    employee_userid = Column(String(100), default="", comment="企微员工ID")
    config_id = Column(String(100), default="", comment="企微联系我配置ID")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PartnerRegister(Base):
    """渠道主带来的填表记录"""
    __tablename__ = "partner_registers"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(String(32), ForeignKey("channel_partners.partner_id"), index=True, nullable=False)
    register_id = Column(String(32), unique=True, default=lambda: uuid.uuid4().hex[:16])
    customer_name = Column(String(50), default="", comment="填表人称呼")
    customer_phone = Column(String(20), default="", comment="填表人手机")
    status = Column(String(20), default="registered", index=True, comment="registered(填表)/dealt(成交)")
    register_fee = Column(DECIMAL(10, 2), default=2.00, comment="填表佣金")
    deal_fee = Column(DECIMAL(10, 2), default=0, comment="成交分润")
    deal_amount = Column(DECIMAL(10, 2), default=0.00, comment="成交金额")
    total_fee = Column(DECIMAL(10, 2), default=2.00, comment="总佣金=填表+分润")
    settled = Column(String(20), default="pending", comment="pending/settled")
    external_userid = Column(String(100), default="", comment="企微客户ExternalUserID")
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PartnerWithdraw(Base):
    """渠道主提现申请"""
    __tablename__ = "partner_withdraws"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(String(32), ForeignKey("channel_partners.partner_id"), index=True)
    amount = Column(DECIMAL(10, 2), nullable=False)
    status = Column(String(20), default="pending", index=True, comment="pending/done/rejected")
    method = Column(String(20), default="wechat", comment="wechat/alipay/bank")
    account = Column(String(100), default="")
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)


# ─── 工具函数 ────────────────────────────────────────────────

COMMISSION_RATE = Decimal("0.20")  # 成交分润20%
REGISTER_FEE = Decimal("2.00")     # 填表2元


def _generate_partner_id() -> str:
    """生成8位渠道ID"""
    import random
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "P" + "".join(random.choices(chars, k=7))


# ─── API ─────────────────────────────────────────────────────


@router.get("/register")
def partner_register(
    name: str = Query(...),
    phone: str = Query(""),
    wechat: str = Query(""),
    source: str = Query("wechat"),
    password: str = Query(...),
    db: Session = Depends(get_db),
):
    """渠道主自助注册API（手机号唯一）"""
    if not name or not password:
        raise HTTPException(status_code=400, detail="姓名和密码不能为空")
    if not phone:
        raise HTTPException(status_code=400, detail="手机号不能为空")

    existing = db.query(ChannelPartner).filter(ChannelPartner.phone == phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="该手机号已注册，请直接登录")

    partner_id = _generate_partner_id()
    partner = ChannelPartner(
        partner_id=partner_id,
        name=name,
        phone=phone,
        wechat=wechat,
        source=source,
        password_hash=password,
        status="pending",
    )
    db.add(partner)
    db.commit()

    return {
        "success": True,
        "partner_id": partner_id,
        "name": name,
        "phone": phone,
        "status": "pending",
        "message": "注册成功，请等待管理员审核（一般24小时内通过）",
    }


@router.get("/login")
def partner_login(
    partner_id: str = Query(""),
    password: str = Query(...),
    phone: str = Query(""),
    db: Session = Depends(get_db),
):
    """渠道主登录，支持partner_id或手机号"""
    if phone:
        partner = db.query(ChannelPartner).filter(
            ChannelPartner.phone == phone,
            ChannelPartner.password_hash == password,
            ChannelPartner.status == "active",
        ).first()
    else:
        partner = db.query(ChannelPartner).filter(
            ChannelPartner.partner_id == partner_id,
            ChannelPartner.password_hash == password,
            ChannelPartner.status == "active",
        ).first()
    if not partner:
        raise HTTPException(status_code=403, detail="ID或密码错误")
    return {
        "success": True,
        "partner_id": partner.partner_id,
        "name": partner.name,
        "status": partner.status,
        "total_registers": partner.total_registers,
        "total_commission": float(partner.total_commission),
        "withdrawable": float(partner.withdrawable),
    }


@router.get("/stats")
def partner_stats(
    partner_id: str = Query(...),
    password: str = Query(...),
    db: Session = Depends(get_db),
):
    """渠道主数据统计"""
    partner = db.query(ChannelPartner).filter(
        ChannelPartner.partner_id == partner_id,
        ChannelPartner.password_hash == password,
    ).first()
    if not partner:
        raise HTTPException(status_code=403, detail="验证失败")

    registers = db.query(PartnerRegister).filter(
        PartnerRegister.partner_id == partner_id
    ).order_by(PartnerRegister.created_at.desc()).limit(50).all()

    withdraws = db.query(PartnerWithdraw).filter(
        PartnerWithdraw.partner_id == partner_id
    ).order_by(PartnerWithdraw.created_at.desc()).limit(20).all()

    return {
        "name": partner.name,
        "partner_id": partner.partner_id,
        "total_registers": partner.total_registers,
        "total_deals": partner.total_deals,
        "total_commission": float(partner.total_commission),
        "withdrawable": float(partner.withdrawable),
        "register_list": [
            {
                "name": r.customer_name,
                "status": r.status,
                "fee": float(r.total_fee),
                "date": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            }
            for r in registers
        ],
        "withdraw_list": [
            {
                "amount": float(w.amount),
                "status": w.status,
                "date": w.created_at.strftime("%Y-%m-%d %H:%M") if w.created_at else "",
            }
            for w in withdraws
        ],
    }


@router.get("/withdraw")
def partner_withdraw(
    partner_id: str = Query(...),
    password: str = Query(...),
    amount: float = Query(...),
    method: str = Query("wechat"),
    account: str = Query(""),
    db: Session = Depends(get_db),
):
    """渠道主申请提现"""
    partner = db.query(ChannelPartner).filter(
        ChannelPartner.partner_id == partner_id,
        ChannelPartner.password_hash == password,
    ).first()
    if not partner:
        raise HTTPException(status_code=403, detail="验证失败")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="提现金额无效")
    if Decimal(str(amount)) > partner.withdrawable:
        raise HTTPException(status_code=400, detail=f"可提现余额不足，当前余额：{float(partner.withdrawable)}元")

    wd = PartnerWithdraw(
        partner_id=partner_id,
        amount=Decimal(str(amount)),
        method=method,
        account=account,
    )
    partner.withdrawable -= Decimal(str(amount))
    db.add(wd)
    db.commit()

    return {
        "success": True,
        "amount": amount,
        "remaining": float(partner.withdrawable),
        "status": "pending",
    }


# ─── 渠道主首页（自助注册入口） ────────────────────────────


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def partner_home():
    """渠道主首页：注册入口"""
    return HTMLResponse(content=_HOME_HTML)


# ─── 渠道主页（移动端H5） ─────────────────────────────────


@router.get("/dashboard", response_class=HTMLResponse)
def partner_dashboard():
    """渠道主移动端面板"""
    return HTMLResponse(content=_DASHBOARD_HTML)


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>屿风 · 渠道合作</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
    background: #1a1a2e; color: #e8e8e8;
    min-height: 100vh;
  }
  .container { max-width: 480px; margin: 0 auto; padding: 16px; }
  .card {
    background: #16213e;
    border-radius: 16px; padding: 24px;
    margin-bottom: 16px;
    border: 1px solid #233554;
  }
  h1 { font-size: 20px; color: #e94560; margin-bottom: 16px; }
  .stat-row { display: flex; gap: 12px; margin-bottom: 16px; }
  .stat-item {
    flex: 1; text-align: center;
    background: rgba(255,255,255,0.03);
    border-radius: 12px; padding: 16px;
  }
  .stat-num { font-size: 24px; font-weight: 700; color: #e94560; }
  .stat-label { font-size: 11px; color: #8892b0; margin-top: 4px; }
  .input-group { margin-bottom: 12px; }
  .input-group label { font-size: 12px; color: #8892b0; display: block; margin-bottom: 4px; }
  .input-group input {
    width: 100%; padding: 12px;
    background: #0d1b2a; color: #e8e8e8;
    border: 1px solid #233554; border-radius: 8px;
    font-size: 14px;
  }
  .input-group input:focus { outline: none; border-color: #e94560; }
  .btn {
    width: 100%; padding: 14px;
    border: none; border-radius: 10px;
    font-size: 15px; font-weight: 600;
    cursor: pointer;
    background: linear-gradient(135deg, #e94560, #d63850);
    color: white;
    margin-bottom: 8px;
  }
  .btn:active { opacity: 0.8; }
  .btn-sm { padding: 10px; font-size: 13px; }
  .tab-bar {
    display: flex;
    background: #0d1b2a;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 16px;
  }
  .tab {
    flex: 1; text-align: center; padding: 10px;
    font-size: 13px; cursor: pointer;
    color: #8892b0;
  }
  .tab.active { background: #e94560; color: white; }
  .link-box {
    background: #0d1b2a;
    border-radius: 8px; padding: 10px;
    font-size: 12px; word-break: break-all;
    margin: 8px 0;
    color: #64ffda;
  }
  .list-item {
    display: flex; justify-content: space-between;
    padding: 10px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    font-size: 13px;
  }
  .list-item:last-child { border-bottom: none; }
  .badge {
    font-size: 11px; padding: 2px 8px;
    border-radius: 8px;
    background: #0f3460; color: #8892b0;
  }
  .badge.success { background: #1b4332; color: #64ffda; }
  .toast {
    position: fixed; top: 16px; left: 50%;
    transform: translateX(-50%);
    background: #1b4332; color: #64ffda;
    padding: 12px 24px; border-radius: 10px;
    font-size: 13px; z-index: 999;
    opacity: 0; transition: opacity 0.3s;
    pointer-events: none;
  }
  .toast.show { opacity: 1; }
  .hidden { display: none; }
</style>
</head>
<body>
<div id="toast" class="toast"></div>
<div class="container" id="app"></div>
<script>
const API = '/partner';

function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg; el.className = 'toast show';
  setTimeout(() => el.className = 'toast', 2500);
}

// ─── 页面路由 ───
function render() {
  const pid = localStorage.getItem('partner_id');
  const pwd = localStorage.getItem('partner_pwd');
  if (pid && pwd) { loadDashboard(pid, pwd); return; }
  renderLogin();
}

function renderLogin() {
  document.getElementById('app').innerHTML = `
    <div class="card" style="text-align:center">
      <h1>🤝 屿风渠道合作</h1>
      <p style="color:#8892b0;font-size:13px;margin-bottom:20px">
        群主/博主推广合作 ← 填表2元/人 + 成交20%分润
      </p>
      <div class="input-group">
        <label>渠道ID</label>
        <input id="pid" placeholder="输入你的渠道ID" />
      </div>
      <div class="input-group">
        <label>密码</label>
        <input id="pwd" type="password" placeholder="密码" />
      </div>
      <button class="btn" onclick="doLogin()">登录</button>
      <p style="font-size:12px;color:#495670;margin-top:12px">
        还没有ID？联系屿风获取
      </p>
    </div>
  `;
}

async function doLogin() {
  const pid = document.getElementById('pid').value.trim();
  const pwd = document.getElementById('pwd').value.trim();
  if (!pid || !pwd) { toast('请填写ID和密码'); return; }
  try {
    const r = await fetch(API + '/login?partner_id=' + encodeURIComponent(pid) + '&password=' + encodeURIComponent(pwd));
    if (!r.ok) { toast('ID或密码错误'); return; }
    const data = await r.json();
    localStorage.setItem('partner_id', pid);
    localStorage.setItem('partner_pwd', pwd);
    renderDashboard(data);
  } catch(e) { toast('网络错误: ' + e.message); }
}

async function loadDashboard(pid, pwd) {
  try {
    const r = await fetch(API + '/stats?partner_id=' + encodeURIComponent(pid) + '&password=' + encodeURIComponent(pwd));
    if (!r.ok) { localStorage.removeItem('partner_id'); localStorage.removeItem('partner_pwd'); renderLogin(); return; }
    const data = await r.json();
    renderDashboard(data);
  } catch(e) { toast('加载失败: ' + e.message); }
}

function renderDashboard(data) {
  const inviteLink = 'https://yufeng.team/partner/reg/' + data.partner_id;

  const regRows = (data.register_list || []).map(r =>
    '<div class="list-item"><span>' + r.name + '</span><span>¥' + r.fee + ' <span class="badge ' + (r.status==='dealt'?'success':'') + '">' + r.status + '</span></span></div>'
  ).join('') || '<div style="text-align:center;color:#495670;font-size:13px;padding:16px">暂无填表记录</div>';

  const wdRows = (data.withdraw_list || []).map(w =>
    '<div class="list-item"><span>¥' + w.amount + '</span><span>' + w.date + ' <span class="badge ' + (w.status==='done'?'success':'') + '">' + w.status + '</span></span></div>'
  ).join('') || '<div style="text-align:center;color:#495670;font-size:13px;padding:16px">暂无提现记录</div>';

  document.getElementById('app').innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <h1>📊 ${data.name}</h1>
      <button class="btn btn-sm" onclick="logout()" style="width:auto;padding:6px 16px;font-size:12px">退出</button>
    </div>

    <div class="card">
      <div class="stat-row">
        <div class="stat-item">
          <div class="stat-num">${data.total_registers}</div>
          <div class="stat-label">填表人数</div>
        </div>
        <div class="stat-item">
          <div class="stat-num">${data.total_deals}</div>
          <div class="stat-label">成交数</div>
        </div>
        <div class="stat-item">
          <div class="stat-num">¥${data.total_commission}</div>
          <div class="stat-label">累计佣金</div>
        </div>
      </div>
      <div class="stat-item" style="margin-top:8px">
        <div class="stat-num" style="color:#64ffda">¥${data.withdrawable}</div>
        <div class="stat-label">可提现余额</div>
      </div>
    </div>

    <div class="card">
      <h1 style="font-size:15px">🔗 你的推广链接</h1>
      <div class="link-box">${inviteLink}</div>
      <p style="font-size:11px;color:#495670">
        把链接发到微信群/朋友圈，好友填表即算你的业绩
      </p>
    </div>

    <div class="tab-bar">
      <div class="tab active" onclick="switchTab(this,'reg')">填表记录</div>
      <div class="tab" onclick="switchTab(this,'wd')">提现记录</div>
      <div class="tab" onclick="switchTab(this,'withdraw')">提现</div>
    </div>

    <div class="card" id="tab-reg">
      <h1 style="font-size:15px">📋 填表记录</h1>
      ${regRows}
      <p style="font-size:11px;color:#495670;margin-top:8px">
        💡 填表=¥2/人，成交=剩余20%自动结算
      </p>
    </div>

    <div class="card hidden" id="tab-wd">
      <h1 style="font-size:15px">💰 提现记录</h1>
      ${wdRows}
    </div>

    <div class="card hidden" id="tab-withdraw">
      <h1 style="font-size:15px">💳 申请提现</h1>
      <div class="stat-item" style="margin-bottom:12px">
        <div class="stat-num" style="color:#64ffda">¥${data.withdrawable}</div>
        <div class="stat-label">可提现余额</div>
      </div>
      <div class="input-group">
        <label>提现金额（元）</label>
        <input id="wdAmount" type="number" step="0.01" placeholder="输入金额" />
      </div>
      <button class="btn" onclick="doWithdraw()">申请提现</button>
      <p style="font-size:11px;color:#495670;margin-top:8px">
        提现后由管理员审核打款，一般1-3个工作日到账
      </p>
    </div>
  `;
}

function switchTab(el, tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  ['reg','wd','withdraw'].forEach(t => {
    document.getElementById('tab-' + t).classList.toggle('hidden', t !== tab);
  });
}

async function doWithdraw() {
  const amount = parseFloat(document.getElementById('wdAmount').value);
  if (!amount || amount <= 0) { toast('请输入有效金额'); return; }
  const pid = localStorage.getItem('partner_id');
  const pwd = localStorage.getItem('partner_pwd');
  try {
    const r = await fetch(API + '/withdraw?partner_id=' + encodeURIComponent(pid) + '&password=' + encodeURIComponent(pwd) + '&amount=' + amount);
    if (!r.ok) { const e = await r.json(); toast(e.detail || '提现失败'); return; }
    toast('✅ 提现申请已提交');
    loadDashboard(pid, pwd);
  } catch(e) { toast('网络错误: ' + e.message); }
}

function logout() {
  localStorage.removeItem('partner_id');
  localStorage.removeItem('partner_pwd');
  renderLogin();
}

render();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════
# 管理后台
# ═══════════════════════════════════════════════════════════════

_ADMIN_PASSWORD = "yufeng2026"


@router.get("/admin/login")
def admin_login(password: str = Query(...)):
    """管理员验证"""
    if password != _ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")
    return {"success": True}


@router.get("/admin/partners")
def admin_partners(password: str = Query(...), db: Session = Depends(get_db)):
    """获取所有渠道主数据"""
    if password != _ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")

    partners = db.query(ChannelPartner).order_by(ChannelPartner.created_at.desc()).all()
    result = []
    for p in partners:
        # 统计最近30天的数据
        from datetime import timedelta
        since = datetime.now(timezone.utc) - timedelta(days=30)
        recent = db.query(func.count(PartnerRegister.id)).filter(
            PartnerRegister.partner_id == p.partner_id,
            PartnerRegister.created_at >= since,
        ).scalar() or 0

        pending_wd = db.query(func.count(PartnerWithdraw.id)).filter(
            PartnerWithdraw.partner_id == p.partner_id,
            PartnerWithdraw.status == "pending",
        ).scalar() or 0

        result.append({
            "partner_id": p.partner_id,
            "name": p.name,
            "phone": p.phone,
            "wechat": p.wechat,
            "source": p.source,
            "status": p.status,
            "total_registers": p.total_registers,
            "total_deals": p.total_deals,
            "deal_amount": 0,
            "total_commission": float(p.total_commission),
            "withdrawable": float(p.withdrawable),
            "recent_30d": recent,
            "pending_withdraws": pending_wd,
            "created_at": p.created_at.strftime("%Y-%m-%d") if p.created_at else "",
        })

    # 全局统计
    total_commission = db.query(func.coalesce(func.sum(ChannelPartner.total_commission), 0)).scalar()
    total_withdrawable = db.query(func.coalesce(func.sum(ChannelPartner.withdrawable), 0)).scalar()
    total_registers = db.query(func.count(PartnerRegister.id)).scalar()
    total_deals = db.query(func.count(PartnerRegister.id)).filter(PartnerRegister.status.in_(["confirmed", "dealt"])).scalar()

    return {
        "partners": result,
        "total": {
            "partners": len(result),
            "registers": total_registers,
            "deals": total_deals,
            "commission": float(total_commission),
            "withdrawable": float(total_withdrawable),
            "deal_amount": float(db.query(func.coalesce(func.sum(PartnerRegister.deal_amount), 0)).scalar() or 0),
            "dealt_count": db.query(func.count(PartnerRegister.id)).filter(PartnerRegister.deal_amount > 0).scalar() or 0,
        },
    }


@router.get("/admin/withdraws")
def admin_withdraws(
    password: str = Query(...),
    status: str = Query("pending"),
    db: Session = Depends(get_db),
):
    """获取提现审核列表"""
    if password != _ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")

    query = db.query(
        PartnerWithdraw, ChannelPartner.name
    ).join(
        ChannelPartner, PartnerWithdraw.partner_id == ChannelPartner.partner_id
    )

    if status != "all":
        query = query.filter(PartnerWithdraw.status == status)

    rows = query.order_by(PartnerWithdraw.created_at.desc()).limit(100).all()

    return {
        "list": [
            {
                "id": wd.id,
                "partner_id": wd.partner_id,
                "partner_name": name,
                "amount": float(wd.amount),
                "method": wd.method,
                "account": wd.account,
                "status": wd.status,
                "created_at": wd.created_at.strftime("%Y-%m-%d %H:%M") if wd.created_at else "",
            }
            for wd, name in rows
        ]
    }


@router.get("/admin/approve_partner")
def admin_approve_partner(
    password: str = Query(...),
    partner_id: str = Query(...),
    action: str = Query("approve"),
    db: Session = Depends(get_db),
):
    """审核渠道主注册 approve/reject"""
    if password != _ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")
    partner = db.query(ChannelPartner).filter(ChannelPartner.partner_id == partner_id).first()
    if not partner:
        raise HTTPException(status_code=404, detail="渠道主不存在")
    if action == "reject":
        partner.status = "rejected"
    else:
        partner.status = "active"
    db.commit()
    return {"success": True, "partner_id": partner_id, "status": partner.status}


@router.get("/admin/approve_withdraw")
def admin_approve_withdraw(
    password: str = Query(...),
    withdraw_id: int = Query(...),
    action: str = Query("approve"),
    db: Session = Depends(get_db),
):
    """审核提现：approve/done/reject"""
    if password != _ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")

    wd = db.query(PartnerWithdraw).filter(PartnerWithdraw.id == withdraw_id).first()
    if not wd:
        raise HTTPException(status_code=404, detail="提现记录不存在")

    if action == "done":
        wd.status = "done"
        wd.processed_at = datetime.now(timezone.utc)
    elif action == "reject":
        # 拒绝时要把金额退回余额
        wd.status = "rejected"
        wd.processed_at = datetime.now(timezone.utc)
        partner = db.query(ChannelPartner).filter(ChannelPartner.partner_id == wd.partner_id).first()
        if partner:
            partner.withdrawable += wd.amount
    else:
        wd.status = "done"
        wd.processed_at = datetime.now(timezone.utc)

    db.commit()
    return {"success": True, "status": wd.status}


@router.get("/admin/record_deal")
def admin_record_deal(
    password: str = Query(...),
    register_id: int = Query(...),
    deal_amount: float = Query(..., ge=0),
    deal_fee: float = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """记录成交：输入实际成交金额和渠道主分润"""
    if password != _ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")

    register = db.query(PartnerRegister).filter(PartnerRegister.id == register_id).first()
    if not register:
        raise HTTPException(status_code=404, detail="记录不存在")

    register.deal_amount = Decimal(str(deal_amount))
    register.deal_fee = Decimal(str(deal_fee))
    register.status = "dealt"

    # 同时更新渠道主的成交数和佣金
    partner = db.query(ChannelPartner).filter(ChannelPartner.partner_id == register.partner_id).first()
    if partner and deal_fee > 0:
        partner.total_commission += Decimal(str(deal_fee))
        partner.withdrawable += Decimal(str(deal_fee))

    db.commit()
    return {
        "success": True,
        "register_id": register_id,
        "customer": register.customer_name,
        "deal_amount": deal_amount,
        "deal_fee": deal_fee,
    }


@router.get("/yf-admin-partners", response_class=HTMLResponse)
def admin_dashboard_page():
    """渠道主管理后台"""
    import os
    html_path = os.path.join(os.path.dirname(__file__), "channel_admin.html")
    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html)


_ADMIN_HTML = None
_ADMIN_HTML = open(os.path.join(os.path.dirname(__file__), "channel_admin.html"), encoding="utf-8").read()
"""#
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>屿风 · 渠道管理后台</title>
<style>
  * {margin:0;padding:0;box-sizing:border-box;}
  body {font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;background:#1a1a2e;color:#e8e8e8;min-height:100vh;padding:16px;}
  .container {max-width:960px;margin:0 auto;}
  .card {background:#16213e;border-radius:16px;padding:24px;margin-bottom:16px;border:1px solid #233554;}
  h1 {font-size:20px;color:#e94560;margin-bottom:16px;}
  .stat-row {display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;}
  .stat-item {flex:1;min-width:100px;text-align:center;background:rgba(255,255,255,0.03);border-radius:12px;padding:16px;}
  .stat-num {font-size:24px;font-weight:700;}
  .stat-num.accent {color:#e94560;}
  .stat-num.blue {color:#4fc3f7;}
  .stat-num.green {color:#64ffda;}
  .stat-num.orange {color:#ffa726;}
  .stat-num.purple {color:#ce93d8;}
  .stat-label {font-size:11px;color:#8892b0;margin-top:4px;}
  table {width:100%;border-collapse:collapse;font-size:13px;}
  th {text-align:left;color:#8892b0;padding:8px;border-bottom:1px solid #233554;font-weight:500;}
  td {padding:10px 8px;border-bottom:1px solid rgba(255,255,255,0.05);}
  .tag {display:inline-block;font-size:11px;padding:2px 8px;border-radius:8px;background:#0f3460;color:#8892b0;}
  .tag.active {background:#1b4332;color:#64ffda;}
  .tag.done {background:#1b4332;color:#64ffda;}
  .tag.pending {background:#3d2e0c;color:#ffd700;}
  .tab-bar {display:flex;background:#0d1b2a;border-radius:10px;overflow:hidden;margin-bottom:16px;}
  .tab {flex:1;text-align:center;padding:10px;font-size:13px;cursor:pointer;color:#8892b0;}
  .tab.active {background:#e94560;color:white;}
  .hidden {display:none;}
  .btn-sm {padding:6px 14px;border:none;border-radius:6px;font-size:12px;cursor:pointer;margin-right:4px;}
  .btn-deal {background:#1b4332;color:#64ffda;}
  .btn-approve {background:#1b4332;color:#64ffda;}
  .btn-reject {background:#3d0c11;color:#ff6b6b;}
  .input-group {margin-bottom:12px;}
  .input-group input,.input-group select {width:100%;padding:10px;background:#0d1b2a;color:#e8e8e8;border:1px solid #233554;border-radius:8px;font-size:14px;}
  .input-row {display:flex;gap:8px;}
  .input-row input {flex:1;}
  .input-row input.small {flex:0 0 80px;}
</style>
</head>
<body>
<div class="container" id="app"></div>
<script>
var API = "/partner/admin", password = localStorage.getItem("pa_pwd") || "";

function esc(s) {var d=document.createElement("div");d.textContent=s||"";return d.innerHTML;}
function num(v) {return Number(v||0).toFixed(2);}

function render() {
  if (!password) {renderLogin();return;}
  loadAll();
}

function renderLogin() {
  document.getElementById("app").innerHTML =
    '<div class="card" style="max-width:400px;margin:40px auto;text-align:center">' +
    '<h1>🔐 渠道管理</h1>' +
    '<p style="color:#8892b0;font-size:13px;margin-bottom:20px">屿风渠道主分销后台</p>' +
    '<div class="input-group"><input type="password" id="pwd" placeholder="管理密码" autofocus onkeypress="if(event.keyCode===13)doLogin()" /></div>' +
    '<button class="tab active" onclick="doLogin()" style="flex:none;padding:10px 40px">登录</button></div>';
}

function doLogin() {
  password = document.getElementById("pwd").value.trim();
  if (!password) return;
  fetch(API+"/login?password="+encodeURIComponent(password)).then(function(r){
    if (!r.ok) {alert("密码错误");password="";renderLogin();return;}
    localStorage.setItem("pa_pwd",password);render();
  });
}

function loadAll() {
  document.getElementById("app").innerHTML =
    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">' +
    '<h1>📊 渠道管理</h1>' +
    '<button onclick="logout()" style="padding:6px 16px;border:none;border-radius:6px;background:#e94560;color:white;font-size:12px;cursor:pointer">退出</button></div>' +
    '<div class="tab-bar">' +
    '<div class="tab active" onclick="switchTab(this,\'partners\')">渠道主</div>' +
    '<div class="tab" onclick="switchTab(this,\'pending\')">待审核</div>' +
    '<div class="tab" onclick="switchTab(this,\'withdraws\')">提现</div>' +
    '<div class="tab" onclick="switchTab(this,\'registers\')">成交录入</div></div>' +
    '<div id="tab-partners"></div><div id="tab-pending" class="hidden"></div>' +
    '<div id="tab-withdraws" class="hidden"></div><div id="tab-registers" class="hidden"></div>';
  loadPartners();loadWithdraws();
}

function switchTab(el,tab) {
  document.querySelectorAll(".tab").forEach(function(t){t.classList.remove("active");});
  el.classList.add("active");
  ["partners","pending","withdraws","registers"].forEach(function(t){
    document.getElementById("tab-"+t).classList.toggle("hidden",t!==tab);
  });
  if(tab==="registers") loadRegisters();
}

function loadPartners() {
  fetch(API+"/partners?password="+encodeURIComponent(password)).then(function(r){
    if(!r.ok){logout();return;}return r.json();
  }).then(function(data){
    var p=data.total||{},partners=data.partners||[];
    var rows=partners.map(function(pm){
      return "<tr><td><strong>"+esc(pm.name)+'</strong><br><span class="tag">'+pm.partner_id+'</span></td>' +
        "<td>"+pm.total_registers+"</td><td>"+pm.total_deals+"</td><td>"+num(pm.deal_amount)+"</td>" +
        "<td>"+num(pm.total_commission)+"</td><td>"+num(pm.withdrawable)+'</td>' +
        '<td><span class="tag '+pm.status+'">'+pm.status+"</span></td></tr>";
    }).join("");
    document.getElementById("tab-partners").innerHTML =
      '<div class="card"><div class="stat-row">' +
      '<div class="stat-item"><div class="stat-num accent">'+p.partners+'</div><div class="stat-label">渠道主</div></div>' +
      '<div class="stat-item"><div class="stat-num blue">'+p.registers+'</div><div class="stat-label">总填表</div></div>' +
      '<div class="stat-item"><div class="stat-num green">'+p.deals+'</div><div class="stat-label">加微</div></div>' +
      '<div class="stat-item"><div class="stat-num orange">'+(p.dealt_count||0)+'</div><div class="stat-label">成交数</div></div>' +
      '<div class="stat-item"><div class="stat-num purple">'+num(p.deal_amount)+'</div><div class="stat-label">成交金额</div></div>' +
      '<div class="stat-item"><div class="stat-num accent">'+num(p.commission)+'</div><div class="stat-label">总佣金</div></div></div></div>' +
      '<div class="card"><table><tr><th>渠道主</th><th>填表</th><th>加微</th><th>成交金额</th><th>佣金</th><th>余额</th><th>状态</th></tr>' +
      (rows||'<tr><td colspan="7" style="text-align:center;color:#495670">暂无数据</td></tr>')+"</table></div>";
    setTimeout(loadPending,50);
  }).catch(function(e){
    document.getElementById("tab-partners").innerHTML='<div class="card"><p>加载失败</p></div>';
  });
}

function loadPending() {
  fetch(API+"/partners?password="+encodeURIComponent(password)).then(function(r){return r.json();}).then(function(data){
    var pending=(data.partners||[]).filter(function(pm){return pm.status==="pending"||pm.status==="rejected";});
    var rows=pending.map(function(pm){
      return "<tr><td><strong>"+esc(pm.name)+'</strong><br><span class="tag">'+pm.partner_id+'</span></td>' +
        "<td>"+(pm.phone||"-")+"</td><td>"+(pm.wechat||"-")+"</td><td>"+pm.created_at+'</td>' +
        '<td><span class="tag '+pm.status+'">'+pm.status+'</span></td><td>' +
        (pm.status==="pending"
          ? '<button class="btn-sm btn-approve" onclick="approvePartner(\''+pm.partner_id+'\',\'approve\')">通过</button>'+
            '<button class="btn-sm btn-reject" onclick="approvePartner(\''+pm.partner_id+'\',\'reject\')">拒绝</button>'
          : "-")+"</td></tr>";
    }).join("");
    document.getElementById("tab-pending").innerHTML =
      '<div class="card"><table><tr><th>姓名</th><th>手机</th><th>微信</th><th>申请时间</th><th>状态</th><th>操作</th></tr>'+
      (rows||'<tr><td colspan="6" style="text-align:center;color:#495670">暂无待审核</td></tr>')+"</table></div>";
  }).catch(function(){});
}

function approvePartner(pid,action) {
  if(!confirm("确定"+(action==="approve"?"通过":"拒绝")+"这个渠道主吗？")) return;
  fetch(API+"/approve_partner?password="+encodeURIComponent(password)+"&partner_id="+pid+"&action="+action)
    .then(function(r){if(r.ok){loadPending();loadPartners();}});
}

function loadWithdraws() {
  fetch(API+"/withdraws?password="+encodeURIComponent(password)+"&status=all").then(function(r){
    if(!r.ok)return;return r.json();
  }).then(function(data){
    var rows=(data.list||[]).map(function(w){
      return "<tr><td>"+esc(w.partner_name)+'<br><span class="tag">'+w.partner_id+'</span></td>' +
        "<td>"+num(w.amount)+"</td><td>"+(w.method||"")+'</td>' +
        '<td><span class="tag '+w.status+'">'+w.status+'</span></td><td>'+w.created_at+"</td><td>" +
        (w.status==="pending"
          ? '<button class="btn-sm btn-approve" onclick="approveWd('+w.id+',\'done\')">打款</button>'+
            '<button class="btn-sm btn-reject" onclick="approveWd('+w.id+',\'reject\')">拒绝</button>'
          : "-")+"</td></tr>";
    }).join("");
    document.getElementById("tab-withdraws").innerHTML =
      '<div class="card"><table><tr><th>渠道主</th><th>金额</th><th>方式</th><th>状态</th><th>申请时间</th><th>操作</th></tr>'+
      (rows||'<tr><td colspan="6" style="text-align:center;color:#495670">暂无提现</td></tr>')+"</table></div>";
  }).catch(function(){});
}

function approveWd(id,action) {
  if(!confirm("确定"+(action==="done"?"打款":"拒绝")+"这笔提现吗？")) return;
  fetch(API+"/approve_withdraw?password="+encodeURIComponent(password)+"&withdraw_id="+id+"&action="+action)
    .then(function(r){if(r.ok){loadWithdraws();loadPartners();}else alert("操作失败");})
    .catch(function(){alert("网络错误");});
}

// ── 成交录入 ──

function loadRegisters() {
  document.getElementById("tab-registers").innerHTML =
    '<div class="card"><h1>📝 记录成交</h1>' +
    '<p style="color:#8892b0;font-size:13px;margin-bottom:12px">客户在企微转账后，在这里录入成交金额和分佣</p>' +
    '<div class="input-row">' +
    '<input class="small" id="reg-id-input" type="number" placeholder="记录ID" />' +
    '<input id="deal-amount-input" type="number" step="0.01" placeholder="成交金额(元)" />' +
    '<input id="deal-fee-input" type="number" step="0.01" placeholder="分佣(元)" />' +
    '<button class="btn-sm btn-deal" onclick="submitDeal()">记录成交</button></div></div>' +
    '<div class="card"><h1>📊 渠道主成交概览</h1>';
  loadRegisterOverview();
}

function loadRegisterOverview() {
  fetch(API+"/partners?password="+encodeURIComponent(password)).then(function(r){return r.json();}).then(function(data){
    var partners=data.partners||[];
    var html='<table><tr><th>渠道主</th><th>填表</th><th>加微</th><th>成交金额</th><th>佣金</th></tr>';
    partners.forEach(function(pm){
      html+="<tr><td><strong>"+esc(pm.name)+'</strong><br><span class="tag">'+pm.partner_id+'</span></td>' +
        "<td>"+pm.total_registers+"</td><td>"+pm.total_deals+"</td><td>"+num(pm.deal_amount)+"</td>"+
        "<td>"+num(pm.total_commission)+"</td></tr>";
    });
    html+="</table><p style='color:#495670;font-size:12px;margin-top:12px'>💡 记录ID可以在客户填表成功后的提示中找到，或让我帮你查</p>";
    document.getElementById("tab-registers").innerHTML+=html+"</div>";
  }).catch(function(){});
}

function submitDeal() {
  var rid=document.getElementById("reg-id-input").value.trim();
  var amt=parseFloat(document.getElementById("deal-amount-input").value);
  var fee=parseFloat(document.getElementById("deal-fee-input").value)||0;
  if(!rid||isNaN(amt)||amt<=0){alert("请填写记录ID和成交金额");return;}
  fetch(API+"/record_deal?password="+encodeURIComponent(password)+"&register_id="+rid+"&deal_amount="+amt+"&deal_fee="+fee)
    .then(function(r){
      if(!r.ok){r.text().then(function(t){alert("失败: "+t);});return;}
      r.json().then(function(d){
        alert("✅ 成交已记录！"+d.customer+" 成交¥"+d.deal_amount+" 分佣¥"+d.deal_fee);
        document.getElementById("reg-id-input").value="";
        document.getElementById("deal-amount-input").value="";
        document.getElementById("deal-fee-input").value="";
        loadPartners();loadRegisters();
      });
    })
    .catch(function(){alert("网络错误");});
}

function logout() {
  password="";localStorage.removeItem("pa_pwd");renderLogin();
}

render();
</script>
</body>
</html>"""


_HOME_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>屿风 · 渠道合作</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif; background:linear-gradient(135deg,#1a1a2e,#16213e); color:#e8e8e8; min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; }
  .card { background:rgba(22,33,62,0.9); backdrop-filter:blur(20px); border:1px solid #233554; border-radius:24px; padding:32px 24px; width:100%; max-width:400px; }
  h1 { font-size:22px; color:#e94560; text-align:center; margin-bottom:6px; }
  .sub { text-align:center; color:#8892b0; font-size:13px; margin-bottom:24px; }
  .input-group { margin-bottom:14px; }
  .input-group label { font-size:12px; color:#8892b0; display:block; margin-bottom:4px; }
  .input-group input { width:100%; padding:12px; background:#0d1b2a; color:#e8e8e8; border:1px solid #233554; border-radius:10px; font-size:15px; }
  .input-group input:focus { outline:none; border-color:#e94560; }
  .btn { width:100%; padding:14px; border:none; border-radius:10px; font-size:15px; font-weight:600; cursor:pointer; background:linear-gradient(135deg,#e94560,#d63850); color:white; margin-top:8px; }
  .btn:active { opacity:0.8; }
  .btn:disabled { opacity:0.5; }
  .rule-box { background:rgba(233,69,96,0.08); border:1px solid rgba(233,69,96,0.2); border-radius:12px; padding:16px; margin:16px 0; font-size:13px; line-height:1.8; }
  .rule-box strong { color:#e94560; }
  .success-box { background:rgba(100,255,218,0.08); border:1px solid rgba(100,255,218,0.2); border-radius:12px; padding:20px; text-align:center; margin:16px 0; }
  .success-box .id { font-size:18px; color:#64ffda; font-weight:700; margin:8px 0; }
  .footer { text-align:center; font-size:11px; color:#495670; margin-top:16px; }
  .toast { position:fixed; top:20px; left:50%; transform:translateX(-50%); padding:12px 24px; border-radius:10px; font-size:13px; z-index:999; opacity:0; transition:opacity 0.3s; pointer-events:none; }
  .toast.show { opacity:1; }
  .toast.err { background:#3d0c11; color:#ff6b6b; }
  .toast.ok { background:#1b4332; color:#64ffda; }
  .hidden { display:none; }
  .link { color:#8892b0; text-decoration:underline; font-size:12px; cursor:pointer; }
</style>
</head>
<body>
<div id="toast" class="toast"></div>
<div class="card" id="app">
  <div id="page-register">
    <h1>🤝 成为屿风渠道主</h1>
    <p class="sub">拉人填表¥2/人 · 成交分润20%</p>
    <div class="rule-box"><strong>合作方式</strong><br>你把推广链接发到微信群/朋友圈<br>好友填表 → 你赚 <strong>2元/人</strong><br>好友后续付费成交 → 你再拿 <strong>20%分润</strong><br>满 <strong>50元</strong> 可随时申请提现</div>
    <div class="input-group"><label>你的称呼</label><input id="regName" placeholder="怎么称呼你" /></div>
    <div class="input-group"><label>手机号（选填）</label><input id="regPhone" type="tel" placeholder="方便联系" /></div>
    <div class="input-group"><label>微信号（选填）</label><input id="regWechat" placeholder="你的微信号" /></div>
    <div class="input-group"><label>设置登录密码</label><input id="regPassword" type="password" placeholder="至少4位" /></div>
    <button class="btn" id="regBtn" onclick="doRegister()">立即申请</button>
    <p style="text-align:center;margin-top:12px"><span class="link" onclick="showLogin()">已有账号？去登录</span></p>
  </div>
  <div id="page-success" class="hidden">
    <h1>✅ 申请已提交</h1>
    <div class="success-box"><p style="font-size:13px;color:#8892b0">你的渠道ID</p><div class="id" id="pidDisplay">---</div><p style="font-size:12px;color:#495670">管理员审核通过后即可使用</p></div>
    <p style="font-size:13px;color:#8892b0;text-align:center">审核通过后我会通知你<br>一般24小时内完成审核</p>
  </div>
  <div id="page-login" class="hidden">
    <h1 style="font-size:18px">🔐 渠道主登录</h1>
    <p class="sub">输入渠道ID和密码查看数据</p>
    <div class="input-group"><label>手机号</label><input id="loginPhone" type="tel" placeholder="注册时填写的手机号" /></div>
    <div class="input-group"><label>密码</label><input id="loginPwd" type="password" placeholder="注册时设置的密码" /></div>
    <button class="btn" onclick="doLogin()">登录面板</button>
    <p style="text-align:center;margin-top:12px"><span class="link" onclick="showRegister()">还没有账号？去注册</span></p>
  </div>
</div>
<div class="footer">屿风 · 渠道合作系统</div>
<script>
const API = '/partner';
function toast(msg,t) { const e=document.getElementById('toast'); e.textContent=msg; e.className='toast '+(t||'ok')+' show'; setTimeout(()=>e.className='toast',2500); }
function showPage(id) { ['page-register','page-success','page-login'].forEach(p=>document.getElementById(p).classList.toggle('hidden',p!==id)); }
function showLogin() { showPage('page-login'); }
function showRegister() { showPage('page-register'); }
async function doRegister() {
  const n=document.getElementById('regName').value.trim(), p=document.getElementById('regPassword').value.trim();
  if(!n){toast('请输入称呼','err');return;}
  if(p.length<4){toast('密码至少4位','err');return;}
  const btn=document.getElementById('regBtn'); btn.disabled=true; btn.textContent='提交中...';
  try {
    const params=new URLSearchParams(); params.append('name',n); params.append('phone',document.getElementById('regPhone').value.trim()); params.append('wechat',document.getElementById('regWechat').value.trim()); params.append('password',p); params.append('source','wechat');
    const r=await fetch(API+'/register?'+params.toString()); const d=await r.json();
    if(d.success){document.getElementById('pidDisplay').textContent=d.partner_id;showPage('page-success');}else{toast(d.detail||'注册失败','err');}
  }catch(e){toast('网络错误: '+e.message,'err');}
  btn.disabled=false; btn.textContent='立即申请';
}
async function doLogin() {
  const pid=document.getElementById('loginPid').value.trim(), pwd=document.getElementById('loginPwd').value.trim();
  if(!pid||!pwd){toast('请填写ID和密码','err');return;}
  try {
    const r=await fetch(API+'/login?partner_id='+encodeURIComponent(pid)+'&password='+encodeURIComponent(pwd));
    if(!r.ok){toast('ID或密码错误','err');return;}
    const d=await r.json();
    if(d.status==='pending'){toast('账号正在审核中','err');return;}
    if(d.status==='rejected'){toast('申请未通过','err');return;}
    localStorage.setItem('partner_id',pid);localStorage.setItem('partner_pwd',pwd);
    window.location.href=API+'/dashboard';
  }catch(e){toast('网络错误: '+e.message,'err');}
}
</script>
</body>
</html>"""
_REGISTER_FORM_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no"><title>屿风 · 会员登记</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:sans-serif;background:linear-gradient(135deg,#1a1a2e,#16213e);color:#e8e8e8;min-height:100vh;padding:24px}
.card{background:rgba(22,33,62,0.9);backdrop-filter:blur(20px);border:1px solid #233554;border-radius:24px;padding:28px 24px;max-width:420px;margin:0 auto}
h1{font-size:20px;color:#e94560;text-align:center;margin-bottom:6px}
.sub{text-align:center;color:#8892b0;font-size:13px;margin-bottom:20px}
.field{margin-bottom:14px}
.field label{font-size:12px;color:#8892b0;display:block;margin-bottom:4px}
.field input{width:100%;padding:12px;background:#0d1b2a;color:#e8e8e8;border:1px solid #233554;border-radius:10px;font-size:15px}
.field input:focus{outline:none;border-color:#e94560}
.btn{width:100%;padding:14px;border:none;border-radius:10px;font-size:15px;font-weight:600;cursor:pointer;background:linear-gradient(135deg,#e94560,#d63850);color:white;margin-top:8px;margin-bottom:12px}
.btn:active{opacity:0.8}
.btn:disabled{opacity:0.5}
.success-box{background:rgba(100,255,218,0.08);border:1px solid rgba(100,255,218,0.2);border-radius:16px;padding:32px;text-align:center;margin:20px 0}
.hidden{display:none}
</style></head><body>
<div class="card"><div id="form">
<h1>🏳️‍🌈 屿风</h1><p class="sub">填写基本信息，红娘为你匹配合适的人选</p>
<div class="field"><label>你的称呼 *</label><input id="name" placeholder="怎么称呼你" /></div>
<div class="field"><label>手机号</label><input id="phone" type="tel" placeholder="方便联系" /></div>
<div class="field"><label>微信号</label><input id="wechat" placeholder="你的微信号" /></div>
<button class="btn" id="submitBtn" onclick="submitForm()">提交登记</button>
<p style="text-align:center;font-size:11px;color:#495670">提交后屿风团队会尽快联系你</p>
</div><div id="success" class="hidden">
<div class="success-box"><p style="font-size:32px;margin-bottom:12px">✅</p>
<p style="font-size:16px;color:#64ffda;font-weight:600" id="successMsg">登记成功！</p>
<p style="font-size:13px;color:#8892b0;margin-top:8px">屿风团队会尽快联系你</p></div></div></div>
<script>
var PID="__PARTNER_ID__";
async function submitForm(){var n=document.getElementById("name").value.trim();if(!n){alert("请填写称呼");return;}
var b=document.getElementById("submitBtn");b.disabled=true;b.textContent="提交中...";
try{var r=await fetch("/partner/register-form/"+PID,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:n,phone:document.getElementById("phone").value.trim(),wechat:document.getElementById("wechat").value.trim()})});var d=await r.json();if(d.success){document.getElementById("successMsg").textContent=d.message;document.getElementById("form").classList.add("hidden");document.getElementById("success").classList.remove("hidden");}else{alert(d.detail||"提交失败");}
}catch(e){alert("网络错误");}
b.disabled=false;b.textContent="提交登记";}
</script></body></html>"""
@router.get("/register-form/{partner_id}", response_class=HTMLResponse)
def partner_register_form(partner_id: str, db: Session = Depends(get_db)):
    from fastapi.responses import HTMLResponse as _HR
    partner = db.query(ChannelPartner).filter(
        ChannelPartner.partner_id == partner_id,
        ChannelPartner.status == "active",
    ).first()
    if not partner:
        return _HR(content="<h3>链接无效</h3><p>渠道主不存在或未通过审核</p>")
    return _HR(content=_REGISTER_FORM_HTML.replace("__PARTNER_ID__", partner_id))


@router.post("/register-form/{partner_id}")
async def partner_register_form_submit(partner_id: str, request: Request, db: Session = Depends(get_db)):
    """渠道主推广填表提交（接收JSON）"""
    import json as _json
    try:
        body = await request.json()
    except Exception:
        body = {}
    name = body.get("name", "").strip()
    wechat = body.get("wechat", "").strip()
    phone = body.get("phone", "").strip()

    if not name:
        from fastapi import HTTPException; raise HTTPException(status_code=400, detail="请填写昵称")
    if not wechat:
        from fastapi import HTTPException; raise HTTPException(status_code=400, detail="微信号必填")

    partner = db.query(ChannelPartner).filter(
        ChannelPartner.partner_id == partner_id,
        ChannelPartner.status == "active",
    ).first()
    if not partner:
        from fastapi import HTTPException; raise HTTPException(status_code=404, detail="渠道主不存在")

    # 记录填表（待确认状态）
    from decimal import Decimal as _D
    reg = PartnerRegister(partner_id=partner_id, customer_name=name, customer_phone=phone, status="pending")
    partner.total_registers += 1
    # 佣金待确认
    db.add(reg)
    db.commit()

    return {"success": True, "message": f"{name}，登记成功！请添加屿风企微"}



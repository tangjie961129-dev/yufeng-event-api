"""企微客户打标签 API（个人微信客户适用）

工作流程（专属链接版）：
1. 员工告诉我：「给清风徐来发填表链接」
2. 系统生成专属链接：https://yufeng.team/register?token=abc123
3. 员工把链接发给对应的客户
4. 客户打开链接 → 看到自己的名字 → 填表提交
5. 系统自动识别客户身份 → 查找 external_userid → 打标签 ✅
"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.registration_link import RegistrationLink
from app.models.member_profile import MemberProfile
from app.services.wecom import (
    find_external_userid,
    ensure_tag_group,
    ensure_tag,
    mark_tag,
    suggest_tags_from_form,
    evaluate_member_level,
    send_text_to_employee,
)
from app.services.matching_service import find_matches

router = APIRouter(prefix="/api/wecom/tag", tags=["企微客户打标签"])


# ─── 第一步：生成专属填表链接 ────────────────────────────────


class GenerateLinkRequest(BaseModel):
    employee_userid: str = ""
    external_userid: str = ""  # 企微外部联系人ID（建议传，避免按昵称搜索失败）
    customer_name: str = ""


class GenerateLinkResponse(BaseModel):
    token: str
    url: str
    customer_name: str


@router.post("/generate-link")
async def generate_link(req: GenerateLinkRequest, db: Session = Depends(get_db)):
    """生成专属填表链接

    员工指定客户名 → 系统生成唯一 token → 返回链接
    如果提供了 external_userid，客户填表后直接匹配，不按昵称搜索。
    """
    if not req.customer_name:
        raise HTTPException(400, "缺少客户名称 customer_name")
    if not req.employee_userid:
        raise HTTPException(400, "缺少员工 userid employee_userid")

    token = uuid.uuid4().hex
    link = RegistrationLink(
        token=token,
        employee_userid=req.employee_userid,
        external_userid=req.external_userid.strip() if req.external_userid else None,
        customer_name=req.customer_name.strip(),
        status="pending",
    )
    db.add(link)
    db.commit()

    # 从已存在的 router 反推 base URL（简化处理）
    url = f"https://yufeng.team/api/wecom/tag/register-form?token={token}"

    return {
        "token": token,
        "url": url,
        "customer_name": req.customer_name,
        "message": f"生成成功，请把链接发给 {req.customer_name}",
    }


# ─── 第二步：打标签（员工直接指定客户名 + 表单数据） ──────────


class TagCustomerRequest(BaseModel):
    employee_userid: str = ""
    customer_name: str = ""
    form_data: dict = {}
    tag_names: list[str] = []


@router.post("/customer")
async def tag_customer(req: TagCustomerRequest):
    """根据员工 userid + 客户名，自动查找并打标签

    employee_userid: 员工的企微 userid（小助理回调里的 FromUserName）
    customer_name: 客户在企微里的名字/昵称（支持模糊匹配）
    form_data: 客户的登记信息（用于 smart 推荐标签）
    tag_names: 可选，额外指定标签名
    """
    if not req.customer_name:
        raise HTTPException(400, "缺少客户名称 customer_name")

    # 1. 查找客户 external_userid
    ext_userid = None

    if req.employee_userid:
        ext_userid = await find_external_userid(req.employee_userid, req.customer_name)

    if not ext_userid:
        raise HTTPException(404, f"在员工 {req.employee_userid} 的客户列表中未找到「{req.customer_name}」")

    # 2. 生成标签
    tag_names = list(req.tag_names)
    if req.form_data:
        smart_tags = suggest_tags_from_form(req.form_data)
        tag_names.extend(smart_tags)

    if not tag_names:
        raise HTTPException(400, "未指定任何标签（可传 tag_names 或 form_data）")

    # 3. 确保标签组和标签存在
    try:
        await ensure_tag_group()
        tag_ids = []
        for name in tag_names:
            tag_id = await ensure_tag(name)
            tag_ids.append(tag_id)

        # 4. 打标签
        await mark_tag(ext_userid, tag_ids, employee_userid=req.employee_userid)
    except RuntimeError as exc:
        raise HTTPException(502, f"打标签失败: {exc}")

    return {
        "success": True,
        "external_userid": ext_userid,
        "customer_name": req.customer_name,
        "tags_applied": tag_names,
    }


# ─── 查找客户（供调试用） ─────────────────────────────────────


@router.get("/find-customer")
async def find_customer(
    employee_userid: str = Query(...),
    customer_name: str = Query(...),
):
    """在员工客户列表中查找客户"""
    try:
        ext_userid = await find_external_userid(employee_userid, customer_name)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc))

    if not ext_userid:
        raise HTTPException(404, f"未找到客户「{customer_name}」")

    return {
        "external_userid": ext_userid,
        "customer_name": customer_name,
    }


# ─── H5 注册表单（专属链接版） ────────────────────────────────


REGISTER_FORM_HTML = REGISTER_FORM_HTML = REGISTER_FORM_HTML = REGISTER_FORM_HTML = REGISTER_FORM_HTML = REGISTER_FORM_HTML = REGISTER_FORM_HTML = REGISTER_FORM_HTML = REGISTER_FORM_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>屿风 · 不负每一次相逢</title>
<meta property="og:title" content="屿风会员登记信息表">
<meta property="og:description" content="请认真填写信息，方便我们为你寻找幸福。">
<meta property="og:image" content="https://yufeng.team/static/yufeng-share-card-og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px}
html,body{height:100%}
body{
  font-family:'Inter',-apple-system,'PingFang SC','Helvetica Neue',sans-serif;
  background:#faf5ee;color:#3d3d3d;overflow-x:hidden;
  -webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale
}
.mx{max-width:480px;margin:0 auto;padding:0 16px 48px;position:relative;z-index:1}

/* ─── SPLASH — Full screen text over hero image ─── */
#splash{
  position:fixed;top:0;left:0;width:100%;height:100%;z-index:100;
  overflow:hidden;
  transition:transform .7s cubic-bezier(.22,1,.36,1),opacity .5s ease
}
#splash.slide-up{transform:translateY(-100%);opacity:0;pointer-events:none}
.splash-bg{
  position:absolute;top:0;left:0;width:100%;height:100%;
  background:#faf5ee
}
.splash-bg img{
  width:100%;height:100%;object-fit:cover
}
.splash-overlay{
  position:absolute;top:0;left:0;width:100%;height:100%;
  background:linear-gradient(180deg,rgba(0,0,0,.12) 0%,rgba(0,0,0,.32) 50%,rgba(0,0,0,.55) 100%);
  z-index:1
}

/* Text content */
.splash-content{
  position:absolute;top:0;left:0;width:100%;height:100%;z-index:2;
  display:flex;flex-direction:column;justify-content:flex-end;
  padding:48px 28px 80px
}
.splash-welcome{
  font-size:14px;font-weight:400;color:rgba(255,255,255,.7);
  letter-spacing:6px;text-transform:uppercase;margin-bottom:8px
}
.splash-title{
  font-size:36px;font-weight:700;color:#fff;
  letter-spacing:2px;line-height:1.2;margin-bottom:16px
}
.splash-desc{
  font-size:15px;font-weight:400;color:rgba(255,255,255,.8);
  line-height:1.7;max-width:400px;margin-bottom:24px
}
.splash-desc p{margin-bottom:10px}
.splash-tag{
  font-size:13px;font-weight:500;color:rgba(255,255,255,.5);
  letter-spacing:1px
}

/* Swipe Area */
.splash-swipe{
  text-align:center;cursor:pointer;z-index:3;
  -webkit-user-select:none;user-select:none;padding:0 28px 40px;
  position:absolute;bottom:0;left:0;width:100%
}
.swipe-hint{
  font-size:12px;color:rgba(255,255,255,.5);
  letter-spacing:2px;margin-bottom:6px
}
.swipe-arrow{
  display:inline-block;width:24px;height:24px;
  animation:bounce 2s ease infinite;opacity:.5
}
.swipe-arrow svg{width:100%;height:100%}
@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(6px)}}
.splash-start-btn{
  display:inline-block;padding:14px 48px;font-size:16px;font-weight:600;color:#fff;
  background:rgba(255,255,255,.15);backdrop-filter:blur(12px);
  -webkit-backdrop-filter:blur(12px);
  border:1px solid rgba(255,255,255,.25);border-radius:14px;
  cursor:pointer;transition:all .3s;letter-spacing:1px;
  display:none;width:100%;max-width:320px
}
.splash-start-btn.show{display:inline-block;animation:fadeUp .4s ease}
.splash-start-btn:hover{background:rgba(255,255,255,.25);border-color:rgba(255,255,255,.4)}
@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}

/* ─── Customer Hint ─── */
.customer-hint{
  background:rgba(212,138,90,.08);border:1px solid rgba(212,138,90,.15);
  border-radius:12px;padding:14px 16px;margin-top:16px;font-size:13px;
  color:#6d5d4d;text-align:center;display:none;line-height:1.6
}
.customer-hint strong{color:#d48a5a;font-weight:600}

/* ─── Progress ─── */
.step-progress{display:flex;justify-content:space-between;margin:16px 0 20px;padding:0}
.step-dot{display:flex;flex-direction:column;align-items:center;gap:6px;flex:1;position:relative}
.step-dot::after{
  content:'';position:absolute;top:12px;left:calc(50% + 14px);
  right:calc(-50% + 14px);height:2px;background:#e8ddd0;z-index:0;transition:background .4s
}
.step-dot:last-child::after{display:none}
.step-dot.active::after{background:linear-gradient(90deg,#d48a5a,#f2b989)}
.step-dot.done::after{background:#d48a5a}
.step-circle{
  width:24px;height:24px;border-radius:50%;background:#e8ddd0;display:flex;
  align-items:center;justify-content:center;font-size:11px;font-weight:600;
  color:#b8a898;z-index:1;transition:all .35s
}
.step-dot.active .step-circle{
  background:#d48a5a;color:#fff;
  box-shadow:0 0 0 4px rgba(212,138,90,.15)
}
.step-dot.done .step-circle{background:#f2b989;color:#fff}
.step-label{font-size:9px;color:#b8a898;text-align:center;font-weight:500;letter-spacing:.3px}
.step-dot.active .step-label{color:#d48a5a}
.step-dot.done .step-label{color:#b8a898}

/* ─── Card & Form ─── */
.card{
  background:#fff;border:1px solid #ede4d8;border-radius:16px;
  padding:28px 24px;box-shadow:
    0 1px 3px rgba(0,0,0,.02),
    0 4px 16px rgba(0,0,0,.03),
    0 12px 32px rgba(0,0,0,.02)
}
.card-title{
  font-size:11px;font-weight:600;color:#d48a5a;text-transform:uppercase;
  letter-spacing:1.5px;margin-bottom:20px
}
.sec{
  font-size:14px;font-weight:600;color:#5d4d3d;margin:0 0 16px;
  display:flex;align-items:center;gap:8px
}
.sec::after{content:'';flex:1;height:1px;background:linear-gradient(90deg,rgba(93,77,61,.15),transparent)}
.fld{margin-bottom:18px;animation:fadeUp .35s ease both}
.fld label{
  display:block;font-size:12px;color:#8a7a6a;margin-bottom:6px;
  font-weight:500;letter-spacing:.3px
}
.fld.req label::after{content:" *";color:#d48a5a}
.fld .hint{font-size:11px;color:#b8a898;margin-top:4px}
input,select,textarea{
  width:100%;padding:12px 14px;font-size:14px;background:#f8f4ee;
  color:#3d3d3d;border:1px solid #e8ddd0;border-radius:10px;outline:none;
  font-family:inherit;transition:border-color .25s,box-shadow .25s;-webkit-appearance:none
}
input:focus,select:focus,textarea:focus{
  border-color:#d48a5a;box-shadow:0 0 0 3px rgba(212,138,90,.08)
}
input::placeholder,textarea::placeholder{color:#c8b8a8}
textarea{resize:vertical;min-height:70px}
select{appearance:none;background-image:url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3e%3cpath fill='none' stroke='%238a7a6a' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='m2 5 6 6 6-6'/%3e%3c/svg%3e");background-repeat:no-repeat;background-position:right 12px center;background-size:14px;padding-right:34px}
.f2{display:flex;gap:10px}.f2 .fld{flex:1}

/* ─── Photo Upload ─── */
.ph-box{
  border:2px dashed #e8ddd0;border-radius:12px;padding:32px 24px;
  text-align:center;cursor:pointer;transition:all .25s;margin-bottom:8px;
  background:#faf6f0
}
.ph-box:hover{border-color:#d48a5a;background:#fdf8f0}
.ph-box.has{border-color:#f2b989;border-style:solid;background:#fffaf5}
.ph-box input{display:none}
.ph-icon{font-size:32px;color:#c8b8a8;margin-bottom:8px}
.ph-txt{font-size:12px;color:#b8a898}
.ph-box img{
  max-width:200px;max-height:200px;border-radius:12px;margin-top:12px;
  display:none;object-fit:cover;box-shadow:0 4px 24px rgba(0,0,0,.06)
}

/* ─── Buttons ─── */
.btn-nav{display:flex;gap:10px;margin-top:24px}
.btn{
  flex:1;padding:14px;font-size:15px;font-weight:600;color:#fff;
  background:linear-gradient(135deg,#d48a5a,#c07a4a);border:none;border-radius:12px;
  cursor:pointer;transition:all .25s;letter-spacing:.5px;position:relative
}
.btn:hover{transform:translateY(-1px);box-shadow:0 6px 24px rgba(212,138,90,.2)}
.btn:active{transform:translateY(0);opacity:.9}
.btn:disabled{opacity:.5;cursor:not-allowed;transform:none;box-shadow:none}
.btn-sec{
  background:#ede4d8;color:#6d5d4d;box-shadow:none
}
.btn-sec:hover{background:#e0d5c5;box-shadow:none;transform:none;color:#3d3d3d}
.btn-primary{
  width:100%;padding:16px;font-size:16px;font-weight:600;color:#fff;
  background:linear-gradient(135deg,#d48a5a,#c07a4a);border:none;border-radius:12px;
  cursor:pointer;margin-top:8px;transition:all .25s;letter-spacing:1px;position:relative
}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(212,138,90,.25)}
.btn-primary.loading{color:transparent}
.btn-primary.loading::after{
  content:'';position:absolute;left:50%;top:50%;width:20px;height:20px;
  margin:-10px 0 0 -10px;border:2px solid rgba(255,255,255,.3);
  border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite
}
@keyframes spin{to{transform:rotate(360deg)}}

/* ─── Success ─── */
.success-card{
  background:#fff;border:1px solid #ede4d8;border-radius:16px;overflow:hidden;margin-top:16px;
  box-shadow:0 1px 3px rgba(0,0,0,.02),0 4px 16px rgba(0,0,0,.03),0 12px 32px rgba(0,0,0,.02)
}
.success-hero{width:100%;height:200px;object-fit:cover;display:block}
.success-body{text-align:center;padding:32px 24px}
.success-icon{
  width:64px;height:64px;border-radius:50%;
  background:rgba(242,185,137,.18);display:flex;align-items:center;
  justify-content:center;margin:0 auto 16px;
  animation:popIn .5s cubic-bezier(.68,-.55,.27,1.55)
}
.success-icon svg{width:32px;height:32px}
@keyframes popIn{0%{transform:scale(0)}70%{transform:scale(1.12)}100%{transform:scale(1)}}
.success-body h2{font-size:22px;color:#d48a5a;margin-bottom:8px;font-weight:600}
.success-body p{color:#8a7a6a;font-size:14px;line-height:1.7;max-width:320px;margin:0 auto}
.success-body .btn-primary{margin-top:24px}
.h{display:none!important}
</style>
</head>
<body>

<!-- ═══════════════ SPLASH ═══════════════ -->
<div id="splash">
  <div class="splash-bg">
    <img src="https://yufeng.team/static/yufeng-register-hero.png" alt="">
    <div class="splash-overlay"></div>
  </div>
  <div class="splash-content">
    <div class="splash-welcome">WELCOME</div>
    <div class="splash-title">欢迎来到屿风</div>
    <div class="splash-desc">
      <p>我们坚信平等，也珍视每一份真心。</p>
      <p>不求速配，只愿陪你找到长久而温暖的真情。</p>
      <p>你的资料仅用于内部匹配，隐私严格保密。</p>
      <p>请静下心来填写——我们想认真了解你，陪你走向属于你的幸福。</p>
    </div>
  </div>
  <div class="splash-swipe" id="swipeArea">
    <div class="swipe-hint" id="swipeHint">上滑进入</div>
    <div class="swipe-arrow" id="swipeArrow">
      <svg viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,.5)" stroke-width="2" stroke-linecap="round"><polyline points="6 9 12 15 18 9"/></svg>
    </div>
    <button class="splash-start-btn" id="startBtn" onclick="startForm()">开始填写</button>
  </div>
</div>

<!-- ═══════════════ FORM ═══════════════ -->
<div class="mx" id="mainContent">
  <input type="hidden" name="token" id="token-input" value="">
  <div class="customer-hint" id="customer-hint">
    你好 <strong id="customer-name-display"></strong>！这是你的专属登记表
  </div>

  <div class="step-progress" id="stepProgress">
    <div class="step-dot active" data-step="1"><div class="step-circle">1</div><div class="step-label">基本</div></div>
    <div class="step-dot" data-step="2"><div class="step-circle">2</div><div class="step-label">外貌</div></div>
    <div class="step-dot" data-step="3"><div class="step-circle">3</div><div class="step-label">角色</div></div>
    <div class="step-dot" data-step="4"><div class="step-circle">4</div><div class="step-label">现状</div></div>
    <div class="step-dot" data-step="5"><div class="step-circle">5</div><div class="step-label">性格</div></div>
    <div class="step-dot" data-step="6"><div class="step-circle">6</div><div class="step-label">期待</div></div>
  </div>

  <div class="card" id="formCard">
    <div class="card-title">会员档案</div>

    <!-- Step 1: 基本 -->
    <div class="step-content" data-step="1">
      <div class="sec">关于你</div>
      <div class="fld req"><label>微信昵称</label><input id="f1" placeholder="你希望我们怎么称呼你？"></div>
      <div class="fld req"><label>所在城市</label><input id="f2" placeholder="如：广州、深圳"></div>
      <div class="fld req"><label>微信号</label><input id="f2c" placeholder="方便红娘联系你"></div>
      <div class="fld req"><label>手机号</label><input id="f2d" type="tel" placeholder="方便红娘紧急联系"></div>
      <div class="fld req"><label>家乡</label><input id="f2b" placeholder="如：湖南长沙、四川成都"></div>
      <div class="fld req"><label>出生年份</label><input id="f3" placeholder="如：1998 或 27岁"></div>
      <div class="fld req"><label>月收入范围</label><select id="f4"><option value="">请选择</option><option value="5k以下">5k以下</option><option value="5k-1w">5k-1w</option><option value="1w-2w">1w-2w</option><option value="2w以上">2w以上</option><option value="保密">保密</option></select></div>
      <div class="fld req"><label>行业</label><input id="f5" placeholder="如：互联网、金融、教育…"></div>
      <div class="fld req"><label>最高学历</label><select id="f6"><option value="">请选择</option><option value="高中及以下">高中及以下</option><option value="大专">大专</option><option value="本科">本科</option><option value="硕士">硕士</option><option value="博士及以上">博士及以上</option></select></div>
      <div class="btn-nav"><button type="button" class="btn" onclick="goStep(2)">下一步</button></div>
    </div>

    <!-- Step 2: 外貌 -->
    <div class="step-content h" data-step="2">
      <div class="sec">外貌与体型</div>
      <div class="fld req"><label>身高（cm）/ 体重（kg）</label><input id="f7" placeholder="格式：175/70"></div>
      <div class="fld req"><label>你的体型是？</label><select id="f8"><option value="">请选择</option><option value="瘦弱">瘦弱</option><option value="匀称">匀称</option><option value="肌肉">肌肉</option><option value="丰满">丰满</option><option value="微胖">微胖</option><option value="其他">其他</option></select></div>
      <div class="fld req"><label>希望对方体型？</label><input id="f9" placeholder="如：匀称+肌肉，或不限"></div>
      <div class="btn-nav"><button type="button" class="btn btn-sec" onclick="goStep(1)">上一步</button><button type="button" class="btn" onclick="goStep(3)">下一步</button></div>
    </div>

    <!-- Step 3: 角色 -->
    <div class="step-content h" data-step="3">
      <div class="sec">角色与属性</div>
      <div class="f2"><div class="fld req"><label>你的性角色</label><select id="f10"><option value="">请选择</option><option value="1">1</option><option value="0.5">0.5</option><option value="0">0</option><option value="side">side</option><option value="不分">不分</option><option value="其他">其他</option></select></div><div class="fld req"><label>期望对方角色</label><select id="f11"><option value="">不限</option><option value="1">1</option><option value="0.5">0.5</option><option value="0">0</option><option value="side">side</option><option value="不分">不分</option></select></div></div>
      <div class="btn-nav"><button type="button" class="btn btn-sec" onclick="goStep(2)">上一步</button><button type="button" class="btn" onclick="goStep(4)">下一步</button></div>
    </div>

    <!-- Step 4: 现状 -->
    <div class="step-content h" data-step="4">
      <div class="sec">感情现状</div>
      <div class="fld req"><label>单身多久了？</label><select id="f12"><option value="">请选择</option><option value="半年">半年</option><option value="1年">1年</option><option value="3年以上">3年以上</option><option value="从未恋爱过">从未恋爱过</option></select></div>
      <div class="fld req"><label>目前已出柜的对象</label><select id="f13"><option value="">请选择</option><option value="父母">父母</option><option value="部分家人">部分家人</option><option value="朋友">朋友</option><option value="同事">同事</option><option value="无人">无人</option></select></div>
      <div class="fld req"><label>是否考虑形婚？</label><select id="f14"><option value="">请选择</option><option value="是">是</option><option value="否">否</option><option value="不确定">不确定</option></select></div>
      <div class="fld req"><label>对脱单的态度？准备好同居了吗？</label><textarea id="f15" placeholder="例如：随缘但还没准备好同居；积极寻找可以接受同居等"></textarea></div>
      <div class="fld req"><label>恋爱/交往经验</label><select id="f16"><option value="">请选择</option><option value="无经验">无经验</option><option value="1段短期">1段短期</option><option value="1段长期">1段长期</option><option value="多段经历">多段经历</option><option value="曾经同居过">曾经同居过</option></select></div>
      <div class="btn-nav"><button type="button" class="btn btn-sec" onclick="goStep(3)">上一步</button><button type="button" class="btn" onclick="goStep(5)">下一步</button></div>
    </div>

    <!-- Step 5: 性格 -->
    <div class="step-content h" data-step="5">
      <div class="sec">个人特点</div>
      <div class="fld req"><label>用3–5个关键词形容自己</label><input id="f17" placeholder="如：内敛、幽默、宅、有规划"></div>
      <div class="fld req"><label>用3–5个关键词形容理想伴侣</label><input id="f18" placeholder="如：成熟、坦诚、有共同爱好"></div>
      <div class="fld req"><label>最不能接受的缺点是？</label><input id="f19" placeholder="只写一个，如：冷暴力/不忠诚/控制欲强"></div>
      <div class="fld req"><label>是否接受异地恋？</label><select id="f20"><option value="">请选择</option><option value="完全不行">完全不行</option><option value="可短期">可短期</option><option value="无所谓">无所谓</option><option value="仅限同城">仅限同城</option></select></div>
      <div class="fld req"><label>你通常怎么交友？</label><textarea id="f21" placeholder="例如：用小软件，觉得效率低但不方便线下"></textarea></div>
      <div class="btn-nav"><button type="button" class="btn btn-sec" onclick="goStep(4)">上一步</button><button type="button" class="btn" onclick="goStep(6)">下一步</button></div>
    </div>

    <!-- Step 6: 理想 + 提交 -->
    <div class="step-content h" data-step="6">
      <div class="sec">理想与补充</div>
      <div class="fld req"><label>描述你理想对象（年龄、身高、角色、类型）</label><textarea id="f22" placeholder="例如：28–35岁，175+，0.5，斯文成熟型"></textarea></div>
      <div class="fld req"><label>恋爱中你喜欢做什么？</label><textarea id="f23" placeholder="例如：喜欢互叫爱称、一起做饭、每天视频等"></textarea></div>
      <div class="fld req"><label>长久在一起最重要的因素是？</label><textarea id="f24" placeholder="一句话理由"></textarea></div>
      <div class="fld"><label>其他想说的</label><textarea id="f25" placeholder="自由填写"></textarea></div>
      <div class="sec">照片</div>
      <div class="ph-box" id="phBox"><div class="ph-icon">📸</div><div class="ph-txt">点击上传你的生活照片</div><input id="phFile" type="file" accept="image/*"><img id="phImg"></div>
      <div class="btn-nav"><button type="button" class="btn btn-sec" onclick="goStep(5)">上一步</button></div>
      <button type="button" class="btn-primary" id="submitBtn" onclick="doSubmit()">提交登记</button>
    </div>
  </div>

  <!-- ═══════════════ SUCCESS ═══════════════ -->
  <div class="success-card h" id="okCard">
    <img class="success-hero" src="https://yufeng.team/static/yufeng-register-success.png" alt="">
    <div class="success-body">
      <div class="success-icon"><svg viewBox="0 0 24 24" fill="none" stroke="#d48a5a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg></div>
      <h2>登记成功</h2>
      <p>你的信息已保存，红娘正在为你筛选合适的匹配人选，请留意微信消息。</p>
    </div>
  </div>
</div>

<script>
// ─── Splash Screen ───
var shownStartBtn = false;
setTimeout(function(){
  document.getElementById('startBtn').classList.add('show');
  document.getElementById('swipeHint').style.display = 'none';
  document.getElementById('swipeArrow').style.display = 'none';
  shownStartBtn = true;
}, 800);

document.getElementById('swipeArea').addEventListener('click', function(e){
  if(e.target.tagName !== 'BUTTON' && shownStartBtn){ startForm(); }
});

function startForm(){
  document.getElementById('splash').classList.add('slide-up');
  setTimeout(function(){
    document.getElementById('splash').style.display = 'none';
    var p=new URLSearchParams(window.location.search),t=p.get('token');
    if(t){
      document.getElementById('token-input').value=t;
      fetch('/api/wecom/tag/check-link?token='+encodeURIComponent(t))
        .then(function(r){return r.json();}).then(function(d){
          if(d.valid){
            document.getElementById('customer-hint').style.display='block';
            document.getElementById('customer-name-display').textContent=d.customer_name;
          }
        }).catch(function(){});
    }
  }, 600);
}

// ─── Touch drag to slide up splash ───
(function(){
  var sp=document.getElementById('splash'),startY=0,moveY=0,isDragging=false;
  sp.addEventListener('touchstart',function(e){
    startY=e.touches[0].clientY;isDragging=true;
  },{passive:true});
  sp.addEventListener('touchmove',function(e){
    if(!isDragging)return;
    moveY=e.touches[0].clientY;
    var dy=startY-moveY;
    if(dy>0){
      sp.style.transform='translateY(-'+Math.min(dy/2,100)+'px)';
      sp.style.opacity=1-(Math.min(dy,200)/200)*0.6;
    }
  },{passive:true});
  sp.addEventListener('touchend',function(e){
    isDragging=false;
    if(startY-moveY>80){
      startForm();
    }else{
      sp.style.transform='';
      sp.style.opacity='';
    }
  },{passive:true});
})();

// ─── Step Navigation ───
var currentStep = 1;
function goStep(n){
  document.querySelectorAll('.step-content').forEach(function(el){el.classList.add('h')});
  var t=document.querySelector('.step-content[data-step="'+n+'"]');
  if(t)t.classList.remove('h');
  document.querySelectorAll('.step-dot').forEach(function(d){
    var s=parseInt(d.getAttribute('data-step'));
    d.classList.remove('active','done');
    if(s===n)d.classList.add('active');
    else if(s<n)d.classList.add('done');
  });
  currentStep=n;window.scrollTo({top:0,behavior:'smooth'});
}

// ─── Photo Upload ───
(function(){
  var b=document.getElementById('phBox'),f=document.getElementById('phFile'),i=document.getElementById('phImg');
  b.addEventListener('click',function(){f.click();});
  f.addEventListener('change',function(){
    var g=f.files[0];if(!g)return;
    var r=new FileReader();
    r.onload=function(e){
      i.src=e.target.result;i.style.display='block';
      b.classList.add('has');
      b.querySelector('.ph-icon').style.display='none';
      b.querySelector('.ph-txt').textContent='点击更换';
    };
    r.readAsDataURL(g);
  });
})();

function $(id){var e=document.getElementById(id);return e?e.value.trim():'';}

async function doSubmit(){
  var required=[
    ['f1','请填写微信昵称'],['f2','请填写所在城市'],['f2c','请填写微信号'],['f2d','请填写手机号'],
    ['f2b','请填写家乡'],['f3','请填写出生年份'],['f4','请选择月收入范围'],['f5','请填写行业'],
    ['f6','请选择最高学历'],['f7','请填写身高/体重'],['f8','请选择你的体型'],
    ['f9','请填写期望对方体型'],['f10','请选择你的性角色'],['f11','请选择期望对方角色'],
    ['f12','请选择单身时长'],['f13','请选择出柜情况'],['f14','请选择是否考虑形婚'],
    ['f15','请填写你对脱单的态度'],['f16','请选择恋爱经验'],
    ['f17','请填写形容自己的关键词'],['f18','请填写理想伴侣的关键词'],
    ['f19','请填写最不能接受的缺点'],['f20','请选择是否接受异地恋'],
    ['f21','请填写交友方式'],['f22','请描述理想对象'],['f23','请填写恋爱中的偏好'],
    ['f24','请填写长久在一起最重要的因素']
  ];
  for(var i=0;i<required.length;i++){
    var el=document.getElementById(required[i][0]);
    if(!el||!el.value.trim()){alert(required[i][1]);if(el)el.focus();return;}
  }
  var btn=document.getElementById('submitBtn');
  btn.disabled=true;btn.classList.add('loading');
  var data={
    city:$('f2'),wechat:$('f2c'),phone:$('f2d'),hometown:$('f2b'),
    nickname:$('f1'),birth_info:$('f3'),income:$('f4'),job:$('f5'),education:$('f6'),
    hw:$('f7'),body_type:$('f8'),ideal_body_type:$('f9'),
    role_self:$('f10'),ideal_role:$('f11'),
    single_duration:$('f12'),out_status:$('f13'),marriage:$('f14'),
    attitude_live:$('f15'),experience:$('f16'),
    self_tags:$('f17'),ideal_type_tags:$('f18'),dealbreaker:$('f19'),
    long_distance:$('f20'),social_info:$('f21'),
    ideal_desc:$('f22'),love_habits:$('f23'),why_together:$('f24'),extra_message:$('f25'),
    token:(document.getElementById('token-input')||{}).value||'',
    source: window.location.pathname.includes("register-form-public")?"gongzhonghao":"",
    age:'',lifestyle_status:'',hobbies:'',current_situation:'',expectation:''
  };
  var p=document.getElementById('phFile').files[0];
  if(p){
    var r=new FileReader();
    r.onload=function(e){data.photo_base64=e.target.result.split(',')[1];sendForm(data);};
    r.readAsDataURL(p);
  }else{sendForm(data);}
}
async function sendForm(d){
  try{
    var r=await fetch('/api/wecom/tag/register-form-submit',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)
    });
    var j=await r.json();
    if(j.success){
      document.getElementById('formCard').classList.add('h');
      document.getElementById('okCard').classList.remove('h');
      window.scrollTo(0,0);
    }else{alert(j.detail||'提交失败');}
  }catch(e){alert('网络错误：'+e.message);}
  var btn=document.getElementById('submitBtn');
  btn.disabled=false;btn.classList.remove('loading');btn.textContent='提交登记';
}
</script>
</body>
</html>"""""
class RegisterFormData(BaseModel):
    nickname: str = ""
    city: str = ""
    age: str = ""
    height: str = ""
    weight: str = ""
    role_self: str = ""
    job: str = ""
    income: str = ""
    lifestyle_status: str = ""
    hobbies: str = ""
    current_situation: str = ""
    expectation: str = ""
    long_distance: str = ""  # 是否接受短暂异地
    body_type: str = ""  # 你认为自己的体型是
    token: str = ""  # 专属链接 token
    source: str = ""  # 来源渠道: gongzhonghao / zhuanshu / etc

@router.get("/register-form", response_class=HTMLResponse)
def register_form():
    """显示会员登记 H5 表单（支持 ?token=xxx 专属链接）"""
    return HTMLResponse(REGISTER_FORM_HTML)
@router.get("/register-form-public", response_class=HTMLResponse)
def register_form_public():
    """公众号专属链接，固定入口，来源标记为 gongzhonghao"""
    return HTMLResponse(REGISTER_FORM_HTML)


@router.get("/check-link")
async def check_link(token: str = Query(...), db: Session = Depends(get_db)):
    """校验 token 是否有效"""
    link = db.query(RegistrationLink).filter(RegistrationLink.token == token).first()
    if not link:
        return {"valid": False, "reason": "not_found"}
    if link.status == "used":
        return {"valid": False, "reason": "already_used"}
    return {
        "valid": True,
        "customer_name": link.customer_name,
    }


def _parse_age(age_str: str) -> int | None:
    """把年龄字符串转成整数"""
    try:
        return int(age_str.strip())
    except (ValueError, AttributeError):
        return None


def _parse_int(val: str) -> int | None:
    try:
        return int(val.strip())
    except (ValueError, AttributeError):
        return None


def _save_member_profile(db: Session, data: RegisterFormData, link: RegistrationLink, result: dict) -> None:
    """保存会员精简档案到 member_profiles 表（25题版）"""
    import base64 as _b64, os as _os

    # 解析身高体重
    height_val = None
    weight_val = None
    if data.hw and "/" in data.hw:
        parts = data.hw.split("/")
        try:
            if parts[0].strip().isdigit():
                height_val = int(parts[0].strip())
        except: pass
        try:
            if len(parts) > 1 and parts[1].strip().isdigit():
                weight_val = int(parts[1].strip())
        except: pass

    # 解析年龄
    age_val = None
    bi = data.birth_info.strip()
    import re as _re
    m = _re.search(r"(\d{4})", bi)
    if m:
        from datetime import datetime as _dt
        age_val = _dt.now().year - int(m.group(1))
    else:
        m = _re.search(r"(\d+)", bi)
        if m:
            try: age_val = int(m.group(1))
            except: pass

    # 保存照片
    photo_path = ""
    if data.photo_base64:
        PHOTO_DIR = "/data/yufeng-uploads/member_photos"
        import uuid as _uuid
        _os.makedirs(PHOTO_DIR, exist_ok=True)
        filename = f"member_{link.token}_{_uuid.uuid4().hex[:12]}.jpg"
        filepath = _os.path.join(PHOTO_DIR, filename)
        try:
            with open(filepath, "wb") as _f:
                _f.write(_b64.b64decode(data.photo_base64))
            photo_path = f"/static/member_photos/{filename}"
        except Exception:
            photo_path = "[照片上传失败]"

    # 拼接所有字段
    ext = []
    def _add(label, val):
        if val: ext.append(f"{label}：{val}")
    _add("微信昵称", data.nickname)
    _add("微信号", data.wechat)
    _add("手机号", data.phone)
    _add("家乡", data.hometown)
    _add("出生信息", data.birth_info)
    _add("月收入", data.income)
    _add("行业", data.job)
    _add("学历", data.education)
    _add("身高/体重", data.hw)
    _add("自评体型", data.body_type)
    _add("期望对方体型", data.ideal_body_type)
    _add("性角色", data.role_self)
    _add("期望对方角色", data.ideal_role)
    _add("单身时长", data.single_duration)
    _add("出柜情况", data.out_status)
    _add("形婚考虑", data.marriage)
    _add("脱单态度/同居", data.attitude_live)
    _add("交往经验", data.experience)
    _add("自我关键词", data.self_tags)
    _add("理想伴侣关键词", data.ideal_type_tags)
    _add("最不能接受", data.dealbreaker)
    _add("异地接受度", data.long_distance)
    _add("交友方式/看法", data.social_info)
    _add("理想对象描述", data.ideal_desc)
    _add("恋爱小癖好", data.love_habits)
    _add("长久因素", data.why_together)
    _add("其他/建议", data.extra_message)
    _add("照片", photo_path)

    lifestyle = "\n".join(ext) if ext else ""

    p = MemberProfile(
        external_userid=link.external_userid or "",
        employee_userid=link.employee_userid or "",
        token=link.token,
        nickname=data.nickname or (data.nickname if data.nickname else "匿名"),
        city=data.city or "",
        age=age_val,
        height=height_val,
        weight=weight_val,
        role_self=data.role_self or "",
        body_type=data.body_type or "",
        job=data.job or "",
        income=data.income or "",
        lifestyle_status=lifestyle,
        hobbies="",
        current_situation="",
        expectation="",
        tags_applied=json.dumps(result.get("tags", []), ensure_ascii=False),
        source=data.source or "",
    )
    # 自动评分
    try:
        from app.services.member_scorer import score_member
        profile = {
            "income": data.income or "",
            "city": data.city or "",
            "role_self": data.role_self or "",
            "ideal_role": data.ideal_role or "",
            "birth_info": data.birth_info or "",
            "nickname": data.nickname or "",
            "height": str(height_val or ""),
            "weight": str(weight_val or ""),
            "body_type": data.body_type or "",
            "job": data.job or "",
            "education": data.education or "",
            "hobbies": "",
            "current_situation": "",
            "expectation": data.ideal_desc or data.dealbreaker or "",
            "ideal_desc": data.ideal_desc or "",
            "dealbreaker": data.dealbreaker or "",
            "marriage": data.marriage or "",
            "photos": photo_path or "",
            "lifestyle_status": lifestyle,
            "long_distance": data.long_distance or "",
        }
        level, score, _ = score_member(profile)
        p.level = level
        p.level_score = score
    except Exception:
        pass
    
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

@router.post("/register-form-submit")
async def register_form_submit(data: RegisterFormData, db: Session = Depends(get_db)):
    """客户提交登记表（有 token 则自动打标签）"""
    if not data.nickname:
        raise HTTPException(400, "昵称不能为空")

    result = {
        "success": True,
        "message": "登记成功，运营人员会尽快联系你",
        "nickname": data.nickname,
        "age": data.age,
        "auto_tagged": False,
    }

    # ── 有 token：专属链接模式，自动打标签 ──
    if data.token:
        link = db.query(RegistrationLink).filter(
            RegistrationLink.token == data.token,
            RegistrationLink.status == "pending",
        ).first()

        if link:
            try:
                # 查找客户 external_userid：优先用链接里存好的，没有才按昵称搜
                ext_userid = link.external_userid
                if not ext_userid:
                    ext_userid = await find_external_userid(
                        link.employee_userid, link.customer_name
                    )
                    # 找到了就存一下，下次不用再搜
                    if ext_userid:
                        link.external_userid = ext_userid
                        db.commit()
                if ext_userid:
                    # 生成标签
                    # 适配新版字段到 evaluate_member_level 需要的格式
                    form_dict = {
                        "city": data.city,
                        "age": data.birth_info,
                        "role_self": data.role_self,
                        "income": data.income,
                        "nickname": data.nickname,
                        "job": data.job,
                        "lifestyle_status": (data.attitude_live + " " + data.social_info + " " + data.self_tags + " " + data.ideal_desc + " " + data.love_habits + " " + data.why_together + " " + data.extra_message).strip(),
                        "hobbies": "",
                        "current_situation": "",
                        "expectation": data.ideal_desc or data.dealbreaker or "",
                        "long_distance": data.long_distance,
                        "body_type": data.body_type,
                    }
                    tag_names = suggest_tags_from_form(form_dict)

                    # 打标签
                    await ensure_tag_group()
                    tag_ids = []
                    for name in tag_names:
                        tag_id = await ensure_tag(name)
                        tag_ids.append(tag_id)
                    await mark_tag(ext_userid, tag_ids, employee_userid=link.employee_userid)

                    # 计算年龄
                    age_str = ""
                    if data.age:
                        age_str = str(data.age)
                    elif data.birth_info:
                        import re
                        m = re.search(r"(\d{4})", data.birth_info)
                        if m:
                            from datetime import datetime
                            age_str = str(datetime.now().year - int(m.group(1)))

                    # 等级（从标签里取）
                    level = evaluate_member_level(form_dict)

                    # 自动备注（格式：昵称｜城市｜属性｜年龄｜等级）
                    try:
                        from app.services.wecom import remark_external_contact, upload_wecom_image_media
                        import io as _io, base64 as _b64
                        from PIL import Image as _Image

                        remark_text = f"{data.nickname or ''}｜{data.city or ''}｜{data.role_self or ''}｜{age_str}｜{level}"
                        desc = (
                            f"昵称: {data.nickname or ''}"
                            f" 城市: {data.city or ''}"
                            f" 年龄: {data.birth_info or ''}"
                            f" 属性: {data.role_self or ''}"
                            f" 身高/体重: {data.hw or ''}"
                            f" 体型: {data.body_type or ''}"
                            f" 职业: {data.job or ''}"
                            f" 学历: {data.education or ''}"
                            f" 收入: {data.income or ''}"
                            f" 微信: {data.wechat or ''}"
                            f" 手机: {data.phone or ''}"
                            f" 出柜: {data.out_status or ''}"
                            f" 单身: {data.single_duration or ''}"
                            f" 自我标签: {data.self_tags or ''}"
                            f" 理想型: {data.ideal_type_tags or ''}"
                            f" 雷区: {data.dealbreaker or ''}"
                            f" 异地: {data.long_distance or ''}"
                            f" 恋爱观: {data.love_habits or ''} {data.why_together or ''}"
                            f" 其他: {data.extra_message or ''}"
                        )
                        remark_pic_mediaid = ""
                        if data.photo_base64:
                            try:
                                # 解码 → 压缩（最长边800px）→ 保存临时文件 → 上传企微
                                img_data = _b64.b64decode(data.photo_base64)
                                img = _Image.open(_io.BytesIO(img_data))
                                # 压缩：最长边 800px，JPEG 质量 70
                                max_size = 800
                                w, h = img.size
                                if w > max_size or h > max_size:
                                    ratio = max_size / max(w, h)
                                    img = img.resize((int(w * ratio), int(h * ratio)), _Image.LANCZOS)
                                compressed = _io.BytesIO()
                                if img.mode in ("RGBA", "P"):
                                    img = img.convert("RGB")
                                img.save(compressed, format="JPEG", quality=70, optimize=True)
                                # 保存临时文件
                                import tempfile as _tf, os as _os
                                tmp_path = _os.path.join(_tf.gettempdir(), f"member_photo_{link.token}.jpg")
                                with open(tmp_path, "wb") as _f:
                                    _f.write(compressed.getvalue())
                                # 上传到企微
                                remark_pic_mediaid = await upload_wecom_image_media(tmp_path)
                                # 清理临时文件
                                try: _os.remove(tmp_path)
                                except: pass
                                desc += " [已传照片]"
                            except Exception as _pic_err:
                                desc += " [照片上传失败]"
                                pass

                        await remark_external_contact(
                            employee_userid=link.employee_userid,
                            external_userid=ext_userid,
                            remark=remark_text[:30],
                            description=desc[:500],
                            remark_pic_mediaid=remark_pic_mediaid,
                        )
                    except Exception:
                        pass  # 备注失败不阻断

                    result["auto_tagged"] = True
                    result["external_userid"] = ext_userid
                    result["tags_applied"] = tag_names
                else:
                    result["tag_warning"] = "客户不在最近客户列表中，需手动补打标签"
            except Exception as e:
                # 打标签失败不阻断表单提交
                result["tag_error"] = str(e)

            # 无论打标签成功与否，链接标记为已使用
            link.status = "used"
            link.used_at = datetime.now(timezone.utc)
            link.submit_result = json.dumps({
                "nickname": data.nickname,
                "city": data.city,
                "age": data.age,
                "role_self": data.role_self,
                "tags_applied": result.get("tags_applied", []),
                "auto_tagged": result["auto_tagged"],
            }, ensure_ascii=False)

            # 保存到会员档案表（同 external_userid 则更新）
            try:
                _save_member_profile(db, data, link, result)
            except Exception:
                pass  # 存档案失败不阻断主流程

            db.commit()

            # ── 匹配 + 推送 ──
            try:
                # 查出刚保存的 profile
                saved_profile = db.query(MemberProfile).filter(
                    MemberProfile.token == link.token
                ).first()
                if saved_profile and saved_profile.nickname:
                    matches = find_matches(db, saved_profile, limit=5)
                    if matches and link.employee_userid:
                        push_text = (
                            f"🎯 新人登记：{saved_profile.nickname}\n"
                            f"📋 城市·{saved_profile.city or '?'} "
                            f"年龄·{saved_profile.age or '?'} "
                            f"属性·{saved_profile.role_self or '?'}\n"
                            f"━━━━━━━━━━━━━━━━\n"
                        )
                        for i, m in enumerate(matches, 1):
                            push_text += f"\n{i}. {m['description']}\n"
                            push_text += f"   💯 匹配度 {m['scores']['total']}%\n"
                        push_text += (
                            f"\n━━━━━━━━━━━━━━━━\n"
                            f"💡 建议：把以上资料发给客户，让他选感兴趣的人"
                        )
                        await send_text_to_employee(link.employee_userid, push_text)
                        result["matched_count"] = len(matches)
            except Exception as e:
                result["push_warning"] = str(e)

    return result

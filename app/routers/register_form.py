"""渠道主推广登记表 — 独立路由，完整表单 + 二维码

路径: /partner/reg/{partner_id}
"""
from __future__ import annotations

import base64
import os
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.partner_router import ChannelPartner, PartnerRegister

router = APIRouter(prefix="/partner/reg", tags=["渠道主完整登记表"])

PHOTO_DIR = "/data/yufeng-uploads/channel_photos"
FALLBACK_QR = "/static/wecom-qr.png"


# ═══════════════════════════════════════════════════════════════
# GET: 登记表页面
# ═══════════════════════════════════════════════════════════════

@router.get("/{partner_id}", response_class=HTMLResponse)
def register_page(partner_id: str, db: Session = Depends(get_db)):
    """渠道主专属登记表页面"""
    partner = db.query(ChannelPartner).filter(
        ChannelPartner.partner_id == partner_id,
        ChannelPartner.status == "active",
    ).first()
    if not partner:
        return HTMLResponse(content='<div style="text-align:center;padding:40px;font-family:sans-serif"><h3>链接无效</h3><p>渠道主不存在或未通过审核</p></div>')

    qr_url = partner.qr_code or FALLBACK_QR

    html = _FORM_HTML.replace("__PID__", partner_id).replace("__QR_URL__", qr_url)
    return HTMLResponse(content=html)


# ═══════════════════════════════════════════════════════════════
# POST: 提交登记表
# ═══════════════════════════════════════════════════════════════

@router.post("/{partner_id}")
async def register_submit(partner_id: str, request: Request, db: Session = Depends(get_db)):
    """提交完整登记表（JSON body）"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="数据格式错误")

    name = (body.get("name") or "").strip()
    wechat = (body.get("wechat") or "").strip()

    if not name:
        raise HTTPException(status_code=400, detail="请填写昵称")
    if not wechat:
        raise HTTPException(status_code=400, detail="微信号必填")

    partner = db.query(ChannelPartner).filter(
        ChannelPartner.partner_id == partner_id,
        ChannelPartner.status == "active",
    ).first()
    if not partner:
        raise HTTPException(status_code=404, detail="渠道主不存在")

    # 处理照片
    photo_path = ""
    photo_b64 = body.get("photo_base64") or ""
    if photo_b64:
        os.makedirs(PHOTO_DIR, exist_ok=True)
        filename = f"{partner_id}_{uuid.uuid4().hex[:12]}.jpg"
        filepath = os.path.join(PHOTO_DIR, filename)
        try:
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(photo_b64))
            photo_path = f"/static/channel_photos/{filename}"
        except Exception:
            photo_path = "[照片上传失败]"

    # 组装完整备注
    note_parts = {
        "wechat": wechat,
        "age": body.get("age", ""),
        "height": body.get("height", ""),
        "weight": body.get("weight", ""),
        "role_self": body.get("role_self", ""),
        "body_type": body.get("body_type", ""),
        "income": body.get("income", ""),
        "job": body.get("job", ""),
        "city": body.get("city", ""),
        "lifestyle_status": body.get("lifestyle_status", ""),
        "hobbies": body.get("hobbies", ""),
        "current_situation": body.get("current_situation", ""),
        "expectation": body.get("expectation", ""),
        "long_distance": body.get("long_distance", ""),
        "photo": photo_path,
    }
    note_json = str({k: v for k, v in note_parts.items() if v})

    # 记录填表
    register = PartnerRegister(
        partner_id=partner_id,
        customer_name=name,
        customer_phone=body.get("phone", "").strip(),
        status="pending",
        note=note_json,
    )
    partner.total_registers = (partner.total_registers or 0) + 1
    db.add(register)
    db.commit()

    return {"success": True, "message": f"{name}，登记成功！请添加屿风企微"}


# ═══════════════════════════════════════════════════════════════
# HTML 模板
# ═══════════════════════════════════════════════════════════════

_FORM_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>屿风 · 会员登记</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,"PingFang SC","Helvetica Neue",sans-serif;background:linear-gradient(135deg,#1a1a2e,#16213e);color:#e8e8e8;min-height:100vh;padding:20px}
.mx{max-width:520px;margin:0 auto}
.card{background:rgba(22,33,62,.92);backdrop-filter:blur(20px);border:1px solid #233554;border-radius:20px;padding:28px 22px;margin-bottom:14px}
h1{font-size:20px;color:#e94560;text-align:center;font-weight:600;margin-bottom:4px}
.sub{text-align:center;color:#8892b0;font-size:13px;margin-bottom:22px}
.sec{font-size:13px;font-weight:600;color:#e94560;margin:16px 0 10px;padding-bottom:5px;border-bottom:1px solid rgba(233,69,96,.18)}
.fld{margin-bottom:14px}
.fld label{display:block;font-size:12px;color:#8892b0;margin-bottom:4px;font-weight:500}
.fld.req label::after{content:" *";color:#e94560}
input,select,textarea{width:100%;padding:11px 13px;font-size:14px;background:#0d1b2a;color:#e8e8e8;border:1px solid #233554;border-radius:10px;outline:none;font-family:inherit;transition:border-color .2s;-webkit-appearance:none}
input:focus,select:focus,textarea:focus{border-color:#e94560}
textarea{resize:vertical;min-height:68px}
select{appearance:none;background-image:url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3e%3cpath fill='none' stroke='%238892b0' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='m2 5 6 6 6-6'/%3e%3c/svg%3e");background-repeat:no-repeat;background-position:right 10px center;background-size:14px;padding-right:32px}
.f2{display:flex;gap:10px}.f2 .fld{flex:1}
.btn{width:100%;padding:14px;font-size:16px;font-weight:600;color:#fff;background:linear-gradient(135deg,#e94560,#d63850);border:none;border-radius:12px;cursor:pointer;margin-top:8px;transition:opacity .2s}
.btn:active{opacity:.85}
.btn:disabled{opacity:.5;cursor:not-allowed}
.ph{border:2px dashed #233554;border-radius:12px;padding:20px;text-align:center;cursor:pointer;transition:border-color .2s}
.ph:hover,.ph.has{border-color:#e94560}
.ph.has{padding:10px}
.ph input{display:none}
.ph .icon{font-size:30px;color:#8892b0;margin-bottom:6px}
.ph .txt{font-size:12px;color:#8892b0}
.ph img{max-width:120px;max-height:120px;border-radius:10px;margin-top:6px;display:none}
.ft{text-align:center;font-size:11px;color:#495670;margin-top:14px}
/* 成功页 */
.ok{text-align:center;padding:20px}
.ok .em{font-size:44px;margin-bottom:14px}
.ok h2{font-size:18px;color:#64ffda;margin-bottom:6px}
.ok p{color:#8892b0;font-size:13px}
.qr{border-radius:16px;background:#fff;width:200px;height:200px;margin:14px auto;display:flex;align-items:center;justify-content:center;overflow:hidden;border:2px solid #e94560}
.qr img{width:100%;height:100%;object-fit:contain}
.feat p{font-size:13px;color:#ccd6f6;padding:5px 0;display:flex;align-items:center;gap:8px}
.h{display:none}
</style>
</head>
<body>
<div class="mx">

  <!-- 登记表 -->
  <div class="card" id="formCard">
    <h1>屿风会员登记</h1>
    <p class="sub">填写真实资料，红娘为你精准匹配</p>

    <div class="sec">📌 联系方式</div>
    <div class="fld req"><label>你的昵称</label><input id="a1" placeholder="怎么称呼你" /></div>
    <div class="fld req"><label>微信号</label><input id="a2" placeholder="方便红娘联系你" /></div>
    <div class="fld"><label>手机号</label><input id="a3" type="tel" placeholder="选填" /></div>

    <div class="sec">📍 基本情况</div>
    <div class="f2">
      <div class="fld"><label>年龄</label><input id="a4" type="number" placeholder="30" min="16" max="99" /></div>
      <div class="fld"><label>身高(cm)</label><input id="a5" type="number" placeholder="185" min="100" max="250" /></div>
      <div class="fld"><label>体重(kg)</label><input id="a6" type="number" placeholder="75" min="30" max="200" /></div>
    </div>
    <div class="f2">
      <div class="fld"><label>属性</label><select id="a7"><option value="">请选择</option><option value="1">1</option><option value="0.5">0.5</option><option value="0">0</option><option value="side">side</option></select></div>
      <div class="fld"><label>体型</label><select id="a8"><option value="">请选择</option><option value="匀称">匀称</option><option value="肌肉">肌肉</option><option value="壮实">壮实</option><option value="精瘦">精瘦</option><option value="偏胖">偏胖</option></select></div>
      <div class="fld"><label>收入</label><select id="a9"><option value="">请选择</option><option value="5k以下">5k以下</option><option value="5k-1w">5k-1w</option><option value="1w-3w">1w-3w</option><option value="3w-10w">3w-10w</option><option value="10w以上">10w以上</option></select></div>
    </div>
    <div class="fld"><label>职业</label><input id="a10" placeholder="互联网、自由职业…" /></div>
    <div class="fld"><label>所在城市</label><input id="a11" placeholder="广州、深圳" /></div>

    <div class="sec">✈️ 日常状态</div>
    <div class="fld"><textarea id="a12" placeholder="说说你当前的日常状态…"></textarea></div>

    <div class="sec">💪 爱好与习惯</div>
    <div class="fld"><textarea id="a13" placeholder="平时喜欢做什么？"></textarea></div>

    <div class="sec">🎐 目前状况</div>
    <div class="fld"><textarea id="a14" placeholder="对感情的态度和期望…"></textarea></div>

    <div class="sec">💝 期待的你</div>
    <div class="fld"><textarea id="a15" placeholder="你希望对方是什么样的人？"></textarea></div>
    <div class="fld"><label>是否接受短暂异地</label><select id="a16"><option value="">请选择</option><option value="接受">接受</option><option value="不接受">不接受</option></select></div>

    <div class="sec">📷 上传照片</div>
    <div class="ph" id="phBox"><div class="icon">+</div><div class="txt">点击上传生活照</div><input id="phFile" type="file" accept="image/*"/><img id="phImg" /></div>

    <button class="btn" id="submitBtn" onclick="doSubmit()">提交登记</button>
    <p class="ft">提交后红娘会尽快联系你</p>
  </div>

  <!-- 成功页 -->
  <div class="card h" id="okCard">
    <div class="ok"><div class="em">✅</div><h2>登记成功！</h2><p>添加屿风企微，获取专属匹配服务</p></div>
    <div class="qr"><img src="__QR_URL__" alt="屿风企微二维码" /></div>
    <div class="feat"><p>✅ 实名认证，真实资料可查</p><p>🎯 AI智能匹配，多维度推荐</p><p>🔒 隐私保护，敏感信息隐藏</p><p>💬 专业红娘1对1牵线</p></div>
    <p class="ft">长按识别二维码添加企微</p>
  </div>

</div>
<script>
(function(){
  var phBox=document.getElementById("phBox");
  var phFile=document.getElementById("phFile");
  var phImg=document.getElementById("phImg");

  phBox.addEventListener("click",function(e){e.stopPropagation();phFile.click();});
  phFile.addEventListener("change",function(){
    var f=phFile.files[0];if(!f)return;
    var r=new FileReader();
    r.onload=function(e){
      phImg.src=e.target.result;phImg.style.display="block";
      phBox.classList.add("has");
      phBox.querySelector(".icon").style.display="none";
      phBox.querySelector(".txt").textContent="点击更换";
    };
    r.readAsDataURL(f);
  });
})();

async function doSubmit(){
  var n=$("a1"),w=$("a2");
  if(!n){alert("请填写昵称");return;}
  if(!w){alert("微信号必填");return;}
  var b=document.getElementById("submitBtn");b.disabled=true;b.textContent="提交中…";

  var data={
    name:n,wechat:w,
    phone:$("a3"),age:$("a4"),height:$("a5"),weight:$("a6"),
    role_self:$("a7"),body_type:$("a8"),income:$("a9"),
    job:$("a10"),city:$("a11"),
    lifestyle_status:$("a12"),hobbies:$("a13"),
    current_situation:$("a14"),expectation:$("a15"),
    long_distance:$("a16")
  };

  var f=document.getElementById("phFile").files[0];
  if(f){data.photo_base64=await toBase64(f);}

  try{
    var r=await fetch("/partner/reg/__PID__",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
    var j=await r.json();
    if(j.success){
      document.getElementById("formCard").classList.add("h");
      document.getElementById("okCard").classList.remove("h");
      window.scrollTo(0,0);
    }else{alert(j.detail||"提交失败");}
  }catch(e){alert("网络错误："+e.message);}
  b.disabled=false;b.textContent="提交登记";
}

function $(id){return(document.getElementById(id)||{}).value.toString().trim();}
function toBase64(file){return new Promise(function(res,rej){
  var r=new FileReader();r.onload=function(e){res(e.target.result.split(",")[1]);};r.onerror=rej;r.readAsDataURL(file);
});}
</script>
</body>
</html>"""

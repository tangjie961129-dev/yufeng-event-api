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
    send_text_to_employee,
)
from app.services.matching_service import find_matches

router = APIRouter(prefix="/api/wecom/tag", tags=["企微客户打标签"])


# ─── 第一步：生成专属填表链接 ────────────────────────────────


class GenerateLinkRequest(BaseModel):
    employee_userid: str = ""
    customer_name: str = ""


class GenerateLinkResponse(BaseModel):
    token: str
    url: str
    customer_name: str


@router.post("/generate-link")
async def generate_link(req: GenerateLinkRequest, db: Session = Depends(get_db)):
    """生成专属填表链接

    员工指定客户名 → 系统生成唯一 token → 返回链接
    员工把链接发给对应客户即可。
    """
    if not req.customer_name:
        raise HTTPException(400, "缺少客户名称 customer_name")
    if not req.employee_userid:
        raise HTTPException(400, "缺少员工 userid employee_userid")

    token = uuid.uuid4().hex
    link = RegistrationLink(
        token=token,
        employee_userid=req.employee_userid,
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


REGISTER_FORM_HTML = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>屿风会员登记</title>
<meta property="og:title" content="屿风会员登记" />
<meta property="og:description" content="填写资料，找到你的专属缘分" />
<meta property="og:image" content="https://yufeng.team/static/logo.jpg" />
<meta property="og:image:width" content="1500" />
<meta property="og:image:height" content="1500" />
<meta property="og:type" content="website" />
<meta property="og:url" content="https://yufeng.team/api/wecom/tag/register-form" />
<meta name="twitter:card" content="summary_large_image" />
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, 'PingFang SC', 'Helvetica Neue', sans-serif; background: #f8f6f3; color: #2c2c2c; padding: 16px; }
.container { max-width: 500px; margin: 0 auto; }
h1 { font-size: 20px; font-weight: 600; text-align: center; margin: 20px 0 4px; color: #1a1a1a; }
.subtitle { text-align: center; color: #999; font-size: 13px; margin-bottom: 20px; }
.customer-hint { background: #fff8e7; border: 1px solid #f0dba8; border-radius: 10px; padding: 10px 14px; margin-bottom: 16px; font-size: 13px; color: #8b6f3c; display: none; }
.customer-hint strong { font-weight: 600; }
.section-title { font-size: 15px; font-weight: 600; color: #d4a373; margin: 20px 0 12px; padding-bottom: 6px; border-bottom: 2px solid #f0dba8; }
.field-row { display: flex; gap: 10px; margin-bottom: 14px; }
.field-row .form-group { flex: 1; margin-bottom: 0; }
.form-group { margin-bottom: 14px; }
label { display: block; font-size: 13px; font-weight: 500; color: #555; margin-bottom: 5px; }
input, select, textarea {
    width: 100%; padding: 10px 12px; font-size: 14px; border: 1px solid #e0ddd9;
    border-radius: 8px; background: #fff; outline: none; transition: border-color .2s;
}
input:focus, select:focus, textarea:focus { border-color: #d4a373; }
textarea { resize: vertical; min-height: 70px; }
.btn {
    width: 100%; padding: 13px; font-size: 15px; font-weight: 600; color: #fff;
    background: linear-gradient(135deg, #d4a373, #c4945e); border: none; border-radius: 10px;
    cursor: pointer; margin-top: 6px; transition: opacity .2s;
}
.btn:hover { opacity: .9; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.success { display: none; text-align: center; padding: 50px 20px; }
.success .icon { font-size: 44px; margin-bottom: 14px; }
.success h2 { font-size: 19px; margin-bottom: 8px; }
.success p { color: #888; font-size: 14px; }
.tip { font-size: 12px; color: #bbb; margin-top: 16px; text-align: center; }
.error-box { display: none; text-align: center; padding: 50px 20px; }
.error-box .icon { font-size: 44px; margin-bottom: 14px; }
.error-box h2 { font-size: 19px; margin-bottom: 8px; }
.error-box p { color: #888; font-size: 14px; }
</style>
</head>
<body>
<div class="container" id="form-container">
    <h1>🌸 屿风会员登记</h1>
    <p class="subtitle">填写后系统会自动为你建立专属档案</p>
    <div class="customer-hint" id="customer-hint">你好 <strong id="customer-name-display"></strong>！请填写以下信息完成登记。</div>
    <form id="register-form">
        <input type="hidden" name="token" id="token-input" value="">

        <div class="section-title">📍 基本情况</div>

        <div class="form-group">
            <label>你的昵称 *</label>
            <input type="text" name="nickname" required placeholder="你希望我们怎么称呼你？">
        </div>

        <div class="form-group">
            <label>所在城市</label>
            <input type="text" name="city" placeholder="如：广州、深圳">
        </div>

        <div class="field-row">
            <div class="form-group">
                <label>年龄</label>
                <input type="number" name="age" placeholder="如 30" min="16" max="99">
            </div>
            <div class="form-group">
                <label>身高 (cm)</label>
                <input type="number" name="height" placeholder="如 185" min="100" max="250">
            </div>
            <div class="form-group">
                <label>体重 (kg)</label>
                <input type="number" name="weight" placeholder="如 79" min="30" max="200">
            </div>
        </div>

        <div class="field-row">
            <div class="form-group">
                <label>属性</label>
                <select name="role_self">
                    <option value="">请选择</option>
                    <option value="1">1</option>
                    <option value="0.5">0.5</option>
                    <option value="0">0</option>
                    <option value="side">side</option>
                    <option value="双">双（男女皆可）</option>
                </select>
            </div>
            <div class="form-group">
                <label>体型</label>
                <select name="body_type">
                    <option value="">请选择</option>
                    <option value="匀称">匀称</option>
                    <option value="肌肉">肌肉</option>
                    <option value="壮实">壮实</option>
                    <option value="精瘦">精瘦</option>
                    <option value="偏胖">偏胖</option>
                </select>
            </div>
            <div class="form-group">
                <label>收入</label>
                <select name="income">
                    <option value="">请选择</option>
                    <option value="5000以下">5k 以下</option>
                    <option value="5000-10000">5k-1w</option>
                    <option value="1w-3w">1w-3w</option>
                    <option value="3w-10w">3w-10w</option>
                    <option value="10w以上">10w 以上</option>
                    <option value="保密">保密</option>
                </select>
            </div>
        </div>

        <div class="form-group">
            <label>职业</label>
            <input type="text" name="job" placeholder="如：互联网、自由职业……">
        </div>

        <div class="section-title">✈ 日常状态</div>
        <div class="form-group">
            <textarea name="lifestyle_status" placeholder="说说你当前的日常状态，工作在哪儿、作息怎么样、圈子风格……"></textarea>
        </div>

        <div class="section-title">💪 爱好与习惯</div>
        <div class="form-group">
            <textarea name="hobbies" placeholder="平时喜欢做什么？运动、音乐、美食、旅行……"></textarea>
        </div>

        <div class="section-title">🎐 目前状况</div>
        <div class="form-group">
            <textarea name="current_situation" placeholder="工作生活状态如何？对感情的态度和期望……"></textarea>
        </div>

        <div class="section-title">💝 期待的你</div>
        <div class="form-group">
            <textarea name="expectation" placeholder="你希望对方是什么样的人？性格、三观……"></textarea>
        </div>
        <div class="form-group">
            <label>是否接受短暂异地</label>
            <select name="long_distance">
                <option value="">请选择</option>
                <option value="接受">接受</option>
                <option value="不接受">不接受</option>
                <option value="看情况">看情况</option>
            </select>
        </div>

        <button type="submit" class="btn" id="submit-btn">提交登记</button>
        <p class="tip">提交后我们会根据你的信息做精准匹配</p>
    </form>
</div>
<div class="success" id="success-container">
    <div class="icon">✅</div>
    <h2>登记成功</h2>
    <p>你的信息已保存，我们会尽快为你匹配合适的人选。</p>
</div>
<div class="error-box" id="error-container">
    <div class="icon">⚠️</div>
    <div id="error-message"><h2>链接无效</h2><p>这个登记链接已失效，请联系拉你进群的屿风工作人员获取新链接。</p></div>
</div>
<script>
const params = new URLSearchParams(window.location.search);
const token = params.get('token');
if (token) {
    document.getElementById('token-input').value = token;
    fetch('/api/wecom/tag/check-link?token=' + encodeURIComponent(token))
        .then(r => r.json())
        .then(data => {
            if (data.valid) {
                document.getElementById('customer-hint').style.display = 'block';
                document.getElementById('customer-name-display').textContent = data.customer_name;
            } else {
                document.getElementById('form-container').style.display = 'none';
                const errBox = document.getElementById('error-container');
                const errMsg = document.getElementById('error-message');
                if (data.reason === 'already_used') {
                    errMsg.innerHTML = '<h2>已使用</h2><p>这份登记表之前已经提交过了，无需重复填写。</p>';
                } else {
                    errMsg.innerHTML = '<h2>链接无效</h2><p>这个登记链接已失效，请联系拉你进群的屿风工作人员获取新链接。</p>';
                }
                errBox.style.display = 'block';
            }
        })
        .catch(() => {});
}
document.getElementById('register-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const btn = document.getElementById('submit-btn');
    btn.disabled = true; btn.textContent = '提交中...';
    const form = new FormData(this);
    const data = {};
    form.forEach((v, k) => { data[k] = v; });
    try {
        const resp = await fetch('/api/wecom/tag/register-form-submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!resp.ok) { const err = await resp.json(); alert('提交失败: ' + (err.detail || '未知错误')); btn.disabled = false; btn.textContent = '提交登记'; return; }
        document.getElementById('form-container').style.display = 'none';
        document.getElementById('success-container').style.display = 'block';
    } catch(e) {
        alert('网络错误，请重试');
        btn.disabled = false; btn.textContent = '提交登记';
    }
});
</script>
</body>
</html>
"""


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


@router.get("/register-form", response_class=HTMLResponse)
def register_form():
    """显示会员登记 H5 表单（支持 ?token=xxx 专属链接）"""
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
    """保存或更新会员档案"""
    ext_userid = result.get("external_userid") or ""

    profile = None
    if ext_userid:
        profile = db.query(MemberProfile).filter(
            MemberProfile.external_userid == ext_userid
        ).first()

    if not profile:
        profile = MemberProfile()

    profile.external_userid = ext_userid if ext_userid else None
    profile.employee_userid = link.employee_userid
    profile.token = link.token
    profile.nickname = data.nickname
    profile.city = data.city
    profile.age = _parse_age(data.age)
    profile.height = _parse_int(data.height)
    profile.weight = _parse_int(data.weight)
    profile.role_self = data.role_self
    profile.body_type = data.body_type
    profile.job = data.job
    profile.income = data.income
    profile.lifestyle_status = data.lifestyle_status
    profile.hobbies = data.hobbies
    profile.current_situation = data.current_situation
    profile.expectation = data.expectation
    profile.long_distance = data.long_distance
    profile.tags_applied = json.dumps(result.get("tags_applied", []), ensure_ascii=False)

    db.add(profile)


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
                # 查找客户 external_userid
                ext_userid = await find_external_userid(
                    link.employee_userid, link.customer_name
                )
                if ext_userid:
                    # 生成标签
                    form_dict = {
                        "city": data.city,
                        "age": data.age,
                        "role_self": data.role_self,
                        "lifestyle_status": data.lifestyle_status,
                        "hobbies": data.hobbies,
                        "current_situation": data.current_situation,
                        "expectation": data.expectation,
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

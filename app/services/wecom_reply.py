"""企微回调回复构建工具模块

封装所有回复文本的生成逻辑，保持 wx_kf.py 主逻辑简洁。
"""

import json
from datetime import date

from app.models.member_profile import MemberProfile


# ─── XML 回复构建 ─────────────────────────────────────────────


def _build_text_reply_xml(from_user: str, to_user: str, content: str) -> str:
    """构造文本回复的 XML"""
    import time
    create_time = int(time.time())
    return f"""<xml>
<ToUserName><![CDATA[{from_user}]]></ToUserName>
<FromUserName><![CDATA[{to_user}]]></FromUserName>
<CreateTime>{create_time}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""


# ─── 自定义菜单回复 ─────────────────────────────────────────


_MENU_ACTIONS = [
    # 结构：(keys列表, 标题, 说明, 快捷指令)
    # -- 会员服务 --
    (["YF_MEMBER_LINK", "link", "登记链接", "发链接", "发登记链接"],
     "🔗 发登记链接",
     "生成客户专属填表链接，填表后自动打标签入档。",
     "给{客户名字}发填表链接"),

    (["YF_MEMBER_LOOKUP", "lookup", "查档案", "查询", "档案"],
     "📋 查会员档案",
     "查询客户的完整资料、标签和匹配偏好。",
     "查{客户名字}的档案"),

    (["YF_MEMBER_MATCH", "match", "推荐", "匹配", "推荐匹配"],
     "💞 推荐匹配",
     "根据已填表的会员资料，推荐合适的匹配人选。",
     "给{客户名字}推荐匹配"),

    # -- 运营 --
    (["YF_RULES", "rules", "规则", "修改规则", "后台规则"],
     "⚙️ 修改规则",
     "动态查询，点击后查看当前图片提示词规则，可发文字修改。",
     ""),

    # -- 朋友圈 --
    (["YF_DAILY_PREVIEW", "preview", "朋友圈预览", "预览", "今日朋友圈预览"],
     "📅 今日朋友圈预览",
     "动态查询，点击后返回今日朋友圈实时状态。",
     "今日朋友圈预览"),
]


def _build_menu_reply(event_key: str) -> str | None:
    """根据 EventKey 匹配菜单动作，返回回复文本，匹配不到返回 None"""
    ek_upper = event_key.upper().strip()

    key_to_action: dict[str, dict] = {}
    for names, title, desc, shortcut in _MENU_ACTIONS:
        for name in names:
            key_to_action[name.upper()] = {"title": title, "desc": desc, "shortcut": shortcut}

    action = key_to_action.get(ek_upper)
    if not action and ek_upper.endswith("_HELP"):
        action = key_to_action.get(ek_upper[:-5])
    if not action:
        for names, title, desc, shortcut in _MENU_ACTIONS:
            check_names = [n.upper() for n in names]
            if any(ek_upper in n or n in ek_upper for n in check_names):
                action = {"title": title, "desc": desc, "shortcut": shortcut}
                break

    if not action:
        return None

    lines = [f"━━━ {action['title']} ━━━", "", action["desc"]]
    shortcut = action.get("shortcut")
    if shortcut:
        has_placeholder = "{" in shortcut
        if has_placeholder:
            lines += ["", "💡 快捷指令：复制下方文字替换客户名后发送", f"📋 {shortcut}"]
        else:
            lines += ["", "💡 点击或复制下方文字直接发送👇", f"📋 {shortcut}"]
    return "\n".join(lines)


# ─── 今日朋友圈预览（动态查询） ──────────────────────────


def _read_today_posts_json() -> dict | None:
    """读取本地的 today_posts.json"""
    today = date.today().isoformat()
    remote_path = f"/home/ubuntu/yufeng-daily/output/{today}/today_posts.json"
    try:
        with open(remote_path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, OSError):
        return None


# ─── 规则查看/修改 ──────────────────────────────────────────

CONFIG_PATH = "/home/ubuntu/yufeng-daily/config/moments_config.json"


def _read_rules() -> dict | None:
    """读取 moments_config.json"""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, OSError):
        return None


def _build_rules_reply() -> str:
    """构建规则查看回复"""
    config = _read_rules()
    lines = ["━━━ ⚙️ 图片提示词规则 ━━━", ""]

    if not config:
        lines.append("⚠️ 配置文件不可读。")
        return "\n".join(lines)

    prompts = config.get("prompts", {})

    # 图片后缀规则（最重要的）
    suffix = prompts.get("member_image_suffix", "未设置")
    lines.append("📷 会员配图提示词后缀（member_image_suffix）：")
    lines.append(f"“{suffix}”")
    lines.append("")

    # 场景/着装规则（代码里硬编码的）
    lines.append("🎨 会员配图场景规则（代码自动匹配年龄）：")
    lines.append("25岁以下 → 休闲T恤/卫衣,校园或咖啡馆")
    lines.append("26-30岁 → 白色衬衫或Polo衫,都市青年感")
    lines.append("31-35岁 → 休闲西装或质感针织衫,成熟有品位")
    lines.append("35岁以上 → 深色Polo衫或薄夹克,稳重大方")
    lines.append("")

    # 配对图片规则
    match_rule = prompts.get("match_copy_rule", "未设置")
    lines.append("💕 配对喜报文案规则：")
    lines.append(f"“{match_rule}”")
    lines.append("")

    # 技巧/观察图片规则
    tip_rule = prompts.get("tip_copy_rule", "未设置")
    lines.append("💡 恋爱技巧文案规则：")
    lines.append(f"“{tip_rule}”")
    lines.append("")

    # 会员点评规则
    comment_rule = prompts.get("member_comment_instruction", "未设置")
    lines.append("✍️ 会员点评文案规则：")
    lines.append(f"“{comment_rule}”")
    lines.append("")

    lines.append("💡 要修改规则，直接说：")
    lines.append("「把配图规则改成……」")
    lines.append("「把配对文案规则改成……」")
    lines.append("「把技巧文案规则改成……」")
    lines.append("「把点评规则改成……」")

    return "\n".join(lines)


def _update_rule(keyword: str, new_value: str) -> tuple[bool, str]:
    """修改规则，返回(成功, 消息)"""
    config = _read_rules()
    if not config:
        return False, "配置文件不可读"

    prompts = config.setdefault("prompts", {})

    # 匹配关键词到规则key
    rule_map = {
        "配图": "member_image_suffix",
        "图片": "member_image_suffix",
        "配对配图": "match_image_rule",
        "配对图片": "match_image_rule",
        "喜报配图": "match_image_rule",
        "Tips海报": "tip_image_rule",
        "海报": "tip_image_rule",
        "配对": "match_copy_rule",
        "喜报": "match_copy_rule",
        "技巧": "tip_copy_rule",
        "观察": "tip_copy_rule",
        "点评": "member_comment_instruction",
        "会员": "member_comment_instruction",
        "系统": "deepseek_system",
    }

    matched_key = None
    for kw, key in rule_map.items():
        if kw in keyword:
            matched_key = key
            break

    if not matched_key:
        return False, (
            "没识别到要改哪个规则。可选：\n"
            "· 「配图规则」— 会员配图提示词后缀\n"
            "· 「配对配图规则」— 配对喜报配图prompt\n"
            "· 「Tips海报规则」— 人格观察海报生成规则\n"
            "· 「配对/喜报规则」— 配对成功文案\n"
            "· 「技巧/观察规则」— 恋爱技巧文案\n"
            "· 「点评规则」— 会员点评文案"
        )

    old_value = prompts.get(matched_key, "")
    prompts[matched_key] = new_value
    config["prompts"] = prompts
    config["updated_at"] = date.today().isoformat()

    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return True, (
            f"✅ 已更新「{matched_key}」规则：\n\n"
            f"旧：{old_value[:100]}…\n\n"
            f"新：{new_value[:100]}…\n\n"
            "💡 规则已保存，下次朋友圈生成将使用新规则"
        )
    except Exception as e:
        return False, f"❌ 写入失败：{e}"


def _build_daily_preview_reply() -> str:
    """构建今日朋友圈预览回复"""
    data = _read_today_posts_json()
    today = date.today().isoformat()

    if not data:
        # 尝试只拿文案列表（没有 today_posts.json 的情况）
        return (
            "━━━ 📅 今日朋友圈预览 ━━━\n\n"
            f"日期：{today}\n\n"
            "⚠️ 今日朋友圈尚未生成或文件不可读。\n\n"
            "💡 检查云端 cron 是否正常运行：\n"
            "ssh ubuntu@106.53.168.186 'tail -30 /home/ubuntu/yufeng-daily/cron.log'"
        )

    slots = data.get("slots", {})
    config_slots = data.get("config", {}).get("slots", [])

    lines = ["━━━ 📅 今日朋友圈预览 ━━━", "", f"📆 {today}", ""]

    total = len(config_slots)
    ready = 0

    for slot_conf in config_slots:
        key = slot_conf["key"]
        label = slot_conf["label"]
        slot_data = slots.get(key, {})
        has_text = bool(slot_data.get("text"))
        has_image = bool(slot_data.get("image"))
        slot_type = slot_data.get("type", "")

        if has_image:
            ready += 1
            img_icon = "🖼️"
        elif slot_data.get("image_prompt"):
            img_icon = "⚠️ 图未生成"
        else:
            img_icon = "❌ 无配图"

        text_icon = "✅" if has_text else "❌"
        status_icon = "✅" if (has_text and has_image) else "⚠️"

        lines.append(f"{status_icon} {slot_conf['send_time']} {label}")
        lines.append(f"   文案: {text_icon}  配图: {img_icon}")

        # 如果文案存在，显示摘要
        if has_text:
            text = slot_data["text"]
            # 取前2行摘要
            first_lines = [l for l in text.split("\n") if l.strip()][:2]
            summary = " | ".join(l.strip()[:40] for l in first_lines)
            lines.append(f"   📝 {summary}")

        lines.append("")

    # 配图检查结果（从 cron.log 获取）
    lines.append(f"📊 状态：{ready}/{total} 条就绪")
    if ready < total:
        lines.append("⚠️ 部分配图缺失，系统已拦截未推送")
    else:
        lines.append("✅ 全部就绪，按计划推送中")

    lines.append("")
    lines.append("💡 如需补图：在企微说「补图」即可触发自动重试")
    return "\n".join(lines)


# ─── 会员信息回复 ────────────────────────────────────────────


def _compact(text: str, limit: int = 700) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _get_val(obj, *attrs, default=""):
    """依次尝试获取属性，第一个有值的返回"""
    for attr in attrs:
        val = getattr(obj, attr, None)
        if val is not None and val != "" and val != "[]" and val != "{}":
            return str(val)
    return default

def _build_member_info_reply(entity) -> str:
    """根据 MemberProfile 或 User 对象构建会员档案回复（模板格式）"""
    lines = ["━━━ 📋 会员档案 ━━━", ""]

    nickname = _get_val(entity, "nickname")
    role_self = _get_val(entity, "role_self", "role")
    age = _get_val(entity, "age")
    city = _get_val(entity, "city")
    education = _get_val(entity, "education")
    job = _get_val(entity, "job")
    height = _get_val(entity, "height")
    weight = _get_val(entity, "weight")

    # 年薪/收入
    income = _get_val(entity, "income", "income_range")

    # 个人情感情况 / 出柜情况
    current_situation = _get_val(entity, "current_situation")
    lifestyle_status = _get_val(entity, "lifestyle_status")

    # 择偶标准
    expectation = _get_val(entity, "expectation")
    match_preferences = _get_val(entity, "match_preferences")

    # 家乡（没有对应字段）
    hometown = ""

    # 层级
    level = _get_val(entity, "level")
    level_str = f" [{level}级]" if level in ("S", "A", "B", "C") else ""
    
    lines.append(f"昵称：{nickname}{level_str}")
    lines.append(f"属性：{role_self}")
    lines.append(f"年龄：{age}")
    lines.append(f"家乡：{hometown}")
    lines.append(f"现居城市：{city}")
    lines.append(f"学历：{education}")
    lines.append(f"职业：{job}")
    lines.append(f"年薪：{income}")
    lines.append(f"身高：{height}")
    lines.append(f"体重：{weight}")
    lines.append(f"个人情感情况：{current_situation}")
    lines.append(f"出柜情况：{lifestyle_status}")
    lines.append(f"择偶标准：{expectation or match_preferences}")
    lines.append("")
    lines.append("💡 下一步：说「推荐匹配」获取匹配建议")
    return "\n".join(lines)

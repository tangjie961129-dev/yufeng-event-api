#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, urllib.parse, urllib.request, urllib.error
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text

SOURCE_CONFIGS = [
    {
        "name": "屿风会员收集表同步库",
        "source_type": "wecom_smartsheet_form",
        "docid": "dcsc4sa9_ONAeZMwfmVdZn5bsjiyhvAw1gFiemghsSEnCJ9rmZ3ckhu1qaWWFoRndeHUCxawh2IHJiWR6bhzSZAw",
        "sheet_id": "tlmpbv",
        "sheet_title": "屿风交友匹配问卷",
    },
    {
        "name": "内部收集匹配会员",
        "source_type": "wecom_smartsheet_internal",
        "docid": "dc5ofGhu4qr4O9enyBiMk5shYR8-fC6LtSIJNe14OWmHSfoW7Opo4sv7xarNHJdCVUmgDAZnq0gld5alLXqV9bHA",
        "sheet_id": "tlFrgl",
        "sheet_title": "屿风交友匹配问卷(企微)",
    },
]
SKIP_SELF_MARKERS = {"唐杰", "唐曾荣", "TangZengRong"}
SKIP_SELF_PHONES = {"13185500021"}


def load_env(path: str = ".env") -> None:
    p = Path(path)
    if p.exists():
        for raw in p.read_text().splitlines():
            if "=" in raw and not raw.strip().startswith("#"):
                k, v = raw.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def db_url() -> str:
    url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not url:
        from app.core.config import settings
        url = settings.DATABASE_URL
    return url


def qyapi(method: str, path: str, token: Optional[str] = None, data: Optional[dict] = None, params: Optional[dict] = None) -> dict:
    params = dict(params or {})
    if token:
        params["access_token"] = token
    url = "https://qyapi.weixin.qq.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"} if body else {})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        if not raw:
            return {"errcode": e.code, "errmsg": "http error with empty body"}
    try:
        return json.loads(raw)
    except Exception:
        return {"errcode": -1, "errmsg": raw[:500]}


def get_token() -> str:
    corp = os.getenv("WECOM_CORP_ID")
    secret = os.getenv("WECOM_APP_SECRET") or os.getenv("WECOM_SECRET")
    if not corp or not secret:
        raise RuntimeError("WECOM_CORP_ID/WECOM_APP_SECRET missing")
    res = qyapi("GET", "/cgi-bin/gettoken", params={"corpid": corp, "corpsecret": secret})
    if res.get("errcode") != 0 or not res.get("access_token"):
        raise RuntimeError(f"gettoken failed: {res}")
    return res["access_token"]


def fetch_records(token: str, docid: str, sheet_id: str, limit: int = 100) -> List[dict]:
    all_records: List[dict] = []
    offset = 0
    while True:
        res = qyapi("POST", "/cgi-bin/wedoc/smartsheet/get_records", token=token, data={
            "docid": docid, "sheet_id": sheet_id, "offset": offset, "limit": limit
        })
        if res.get("errcode") != 0:
            raise RuntimeError(f"get_records failed docid={docid} sheet_id={sheet_id}: {res}")
        batch = res.get("records") or []
        all_records.extend(batch)
        if not res.get("has_more"):
            break
        nxt = res.get("next")
        if nxt is None or nxt == offset:
            offset += len(batch) or limit
        else:
            offset = int(nxt)
    return all_records


def cell_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float)):
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
    if isinstance(v, list):
        parts = []
        for item in v:
            if isinstance(item, dict):
                if item.get("text") is not None:
                    parts.append(str(item.get("text")))
                elif item.get("name") is not None:
                    parts.append(str(item.get("name")))
                elif item.get("user_id") is not None:
                    parts.append(str(item.get("user_id")))
            elif item is not None:
                parts.append(str(item))
        return "、".join(p.strip() for p in parts if p is not None and str(p).strip())
    if isinstance(v, dict):
        if v.get("text") is not None:
            return str(v.get("text")).strip()
        return json.dumps(v, ensure_ascii=False)
    return str(v).strip()


def normalize_record_values(values: dict) -> Dict[str, str]:
    return {str(k): cell_text(v) for k, v in values.items()}


def normalize_income(text_value: str) -> str:
    t = (text_value or "").strip()
    if not t:
        return "未填写"
    return t.replace("3w", "3万").replace("10w", "10万")[:50]


def age_from_birthday(s: str) -> Optional[int]:
    s = str(s or "").strip()
    if not s:
        return None
    try:
        if s.isdigit() and len(s) >= 12:
            dt = datetime.fromtimestamp(int(s) / 1000).date()
        else:
            dt = datetime.fromisoformat(s.replace("/", "-")).date()
        today = date.today()
        return today.year - dt.year - ((today.month, today.day) < (dt.month, dt.day))
    except Exception:
        return None


def parse_tags(text_value: str) -> Tuple[List[str], List[str]]:
    text_value = text_value or ""
    personality, hobbies = [], []
    for kw in ["帅气", "活泼", "温柔", "稳重", "成熟", "幽默", "真诚", "阳光", "硬朗", "男人味"]:
        if kw in text_value:
            personality.append(kw)
    for kw in ["健身", "运动", "旅行", "电影", "音乐", "摄影", "读书", "户外", "游泳", "骑行"]:
        if kw in text_value:
            hobbies.append(kw)
    return list(dict.fromkeys(personality)), list(dict.fromkeys(hobbies))


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def parse_int(value: str) -> Optional[int]:
    m = re.search(r"\d+", str(value or ""))
    return int(m.group(0)) if m else None


def first_raw(raw: Dict[str, str], *keys: str) -> str:
    for key in keys:
        v = (raw.get(key) or "").strip()
        if v:
            return v
    return ""

def raw_hash(rec: dict) -> str:
    return sha(json.dumps(rec, ensure_ascii=False, sort_keys=True))


def member_from_record(record: dict, source_type: str, idx: int) -> Optional[Dict[str, Any]]:
    raw = normalize_record_values(record.get("values") or {})
    if not raw:
        return None
    nickname = raw.get("你的微信昵称", "").strip() or raw.get("填写人", "").strip()
    wechat = raw.get("你的微信号", "").strip()
    phone = (raw.get("你的手机号-手机号", "") or raw.get("你的手机号", "") or raw.get("你的手机号-手机号(已删除)", "")).strip()
    if any(marker in nickname for marker in SKIP_SELF_MARKERS) or phone in SKIP_SELF_PHONES:
        return None
    if not nickname and not wechat and not phone:
        return None
    age = age_from_birthday(raw.get("你的生日", ""))
    if age is not None and age < 18:
        return None
    record_id = record.get("record_id") or sha(f"{wechat}|{phone}|{nickname}|{idx}")[:16]
    city = raw.get("你所在具体城市", "")
    text_all = " ".join(str(v) for v in raw.values())
    p_tags, h_tags = parse_tags(text_all)
    bio_parts = []
    for label, key in [
        ("来源", "填写人"), ("身高/体重", None), ("体型", "你认为自己的体型是"), ("行业", "你所在的行业"),
        ("属性", "你的性角色是"), ("交往经验", "你的交往经验如何？"), ("交往经验", "你的交往经验如何"),
        ("自我关键词", "用几个关键词来形容你自己"),
        ("脱单态度", "目前对脱单的态度？是否准备好跟另一个男人同居生活？"), ("脱单态度", "目前对脱单的态度"),
        ("资产情况", "个人资产情况"), ("来源备注", "来源备注"),
    ]:
        if key is None:
            v = f"{raw.get('你的身高-数字') or raw.get('你的身高','')}/{raw.get('你的体重是-数字') or raw.get('你的体重','')}"
        else:
            v = raw.get(key, "")
        if v and v != "/":
            bio_parts.append(f"{label}：{v}")
    pref_parts = []
    for label, key in [
        ("理想属性", "你希望对方是什么角色"), ("理想体型", "你希望对方的体型是"),
        ("伴侣关键词", "用几个关键词来形容你未来的伴侣"), ("异地接受度", "是否接受异地"),
        ("不能接受", "最不能接受对方的缺点是？"), ("不能接受", "最不能接受对方的缺点是"),
    ]:
        v = raw.get(key, "")
        if v:
            pref_parts.append(f"{label}：{v}")
    return {
        "source_type": source_type,
        "source_record_id": str(record_id),
        "openid": f"{source_type}_{record_id}",
        "nickname": nickname[:80] if nickname else f"屿风会员{idx}",
        "phone": None,
        "contact_phone": phone,
        "contact_wechat": wechat,
        "age": age,
        "city": city,
        "height": parse_int(first_raw(raw, "你的身高-数字", "你的身高")),
        "weight": parse_int(first_raw(raw, "你的体重是-数字", "你的体重")),
        "role_self": first_raw(raw, "你的性角色是", "你的属性", "属性"),
        "role_preference": first_raw(raw, "你希望对方是什么角色", "理想属性"),
        "body_type": first_raw(raw, "你认为自己的体型是", "你的体型", "体型"),
        "job": first_raw(raw, "你所在的行业", "你的职业", "职业"),
        "long_distance": first_raw(raw, "是否接受异地", "是否接受短暂异地"),
        "expectation": first_raw(raw, "用几个关键词来形容你未来的伴侣", "你希望对方的体型是", "期待的你", "17其他对于他的期望?"),
        "lifestyle_status": first_raw(raw, "目前对脱单的态度？是否准备好跟另一个男人同居生活？", "目前对脱单的态度"),
        "current_situation": first_raw(raw, "你的交往经验如何？", "你的交往经验如何"),
        "bio": "；".join(dict.fromkeys(bio_parts)),
        "education": raw.get("你的最高学历是", ""),
        "income_range": normalize_income(raw.get("你的月收入", "")),
        "personality_tags": p_tags,
        "hobby_tags": h_tags,
        "match_preferences": "；".join(dict.fromkeys(pref_parts)),
        "raw": {**raw, "_record_id": record_id, "_create_time": record.get("create_time"), "_update_time": record.get("update_time")},
    }


def ensure_tables(conn) -> None:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS member_sync_sources (
            id SERIAL PRIMARY KEY,
            source_type VARCHAR(50) NOT NULL,
            source_file VARCHAR(255),
            source_record_id VARCHAR(128) NOT NULL,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            raw_hash VARCHAR(64) NOT NULL,
            raw_json JSONB,
            last_synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(source_type, source_record_id)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS member_contact_methods (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            source_type VARCHAR(50) NOT NULL,
            source_record_id VARCHAR(128),
            phone VARCHAR(64),
            wechat_id VARCHAR(128),
            contact_note TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(user_id, source_type)
        )
    """))


def existing_user(conn, member: Dict[str, Any]):
    row = conn.execute(text("""
        SELECT u.id, u.openid FROM member_sync_sources s JOIN users u ON u.id=s.user_id
        WHERE s.source_type=:st AND s.source_record_id=:sid
    """), {"st": member["source_type"], "sid": member["source_record_id"]}).mappings().first()
    if row:
        return row
    return conn.execute(text("SELECT id, openid FROM users WHERE openid=:openid"), {"openid": member["openid"]}).mappings().first()


def upsert_member(conn, member: Dict[str, Any], source_file: str, dry_run: bool, counters: Counter) -> None:
    ex = existing_user(conn, member)
    if dry_run:
        counters["would_update" if ex else "would_insert"] += 1
        return
    params = {
        "openid": member["openid"], "phone": member.get("phone"), "nickname": member["nickname"], "avatar_url": "",
        "age": member.get("age"), "city": member.get("city") or "", "bio": (member.get("bio") or "")[:5000],
        "height": member.get("height"), "weight": member.get("weight"),
        "role_self": member.get("role_self") or "", "role_preference": member.get("role_preference") or "",
        "body_type": member.get("body_type") or "", "job": member.get("job") or "",
        "long_distance": member.get("long_distance") or "", "expectation": (member.get("expectation") or "")[:5000],
        "lifestyle_status": (member.get("lifestyle_status") or "")[:5000], "current_situation": (member.get("current_situation") or "")[:5000],
        "education": member.get("education") or "", "income_range": member.get("income_range") or "未填写",
        "personality_tags": json.dumps(member.get("personality_tags") or [], ensure_ascii=False),
        "hobby_tags": json.dumps(member.get("hobby_tags") or [], ensure_ascii=False),
        "match_preferences": (member.get("match_preferences") or "")[:5000],
        "source_channel": member.get("source_type") or "",
    }
    h = raw_hash(member["raw"])
    if ex:
        user_id = ex["id"]
        conn.execute(text("""
            UPDATE users SET nickname=:nickname, age=:age, city=:city, bio=:bio,
                height=:height, weight=:weight, role_self=:role_self, role_preference=:role_preference,
                body_type=:body_type, job=:job, long_distance=:long_distance, expectation=:expectation,
                lifestyle_status=:lifestyle_status, current_situation=:current_situation,
                education=:education, income_range=:income_range, personality_tags=:personality_tags, hobby_tags=:hobby_tags,
                match_preferences=:match_preferences, match_status='ready', source_channel=:source_channel,
                profile_completed_at=COALESCE(profile_completed_at, NOW()), updated_at=NOW()
            WHERE id=:id
        """), {**params, "id": user_id})
        counters["updated"] += 1
    else:
        user_id = conn.execute(text("""
            INSERT INTO users (openid, phone, nickname, avatar_url, age, city, bio,
                height, weight, role_self, role_preference, body_type, job, long_distance, expectation,
                lifestyle_status, current_situation, education, income_range,
                personality_tags, hobby_tags, match_preferences, match_status, source_channel, profile_completed_at, created_at, updated_at)
            VALUES (:openid, :phone, :nickname, :avatar_url, :age, :city, :bio,
                :height, :weight, :role_self, :role_preference, :body_type, :job, :long_distance, :expectation,
                :lifestyle_status, :current_situation, :education, :income_range,
                :personality_tags, :hobby_tags, :match_preferences, 'ready', :source_channel, NOW(), NOW(), NOW())
            RETURNING id
        """), params).scalar_one()
        counters["inserted"] += 1
    conn.execute(text("""
        INSERT INTO member_sync_sources (source_type, source_file, source_record_id, user_id, raw_hash, raw_json, last_synced_at, updated_at)
        VALUES (:st, :sf, :sid, :uid, :rh, CAST(:raw AS JSONB), NOW(), NOW())
        ON CONFLICT (source_type, source_record_id)
        DO UPDATE SET user_id=EXCLUDED.user_id, raw_hash=EXCLUDED.raw_hash, raw_json=EXCLUDED.raw_json,
            source_file=EXCLUDED.source_file, last_synced_at=NOW(), updated_at=NOW()
    """), {"st": member["source_type"], "sf": source_file, "sid": member["source_record_id"], "uid": user_id, "rh": h, "raw": json.dumps(member["raw"], ensure_ascii=False)})
    if member.get("contact_phone") or member.get("contact_wechat"):
        conn.execute(text("""
            INSERT INTO member_contact_methods (user_id, source_type, source_record_id, phone, wechat_id, contact_note, updated_at)
            VALUES (:uid, :st, :sid, :phone, :wechat, :note, NOW())
            ON CONFLICT (user_id, source_type)
            DO UPDATE SET source_record_id=EXCLUDED.source_record_id, phone=EXCLUDED.phone, wechat_id=EXCLUDED.wechat_id,
                contact_note=EXCLUDED.contact_note, updated_at=NOW()
        """), {"uid": user_id, "st": member["source_type"], "sid": member["source_record_id"], "phone": member.get("contact_phone"), "wechat": member.get("contact_wechat"), "note": "来自企微自建应用智能表格；仅授权内部调用方明确要求联系方式时返回"})
        counters["contacts_upserted"] += 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="reserved for manual trigger; currently syncs all records")
    args = ap.parse_args()
    load_env()
    token = get_token()
    counters = Counter()
    all_members: List[Dict[str, Any]] = []
    for cfg in SOURCE_CONFIGS:
        records = fetch_records(token, cfg["docid"], cfg["sheet_id"])
        counters[f"{cfg['source_type']}_records"] = len(records)
        for i, rec in enumerate(records, start=1):
            member = member_from_record(rec, cfg["source_type"], i)
            if member:
                all_members.append(member)
                counters[f"{cfg['source_type']}_valid"] += 1
            else:
                counters[f"{cfg['source_type']}_skipped"] += 1
    engine = create_engine(db_url())
    with engine.begin() as conn:
        ensure_tables(conn)
        if not args.dry_run:
            bk = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            counters["users_before"] = int(bk or 0)
        for m in all_members:
            upsert_member(conn, m, "wecom_app_smartsheet", args.dry_run, counters)
        if not args.dry_run:
            counters["users_after"] = int(conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0)
            counters["contact_rows"] = int(conn.execute(text("SELECT COUNT(*) FROM member_contact_methods")).scalar() or 0)
    print(json.dumps(counters, ensure_ascii=False, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

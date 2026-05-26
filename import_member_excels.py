#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

ONLINE_SOURCE = "online_mutual"
FORM_SOURCE = "yufeng_form"

SKIP_SELF_MARKERS = {"唐杰", "唐曾荣", "TangZengRong"}
SKIP_SELF_PHONES = {"13185500021"}


def load_env(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def db_url() -> str:
    url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not url:
        try:
            from app.core.config import settings
            url = getattr(settings, "DATABASE_URL", None) or getattr(settings, "database_url", None)
        except Exception:
            pass
    if not url:
        raise RuntimeError("DATABASE_URL not found")
    return url


def col_to_idx(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch.upper()) - 64
    return n - 1


def read_xlsx_sheet(path: str, sheet_name: Optional[str] = None) -> Tuple[List[str], List[Dict[str, str]]]:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared: List[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", NS):
                shared.append("".join((t.text or "") for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))

        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        chosen = None
        for sh in wb.find("a:sheets", NS):
            name = sh.attrib.get("name")
            if sheet_name is None or name == sheet_name:
                rid = sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                target = rid_to_target[rid]
                chosen = target.lstrip("/") if target.startswith("/xl/") else posixpath.normpath(posixpath.join("xl", target))
                break
        if not chosen:
            raise RuntimeError(f"sheet not found: {sheet_name}")
        root = ET.fromstring(z.read(chosen))
        rows: List[List[str]] = []
        for row in root.findall(".//a:sheetData/a:row", NS):
            vals: List[str] = []
            for c in row.findall("a:c", NS):
                idx = col_to_idx(c.attrib.get("r", "A1"))
                while len(vals) <= idx:
                    vals.append("")
                val = ""
                if c.attrib.get("t") == "inlineStr":
                    is_el = c.find("a:is", NS)
                    if is_el is not None:
                        val = "".join((t.text or "") for t in is_el.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"))
                else:
                    v = c.find("a:v", NS)
                    if v is not None:
                        val = v.text or ""
                        if c.attrib.get("t") == "s" and val.isdigit() and int(val) < len(shared):
                            val = shared[int(val)]
                vals[idx] = str(val).strip()
            rows.append(vals)
    if not rows:
        return [], []
    header = [h.strip() for h in rows[0]]
    data = []
    for r in rows[1:]:
        if not any(str(x).strip() for x in r):
            continue
        rec = dict(zip(header, r + [""] * (len(header) - len(r))))
        data.append(rec)
    return header, data


def normalize_income(text_value: str) -> str:
    t = str(text_value or "").strip().lower()
    if not t:
        return "未填写"
    if "10w" in t or "10万" in t:
        return "30k以上"
    if "3w" in t or "3万" in t:
        return "30k以上"
    if "w" in t or "万" in t:
        nums = [int(x) * 10000 for x in re.findall(r"\d+", t)]
    else:
        nums = [int(x) for x in re.findall(r"\d+", t.replace("k", "000"))]
    if not nums:
        return "未填写"
    v = max(nums)
    if v <= 3000:
        return "3k以下"
    if v <= 5000:
        return "3-5k"
    if v <= 8000:
        return "5-8k"
    if v <= 15000:
        return "8-15k"
    if v <= 30000:
        return "15-30k"
    return "30k以上"


def age_from_birthday(s: str) -> Optional[int]:
    if not s:
        return None
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", s)
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    today = date.today()
    return today.year - y - ((today.month, today.day) < (mo, d))


def safe_age(s: str) -> Optional[int]:
    m = re.search(r"\d+", str(s or ""))
    if not m:
        return None
    age = int(m.group())
    return age if 18 <= age <= 80 else None


def parse_tags(text_value: str) -> Tuple[List[str], List[str]]:
    t = str(text_value or "")
    personality_map = {
        "硬朗": ["硬朗", "男人味", "糙", "粗犷"],
        "帅气": ["帅气", "好看", "颜值"],
        "温柔": ["温柔", "体贴", "暖"],
        "开朗": ["开朗", "活泼", "阳光", "外向"],
        "成熟": ["成熟", "稳重", "踏实", "靠谱"],
        "责任感强": ["责任感", "负责", "担当"],
        "专一": ["专一", "忠诚"],
        "包容": ["包容", "理解"],
        "运动": ["运动", "健身", "肌肉", "壮"],
        "文艺": ["文艺", "文学", "艺术"],
    }
    hobby_map = {
        "健身": ["健身", "运动", "肌肉", "撸铁"],
        "旅行": ["旅行", "旅游", "自驾"],
        "音乐": ["音乐", "唱歌", "乐器"],
        "电影": ["电影", "追剧", "影视"],
        "游戏": ["游戏", "电竞"],
        "阅读": ["阅读", "读书", "看书"],
        "美食": ["美食", "做饭", "吃"],
        "宠物": ["宠物", "猫", "狗"],
    }
    p_tags = [tag for tag, keys in personality_map.items() if any(k in t for k in keys)]
    h_tags = [tag for tag, keys in hobby_map.items() if any(k in t for k in keys)]
    return sorted(set(p_tags or ["随和"])), sorted(set(h_tags or ["美食"]))


def sha(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def raw_hash(rec: Dict[str, str]) -> str:
    return sha(json.dumps(rec, sort_keys=True, ensure_ascii=False))


def online_to_member(rec: Dict[str, str]) -> Optional[Dict[str, Any]]:
    no = rec.get("编号", "").strip()
    if not re.fullmatch(r"\d+-\d+", no):
        return None
    text_all = " ".join(str(v) for v in rec.values())
    p_tags, h_tags = parse_tags(text_all)
    bio_parts = []
    for label, key in [
        ("编号", "编号"), ("身高/体重", "身高/体重"), ("体型", "你的体型"), ("职业/行业", "你的职业/从事行业"),
        ("属性", "你的属性"), ("星座/MBTI", "星座/MBTI"), ("单身时长", "你单身多久了"),
        ("个人特点", "在生活中/社交中，你的个人特点"), ("恋爱观", "随着年龄增长/随着生活境遇变化，你的恋爱观念有何改变"),
        ("理想关系", "你想要的理想的伴侣关系是怎样的"), ("其他", "其他想说的话"),
    ]:
        v = rec.get(key, "")
        if v:
            bio_parts.append(f"{label}：{v}")
    pref_parts = []
    for label, key in [
        ("编号", "编号"), ("异地接受度", "对异地恋的接受程度"), ("理想年龄", "理想对象的年龄"),
        ("理想身高", "理想对象的身高"), ("理想属性", "理想对象的属性"), ("理想类型", "理想对象的类型"),
        ("理想型", "理想型是什么样的，希望未来交友遇到什么样的人"),
    ]:
        v = rec.get(key, "")
        if v:
            pref_parts.append(f"{label}：{v}")
    return {
        "source_type": ONLINE_SOURCE,
        "source_record_id": no,
        "openid": f"online_mutual_{no}",
        "nickname": f"互选会员{no}",
        "phone": None,
        "age": safe_age(rec.get("你的年龄", "")),
        "city": rec.get("你常驻的城市", ""),
        "bio": "；".join(bio_parts),
        "education": rec.get("你的最高学历", ""),
        "income_range": "未填写",
        "personality_tags": p_tags,
        "hobby_tags": h_tags,
        "match_preferences": "；".join(pref_parts),
        "raw": rec,
    }


def form_to_member(rec: Dict[str, str], idx: int) -> Optional[Dict[str, Any]]:
    nickname = rec.get("你的微信昵称", "").strip() or rec.get("填写人", "").strip()
    wechat = rec.get("你的微信号", "").strip()
    phone = (rec.get("你的手机号-手机号", "") or rec.get("你的手机号-手机号(已删除)", "")).strip()
    if any(marker in nickname for marker in SKIP_SELF_MARKERS) or phone in SKIP_SELF_PHONES:
        return None
    if not nickname and not wechat:
        return None
    source_id = sha(f"{wechat}|{phone}|{nickname}|{idx}")[:16]
    city = rec.get("你所在具体城市", "")
    age = age_from_birthday(rec.get("你的生日", ""))
    if age is not None and age < 18:
        return None
    role = rec.get("你的性角色是", "")
    prefer_role = rec.get("你希望对方是什么角色", "")
    self_keywords = rec.get("用几个关键词来形容你自己", "")
    partner_keywords = rec.get("用几个关键词来形容你未来的伴侣", "")
    text_all = " ".join(str(v) for v in rec.values())
    p_tags, h_tags = parse_tags(text_all)
    bio_parts = []
    for label, key in [
        ("来源", "填写人"), ("身高/体重", None), ("体型", "你认为自己的体型是"), ("行业", "你所在的行业"),
        ("属性", "你的性角色是"), ("交往经验", "你的交往经验如何？"), ("自我关键词", "用几个关键词来形容你自己"),
        ("脱单态度", "目前对脱单的态度？是否准备好跟另一个男人同居生活？"),
    ]:
        if key is None:
            v = f"{rec.get('你的身高-数字','')}/{rec.get('你的体重是-数字','')}"
        else:
            v = rec.get(key, "")
        if v and v != "/":
            bio_parts.append(f"{label}：{v}")
    pref_parts = []
    for label, key in [
        ("理想属性", "你希望对方是什么角色"), ("理想体型", "你希望对方的体型是"),
        ("伴侣关键词", "用几个关键词来形容你未来的伴侣"), ("异地接受度", "是否接受异地"),
        ("不能接受", "最不能接受对方的缺点是？"),
    ]:
        v = rec.get(key, "")
        if v:
            pref_parts.append(f"{label}：{v}")
    return {
        "source_type": FORM_SOURCE,
        "source_record_id": source_id,
        "openid": f"yufeng_form_{source_id}",
        "nickname": nickname[:80] if nickname else f"屿风会员{idx}",
        "phone": None,
        "age": age,
        "city": city,
        "bio": "；".join(bio_parts),
        "education": rec.get("你的最高学历是", ""),
        "income_range": normalize_income(rec.get("你的月收入", "")),
        "personality_tags": p_tags,
        "hobby_tags": h_tags,
        "match_preferences": "；".join(pref_parts),
        "raw": rec,
    }


def ensure_sync_table(conn) -> None:
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


def existing_user(conn, source_type: str, source_record_id: str, openid: str):
    has_sync_table = conn.execute(text("""
        SELECT to_regclass('public.member_sync_sources') IS NOT NULL
    """)).scalar()
    if has_sync_table:
        row = conn.execute(text("""
            SELECT u.id, u.openid
            FROM member_sync_sources s JOIN users u ON u.id=s.user_id
            WHERE s.source_type=:st AND s.source_record_id=:sid
        """), {"st": source_type, "sid": source_record_id}).mappings().first()
        if row:
            return row
    return conn.execute(text("SELECT id, openid FROM users WHERE openid=:openid"), {"openid": openid}).mappings().first()


def upsert_member(conn, member: Dict[str, Any], source_file: str, dry_run: bool, counters: Counter) -> None:
    ex = existing_user(conn, member["source_type"], member["source_record_id"], member["openid"])
    params = {
        "openid": member["openid"], "phone": member.get("phone"), "nickname": member["nickname"], "avatar_url": "",
        "age": member.get("age"), "city": member.get("city") or "", "bio": (member.get("bio") or "")[:5000],
        "education": member.get("education") or "", "income_range": member.get("income_range") or "未填写",
        "personality_tags": json.dumps(member.get("personality_tags") or [], ensure_ascii=False),
        "hobby_tags": json.dumps(member.get("hobby_tags") or [], ensure_ascii=False),
        "match_preferences": (member.get("match_preferences") or "")[:5000],
    }
    h = raw_hash(member["raw"])
    if dry_run:
        counters["would_update" if ex else "would_insert"] += 1
        return
    if ex:
        user_id = ex["id"]
        conn.execute(text("""
            UPDATE users SET nickname=:nickname, age=:age, city=:city, bio=:bio, education=:education,
                income_range=:income_range, personality_tags=:personality_tags, hobby_tags=:hobby_tags,
                match_preferences=:match_preferences, match_status='ready', updated_at=NOW()
            WHERE id=:id
        """), {**params, "id": user_id})
        counters["updated"] += 1
    else:
        user_id = conn.execute(text("""
            INSERT INTO users (openid, phone, nickname, avatar_url, age, city, bio, education, income_range,
                personality_tags, hobby_tags, match_preferences, match_status, created_at, updated_at)
            VALUES (:openid, :phone, :nickname, :avatar_url, :age, :city, :bio, :education, :income_range,
                :personality_tags, :hobby_tags, :match_preferences, 'ready', NOW(), NOW())
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--online-xlsx", default="/tmp/online_mutual_latest.xlsx")
    ap.add_argument("--form-xlsx", default="/tmp/yufeng_form_latest.xlsx")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    load_env()
    counters = Counter()
    members: List[Dict[str, Any]] = []
    _, online_rows = read_xlsx_sheet(args.online_xlsx, "总表")
    seen_online = set()
    for rec in online_rows:
        m = online_to_member(rec)
        if not m:
            counters["online_skipped_invalid"] += 1
            continue
        if m["source_record_id"] in seen_online:
            counters["online_skipped_duplicate"] += 1
            continue
        seen_online.add(m["source_record_id"])
        members.append(m)
        counters["online_valid"] += 1
    _, form_rows = read_xlsx_sheet(args.form_xlsx, None)
    for idx, rec in enumerate(form_rows, start=1):
        m = form_to_member(rec, idx)
        if not m:
            counters["form_skipped_self_or_invalid"] += 1
            continue
        members.append(m)
        counters["form_valid"] += 1
    engine = create_engine(db_url())
    with engine.begin() as conn:
        if not args.dry_run:
            ensure_sync_table(conn)
        else:
            # Verify table DDL is valid in a rolled-back temp transaction would be overkill; just count.
            pass
        for m in members:
            upsert_member(conn, m, args.online_xlsx if m["source_type"] == ONLINE_SOURCE else args.form_xlsx, args.dry_run, counters)
        if args.dry_run:
            conn.rollback()
    print(json.dumps(counters, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

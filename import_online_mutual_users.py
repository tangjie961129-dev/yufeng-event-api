#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import 线上互选.xlsx into yufeng.users.

- Parses xlsx via zip/xml to avoid openpyxl style parsing issues.
- Upserts by openid=online_mutual_{编号}.
- Keeps phone NULL to avoid unique conflicts.
- Sets match_status='ready'.
"""
import argparse
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from sqlalchemy import text

# Allow running from yufeng-event-api project root.
from app.core.database import SessionLocal

NS = {'a': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
REL_NS = {'pr': 'http://schemas.openxmlformats.org/package/2006/relationships'}

EDUCATION_MAP = {
    '博士': '博士',
    '硕士': '硕士', '研究生': '硕士', '985硕': '硕士', '211硕': '硕士',
    '本科': '本科', '大学': '本科', '学士': '本科',
    '大专': '大专/专科', '专科': '大专/专科', '高职': '大专/专科',
    '高中': '高中/中专', '中专': '高中/中专', '中职': '高中/中专', '高中及以下': '高中/中专', '初中': '高中/中专',
}

PERSONALITY_MAP = {
    '外向': ['外向', '开朗', '活泼', '热情', '社牛'],
    '内向': ['内向', '安静', '文静', '慢热', '社恐'],
    '文艺': ['文艺', '艺术', '文学', '诗', '写作'],
    '幽默': ['幽默', '搞笑', '风趣', '有趣', '开心果'],
    '成熟': ['成熟', '稳重', '踏实', '靠谱', '稳定'],
    '运动': ['运动', '健身', '肌肉', '壮', '跑步', '篮球'],
    '温柔': ['温柔', '体贴', '暖', '细腻', '照顾'],
    '阳光': ['阳光', '积极', '正能量', '乐观'],
    '专一': ['专一', '长久', '认真', '忠诚'],
}

HOBBY_MAP = {
    '健身': ['健身', '运动', '跑步', '撸铁', '肌肉', '篮球', '游泳'],
    '摄影': ['摄影', '拍照', '摄像'],
    '旅行': ['旅行', '旅游', '自驾', '出行'],
    '音乐': ['音乐', '唱歌', '乐器', '吉他'],
    '阅读': ['阅读', '看书', '读书', '文学', '小说'],
    '游戏': ['游戏', '电竞', '网游'],
    '电影': ['电影', '影视', '追剧', '动漫'],
    '美食': ['美食', '做饭', '烹饪', '吃', '烘焙'],
    '户外': ['户外', '爬山', '徒步', '露营', '骑行'],
    '宠物': ['宠物', '猫', '狗', '撸猫'],
}


def norm(v):
    if v is None:
        return ''
    return str(v).replace('\u00a0', ' ').strip()


def clean_city(v):
    s = norm(v)
    s = re.sub(r'\s+', ' ', s)
    return s[:50]


def parse_int(v):
    m = re.search(r'\d+', norm(v))
    return int(m.group()) if m else None


def normalize_education(v):
    s = norm(v)
    for k, out in EDUCATION_MAP.items():
        if k in s:
            return out
    return s[:20] if s else ''


def normalize_role(v):
    s = norm(v).lower().replace(' ', '')
    if 'side' in s:
        return 'side'
    if '0.5' in s or '05' == s or '皆可' in s or '都可' in s or '可0可1' in s:
        return '0.5'
    if '纯1' in s or s == '1' or '偏1' in s:
        return '1'
    if '纯0' in s or s == '0' or '偏0' in s:
        return '0'
    if '1' in s and '0' in s:
        return '0.5'
    if '1' in s:
        return '1'
    if '0' in s:
        return '0'
    return s[:20] if s else ''


def extract_tags(text_value, mapping, default):
    t = norm(text_value).lower()
    tags = []
    for tag, keys in mapping.items():
        if any(k.lower() in t for k in keys):
            tags.append(tag)
    return tags[:8] or [default]


def compact_parts(parts, limit=4000):
    out = []
    for label, val in parts:
        val = norm(val)
        if val:
            out.append(f'{label}：{val}')
    return '；'.join(out)[:limit]


def colrow(ref):
    m = re.match(r'([A-Z]+)(\d+)', ref)
    col = 0
    for ch in m.group(1):
        col = col * 26 + ord(ch) - 64
    return col, int(m.group(2))


def parse_xlsx(path: Path, sheet_name='总表'):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared = []
        if 'xl/sharedStrings.xml' in names:
            root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root.findall('a:si', NS):
                shared.append(''.join(t.text or '' for t in si.findall('.//a:t', NS)))
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        rid_to_target = {r.attrib['Id']: r.attrib['Target'] for r in rels.findall('pr:Relationship', REL_NS)}
        target_path = None
        for s in wb.findall('.//a:sheet', NS):
            name = s.attrib['name']
            rid = s.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            target = rid_to_target.get(rid, '')
            full = 'xl/' + target.lstrip('/') if not target.startswith('xl/') else target
            if name == sheet_name:
                target_path = full
                break
        if not target_path:
            raise RuntimeError(f'sheet not found: {sheet_name}')
        root = ET.fromstring(z.read(target_path))
        rows = {}
        for c in root.findall('.//a:sheetData/a:row/a:c', NS):
            ref = c.attrib.get('r', 'A1')
            col, row = colrow(ref)
            typ = c.attrib.get('t')
            v = c.find('a:v', NS)
            inline = c.find('a:is', NS)
            val = ''
            if typ == 's' and v is not None and v.text is not None:
                idx = int(v.text)
                val = shared[idx] if idx < len(shared) else ''
            elif typ == 'inlineStr' and inline is not None:
                val = ''.join(t.text or '' for t in inline.findall('.//a:t', NS))
            elif v is not None and v.text is not None:
                val = v.text
            rows.setdefault(row, {})[col] = val
        max_col = max((c for r in rows.values() for c in r), default=0)
        header = [norm(rows.get(1, {}).get(i, '')) or f'COL{i}' for i in range(1, max_col + 1)]
        records = []
        for rn in sorted(k for k in rows if k >= 3):
            rec = {header[i - 1]: norm(rows[rn].get(i, '')) for i in range(1, len(header) + 1)}
            if any(rec.values()):
                records.append(rec)
        return records


def transform(rec):
    member_no = norm(rec.get('编号'))
    if not member_no:
        return None, 'missing_no'
    age = parse_int(rec.get('你的年龄'))
    if age is not None and age < 18:
        return None, 'underage'
    role = normalize_role(rec.get('你的属性'))
    text_blob = ' '.join(norm(rec.get(k)) for k in [
        '理想对象的类型', '理想型是什么样的，希望未来交友遇到什么样的人',
        '在生活中/社交中，你的个人特点', '恋爱中的小癖好/恋爱中喜欢做的事',
        '你认为能在一起的最重要因素是什么，为何这么看', '你想要的理想的伴侣关系是怎样的',
        '什么样的事会让你有幸福感', '其他想说的话'
    ])
    bio = compact_parts([
        ('编号', member_no),
        ('身高/体重', rec.get('身高/体重')),
        ('体型', rec.get('你的体型')),
        ('职业/行业', rec.get('你的职业/从事行业')),
        ('属性', rec.get('你的属性')),
        ('星座/MBTI', rec.get('星座/MBTI')),
        ('单身时长', rec.get('你单身多久了')),
        ('个人特点', rec.get('在生活中/社交中，你的个人特点')),
        ('恋爱观', rec.get('如何看待单身、恋爱或其他状态')),
        ('理想关系', rec.get('你想要的理想的伴侣关系是怎样的')),
        ('其他', rec.get('其他想说的话')),
    ])
    prefs = compact_parts([
        ('编号', member_no),
        ('异地接受度', rec.get('对异地恋的接受程度')),
        ('理想年龄', rec.get('理想对象的年龄')),
        ('理想身高', rec.get('理想对象的身高')),
        ('理想属性', rec.get('理想对象的属性')),
        ('理想类型', rec.get('理想对象的类型')),
        ('理想型', rec.get('理想型是什么样的，希望未来交友遇到什么样的人')),
    ])
    return {
        'openid': f'online_mutual_{member_no}',
        'phone': None,
        'nickname': f'互选会员{member_no}'[:50],
        'avatar_url': '',
        'city': clean_city(rec.get('你常驻的城市')),
        'age': age,
        'education': normalize_education(rec.get('你的最高学历')),
        'income_range': '未填写',
        'personality_tags': json.dumps(extract_tags(text_blob, PERSONALITY_MAP, '随和'), ensure_ascii=False),
        'hobby_tags': json.dumps(extract_tags(text_blob, HOBBY_MAP, '美食'), ensure_ascii=False),
        'bio': bio,
        'match_preferences': prefs,
        'match_status': 'ready',
        'match_records_json': '[]',
        'photos': '[]',
        'role': role,
        'member_no': member_no,
    }, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--xlsx', required=True)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    records = parse_xlsx(Path(args.xlsx))
    if args.limit:
        records = records[:args.limit]
    transformed = []
    skip = Counter()
    seen = set()
    dup = 0
    for rec in records:
        row, reason = transform(rec)
        if reason:
            skip[reason] += 1
            continue
        if row['member_no'] in seen:
            dup += 1
            continue
        seen.add(row['member_no'])
        transformed.append(row)

    print(f'xlsx_rows={len(records)} valid={len(transformed)} duplicate_in_xlsx={dup} skipped={dict(skip)}')
    print('sample=')
    for row in transformed[:5]:
        print(json.dumps({k: row[k] for k in ['member_no','nickname','openid','city','age','education','role']}, ensure_ascii=False))

    if args.dry_run:
        print('DRY_RUN=1 no database writes')
        return

    db = SessionLocal()
    inserted = updated = 0
    try:
        for row in transformed:
            exists = db.execute(text('select id from users where openid=:openid'), {'openid': row['openid']}).scalar()
            params = dict(row)
            if exists:
                db.execute(text('''
                    update users set
                      nickname=:nickname, avatar_url=:avatar_url, phone=:phone,
                      city=:city, age=:age, education=:education, income_range=:income_range,
                      personality_tags=:personality_tags, hobby_tags=:hobby_tags,
                      bio=:bio, match_preferences=:match_preferences,
                      match_status=:match_status, photos=coalesce(nullif(:photos, ''), photos),
                      updated_at=now()
                    where openid=:openid
                '''), params)
                updated += 1
            else:
                db.execute(text('''
                    insert into users (
                      openid, phone, nickname, avatar_url,
                      is_organizer, organizer_verified,
                      city, age, education, income_range,
                      personality_tags, hobby_tags, bio, match_preferences, match_status,
                      match_records_json, points, member_level, points_history_json, photos,
                      created_at, updated_at
                    ) values (
                      :openid, :phone, :nickname, :avatar_url,
                      false, false,
                      :city, :age, :education, :income_range,
                      :personality_tags, :hobby_tags, :bio, :match_preferences, :match_status,
                      :match_records_json, 0, 0, '[]', :photos,
                      now(), now()
                    )
                '''), params)
                inserted += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(f'import_done inserted={inserted} updated={updated} total={inserted+updated}')


if __name__ == '__main__':
    main()

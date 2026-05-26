#!/usr/bin/env python3
"""Daily private backup for Yufeng production data.

- Full private PostgreSQL dump stays on server.
- Sanitized summary is written to GBrain/Wiki-friendly markdown.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path

from sqlalchemy import create_engine, text

PROJECT = Path('/home/ubuntu/yufeng-event-api')
BACKUP_ROOT = Path('/home/ubuntu/backups/yufeng-daily')
SUMMARY_ROOT = Path('/home/ubuntu/backups/yufeng-daily-summaries')


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k,v=line.split('=',1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def pg_dump(day: str) -> Path:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    out = BACKUP_ROOT / f'yufeng-{day}.dump'
    if not out.exists():
        subprocess.run(['pg_dump', os.environ['DATABASE_URL'], '-Fc', '-f', str(out)], check=True)
    return out


def make_summary(day: str) -> Path:
    SUMMARY_ROOT.mkdir(parents=True, exist_ok=True)
    engine=create_engine(os.environ['DATABASE_URL'])
    with engine.connect() as c:
        stats=c.execute(text("""
            select count(*) total,
                   count(*) filter(where match_status='ready') ready,
                   count(*) filter(where height is not null) height_filled,
                   count(*) filter(where weight is not null) weight_filled,
                   count(*) filter(where coalesce(role_self,'') <> '') role_filled,
                   count(*) filter(where coalesce(body_type,'') <> '') body_filled,
                   count(*) filter(where coalesce(job,'') <> '') job_filled,
                   count(*) filter(where coalesce(expectation,'') <> '') expectation_filled,
                   count(*) filter(where coalesce(source_channel,'') <> '') source_filled
            from users
        """)).mappings().first()
        city_rows=c.execute(text("""
            select coalesce(nullif(split_part(city,'/',1),''),'未知') city, count(*) n
            from users where match_status='ready'
            group by 1 order by n desc limit 20
        """)).mappings().all()
        source_rows=c.execute(text("""
            select coalesce(nullif(source_channel,''),'unknown') source, count(*) n
            from users group by 1 order by n desc limit 20
        """)).mappings().all()
        recent=c.execute(text("""
            select id,nickname,city,age,height,weight,body_type,job,source_channel,updated_at
            from users where match_status='ready'
            order by updated_at desc nulls last, id desc limit 12
        """)).mappings().all()
    md = [
        f"# 屿风会员库脱敏日报 {day}",
        "",
        "说明：这是给 Wiki/GBrain 的脱敏运营摘要；完整 PostgreSQL dump 只保存在生产服务器私有备份目录，不写入 Wiki/GBrain。",
        "",
        "## 主表 users 覆盖情况",
        "",
        "```json",
        json.dumps(dict(stats), ensure_ascii=False, indent=2, default=str),
        "```",
        "",
        "## 城市分布 Top20",
        "",
    ]
    md += [f"- {r['city']}: {r['n']}" for r in city_rows]
    md += ["", "## 来源渠道", ""]
    md += [f"- {r['source']}: {r['n']}" for r in source_rows]
    md += ["", "## 最近更新会员（脱敏，不含联系方式/真实姓名/属性）", ""]
    for r in recent:
        md.append(f"- ID {r['id']}｜{r['nickname']}｜{r['city']}｜{r['age'] or '未知'}岁｜{r['height'] or '-'}cm/{r['weight'] or '-'}kg｜{r['body_type'] or '体型未知'}｜{r['job'] or '职业未知'}｜来源:{r['source_channel'] or 'unknown'}")
    md += ["", f"生成时间：{dt.datetime.now().isoformat(timespec='seconds')}"]
    out = SUMMARY_ROOT / f'yufeng-member-summary-{day}.md'
    out.write_text('\n'.join(md), encoding='utf-8')
    return out


def put_gbrain(summary: Path, day: str) -> None:
    # Cloud GBrain CLI may be uninitialized on production; local summary is authoritative.
    gbrain = os.environ.get('GBRAIN_BIN') or '/home/ubuntu/.bun/bin/gbrain'
    if not Path(gbrain).exists():
        gbrain = 'gbrain'
    env=os.environ.copy()
    env.setdefault('HOME', '/home/ubuntu')
    slug=f'yufeng/member-db-daily-summary-{day}'
    try:
        subprocess.run([gbrain, 'put', slug], input=summary.read_text(encoding='utf-8'), text=True, env=env, check=True, timeout=60)
        print(f'GBRAIN_SLUG={slug}')
    except Exception as exc:
        print(f'GBRAIN_SKIP={type(exc).__name__}: {exc}')


def main() -> int:
    load_env(PROJECT / '.env')
    if 'DATABASE_URL' not in os.environ:
        raise SystemExit('DATABASE_URL missing')
    day=dt.date.today().isoformat()
    dump=pg_dump(day)
    summary=make_summary(day)
    put_gbrain(summary, day)
    print(f'DUMP={dump}')
    print(f'SUMMARY={summary}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

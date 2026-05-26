from import_member_excels import load_env, db_url
from sqlalchemy import create_engine, text
load_env(); e=create_engine(db_url())
with e.connect() as c:
    rows=c.execute(text("""
    select s.user_id, u.nickname,
           s.raw_json->>'你的微信号' as wechat,
           coalesce(s.raw_json->>'你的手机号-手机号', s.raw_json->>'你的手机号-手机号(已删除)') as phone
    from member_sync_sources s join users u on u.id=s.user_id
    where s.source_type='yufeng_form'
    order by s.user_id limit 5
    """)).mappings().all()
    for r in rows: print(dict(r))
    print('contact_candidates', c.execute(text("""
    select count(*) from member_sync_sources s join users u on u.id=s.user_id
    where s.source_type='yufeng_form'
      and (nullif(s.raw_json->>'你的微信号','') is not null
           or nullif(s.raw_json->>'你的手机号-手机号','') is not null
           or nullif(s.raw_json->>'你的手机号-手机号(已删除)','') is not null)
    """)).scalar())

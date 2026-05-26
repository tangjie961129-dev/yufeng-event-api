from import_member_excels import load_env, db_url
from sqlalchemy import create_engine, text
load_env(); e=create_engine(db_url())
with e.begin() as c:
    rows = c.execute(text("select id, openid, nickname, age from users where openid like 'yufeng_form_%' and age < 18")).mappings().all()
    print('underage_rows=', [dict(r) for r in rows])
    ids=[r['id'] for r in rows]
    if ids:
        c.execute(text('delete from member_sync_sources where user_id = any(:ids)'), {'ids': ids})
        c.execute(text('delete from users where id = any(:ids)'), {'ids': ids})
        print('deleted=', len(ids))
    else:
        print('deleted=0')

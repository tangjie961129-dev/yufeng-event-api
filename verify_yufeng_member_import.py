from import_member_excels import load_env, db_url
from sqlalchemy import create_engine, text
load_env(); e=create_engine(db_url())
with e.connect() as c:
    qs = {
        'total_users': 'select count(*) from users',
        'ready_users': "select count(*) from users where match_status='ready'",
        'online_mutual_users': "select count(*) from users where openid like 'online_mutual_%'",
        'yufeng_form_users': "select count(*) from users where openid like 'yufeng_form_%'",
        'sync_rows': 'select count(*) from member_sync_sources',
        'sync_online_rows': "select count(*) from member_sync_sources where source_type='online_mutual'",
        'sync_form_rows': "select count(*) from member_sync_sources where source_type='yufeng_form'",
    }
    for k,q in qs.items():
        print(f'{k}={c.execute(text(q)).scalar()}')
    print('sample_form=')
    rows=c.execute(text("select id,nickname,age,city,bio,match_preferences from users where openid like 'yufeng_form_%' order by id limit 3")).mappings().all()
    for r in rows:
        print(dict(r))

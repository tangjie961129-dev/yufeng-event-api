from import_member_excels import load_env, db_url
from sqlalchemy import create_engine, text
load_env(); e=create_engine(db_url())
with e.connect() as c:
    queries = {
        'total_users': "select count(*) from users",
        'ready_users': "select count(*) from users where match_status='ready'",
        'wecom_form_sources': "select count(*) from member_sync_sources where source_type='wecom_smartsheet_form'",
        'wecom_internal_sources': "select count(*) from member_sync_sources where source_type='wecom_smartsheet_internal'",
        'wecom_contacts': "select count(*) from member_contact_methods where source_type like 'wecom_smartsheet%'",
    }
    for k,q in queries.items():
        print(k, c.execute(text(q)).scalar())
    rows=c.execute(text("select id,nickname,city,bio,match_preferences from users where openid like 'wecom_smartsheet_internal_%' limit 3")).mappings().all()
    print('internal_rows')
    for r in rows:
        print(dict(r))

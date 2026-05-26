from import_member_excels import load_env, db_url
from sqlalchemy import create_engine, text
load_env(); e=create_engine(db_url())
with e.connect() as c:
    rows=c.execute(text("select column_name,data_type from information_schema.columns where table_name=:t order by ordinal_position"), {"t":"users"}).fetchall()
    for r in rows: print(r[0], r[1])
    print('sync_table', c.execute(text("select to_regclass('public.member_sync_sources')")).scalar())
    print('counts', c.execute(text("select count(*) from users")).scalar())

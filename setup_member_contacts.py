from import_member_excels import load_env, db_url
from sqlalchemy import create_engine, text
load_env(); e=create_engine(db_url())
with e.begin() as c:
    c.execute(text("""
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
    result = c.execute(text("""
    INSERT INTO member_contact_methods (user_id, source_type, source_record_id, phone, wechat_id, contact_note, updated_at)
    SELECT s.user_id,
           s.source_type,
           s.source_record_id,
           NULLIF(coalesce(s.raw_json->>'你的手机号-手机号', s.raw_json->>'你的手机号-手机号(已删除)'), '') AS phone,
           NULLIF(s.raw_json->>'你的微信号', '') AS wechat_id,
           '来自屿风交友匹配问卷；仅授权内部调用方明确要求联系方式时返回' AS contact_note,
           NOW()
    FROM member_sync_sources s
    JOIN users u ON u.id=s.user_id
    WHERE s.source_type='yufeng_form'
      AND (NULLIF(s.raw_json->>'你的微信号','') IS NOT NULL
           OR NULLIF(s.raw_json->>'你的手机号-手机号','') IS NOT NULL
           OR NULLIF(s.raw_json->>'你的手机号-手机号(已删除)','') IS NOT NULL)
    ON CONFLICT (user_id, source_type)
    DO UPDATE SET phone=EXCLUDED.phone, wechat_id=EXCLUDED.wechat_id, source_record_id=EXCLUDED.source_record_id,
        contact_note=EXCLUDED.contact_note, updated_at=NOW()
    """))
    print('upserted_contacts=', result.rowcount)
    print('contact_rows=', c.execute(text('select count(*) from member_contact_methods')).scalar())
    print('with_phone=', c.execute(text("select count(*) from member_contact_methods where phone is not null and phone<>''")).scalar())
    print('with_wechat=', c.execute(text("select count(*) from member_contact_methods where wechat_id is not null and wechat_id<>''")).scalar())

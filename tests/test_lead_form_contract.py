import json
from datetime import datetime, timezone

from app.models.lead_form import LeadForm, LeadFormVersion
from app.schemas.lead_form import LeadFormCreate, LeadFormField, LeadFormFieldOption
from app.routers.admin_lead_forms import _default_public_wechat_schema


def test_lead_form_models_store_schema_and_publish_metadata():
    form = LeadForm(
        slug="public-wechat-v1",
        name="个人微信公开引流表单",
        title="屿风会员登记",
        scene="public_wechat",
        form_schema={"fields": [{"key": "nickname", "label": "昵称", "type": "text"}]},
        ui_schema={"submit_text": "提交资料"},
        status="draft",
        version=1,
    )
    assert form.slug == "public-wechat-v1"
    assert form.form_schema["fields"][0]["key"] == "nickname"

    version = LeadFormVersion(
        form_id=1,
        version=2,
        form_schema=form.form_schema,
        ui_schema=form.ui_schema,
        published_at=datetime.now(timezone.utc),
    )
    assert version.version == 2
    assert version.form_schema["fields"][0]["label"] == "昵称"


def test_lead_form_schema_validates_fields_and_options():
    payload = LeadFormCreate(
        slug="public-wechat-v1",
        name="个人微信公开引流表单",
        title="屿风会员登记",
        scene="public_wechat",
        fields=[
            LeadFormField(
                key="role_self",
                label="属性",
                type="select",
                required=True,
                options=[LeadFormFieldOption(label="1", value="1")],
                profile_field="role_self",
                sort=10,
            )
        ],
    )
    data = payload.to_form_schema()
    assert data["fields"][0]["key"] == "role_self"
    assert data["fields"][0]["options"][0]["value"] == "1"


def test_default_public_wechat_schema_contains_expected_core_fields():
    schema = _default_public_wechat_schema()
    keys = [f["key"] for f in schema["fields"]]
    for key in ["nickname", "city", "age", "role_self", "body_type", "income", "expectation", "phone", "wechat_id"]:
        assert key in keys

from app.schemas.lead_form import LeadFormField, LeadFormFieldUploadConfig
from app.models.lead_form import LeadFormSubmission
from app.routers.public_lead_forms import _coerce_submission_value, _validate_submission_payload


def test_image_and_multi_image_field_schema_support_upload_config():
    single = LeadFormField(key="avatar", label="近照", type="image", upload=LeadFormFieldUploadConfig(max_count=1, max_size_mb=5))
    multi = LeadFormField(key="photos", label="生活照", type="images", upload=LeadFormFieldUploadConfig(max_count=3, max_size_mb=5))
    assert single.upload.max_count == 1
    assert multi.upload.max_count == 3


def test_checkbox_submission_value_is_list_and_image_is_url_list():
    checkbox_field = {"key": "hobbies", "type": "checkbox", "required": True}
    image_field = {"key": "photos", "type": "images", "required": True, "upload": {"max_count": 3}}
    assert _coerce_submission_value(checkbox_field, ["健身", "旅行"]) == ["健身", "旅行"]
    assert _coerce_submission_value(image_field, ["/static/a.jpg"]) == ["/static/a.jpg"]


def test_validate_submission_payload_requires_required_fields():
    form_schema = {"fields": [{"key": "nickname", "label": "昵称", "type": "text", "required": True}]}
    ok = _validate_submission_payload(form_schema, {"nickname": "清风"})
    assert ok["nickname"] == "清风"
    try:
        _validate_submission_payload(form_schema, {})
    except ValueError as exc:
        assert "昵称" in str(exc)
    else:
        raise AssertionError("required field did not fail")


def test_lead_form_submission_model_keeps_raw_and_mapped_data():
    obj = LeadFormSubmission(form_id=1, form_slug="public-wechat-v1", form_version=1, raw_data={"photos": ["/static/a.jpg"]}, mapped_profile={"nickname": "清风"}, upload_files={"photos": ["/static/a.jpg"]})
    assert obj.raw_data["photos"][0].endswith("a.jpg")
    assert obj.mapped_profile["nickname"] == "清风"

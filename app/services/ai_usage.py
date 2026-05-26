"""Best-effort AI usage telemetry service."""
from __future__ import annotations

from typing import Any

from app.core.database import SessionLocal
from app.models.ai_usage import AiCostRule, AiUsageLog

DEFAULT_COST_RULES = [
    {
        "provider": "hermes-gateway",
        "model": "deepseek-v4-flash",
        "prompt_cny_per_m": 0.0,
        "completion_cny_per_m": 0.0,
        "notes": "默认占位价。请在总后台 AI 成本核算中按实际供应商价格调整。",
    },
    {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "prompt_cny_per_m": 1.0,
        "completion_cny_per_m": 2.0,
        "notes": "估算价，可按 DeepSeek 控制台账单调整。",
    },
]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except Exception:
        return default


def estimate_tokens(text: str) -> int:
    """Rough Chinese-friendly token estimate when provider does not return usage."""
    text = text or ""
    if not text:
        return 0
    # Chinese text is often close to 1 char/token; English closer to 4 chars/token.
    # Use a conservative mixed estimate for cost visibility.
    return max(1, int(len(text) / 1.8))


def ensure_default_cost_rules() -> None:
    db = SessionLocal()
    try:
        for item in DEFAULT_COST_RULES:
            exists = db.query(AiCostRule).filter(AiCostRule.model == item["model"]).first()
            if not exists:
                db.add(AiCostRule(**item))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _get_rule(db, model: str) -> AiCostRule | None:
    if not model:
        return None
    return db.query(AiCostRule).filter(AiCostRule.model == model, AiCostRule.enabled == True).first()  # noqa: E712


def calculate_cost_cny(db, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rule = _get_rule(db, model)
    if not rule:
        return 0.0
    return round(
        (prompt_tokens or 0) * (rule.prompt_cny_per_m or 0) / 1_000_000
        + (completion_tokens or 0) * (rule.completion_cny_per_m or 0) / 1_000_000,
        6,
    )


def record_ai_usage(
    *,
    request_id: str = "",
    scene: str = "general",
    provider: str = "",
    model: str = "",
    employee_userid: str = "",
    business_ref: str = "",
    prompt_text: str = "",
    response_text: str = "",
    usage: dict[str, Any] | None = None,
    success: bool = True,
    http_status: int = 0,
    latency_ms: int = 0,
    error_message: str = "",
) -> None:
    """Best-effort logging. Never raise into business flow."""
    db = SessionLocal()
    try:
        usage = usage or {}
        prompt_tokens = _safe_int(usage.get("prompt_tokens"))
        completion_tokens = _safe_int(usage.get("completion_tokens"))
        total_tokens = _safe_int(usage.get("total_tokens"))
        estimated = False
        if total_tokens <= 0:
            estimated = True
            prompt_tokens = prompt_tokens or estimate_tokens(prompt_text)
            completion_tokens = completion_tokens or estimate_tokens(response_text)
            total_tokens = prompt_tokens + completion_tokens
        cost_cny = calculate_cost_cny(db, model, prompt_tokens, completion_tokens)
        db.add(
            AiUsageLog(
                request_id=(request_id or "")[:64],
                scene=(scene or "general")[:80],
                provider=(provider or "")[:80],
                model=(model or "")[:120],
                employee_userid=(employee_userid or "")[:100],
                business_ref=(business_ref or "")[:160],
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated=estimated,
                cost_cny=cost_cny,
                success=bool(success),
                http_status=_safe_int(http_status),
                latency_ms=_safe_int(latency_ms),
                error_message=(error_message or "")[:1000],
                request_preview=(prompt_text or "")[:500],
                response_preview=(response_text or "")[:500],
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

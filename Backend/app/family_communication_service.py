from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel, Field

from app import schemas


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
SUPPORTED_LANGUAGES = {
    "hi": "Hindi",
    "mr": "Marathi",
    "gu": "Gujarati",
    "ta": "Tamil",
}


class _OpenAIFamilyTranslation(BaseModel):
    code: str
    label: str
    text: str


class _OpenAIFamilyPayload(BaseModel):
    english: str = Field(min_length=1)
    translations: list[_OpenAIFamilyTranslation] = Field(default_factory=list)


def _get_env_value(key: str) -> Optional[str]:
    load_dotenv(dotenv_path=ENV_PATH, override=False)
    direct = os.getenv(key)
    if direct:
        return direct

    env_values = dotenv_values(ENV_PATH)
    for raw_key, value in env_values.items():
        normalized_key = raw_key.replace("\ufeff", "") if raw_key else ""
        if normalized_key == key and value:
            cleaned = value.strip().strip('"').strip("'")
            os.environ[key] = cleaned
            return cleaned
    return None


def _has_real_openai_api_key() -> bool:
    api_key = _get_env_value("OPENAI_API_KEY")
    if not api_key:
        return False

    normalized = api_key.strip().lower()
    placeholders = {
        "your_openai_api_key_here",
        "openai_api_key",
        "replace_me",
    }
    return normalized not in placeholders


def _build_user_payload(
    report: schemas.AnalysisReport,
    outlier_alert: Optional[schemas.OutlierAlert],
) -> str:
    anomalies = report.detected_anomalies[:5]
    recommendations = report.recommendations[:5]
    handover = report.handover_summary[:3]
    outlier_context = (
        {
            "affected_lab": outlier_alert.affectedLab,
            "message": outlier_alert.message,
            "action_required": outlier_alert.actionRequired,
        }
        if outlier_alert and outlier_alert.isProbableLabError
        else None
    )

    return (
        "Create a compassionate ICU family update from this analysis context.\n"
        f"Risk score: {report.risk_score}\n"
        f"Detected anomalies: {anomalies}\n"
        f"Recommendations: {recommendations}\n"
        f"Handover summary: {handover}\n"
        f"Outlier alert: {outlier_context}\n"
        f"Required translation languages: {list(SUPPORTED_LANGUAGES.items())}\n"
        "Keep the English summary under 120 words, plain-language, medically faithful, and non-alarmist.\n"
        "For translations, preserve the same meaning and tone, and do not invent new clinical facts.\n"
    )


def generate_family_communication_with_openai(
    report: schemas.AnalysisReport,
    outlier_alert: Optional[schemas.OutlierAlert],
) -> schemas.FamilyCommunication:
    api_key = _get_env_value("OPENAI_API_KEY")
    if not _has_real_openai_api_key():
        raise ValueError("OPENAI_API_KEY is not configured.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The openai package is not installed.") from exc

    client_kwargs = {"api_key": api_key}
    base_url = _get_env_value("OPENAI_BASE_URL")
    if base_url:
        client_kwargs["base_url"] = base_url

    client = OpenAI(**client_kwargs)
    model = _get_env_value("OPENAI_FAMILY_MODEL") or _get_env_value("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL

    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You write ICU family updates for clinician review. "
                    "Return one plain-language English summary and accurate local-language translations. "
                    "Do not add diagnoses, timelines, or treatments beyond the supplied analysis. "
                    "Avoid jargon when a simpler phrase will preserve meaning."
                ),
            },
            {
                "role": "user",
                "content": _build_user_payload(report, outlier_alert),
            },
        ],
        text_format=_OpenAIFamilyPayload,
    )

    parsed = response.output_parsed
    if parsed is None:
        raise ValueError("OpenAI did not return a structured family communication payload.")

    translations: list[schemas.FamilyTranslation] = []
    for item in parsed.translations:
        code = item.code.strip().lower()
        if code not in SUPPORTED_LANGUAGES:
            continue
        text = item.text.strip()
        if not text:
            continue
        translations.append(
            schemas.FamilyTranslation(
                code=code,
                label=SUPPORTED_LANGUAGES[code],
                text=text,
            )
        )

    missing_codes = [code for code in SUPPORTED_LANGUAGES if code not in {item.code for item in translations}]
    if missing_codes:
        raise ValueError(f"OpenAI response omitted required translations: {', '.join(missing_codes)}")

    default_translation = translations[0]
    return schemas.FamilyCommunication(
        updatedWindow="Last 12 hours",
        english=parsed.english.strip(),
        regionalLanguage=default_translation.label,
        regional=default_translation.text,
        translations=translations,
    )


def get_family_communication_provider_status() -> dict:
    api_key = _get_env_value("OPENAI_API_KEY")
    base_url = _get_env_value("OPENAI_BASE_URL")
    model = _get_env_value("OPENAI_FAMILY_MODEL") or _get_env_value("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL

    try:
        import openai  # noqa: F401
        sdk_installed = True
    except ImportError:
        sdk_installed = False

    configured = bool(_has_real_openai_api_key() and sdk_installed)
    return {
        "provider": "openai" if configured else "fallback",
        "openai_configured": _has_real_openai_api_key(),
        "sdk_installed": sdk_installed,
        "model": model,
        "base_url_configured": bool(base_url),
        "supported_languages": [
            {"code": code, "label": label}
            for code, label in SUPPORTED_LANGUAGES.items()
        ],
    }

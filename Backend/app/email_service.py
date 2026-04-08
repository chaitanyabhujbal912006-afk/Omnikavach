from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import dotenv_values, load_dotenv

from app import schemas


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
RESEND_API_URL = "https://api.resend.com/emails"


def _get_env_value(key: str) -> str | None:
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


def send_family_email(
    *,
    patient_name: str,
    recipient_email: str,
    family_communication: schemas.FamilyCommunication,
) -> dict:
    api_key = _get_env_value("RESEND_API_KEY")
    if not api_key:
        raise ValueError("RESEND_API_KEY is not configured.")

    sender = _get_env_value("RESEND_FROM_EMAIL") or "OmniKavach <onboarding@resend.dev>"
    reply_to = _get_env_value("RESEND_REPLY_TO")

    translation_sections = []
    if family_communication.translations:
        for translation in family_communication.translations:
            translation_sections.append(
                f"<h3 style=\"margin-bottom: 8px; margin-top: 24px;\">{translation.label}</h3>"
                f"<p>{translation.text}</p>"
            )
    elif family_communication.regional:
        translation_sections.append(
            f"<h3 style=\"margin-bottom: 8px; margin-top: 24px;\">{family_communication.regionalLanguage}</h3>"
            f"<p>{family_communication.regional}</p>"
        )

    subject = f"Update for {patient_name} from OmniKavach"
    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #0f172a;">
      <h2 style="margin-bottom: 8px;">Family Update for {patient_name}</h2>
      <p style="margin-top: 0; color: #475569;">This is a family-friendly summary generated from the latest ICU review. Please use it alongside direct clinician communication.</p>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;" />
      <h3 style="margin-bottom: 8px;">English</h3>
      <p>{family_communication.english}</p>
      {''.join(translation_sections)}
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;" />
      <p style="font-size: 12px; color: #64748b;">Decision-support prototype message. Clinical teams should review before acting on any information.</p>
    </div>
    """.strip()

    payload = {
        "from": sender,
        "to": [recipient_email],
        "subject": subject,
        "html": html,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    response = requests.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if response.status_code >= 400:
        detail = response.text
        raise ValueError(f"Resend rejected the email request: {detail}")

    return response.json()

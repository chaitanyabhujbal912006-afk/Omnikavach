from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from typing import Tuple

from dotenv import dotenv_values, load_dotenv
from groq import Groq


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
PDF_EXTENSIONS = {".pdf"}
TEXT_EXTENSIONS = {".txt"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"


def _get_groq_api_key() -> str:
    load_dotenv(dotenv_path=ENV_PATH, override=False)

    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        return api_key

    env_values = dotenv_values(ENV_PATH)
    for key, value in env_values.items():
        normalized_key = key.replace("\ufeff", "") if key else ""
        if normalized_key == "GROQ_API_KEY" and value:
            cleaned = value.strip().strip('"').strip("'")
            os.environ["GROQ_API_KEY"] = cleaned
            return cleaned

    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key:
        os.environ["GROQ_API_KEY"] = google_key
        return google_key

    raise ValueError("GROQ_API_KEY is not configured for image extraction.")


def _get_extension(filename: str) -> str:
    return os.path.splitext(filename.lower())[1]


def _extract_text_from_pdf(contents: bytes) -> str:
    import PyPDF2

    reader = PyPDF2.PdfReader(io.BytesIO(contents))
    extracted_text = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            extracted_text.append(page_text)
    return "\n".join(extracted_text).strip()


def _extract_text_from_text_file(contents: bytes) -> str:
    return contents.decode("utf-8", errors="replace").strip()


def _extract_text_from_image(contents: bytes, extension: str) -> str:
    api_key = _get_groq_api_key()

    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(extension)

    if not mime_type:
        raise ValueError("Unsupported image type.")

    encoded = base64.b64encode(contents).decode("utf-8")
    client = Groq(api_key=api_key)
    model = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

    completion = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an ICU document transcription assistant. "
                    "Extract the visible clinical text from the image accurately. "
                    "Preserve measurements, medication names, findings, dates, headings, and note structure. "
                    "Do not summarize. Return only the extracted text."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract the report text from this clinical image."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                    },
                ],
            },
        ],
    )

    text = completion.choices[0].message.content or ""
    return text.strip()


def extract_document_text(filename: str, contents: bytes) -> Tuple[str, str]:
    if not filename:
        raise ValueError("Uploaded file must have a filename.")
    if not contents:
        raise ValueError("Uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise ValueError("File is too large. Please upload a file smaller than 8 MB.")

    extension = _get_extension(filename)

    if extension in PDF_EXTENSIONS:
        text = _extract_text_from_pdf(contents)
        category = "External Report"
    elif extension in IMAGE_EXTENSIONS:
        text = _extract_text_from_image(contents, extension)
        category = "Clinical Photo"
    elif extension in TEXT_EXTENSIONS:
        text = _extract_text_from_text_file(contents)
        category = "Typed Report"
    else:
        raise ValueError("Unsupported file type. Please upload a PDF, image, or text file.")

    if not text.strip():
        raise ValueError("No readable clinical text could be extracted from this file.")

    if len(text) > 450000:
        text = text[:450000] + "\n[Rest of document truncated]"

    return text, category


from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


load_dotenv(BASE_DIR / ".env", override=True, encoding="utf-8-sig")
load_dotenv(BASE_DIR.parent / ".env", override=False, encoding="utf-8-sig")


def _int_env(name: str, default: int) -> int:
    """환경 변수 값을 정수로 읽고 실패하면 기본값을 반환한다."""
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """API, AI provider, 업로드, 변환기 관련 런타임 설정을 한 곳에 모은다."""
    api_base_url: str = os.getenv("DESKAD_API_BASE", "http://127.0.0.1:8000")
    public_api_base_url: str = os.getenv("DESKAD_PUBLIC_API_BASE", os.getenv("DESKAD_API_BASE", "http://127.0.0.1:8000"))
    ai_provider: str = os.getenv("AI_PROVIDER", "auto")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_text_model: str = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
    openai_image_model: str = os.getenv("OPENAI_IMAGE_MODEL", "")
    local_llm_base_url: str = os.getenv("LOCAL_LLM_BASE_URL", "")
    local_llm_model: str = os.getenv("LOCAL_LLM_MODEL", "")
    local_image_endpoint: str = os.getenv("LOCAL_IMAGE_ENDPOINT", "")
    request_timeout_seconds: int = _int_env("AI_REQUEST_TIMEOUT_SECONDS", 45)
    max_upload_mb: int = _int_env("MAX_UPLOAD_MB", 60)
    step_converter_cmd: str = os.getenv("STEP_CONVERTER_CMD", "")
    step_converter_timeout_seconds: int = _int_env("STEP_CONVERTER_TIMEOUT_SECONDS", 120)
    drawing_converter_cmd: str = os.getenv("DRAWING_CONVERTER_CMD", "")
    drawing_converter_timeout_seconds: int = _int_env("DRAWING_CONVERTER_TIMEOUT_SECONDS", 120)

    @property
    def has_openai_key(self) -> bool:
        """OpenAI 텍스트 API 키가 설정되어 있는지 반환한다."""
        return bool(self.openai_api_key)

    @property
    def has_openai_image(self) -> bool:
        """OpenAI 이미지 모델 호출에 필요한 키와 모델명이 모두 있는지 반환한다."""
        return bool(self.openai_api_key and self.openai_image_model)

    @property
    def has_local_llm(self) -> bool:
        """로컬 LLM 엔드포인트가 설정되어 있는지 반환한다."""
        return bool(self.local_llm_base_url)

    @property
    def has_local_image(self) -> bool:
        """로컬 이미지 생성 엔드포인트가 설정되어 있는지 반환한다."""
        return bool(self.local_image_endpoint)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """프로세스 전체에서 재사용할 Settings 객체를 캐시해 반환한다."""
    return Settings()


def redacted_settings() -> dict:
    """민감한 값은 숨기고 UI/API 상태 표시용 설정 요약을 반환한다."""
    settings = get_settings()
    return {
        "api_base_url": settings.api_base_url,
        "public_api_base_url": settings.public_api_base_url,
        "ai_provider": settings.ai_provider,
        "openai_api_key": "set" if settings.openai_api_key else "missing",
        "openai_base_url": settings.openai_base_url,
        "openai_text_model": settings.openai_text_model,
        "openai_image_model": settings.openai_image_model or "disabled",
        "local_llm_base_url": "set" if settings.local_llm_base_url else "missing",
        "local_llm_model": settings.local_llm_model or "default",
        "local_image_endpoint": "set" if settings.local_image_endpoint else "missing",
        "max_upload_mb": settings.max_upload_mb,
        "step_converter_cmd": "set" if settings.step_converter_cmd else "missing",
        "drawing_converter_cmd": "set" if settings.drawing_converter_cmd else "missing",
    }

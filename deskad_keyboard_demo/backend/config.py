
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    """.env 파일이 있으면 KEY=VALUE 형식의 환경 변수를 현재 프로세스에 주입한다."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env_file(BASE_DIR / ".env")
_load_env_file(BASE_DIR.parent / ".env")


def _int_env(name: str, default: int) -> int:
    """환경 변수 값을 정수로 읽고 실패하면 기본값을 반환한다."""
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float_env(
    name: str,
    default: float,
    *,
    lo: float | None = None,
    hi: float | None = None,
) -> float:
    """환경 변수 값을 실수로 읽고 실패하면 기본값을 반환한다.

    lo/hi를 주면 그 범위로 클램프한다 — env 오타(denoise=9 등)가 KSampler까지
    그대로 흘러가 job이 원인 안내 없이 실패하는 것을 막는다(QA 2026-06-10 #3).
    """
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# ComfyUI 워크플로의 {negative_prompt} 자리에 들어갈 기본 부정 프롬프트.
# COMFYUI_NEGATIVE_PROMPT 로 재정의 가능.
DEFAULT_COMFYUI_NEGATIVE_PROMPT = (
    "logo, watermark, distorted keyboard, extra keys, unreadable text, low quality"
)


@dataclass(frozen=True)
class Settings:
    """API, AI provider, 업로드, 변환기 관련 런타임 설정을 한 곳에 모은다."""
    api_base_url: str = os.getenv("DESKAD_API_BASE", "http://127.0.0.1:8010")
    public_api_base_url: str = os.getenv("DESKAD_PUBLIC_API_BASE", os.getenv("DESKAD_API_BASE", "http://127.0.0.1:8010"))
    ai_provider: str = os.getenv("AI_PROVIDER", "auto")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_text_model: str = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
    openai_image_model: str = os.getenv("OPENAI_IMAGE_MODEL", "")
    local_llm_base_url: str = os.getenv("LOCAL_LLM_BASE_URL", "")
    local_llm_model: str = os.getenv("LOCAL_LLM_MODEL", "")
    hyperclova_base_url: str = os.getenv("HYPERCLOVA_BASE_URL", "")
    hyperclova_api_key: str = os.getenv("HYPERCLOVA_API_KEY", "")
    hyperclova_model: str = os.getenv("HYPERCLOVA_MODEL", "")
    hyperclova_use_direct: bool = _bool_env("HYPERCLOVA_USE_DIRECT_API", False)
    hyperclova_apigw_key: str = os.getenv("HYPERCLOVA_APIGW_KEY", "")
    hyperclova_vision_base_url: str = os.getenv("HYPERCLOVA_VISION_BASE_URL", "")
    hyperclova_vision_api_key: str = os.getenv("HYPERCLOVA_VISION_API_KEY", "")
    hyperclova_vision_model: str = os.getenv("HYPERCLOVA_VISION_MODEL", "")
    hyperclova_image_base_url: str = os.getenv("HYPERCLOVA_IMAGE_BASE_URL", "")
    hyperclova_image_api_key: str = os.getenv("HYPERCLOVA_IMAGE_API_KEY", "")
    hyperclova_image_model: str = os.getenv("HYPERCLOVA_IMAGE_MODEL", "")
    hyperclova_image_mode: str = os.getenv("HYPERCLOVA_IMAGE_MODE", "omniserve_chat")
    kanana_base_url: str = os.getenv("KANANA_BASE_URL", "")
    kanana_api_key: str = os.getenv("KANANA_API_KEY", "")
    kanana_model: str = os.getenv("KANANA_MODEL", "")
    midm_base_url: str = os.getenv("MIDM_BASE_URL", "")
    midm_api_key: str = os.getenv("MIDM_API_KEY", "")
    midm_model: str = os.getenv("MIDM_MODEL", "")
    local_image_endpoint: str = os.getenv("LOCAL_IMAGE_ENDPOINT", "")
    image_model_backend: str = os.getenv("IMAGE_MODEL_BACKEND", "auto")
    comfyui_base_url: str = os.getenv("COMFYUI_BASE_URL", "")
    comfyui_workflow_path: str = os.getenv("COMFYUI_WORKFLOW_PATH", "")
    comfyui_workflows_dir: str = os.getenv("COMFYUI_WORKFLOWS_DIR", "")
    comfyui_default_workflow: str = os.getenv("COMFYUI_DEFAULT_WORKFLOW", "flux_schnell_basic")
    comfyui_negative_prompt: str = os.getenv("COMFYUI_NEGATIVE_PROMPT", DEFAULT_COMFYUI_NEGATIVE_PROMPT)
    comfyui_lora_name: str = os.getenv("COMFYUI_LORA_NAME", "")
    comfyui_lora_strength: float = _float_env("COMFYUI_LORA_STRENGTH", 0.0)
    comfyui_controlnet_image: str = os.getenv("COMFYUI_CONTROLNET_IMAGE", "")
    comfyui_controlnet_strength: float = _float_env("COMFYUI_CONTROLNET_STRENGTH", 0.0)
    # depth-ControlNet 워크플로(flux_controlnet_depth)가 쓰는 ControlNet 모델 파일명
    # (ComfyUI models/controlnet/ 기준). 비어 있으면 ControlNet 경로가 비활성이라
    # 셋업 레퍼런스는 기존 img2img(flux_img2img)로 폴백한다. strength>0 와 함께여야
    # 활성. 평면 색블록 img2img로는 "사진+정확 배열"을 동시에 못 얻어(2026-06-16 A/B),
    # GLB depth로 배열을 denoise와 독립적으로 고정하기 위한 노브.
    comfyui_controlnet_model: str = os.getenv("COMFYUI_CONTROLNET_MODEL", "")
    # FLUX schnell 기본은 4스텝으로 빠르지만, 셋업 구도 맵 img2img는 키캡/배열
    # 디테일이 뭉개지기 쉬워 composition 전용 steps를 따로 높일 수 있게 한다.
    comfyui_steps: int = _int_env("COMFYUI_STEPS", 4)
    comfyui_composition_steps: int = _int_env("COMFYUI_COMPOSITION_STEPS", 8)
    # img2img 워크플로(flux_img2img)에서 선택 도면을 latent로 인코딩한 뒤 적용할 denoise.
    # 1.0이면 도면을 무시(text-to-image와 동일), 0에 가까울수록 도면 원형을 강하게 유지.
    # 0.6~0.7이 "도면 구조는 따르되 광고 톤으로 재생성" 균형(schnell cfg=1 기준).
    comfyui_img2img_denoise: float = _float_env("COMFYUI_IMG2IMG_DENOISE", 0.65, lo=0.0, hi=1.0)
    # 셋업 구도 맵(평면 색블록)은 라인아트 도면보다 디테일이 없어 낮은 denoise면 도식
    # 그대로 남는다 → 사실감을 얻으려면 높은 denoise가 필요(라이브 검증: 0.90이 구도
    # 유지+사진화 균형, schnell 4스텝). 도면 레퍼런스(0.65)와 분리해 회귀를 막는다.
    comfyui_composition_denoise: float = _float_env("COMFYUI_COMPOSITION_DENOISE", 0.90, lo=0.0, hi=1.0)
    flux_model_variant: str = os.getenv("FLUX_MODEL_VARIANT", "")
    image_quantization: str = os.getenv("IMAGE_QUANTIZATION", "")
    enable_vae_tiling: bool = _bool_env("ENABLE_VAE_TILING", False)
    enable_xformers: bool = _bool_env("ENABLE_XFORMERS", False)
    request_timeout_seconds: int = _int_env("AI_REQUEST_TIMEOUT_SECONDS", 45)
    max_upload_mb: int = _int_env("MAX_UPLOAD_MB", 60)
    shared_data_dir: str = os.getenv("DESKAD_SHARED_DATA_DIR", "/opt/shared_data")
    shared_model_dir: str = os.getenv("DESKAD_SHARED_MODEL_DIR", "/opt/shared_model")
    step_converter_cmd: str = os.getenv("STEP_CONVERTER_CMD", "")
    step_converter_timeout_seconds: int = _int_env("STEP_CONVERTER_TIMEOUT_SECONDS", 120)
    drawing_converter_cmd: str = os.getenv("DRAWING_CONVERTER_CMD", "")
    drawing_converter_timeout_seconds: int = _int_env("DRAWING_CONVERTER_TIMEOUT_SECONDS", 120)
    cors_origins_raw: str = os.getenv("DESKAD_CORS_ORIGINS", "")

    @property
    def cors_origins(self) -> list[str]:
        """Allowed Origin headers. Empty list means same-origin only (no CORS responses)."""
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

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
    def has_hyperclova(self) -> bool:
        return bool(self.hyperclova_base_url and self.hyperclova_api_key)

    @property
    def has_hyperclova_direct(self) -> bool:
        return bool(self.hyperclova_use_direct and self.hyperclova_base_url and self.hyperclova_api_key)

    @property
    def effective_hyperclova_vision_base_url(self) -> str:
        return self.hyperclova_vision_base_url or self.hyperclova_image_base_url

    @property
    def effective_hyperclova_vision_api_key(self) -> str:
        return self.hyperclova_vision_api_key or self.hyperclova_image_api_key

    @property
    def effective_hyperclova_vision_model(self) -> str:
        return self.hyperclova_vision_model or self.hyperclova_image_model

    @property
    def has_hyperclova_vision(self) -> bool:
        return bool(self.effective_hyperclova_vision_base_url and self.effective_hyperclova_vision_model)

    @property
    def effective_hyperclova_image_base_url(self) -> str:
        return self.hyperclova_image_base_url

    @property
    def effective_hyperclova_image_api_key(self) -> str:
        return self.hyperclova_image_api_key

    @property
    def effective_hyperclova_image_model(self) -> str:
        return self.hyperclova_image_model

    @property
    def has_hyperclova_image(self) -> bool:
        mode = self.hyperclova_image_mode.strip().lower()
        if mode in {"", "disabled", "off", "false"}:
            return False
        return bool(self.effective_hyperclova_image_base_url and self.effective_hyperclova_image_model)

    @property
    def has_kanana(self) -> bool:
        return bool(self.kanana_base_url)

    @property
    def has_midm(self) -> bool:
        return bool(self.midm_base_url)

    @property
    def has_local_image(self) -> bool:
        """로컬 이미지 생성 엔드포인트가 설정되어 있는지 반환한다."""
        return bool(self.local_image_endpoint)

    @property
    def has_comfyui(self) -> bool:
        return bool(self.comfyui_base_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """프로세스 전체에서 재사용할 Settings 객체를 캐시해 반환한다."""
    return Settings()


def redacted_settings() -> dict:
    """민감한 값은 마스킹하고 UI/API 상태 표시용 설정 요약을 반환한다.

    Secret detection delegates to backend.security so logs/responses/CLI dumps
    all share the same definition of "sensitive".
    """
    from .security import mask_value

    settings = get_settings()
    return {
        "api_base_url": settings.api_base_url,
        "public_api_base_url": settings.public_api_base_url,
        "ai_provider": settings.ai_provider,
        "openai_api_key": mask_value(settings.openai_api_key),
        "openai_base_url": settings.openai_base_url,
        "openai_text_model": settings.openai_text_model,
        "openai_image_model": settings.openai_image_model or "disabled",
        "local_llm_base_url": "set" if settings.local_llm_base_url else "missing",
        "local_llm_model": settings.local_llm_model or "default",
        "hyperclova_base_url": "set" if settings.hyperclova_base_url else "missing",
        "hyperclova_api_key": mask_value(settings.hyperclova_api_key),
        "hyperclova_model": settings.hyperclova_model or "default",
        "hyperclova_use_direct": settings.hyperclova_use_direct,
        "hyperclova_apigw_key": mask_value(settings.hyperclova_apigw_key),
        "hyperclova_vision_base_url": "set" if settings.effective_hyperclova_vision_base_url else "missing",
        "hyperclova_vision_api_key": mask_value(settings.effective_hyperclova_vision_api_key),
        "hyperclova_vision_model": settings.effective_hyperclova_vision_model or "default",
        "hyperclova_vision_configured": settings.has_hyperclova_vision,
        "hyperclova_image_base_url": "set" if settings.effective_hyperclova_image_base_url else "missing",
        "hyperclova_image_api_key": mask_value(settings.effective_hyperclova_image_api_key),
        "hyperclova_image_model": settings.effective_hyperclova_image_model or "default",
        "hyperclova_image_mode": settings.hyperclova_image_mode,
        "hyperclova_image_configured": settings.has_hyperclova_image,
        "kanana_base_url": "set" if settings.kanana_base_url else "missing",
        "kanana_api_key": mask_value(settings.kanana_api_key),
        "kanana_model": settings.kanana_model or "default",
        "midm_base_url": "set" if settings.midm_base_url else "missing",
        "midm_api_key": mask_value(settings.midm_api_key),
        "midm_model": settings.midm_model or "default",
        "local_image_endpoint": "set" if settings.local_image_endpoint else "missing",
        "image_model_backend": settings.image_model_backend,
        "comfyui_base_url": "set" if settings.comfyui_base_url else "missing",
        "comfyui_workflow_path": "set" if settings.comfyui_workflow_path else "missing",
        "comfyui_workflows_dir": "set" if settings.comfyui_workflows_dir else "missing",
        "comfyui_default_workflow": settings.comfyui_default_workflow or "unset",
        "comfyui_steps": settings.comfyui_steps,
        "comfyui_composition_steps": settings.comfyui_composition_steps,
        "comfyui_img2img_denoise": settings.comfyui_img2img_denoise,
        "comfyui_composition_denoise": settings.comfyui_composition_denoise,
        "comfyui_controlnet_model": settings.comfyui_controlnet_model or "unset",
        "comfyui_controlnet_strength": settings.comfyui_controlnet_strength,
        "flux_model_variant": settings.flux_model_variant or "unset",
        "image_quantization": settings.image_quantization or "unset",
        "enable_vae_tiling": settings.enable_vae_tiling,
        "enable_xformers": settings.enable_xformers,
        "max_upload_mb": settings.max_upload_mb,
        "shared_data_dir": settings.shared_data_dir,
        "shared_model_dir": settings.shared_model_dir,
        "step_converter_cmd": "set" if settings.step_converter_cmd else "missing",
        "drawing_converter_cmd": "set" if settings.drawing_converter_cmd else "missing",
    }

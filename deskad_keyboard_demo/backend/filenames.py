from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


# 한글을 보존해야 한국 셀러가 생성 모델 파일을 제품명으로 식별할 수 있다
# ("크림 베이지 65% 키보드" → "65"로 뭉개지던 QA 06-05 지적). 경로 구분자·제어문자
# 등 위험 문자는 토큰화 단계에서 자연히 떨어져 나간다.
_SLUG_PART_RE = re.compile(r"[A-Za-z0-9가-힣]+")


def product_slug(value: str | None, *, fallback: str = "model") -> str:
    """Return a filesystem/URL-safe slug (ASCII + 한글) for generated model files."""
    parts = _SLUG_PART_RE.findall(str(value or "").lower())
    slug = "_".join(parts)[:80].strip("_")
    return slug or fallback


def timestamped_model_filename(product_name: str | None, *, fallback: str = "model", suffix: str = ".glb") -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return f"{stamp}_{product_slug(product_name, fallback=fallback)}{clean_suffix.lower()}"


def unique_timestamped_model_path(
    directory: Path,
    product_name: str | None,
    *,
    fallback: str = "model",
    suffix: str = ".glb",
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    filename = timestamped_model_filename(product_name, fallback=fallback, suffix=suffix)
    base = directory / filename
    stem, clean_suffix = base.stem, base.suffix
    # exists() 확인과 사용 사이의 TOCTOU(동시 요청 2건이 같은 경로 수령)를 막기 위해
    # O_EXCL 생성(touch(exist_ok=False))으로 경로를 원자적으로 선점한다.
    for counter in range(1, 1000):
        candidate = base if counter == 1 else directory / f"{stem}_{counter}{clean_suffix}"
        try:
            candidate.touch(exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise FileExistsError(f"Could not allocate a unique generated model filename for {filename}")

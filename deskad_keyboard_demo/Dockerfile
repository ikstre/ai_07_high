# syntax=docker/dockerfile:1
#
# DeskAd 앱 티어(FastAPI + Streamlit) 단일 이미지.
# 백엔드/프론트엔드가 같은 이미지를 공유하고 docker-compose의 command로 역할을 나눈다.
#
# 앱 티어는 CPU-only다. requirements.txt에 torch/transformers가 없으며,
# GPU 작업(LLM·이미지 생성)은 전부 외부 워커를 HTTP로 호출한다(GPU_WORKER_MODE=always_on).
# 모델 weight는 절대 이미지에 굽지 않는다 — 호스트 디렉터리를 볼륨으로 마운트한다.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GPU_WORKER_MODE=always_on

# curl: compose healthcheck(/health, /)용. 그 외 빌드 도구는 불필요(순수 파이썬 휠).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 레이어를 앱 소스와 분리해 캐시를 살린다.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스. 런타임/생성물(.env, static/, data/runtime/ 등)은 .dockerignore로 제외된다.
COPY . .

# non-root 실행. 기본 UID/GID 1000은 호스트 배포 계정과 맞춰 bind 마운트 쓰기 권한을 보장한다.
# 호스트 계정 UID가 다르면: docker build --build-arg UID=$(id -u) --build-arg GID=$(id -g) ...
ARG UID=1000
ARG GID=1000
RUN groupadd --gid "${GID}" appuser \
    && useradd --uid "${UID}" --gid "${GID}" --create-home appuser \
    && mkdir -p data/runtime data/runtime/cache static/uploads static/models static/posters \
    && chown -R "${UID}:${GID}" /app
USER appuser

# 8010 FastAPI(내부) / 8501 Streamlit(내부). 외부 노출은 호스트 nginx :8443가 담당.
EXPOSE 8010 8501

# 기본은 백엔드. 프론트엔드는 compose에서 command로 streamlit을 지정한다.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8010"]

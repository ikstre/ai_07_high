# DeskAd AI Studio

소상공인 커스텀 키보드 / 데스크테리어 판매자를 위한 **3D 셋업 미리보기 + 광고 콘텐츠 생성** 프로토타입입니다.

## 기능 요약

| 단계 | 기능 |
|------|------|
| ① 상품 정보 | 키보드 모델명·레이아웃 입력, STEP/STP/GLB 업로드 |
| ② 도면 미리보기 | 레이아웃 JSON → SVG 탑뷰 도면 생성 |
| ③ 3D 셋업 구성 | 책상 크기·모니터 크기·데스크테리어 선택 후 GLB 생성 |
| ④ 광고 생성 | 광고 문구(AI/폴백 템플릿) + SVG 포스터 다운로드 |

---

## 빠른 시작

### 1. 환경 준비

```bash
# 의존성 설치 (최초 1회)
conda run -n sprint_high pip install -r deskad_keyboard_demo/requirements.txt

# 환경 변수 설정
cp deskad_keyboard_demo/.env.example deskad_keyboard_demo/.env
# .env에서 OPENAI_API_KEY 등 필요한 항목 입력
# API 키 없이도 GLB 렌더 + 템플릿 광고 문구는 동작합니다
```

### 2. 통합 실행 (권장)

```bash
bash deskad_keyboard_demo/start.sh
```

옵션:

```bash
bash deskad_keyboard_demo/start.sh --restart   # 실행 중인 서버 재시작
bash deskad_keyboard_demo/start.sh --stop      # 서버 종료
```

### 3. 모델 워커(systemd, 선택)

로컬 이미지 생성을 쓸 때는 ComfyUI를 systemd 서비스로 등록합니다. Ollama는 패키지 설치 시 생성되는 `ollama.service`를 사용하며, `start.sh`가 두 워커 상태를 점검합니다.

```bash
sudo install -m 0644 deskad_keyboard_demo/tools/systemd/comfyui.service /etc/systemd/system/comfyui.service
sudo systemctl daemon-reload
sudo systemctl enable --now comfyui
systemctl status comfyui --no-pager
```

로그 확인:

```bash
journalctl -u comfyui -f
```

### 4. 개별 실행

**백엔드 (FastAPI, 포트 8010)**

```bash
cd deskad_keyboard_demo
conda run -n sprint_high python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010
```

**프론트엔드 (Streamlit, 포트 8501)**

```bash
cd deskad_keyboard_demo
conda run -n sprint_high python -m streamlit run streamlit_app.py \
  --server.port 8501 --server.address 127.0.0.1 --server.headless true \
  --server.enableCORS false --server.enableXsrfProtection true
```

### 5. 접속

```
https://<VM_IP>:8443
```

> **포트 안내**  
> - `8443` — nginx + basic auth 외부 접속  
> - `8501` — Streamlit 프론트엔드, loopback 전용  
> - `8010` — FastAPI 백엔드, loopback 전용  
> - `8188` — ComfyUI 이미지 워커, loopback 전용  
> - `11434` — Ollama 로컬 LLM, loopback 전용  
> - `8000` — JupyterHub 전용, **절대 사용 금지**

---

## 보안 설정

실제 API 키는 커밋하지 않습니다.

- `.gitignore`에 `.env`, `.env.*`, 업로드/포스터/모델 파일 제외 설정 포함
- `/security/config` API 엔드포인트는 키의 "설정됨/미설정" 상태만 반환, 실제 값 미노출

---

## 렌더링 치수 기준

모든 3D 씬은 `1 GLB unit = 1 cm` 기준입니다. 외부 모델 없이 `backend/renderer.py`의 절차적 박스 렌더러로 생성합니다.

### 책상 프리셋

| 이름 | 너비 × 깊이 |
|------|------------|
| 소형 | 120 × 60 cm |
| 중형 | 120 × 80 cm |
| L형 소형 | 140 × 70 cm |
| L형 중형 | 160 × 80 cm |
| 와이드 | 180 × 80 cm |

### 모니터 크기 프리셋

| 선택 | 패널 크기 |
|------|----------|
| 24인치 | 56 × 33 cm |
| 27인치 | 62 × 36 cm |
| 32인치 | 74 × 43 cm |

모니터암은 VESA MIS-D 100×100mm 기준입니다.

### 키보드 레이아웃 프리셋

| 레이아웃 | 크기 | 키 수 |
|----------|------|-------|
| 60% | 약 28.6 × 9.5 cm | 61키 |
| 65% | 약 30.5 × 9.5 cm | 67키 |
| 75% | 약 30.5 × 11.4 cm | 84키 |

MX 스위치 간격 기준 `1u = 19.05 mm`.

---

## 파일 구조

```
deskad_keyboard_demo/
├── start.sh                    # 통합 실행 스크립트
├── streamlit_app.py            # Streamlit 프론트엔드
├── requirements.txt
├── .env.example
├── backend/
│   ├── main.py                 # FastAPI 라우터
│   ├── renderer.py             # 절차적 GLB 생성기
│   ├── ai.py                   # 광고 문구 생성 (OpenAI / 로컬 LLM / 템플릿)
│   ├── assets.py               # 데스크테리어 카탈로그
│   ├── cad.py                  # STEP 변환 유틸
│   └── config.py               # 환경 변수 로딩
├── data/
│   ├── desk_assets.json        # 데스크테리어 항목 정의
│   └── layouts/
│       ├── layout_60.json      # 60% ANSI (61키)
│       ├── layout_65.json      # 65% (67키)
│       └── layout_75.json      # 75% (84키)
└── training/
    ├── README.md               # LoRA 학습 준비 가이드
    └── prepare_desk_lora_dataset.py
```

---

## 주요 API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 헬스체크 |
| GET | `/assets/desk` | 데스크테리어 항목 카탈로그 |
| POST | `/render/desk-setup` | 키보드 + 데스크테리어 GLB 생성 |
| POST | `/render/uploaded-model` | STEP/STP/GLB 업로드 미리보기 |
| POST | `/ai/copy` | 광고 문구 생성 |
| POST | `/ai/poster` | 광고 문구 + SVG 포스터 생성 |
| GET | `/security/config` | API 키 마스킹 상태 확인 |

---

## STEP 파일 변환

`.env`의 `STEP_CONVERTER_CMD`를 설정하면 STEP/STP → GLB 변환을 지원합니다. 미설정 시 프록시 GLB를 자동 생성합니다.

```bash
# 옵션 A: trimesh (pip install trimesh[all])
STEP_CONVERTER_CMD=python -c "import trimesh,sys; s=trimesh.load(sys.argv[1]); s.export(sys.argv[2])" {input} {output}

# 옵션 B: Blender 헤드리스
STEP_CONVERTER_CMD=blender --background --python /opt/deskad/step_to_glb.py -- {input} {output}

# 옵션 C: FreeCADCmd (Ubuntu: sudo apt install freecad)
STEP_CONVERTER_CMD=FreeCADCmd ...
```

---

## LoRA 학습 준비

`training/README.md`를 확인하세요.

```bash
# 의존성 설치 (sprint_high 환경에 미설치 상태)
conda run -n sprint_high pip install diffusers accelerate peft safetensors transformers

# 데이터셋 준비
conda run -n sprint_high python training/prepare_desk_lora_dataset.py \
  --images-dir ./raw_images \
  --output-dir ./training/output/desk_lora \
  --commercial-use-checked
```

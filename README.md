# ai_07_high

AI 기반 소상공인 커스텀 키보드/데스크테리어 광고 콘텐츠 생성 프로젝트입니다.

## 프로젝트

### [deskad_keyboard_demo](./deskad_keyboard_demo/)

커스텀 키보드 판매자를 위한 3D 셋업 미리보기 + 광고 콘텐츠 자동 생성 데모 앱.

- 절차적 GLB 렌더러로 책상/모니터/키보드 3D 씬 생성 (외부 모델 불필요)
- 60 / 65 / 75 / 87 / 104% 키보드 레이아웃 지원
- 24" / 27" / 32" 모니터 크기 프리셋
- 엔진 선택형 광고 생성: 문구(로컬 LLM·HyperCLOVA·OpenAI) + 이미지(ComfyUI/FLUX·OpenAI), 폴백 템플릿 내장
- 비동기 이미지 잡 + depth-ControlNet 배열 충실도 고정 + best-of-N(구도·액센트 색) 선별
- FastAPI (포트 8010, 내부) + Streamlit (포트 8501, 내부) — 외부는 nginx :8443

```bash
bash deskad_keyboard_demo/start.sh
```

앱 티어는 CPU-only라 Docker로도 실행할 수 있습니다 (`deskad_keyboard_demo/docker-compose.yml`, GPU 워커는 호스트 유지).

```bash
cd deskad_keyboard_demo && docker compose up -d --build
```

자세한 내용: [deskad_keyboard_demo/README.md](./deskad_keyboard_demo/README.md) · 배포 가이드 [deskad_keyboard_demo/docs/deploy.md](./deskad_keyboard_demo/docs/deploy.md)

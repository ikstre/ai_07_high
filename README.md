# ai_07_high

AI 기반 소상공인 커스텀 키보드/데스크테리어 광고 콘텐츠 생성 프로젝트입니다.

## 프로젝트

### [deskad_keyboard_demo](./deskad_keyboard_demo/)

커스텀 키보드 판매자를 위한 3D 셋업 미리보기 + 광고 콘텐츠 자동 생성 데모 앱.

- 절차적 GLB 렌더러로 책상/모니터/키보드 3D 씬 생성 (외부 모델 불필요)
- 60% / 65% / 75% 키보드 레이아웃 지원
- 24" / 27" / 32" 모니터 크기 프리셋
- OpenAI 호환 API 또는 로컬 LLM 기반 광고 문구 생성 (폴백 템플릿 내장)
- FastAPI (포트 8010, 내부) + Streamlit (포트 8501, 외부)

```bash
bash deskad_keyboard_demo/start.sh
```

자세한 내용: [deskad_keyboard_demo/README.md](./deskad_keyboard_demo/README.md)

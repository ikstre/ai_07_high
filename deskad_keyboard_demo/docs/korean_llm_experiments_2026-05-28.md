# Korean LLM 실험 연결 메모

작성일: 2026-05-28

## 목표

DeskAd AI Studio의 광고 카피 생성 provider를 특정 벤더 하나에 고정하지 않고, 한국어 특화 모델을 같은 OpenAI-compatible chat completions 규격으로 비교한다.

## 현재 지원 provider

- `openai`
- `hyperclova`
- `kanana`
- `midm`
- `local`
- `fallback`

`AI_PROVIDER=auto`일 때 순서는 `openai -> hyperclova -> kanana -> midm -> local -> fallback`이다. 단, 설정되지 않은 provider는 건너뛴다.

## 환경변수

```bash
AI_PROVIDER=auto

HYPERCLOVA_BASE_URL=
HYPERCLOVA_API_KEY=
HYPERCLOVA_MODEL=

KANANA_BASE_URL=
KANANA_API_KEY=
KANANA_MODEL=

MIDM_BASE_URL=
MIDM_API_KEY=
MIDM_MODEL=
```

`KANANA_BASE_URL`, `MIDM_BASE_URL`은 vLLM, SGLang, Ollama, LM Studio 같은 OpenAI-compatible gateway를 바라보게 한다.

## API

- `GET /ai/providers`: provider 설정 상태와 auto 순서 확인
- `POST /ai/copy`: 현재 `AI_PROVIDER` 기준 단일 카피 생성
- `POST /ai/copy/experiment`: `providers` 배열 기준 같은 입력을 여러 provider로 비교

예시:

```json
{
  "product_name": "크림 베이지 65% 커스텀 키보드",
  "target_channel": "스마트스토어",
  "selling_point": "가스켓 마운트, 조용한 리니어 스위치, 작은 책상에 맞는 배열",
  "providers": ["kanana", "midm", "local", "fallback"]
}
```

## 후보 모델 메모

- Kanana: Kakao가 Kanana 1.5 모델군을 Hugging Face에 공개했고, 8B/2.1B base/instruct 라인업과 Apache 2.0 상업 사용 가능성을 공지했다. 2026년 1월에는 Kanana-2 계열도 Hugging Face 조직에 올라와 있으므로, 실제 실험 전 해당 모델 카드의 라이선스와 VRAM 요구량을 다시 확인한다.
- Mi:dm: `K-intelligence/Midm-2.0-Base-Instruct` 모델 카드는 vLLM/SGLang OpenAI-compatible 호출 예시와 MIT 라이선스를 제공한다. L4 24GB 환경에서는 Mini 또는 GGUF/양자화 변형부터 검토한다.

## 운영 원칙

- 모델 가중치와 HF 토큰은 repo가 아니라 `/opt/shared_model` 또는 HF cache에 둔다.
- `.env.example`에는 토큰 값을 넣지 않는다.
- provider 비교 API 응답에는 API key나 실제 secret 값을 노출하지 않는다.
- 상업 사용 전에는 모델 카드의 최신 license, use restriction, attribution 요구사항을 다시 확인한다.

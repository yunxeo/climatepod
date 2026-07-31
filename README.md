# Climatepod AI 대화 효율 분석 에이전트

붙여 넣은 ChatGPT, Claude, Gemini 대화를 파싱해 보이는 텍스트의 토큰 사용량, AI 효율성, EcoLogits 기반 환경 영향을 SSE 리포트로 반환하는 FastAPI 에이전트입니다.

## 폴더 구조와 파일 역할

```text
climatepod/
├─ climatepod-agent/
│  ├─ api/
│  │  ├─ index.py       # FastAPI /chat 계약, 인증, SSE, 출력 새니타이저
│  │  ├─ pipeline.py    # 파싱 → 측정 → 평가 → 환경 영향 → 리포트 순서 조정
│  │  ├─ parser.py      # user/assistant/ui/unknown 분리, 발화 ID와 신뢰도
│  │  ├─ provider.py    # 공급사와 모델명 탐지
│  │  ├─ tokens.py      # 보이는 텍스트의 문자 기반 토큰 근사
│  │  ├─ evaluation.py  # Grooo v0.1 항목 평가와 가중 점수 계산
│  │  ├─ analysis.py    # 작업 유형, 복잡도, 장점, 개선점 휴리스틱
│  │  ├─ ecologits.py   # EcoLogits 환경 영향 API 클라이언트
│  │  ├─ report.py      # 사용자용 Markdown 리포트 섹션 렌더링
│  │  └─ constants.py   # 모델 기본값, 토큰 계수, 환산 상수
│  ├─ evaluation_criteria.md # 평가 기준의 단일 문서 원본
│  ├─ requirements.txt
│  └─ vercel.json
├─ SKILL.md             # Climatepod 외부 에이전트 제작·검증 계약
├─ workshop-guide.md    # 제작 워크숍 진행 가이드
└─ vercel-deploy.md     # Vercel 배포 절차
```

## 현재 평가 흐름

1. 원문을 발화 단위로 분리하고 `T1`, `T2` 형식의 근거 ID를 부여합니다.
2. 화자 라벨이 명시되면 높은 신뢰도, 빈 줄 교대 추정이면 낮은 신뢰도로 기록합니다.
3. UI 문구는 토큰 계산에서 제외하고, 역할 미확정 구간은 별도 토큰으로 표시합니다.
4. `GEMINI_API_KEY`가 있으면 Gemini 구조화 출력으로 `evaluation_criteria.md`의 18개 항목을 평가합니다.
5. 키가 없거나 Gemini 호출·검증이 실패하면 규칙 기반 예비 평가로 자동 전환합니다.
6. 적용 가능한 항목만으로 영역 점수와 종합 점수를 재정규화합니다.
7. 화자 분리 신뢰도가 낮으면 단일 종합 점수를 보류합니다.
8. 환경 영향과 함께 Markdown 리포트로 렌더링합니다.

Gemini 연결 시 의미 기반 평가를 사용합니다. 현재 대화 분리는 코드 기반이므로 에피소드 경계와 복잡한 인용 대화는 여전히 보수적으로 처리합니다. 원자료가 없는 사실 정확성은 Gemini 연결 여부와 관계없이 `not_applicable`로 제외합니다.

## 외부 명세 반영 상태

반영 완료:

- 프롬프트 준비도, 응답 효과성, 상호작용 효율의 3영역 기준
- 항목별 근거 발화 ID
- `not_applicable`과 가중치 재정규화
- 화자 분리 신뢰도가 낮을 때 단일 점수 보류
- UI와 역할 미확정 구간 구분
- `generic_estimate` 측정 품질과 숨겨진 토큰 미포함 표시
- 정확성 근거가 없을 때 점수 추정 금지
- 개선점 최대 3개 원칙
- Google AI Studio Gemini API 구조화 평가
- Gemini 미설정·오류 시 규칙 기반 fallback

후속 구현:

- LLM 기반 Transcript Normalizer와 JSON Schema 검증
- 작업 에피소드 및 후속 발화 유형의 의미 기반 분류
- 최소 수정 개선 프롬프트 생성과 입력 토큰 비교
- 동일 모델·설정 재실행을 통한 출력 품질과 전체 사용량 A/B 검증
- 공급사 token-count API 또는 실제 usage 연동

## 로컬 실행

```powershell
cd climatepod-agent
pip install -r requirements.txt
$env:AGENT_SECRET_KEY = "test-key"
$env:GEMINI_API_KEY = "AI Studio에서 발급한 키"
$env:GEMINI_MODEL = "gemini-2.5-flash"
uvicorn api.index:app --port 8000
```

```powershell
curl.exe -N -X POST http://localhost:8000/chat `
  -H "Content-Type: application/json" `
  -H "x-api-key: test-key" `
  -d '{"message":"User: 세 문장으로 요약해줘`nAssistant: 첫째 문장입니다."}'
```

`GEMINI_MODEL`은 선택 항목이며 생략하면 `gemini-2.5-flash`를 사용합니다. API 키는 `.env`, 소스 코드, 채팅 메시지에 저장하지 마세요. 공식 SDK는 `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY`를 지원하며 둘 다 설정되면 `GOOGLE_API_KEY`가 우선합니다.

## Vercel 환경변수

```powershell
vercel env add GEMINI_API_KEY production
vercel env add GEMINI_MODEL production
vercel --prod
```

첫 번째 명령의 입력 프롬프트에 API 키 값을 붙여 넣습니다. 키를 변경한 뒤에는 반드시 재배포해야 합니다.

공식 문서:

- [Gemini API 키 설정](https://ai.google.dev/gemini-api/docs/api-key)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)
- [Gemini 구조화 출력](https://ai.google.dev/gemini-api/docs/structured-output)

# 클라이밋팟 에이전트 — Vercel 배포 문서 (기본값)

프로젝트에 정해진 배포 방식이 없을 때 사용하는 기본 배포 예시입니다.
스킬 본문(규칙 1·8)에서 "Vercel 배포 문서"라고 지칭하는 문서가 이것입니다.

## 1. 파일 구조 (Vercel Python 서버리스 함수 규격)

에이전트 폴더는 정확히 이 구조로 만드세요:

```
climatepod-agent/
├── api/
│   └── index.py        # FastAPI 앱 전체 (단일 파일, 스킬 규칙 5 템플릿)
├── vercel.json
├── requirements.txt
└── (프로젝트에서 복사한 데이터 파일들 — 폴더 안에 있어야 배포에 포함됩니다)
```

`vercel.json` (모든 경로를 FastAPI로 라우팅):

```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/api/index" }]
}
```

주의: Vercel은 **이 폴더만** 번들합니다. 폴더 밖의 코드·데이터를 `../`로 참조하면
로컬 검증은 통과하고 배포에서만 죽습니다. 서버리스 함수 크기 제한(압축 후 250MB)도
고려해 필요한 파일만 복사하세요.

## 2. 배포 절차

```bash
# 로그인 확인 — 안 돼 있으면 사용자에게 `vercel login`을 직접 실행해달라고
# 요청하고 기다리세요 (브라우저 인증이라 사용자만 할 수 있습니다)
vercel whoami

# 에이전트 폴더에서:
vercel link --yes
vercel --prod --yes
```

API 키(`AGENT_SECRET_KEY`)는 AI가 값을 정하거나 묻지 않습니다. **사용자가 키 포함
배포를 명시적으로 요청한 경우에만** 아래 5절의 CLI 명령 실행을 안내하고, 값은 사용자가
직접 입력합니다 (스킬 규칙 8). 요청이 없었으면 배포 과정에서 건드리지 마세요.

## 3. 등록에 쓸 URL — 반드시 별칭 도메인

클라이밋팟 어드민에 등록하는 주소는 **별칭 도메인**을 쓰세요:

```
https://<프로젝트명>.vercel.app/chat
```

해시가 붙은 긴 배포 URL(`https://<프로젝트>-abc123-<팀>.vercel.app`)은 Vercel 보호
기능 때문에 클라이밋팟이 접근하지 못합니다. 배포 후 별칭 도메인으로 헬스체크와 정상
SSE를 curl로 재확인하세요.

## 4. 프로젝트 기능용 환경변수 이관 (키·백엔드를 쓰는 프로젝트는 필수)

원본이 쓰던 API 키·백엔드 URL·DB 접속정보 등은 배포 환경에 **자동으로 넘어오지
않습니다.** 없으면 배포·헬스체크는 되지만 실제 질문에서 백엔드 호출이 실패합니다
(스킬 규칙 8의 "기능용 환경변수 이관" 참고). 배포 시 AI가 이렇게 처리합니다:

```bash
# (1) 원본이 이미 가진 값이 있으면 그대로 이관 — 로컬 .env.local 이 있을 때
#     (없으면 사용자에게 값을 요청. 값을 지어내지 마세요. AGENT_SECRET_KEY 는 제외)
vercel env add GATEWAY_API_KEY production      # 값 입력 프롬프트
vercel env add GATEWAY_BASE_URL production
# 필요한 기능용 변수마다 반복 (이름은 에이전트 코드가 읽는 것과 동일해야 함)

# (2) 기존 배포 환경에 이미 값이 있는지 확인하려면
vercel env ls production

# (3) 등록 후 반드시 재배포해야 적용됩니다
vercel --prod
```

기존 값을 바꾸려면 `vercel env rm <NAME> production` 후 다시 add 하세요. 등록한 기능용
변수 **이름만** 완료 보고에 남기고 값은 적지 마세요.

현재 Climatepod 평가기는 다음 Production 변수를 사용합니다.

```bash
vercel env add EVALUATOR_PROVIDER production  # anthropic
vercel env add ANTHROPIC_API_KEY production   # 플랫폼에서 지급받은 키
vercel env add ANTHROPIC_MODEL production     # claude-haiku-4-5-20251001 또는 지정 모델
vercel --prod
```

`ANTHROPIC_API_KEY`를 `AGENT_SECRET_KEY`에 넣지 마세요. 전자는 Claude 호출용이고,
후자는 클라이밋팟 마켓이 `/chat`을 호출할 때 쓰는 별도 인증 키입니다.
키 값은 사용자가 Vercel의 비밀 입력 프롬프트에 직접 넣고, 소스·Git·채팅·로그에
남기지 않습니다.

## 5. API 키 설정 (키를 넣고 싶은 사람이 직접, 두 방법 중 하나)

두 방법 모두 **재배포해야 적용**되고, 어드민에는 같은 값을 (`Bearer` 접두사 없이) 입력합니다.

1. **Vercel 웹 대시보드**: 프로젝트 → Settings → Environment Variables에
   `AGENT_SECRET_KEY` 추가 (Production) → Deployments 탭에서 최신 배포 **Redeploy**
2. **CLI** (에이전트 폴더에서):
   ```bash
   vercel env add AGENT_SECRET_KEY production   # 값 입력 프롬프트
   vercel --prod                                # 재배포해야 적용
   ```
   값을 바꾸려면 먼저 `vercel env rm AGENT_SECRET_KEY production` 후 다시 add 하세요.

⚠️ 등록한 키 값은 Vercel에서 다시 볼 수 없으므로(Sensitive 변수는 쓰기 전용)
어드민에 입력할 수 있도록 따로 안전하게 보관하세요. 키 형식 권장: 영문·숫자 20자 이상,
한글·공백·특수문자 금지 (HTTP 헤더에서 깨집니다).

## 6. 배포 후 확인

```bash
curl -s https://<프로젝트명>.vercel.app/            # → {"status": "ok"}
curl -sN -X POST https://<프로젝트명>.vercel.app/chat \
  -H 'Content-Type: application/json' -d '{"message":"안녕"}'
# → data: {"content": ...} 스트림 + data: [DONE]
# (키를 설정했다면 위 요청은 401이어야 하고, 헤더에 키를 넣으면 SSE가 흘러야 합니다)
```

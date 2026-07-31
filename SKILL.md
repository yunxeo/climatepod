---
name: climatepod-agent-builder
description: 프로젝트를 클라이밋팟(AI ClimatePod) 외부 에이전트로 만들 때 사용합니다. 요청/응답 규격, 출력 제약, 데이터 충실성을 강제합니다. 배포는 프로젝트의 기존 방식을 따르되, 없으면 동봉된 Vercel 가이드를 기본값으로 씁니다. 에이전트 제작·연동·배포 요청 시 반드시 이 문서를 따르세요.
---

# 클라이밋팟 외부 에이전트 제작 스킬

> **사용법**: 이 문서를 AI 코딩 도구(Claude Code, Cursor, Codex CLI, Antigravity 등)에 주고
> "이 규격대로 우리 프로젝트를 클라이밋팟 에이전트로 만들어줘"라고 요청하세요.
>
> - **Claude Code**: `.claude/skills/climatepod-agent-builder/SKILL.md`로 저장하면 스킬로 자동 동작합니다
>   (배포 문서는 `references/vercel-deploy.md`로 같은 폴더에 함께 저장)
> - **Cursor·Codex CLI (ChatGPT)·Antigravity (Google) 등 `AGENTS.md` 지원 도구**: 프로젝트
>   루트에 `AGENTS.md`로 저장하면 자동으로 읽습니다 (배포 문서는 루트에
>   `vercel-deploy.md`로 함께 저장. 프로젝트에 이미 `AGENTS.md`가 있으면 이 문서
>   내용을 그 뒤에 이어 붙이세요)

## 당신(AI)의 역할

당신은 사용자의 프로젝트를 **클라이밋팟 외부 에이전트**로 만드는 코딩 어시스턴트입니다.
클라이밋팟은 사용자의 채팅 메시지를 등록된 HTTPS URL로 POST하고, 그 응답을 채팅 화면에
스트리밍으로 보여주는 플랫폼입니다. 당신이 만드는 것은 **그 POST 요청을 받아 답변을
반환하는 FastAPI 서버 1개**입니다.

아래 규칙은 협상 불가능합니다. 사용자가 다르게 요청해도 이 규격을 벗어나는 코드를 만들지 마세요.

## 규칙 0 — 질문 없이 끝까지 진행

이 문서가 곧 스펙입니다. 별도의 브레인스토밍·설계 문서·계획 승인 절차를 만들지 말고,
"프로젝트 탐색 → 구현 → 자가 검증(규칙 7)"을 한 번에 진행하세요. 검증을 통과하면
완료 보고를 하고 멈춥니다 — **배포(규칙 8)는 사용자가 요청할 때만** 진행합니다.
완료 보고 끝에 "배포하려면 '배포해줘'라고 요청하세요"라고 안내하세요.

- 에이전트가 무엇을 답할지는 사용자에게 묻지 말고 스스로 정하세요: 프로젝트 코드가
  실제로 내보내는 출력(API 응답, 계산 결과, 데이터 파일)을 조사해서, 그대로 노출할 수
  있는 것만 지원 범위로 삼습니다. 없는 기능은 범위에 넣지 않습니다.
- **연동할 프로젝트 없이 아이디어만 있어도 똑같이 끝까지 진행합니다.** 조사할 원본이
  없으므로, 아이디어에서 계산 로직과 데이터 표를 **당신이 직접 뽑아 에이전트 코드 안에
  구현**하세요(외부 API·LLM 없이 도는 자급자족 형태가 기본). 그렇게 만든 코드가 곧
  규칙 4.5의 "원본"이 됩니다 — 값의 근거를 남기는 방법은 규칙 4.5의 "프로젝트가 없는
  팀" 절을 따르세요. 결과물은 프로젝트가 있는 팀과 동일하게 `/chat` 서버 1개입니다.
- "이렇게 진행해도 될까요?" 류의 중간 확인을 하지 마세요. 선택지가 갈리면 데이터
  충실성(규칙 4.5)에 더 안전한 쪽을 골라 진행하고, 선택 이유는 완료 보고에 적으세요.
- 사용자에게 묻는 것이 허용되는 경우는 셋뿐입니다: ① 배포 로그인 등 사용자만 할 수
  있는 인증, ② 원본에 없는 값이 꼭 필요한 경우(규칙 4.5), ③ 프로젝트도 없고 요청에
  아이디어 설명도 없어 무엇을 만들지 단서가 전혀 없는 경우 — 이때만 "어떤 질문에 어떤
  식으로 답하는 에이전트를 원하세요?"를 **한 번** 묻고, 답을 받으면 끝까지 진행합니다.
- 도구에 플랜 모드/설계 우선 워크플로가 있어도 이 작업에는 적용하지 마세요.

## 규칙 1 — 아키텍처

에이전트는 **FastAPI 앱 단일 파일 + `requirements.txt`**로 구성합니다. 기존 프로젝트
코드를 수정하지 말고, 별도의 에이전트 폴더(예: `climatepod-agent/`)를 만들어 그 안에
독립적으로 담으세요. (연동할 프로젝트가 없는 팀은 작업 폴더 안에 이 에이전트 폴더
하나만 만들면 됩니다 — 구성은 동일합니다.)

`requirements.txt` 기본:

```
fastapi
uvicorn
```

(프로젝트 로직에 필요한 패키지는 추가해도 됩니다. 단 배포 환경의 크기 제한을 고려해 최소화하세요.)

**독립 배포 원칙**: 에이전트 폴더가 곧 배포 단위입니다. 폴더 밖의 프로젝트 코드나 데이터를
상대경로로 import/read 하지 마세요 — 로컬에서는 되고 배포에서만 깨지는 대표적 함정입니다.
필요한 로직과 데이터 파일은 에이전트 폴더 안으로 복사(이식)하세요.

**파일 배치와 배포 방식**은 배포 플랫폼을 따릅니다:

- 프로젝트에 이미 배포 설정(render.yaml, Dockerfile, fly.toml, Procfile 등)이 있고
  사용자가 그 플랫폼을 원하면, 그 방식에 `/chat` 엔드포인트 서버를 얹으세요.
- 정해진 것이 없으면 **기본값으로 동봉된 Vercel 배포 문서**의 구조를 그대로 쓰세요
  (도구에 따라 `references/vercel-deploy.md` 또는 루트의 `vercel-deploy.md`로
  저장돼 있습니다).

어느 플랫폼이든 규칙 2~8의 계약(요청/응답/출력/검증/등록 정보)은 동일하게 적용됩니다.

## 규칙 2 — 요청 계약 (클라이밋팟 → 에이전트)

클라이밋팟은 `POST /chat`으로 아래 JSON을 보냅니다:

```json
{
  "message": "이번 턴의 사용자 메시지 (항상 있음)",
  "conversation_history": [
    { "role": "user", "content": "이전 사용자 발화" },
    { "role": "assistant", "content": "이전 에이전트 답변" }
  ],
  "user_id": "사용자 식별자 (항상 있음)",
  "conversation_id": "대화 스레드 식별자 (항상 있음)"
}
```

- `message`만 필수로 처리하고, 나머지는 없어도 동작해야 합니다 (`conversation_history`는
  플랫폼 설정에 따라 빠질 수 있음).
- 인증: 클라이밋팟은 `Authorization: Bearer <키>`와 `x-api-key: <키>` 헤더를 **둘 다**
  보냅니다. 서버는 **둘 중 하나만 검증**하면 됩니다. 키는 환경변수 `AGENT_SECRET_KEY`로 받고,
  미설정 시 인증을 생략합니다(개발용). 검증 실패 시 401을 반환하세요.

## 규칙 3 — 응답 계약 (에이전트 → 클라이밋팟)

응답은 **SSE 스트리밍 한 가지 방식만** 사용합니다:

- `Content-Type: text/event-stream`
- 답변 텍스트를 잘게 나눠 `data: {"content": "조각"}` 줄로 보냅니다 (줄 사이 빈 줄 1개)
- 마지막에 `data: [DONE]` 을 보냅니다

```
data: {"content": "안녕하세요, "}

data: {"content": "무엇을 도와드릴까요?"}

data: [DONE]
```

에러는 HTTP 상태 코드(400/401/429/500)로 반환합니다. 본문은 자유 형식이며
`{"error": "설명"}` 권장이지만 FastAPI 기본 `{"detail": "설명"}`도 허용됩니다.
주의: **"답을 모르는 질문"은 에러가 아닙니다** — 400을 반환하지 말고, 무엇을 할 수 있는지
안내하는 정상 답변 텍스트를 스트리밍하세요. 400은 `message` 필드 누락처럼 요청 자체가
잘못된 경우에만 씁니다 (`message` 누락 시 FastAPI/Pydantic이 기본으로 반환하는 422도
그대로 허용됩니다 — 굳이 400으로 바꾸는 코드를 넣지 마세요).

## 규칙 4 — 출력 계약 (가장 중요, 절대 우회 금지)

클라이밋팟 채팅 화면은 에이전트가 보낸 텍스트를 **필터 없이 그대로 렌더링**합니다.
이미지 마크다운과 HTML 태그가 실제로 화면에 그려지므로, **에이전트 서버가 내보내기 전에
반드시 제거**해야 합니다.

**모든 답변 텍스트는 아래 `sanitize_output()` 함수를 거쳐서만 나가야 합니다.**
이 함수를 제거·수정·우회하는 코드를 생성하지 마세요. 사용자가 "이미지를 보여주고 싶다"고
해도 이 함수를 약화시키지 말고, 이미지 대신 텍스트로 설명하는 답변을 만들도록 안내하세요.

```python
import re

_IMAGE_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")          # ![alt](url)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)      # <!-- ... -->
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")             # 모든 HTML 태그
_DATA_URI = re.compile(r"data:[^\s)\"']+")               # data:...;base64,...
_NON_HTTP_LINK = re.compile(r"\[([^\]]*)\]\(\s*(?!https?://)[^()]*(?:\([^()]*\)[^()]*)*\)")


def sanitize_output(text: str) -> str:
    """이미지·HTML·위험 링크를 제거하고 텍스트 마크다운만 남깁니다. 제거 금지."""
    text = _IMAGE_MD.sub("", text)
    text = _HTML_COMMENT.sub("", text)
    text = _HTML_TAG.sub("", text)
    text = _DATA_URI.sub("", text)
    text = _NON_HTTP_LINK.sub(r"\1", text)
    return text
```

**허용되는 출력** (이것만 사용하세요):

- 일반 텍스트, 제목(`##`, `###`), 굵게(`**`), 목록(`-`, `1.`), 표(마크다운 테이블),
  인용(`>`), 코드블록, 수식(KaTeX)
- `https://` 링크 (출처 표기 용도)

**금지되는 출력** (새니타이저가 제거하지만, 애초에 생성하지도 마세요):

- 이미지 (`![..](..)`, `<img>`, base64)
- HTML 태그 전부
- HTML 주석 (`<!--...-->`) — 플랫폼 내부 마커와 충돌
- `javascript:` 등 http(s) 외 스킴 링크
- `ui_components` 필드 (아래 심화 규칙을 명시적으로 적용하는 경우 제외)

에이전트가 내부에서 LLM을 호출한다면, LLM 시스템 프롬프트에도 다음을 반드시 포함시키세요:

```
답변은 텍스트와 마크다운 서식(제목·목록·표·굵게)만 사용합니다.
이미지, HTML 태그, HTML 주석, 이모지 아트, base64는 절대 출력하지 않습니다.
링크는 https:// 로 시작하는 출처 링크만 허용됩니다.
```

(프롬프트는 1차 방어일 뿐입니다. `sanitize_output()`이 최종 방어선이므로 둘 다 필요합니다.)

## 규칙 4.5 — 데이터 충실성 (팀의 설계를 존중하세요)

에이전트의 답변 내용은 **팀 프로젝트의 원본 데이터와 로직에서만** 나와야 합니다.

**대원칙: 에이전트는 통역기입니다 — 프로젝트 출력의 내용을 편집할 권한이 없습니다.**
표시할 값의 기준은 단 하나, **프로젝트 코드가 응답으로 내보내는 필드 그대로**입니다.

- 프로젝트가 출력하는 값은 **전부, 그대로** 표시하세요. 값이 이상해 보여도
  (모든 구간이 동일한 상수, 중복된 데이터, 예상과 다른 범위·단위 등)
  **고치지도, 빼지도, 라벨을 재해석하지도 마세요.** 데이터의 오류를 판단하고
  고치는 것은 프로젝트 주인의 몫입니다. 발견한 이상 징후는 완료 보고에 적어 알리기만 하세요.
- 프로젝트가 출력하지 않는 값은 **추가하지 마세요.** 원본 데이터에서 새로 만든
  집계·파생값(평균, 비율, 환산치 — 예: 노드 온도의 경로 평균, 거리→도보 시간 환산)도
  "원본에서 계산했으니 괜찮다"고 합리화하지 마세요. 프로젝트 코드가 계산해주지 않으면 없는 값입니다.
- 프로젝트에 이미 있는 계산 로직(정렬 기준, 가중치, 추천 알고리즘)이 있으면
  단순화해서 새로 만들지 말고 **그 로직을 이식하거나 호출**하세요.
- 단, **기계용 필드는 채팅에 출력하지 마세요**: GeoJSON 지오메트리·좌표 배열, base64,
  내부 ID 배열처럼 사람이 읽지 않는 값은 표시 대상이 아닙니다. 통째로 빼고
  "(경로 좌표 데이터는 생략)"처럼 생략 사실만 한 줄 밝히세요. 채팅 답변 하나가
  수천 자를 넘으면 스트리밍이 수 분 이상 걸립니다 — 사람이 읽는 필드(수치·이름·텍스트)를
  그대로 보여주는 것과 기계용 필드를 통째로 생략하는 것은 충돌하지 않습니다.
- 값이 꼭 필요해 보이는데 원본에 없으면 지어내지 말고 사용자에게 물어보세요.
- 완성 후, 팀이 만든 "질문 → 기대 답변" 표(있다면)와 실제 답변을 대조해서
  다른 부분을 보고하세요. 형식이 맞아도 내용이 팀 의도와 다르면 완성이 아닙니다.

**프로젝트가 없는 팀 (아이디어만 있는 경우)**

원본이 없으니 위 규칙을 그대로 적용할 수 없습니다. 대신 **당신이 아이디어에서 구현해
에이전트 코드에 넣은 로직·데이터가 그 팀의 원본**이 됩니다. 그 원본을 팀이 검수하고
고칠 수 있게 만드는 것이 이 절의 목표입니다.

- **값은 코드 상단 한 곳에 상수로 모으세요.** 계수·기준치·항목 목록을 답변 문자열
  속에 흩어 놓지 말고, 팀이 파일을 열자마자 찾아서 고칠 수 있게 배치합니다.
- **값마다 근거를 주석으로 남기세요.**
  예: `TREE_KG_PER_YEAR = 6.6  # 30년생 소나무 1그루 연간 CO₂ 흡수량 — 산림청 근사값`
  근거를 댈 수 없는 값은 넣지 말고, 그 기능을 지원 범위에서 빼세요.
- **가짜 출처·가짜 통계를 만들지 마세요.** 실존 기관·논문의 이름을 빌려 존재하지 않는
  수치를 인용하는 것은 금지입니다. 일반적으로 통용되는 표준값이면 "표준 계수"라고만
  쓰고, 확실하지 않으면 그 사실을 주석과 완료 보고에 그대로 적으세요.
- **추정치는 답변에서도 추정치라고 밝히세요.** 예: 답변 끝에
  `> 표준 배출계수 기반 추정치예요. 실제 값은 조건에 따라 달라질 수 있어요.` 한 줄.
- 값을 코드에 넣은 다음부터는 위의 일반 규칙이 그대로 적용됩니다 — 답변 단계에서 그
  값을 임의로 바꾸거나, 상수에 없는 새 파생값을 만들어 붙이지 마세요.
- **완료 보고에 당신이 새로 넣은 값을 전부 표로 나열하세요** (값 · 단위 · 근거).
  프로젝트가 없는 팀이 검수할 대상은 코드가 아니라 그 표입니다.
- **근거가 불확실한 값은 표에서 눈에 띄게 구분하세요** (예: 근거 칸 앞에 ⚠️와
  "근거 미확정"). 공식 기준값과 "통용되는 권고를 요약한 것"을 같은 표에 나란히 두면
  팀이 구분하지 못하고 넘어갑니다. 그런 항목이 하나라도 있으면 **완료 보고 맨 앞에서
  먼저** "근거 미확정 N건 — 검수 필요"라고 알리고, 무엇으로 교체하면 되는지도 적으세요
  (예: "기관 공식 문구로 교체 권장"). 코드 주석에도 같은 사실을 남깁니다.

## 규칙 5 — 완성 템플릿

새 에이전트를 만들 때 이 코드에서 시작하세요. **`generate_answer()`만 프로젝트 로직으로
교체**하고 나머지 구조(인증, 새니타이저, SSE)는 그대로 두세요.

```python
"""클라이밋팟 외부 에이전트 — FastAPI 앱 단일 파일"""

import asyncio
import json
import os
import re
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()

SECRET_KEY = os.environ.get("AGENT_SECRET_KEY", "")


class HistoryItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[list[HistoryItem]] = None
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None


# --- 출력 새니타이저 (규칙 4, 제거 금지) ---

_IMAGE_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_DATA_URI = re.compile(r"data:[^\s)\"']+")
_NON_HTTP_LINK = re.compile(r"\[([^\]]*)\]\(\s*(?!https?://)[^()]*(?:\([^()]*\)[^()]*)*\)")


def sanitize_output(text: str) -> str:
    text = _IMAGE_MD.sub("", text)
    text = _HTML_COMMENT.sub("", text)
    text = _HTML_TAG.sub("", text)
    text = _DATA_URI.sub("", text)
    text = _NON_HTTP_LINK.sub(r"\1", text)
    return text


# --- 여기만 교체: 프로젝트 로직 / LLM 호출 ---

def generate_answer(message: str, history: Optional[list[HistoryItem]]) -> str:
    return f"'{message}' 질문을 받았습니다. 여기에 프로젝트 로직을 연결하세요."


# --- 엔드포인트 (구조 유지) ---

def _check_auth(authorization: Optional[str], x_api_key: Optional[str]) -> None:
    if not SECRET_KEY:
        return
    if authorization != f"Bearer {SECRET_KEY}" and x_api_key != SECRET_KEY:
        raise HTTPException(status_code=401, detail="API key is invalid or missing.")


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(
    req: ChatRequest,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
):
    _check_auth(authorization, x_api_key)

    # 전체 답변 생성 → 새니타이즈 → 스트리밍.
    # 청크 단위로 새니타이즈하면 패턴이 청크 경계에서 잘려 누락되므로 이 순서를 지키세요.
    answer = sanitize_output(generate_answer(req.message, req.conversation_history))

    async def stream():
        chunk_size = 12  # 문자 수 기준 — json.dumps가 이스케이프하므로 한글이 깨지지 않습니다
        for i in range(0, len(answer), chunk_size):
            payload = json.dumps({"content": answer[i : i + chunk_size]}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
            await asyncio.sleep(0.02)
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
```

LLM을 붙이는 경우: `generate_answer()` 안에서 LLM API를 호출하고 **완성된 텍스트를
반환**하세요. LLM 스트리밍을 그대로 통과시키려면 누적 버퍼에 새니타이저를 적용하는 구현이
필요한데, 특별한 이유가 없다면 "전체 생성 → 새니타이즈 → 재스트리밍"이 정답입니다.

## 규칙 6 — (심화, 선택) 구조화 UI 컴포넌트

기본은 텍스트 전용입니다. 팀이 명시적으로 원하고 시간이 남을 때만, 아래 **화이트리스트
8종**의 `ui_components`를 SSE 스트림에 실을 수 있습니다:

`table` · `list` · `chart`(bar/line/pie) · `info-box` · `comparison-list` ·
`button-group` · `step-note` · `card`

제약:

- `card`의 `image`, `comparison-list`의 `logo` 등 **이미지 URL 필드는 절대 채우지 마세요.**
- 위 8종 외 타입(특히 `artifact`, `image-gallery`, `carousel`)은 절대 생성하지 마세요.
- 텍스트 델타와 같은 스트림에서, 별도의 `data:` 줄로 보냅니다:

```
data: {"ui_components": [{"type": "table", "data": {"columns": [{"key": "route", "label": "경로"}, {"key": "shade", "label": "그늘 비율"}], "rows": [{"route": "수변길", "shade": "78%"}]}}]}
```

- 코드에는 화이트리스트 검증을 넣으세요: 8종 외 타입이 들어오면 해당 컴포넌트를 버립니다.

## 규칙 7 — 완료 전 자가 검증 (필수)

코드를 완성했다고 말하기 전에 아래를 실제로 실행해 통과를 확인하세요.
(`<앱모듈>`은 실제 파일 위치에 맞추세요 — 예: Vercel 구조면 `api.index:app`)

```bash
pip install -r requirements.txt

# 포트가 비어 있는지 먼저 확인하세요. 이전 세션의 서버가 남아 있으면 검증 요청이
# 그 서버로 가서 "통과한 것처럼" 보입니다 (실제로 일어난 사고). 점유돼 있으면
# 그 프로세스를 죽이지 말고 다른 빈 포트로 바꿔서 진행하세요.
lsof -nP -iTCP:8000 -sTCP:LISTEN && echo "포트 8000 사용 중 — 다른 포트로 변경할 것"

AGENT_SECRET_KEY=test-key uvicorn <앱모듈>:app --port 8000 &

# 1. 인증 없음 → HTTP 401 (본문은 {"detail": ...} 또는 {"error": ...})
curl -s -X POST http://localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"message":"안녕"}'

# 2. 정상 요청 → data: {"content": ...} 스트림이 흐르고 마지막에 data: [DONE]
curl -sN -X POST http://localhost:8000/chat -H 'Content-Type: application/json' \
  -H 'x-api-key: test-key' -d '{"message":"안녕"}'

# 3. history 없이도 동작 (정상 SSE 스트림이면 통과)
curl -sN -X POST http://localhost:8000/chat -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer test-key' \
  -d '{"message":"테스트","user_id":"u1","conversation_id":"c1"}'

# 4. 새니타이저 단위 검증 (서버 불필요, <앱모듈>은 위와 동일)
python -c "
from <앱모듈 import 경로> import sanitize_output as s
out = s('![x](https://e.com/x.png) <img src=a> <!--m--> [c](javascript:alert(1)) data:image/png;base64,AA [ok](https://e.com)')
assert '![' not in out and '<' not in out and 'javascript' not in out and 'data:' not in out
assert '[ok](https://e.com)' in out
print('sanitizer OK')
"

# 검증이 끝나면 백그라운드 서버를 반드시 종료하세요
kill %1
```

## 규칙 8 — 배포 + 등록 정보 파일 생성 (`CLIMATEPOD.md`)

**사용자가 배포를 요청하면**(예: "배포해줘") 진행하세요. 자가 검증(규칙 7)을 통과한
상태여야 하며, 요청 없이 먼저 배포하지 마세요.

**배포 플랫폼 선택** (규칙 1과 동일):

- 프로젝트에 이미 배포 설정·플랫폼이 있으면 그 방식으로 에이전트를 배포하세요.
- 정해진 것이 없으면 동봉된 **Vercel 배포 문서**를 그대로 따르세요
  (도구에 따라 `references/vercel-deploy.md` 또는 루트의 `vercel-deploy.md`).

**프로젝트 기능용 환경변수 이관 (키·백엔드를 쓰는 프로젝트는 필수)**:

에이전트는 독립 배포 단위라, 원본 프로젝트가 쓰던 환경변수를 **자동으로 물려받지
않습니다.** 원본이 API 키·백엔드 URL·DB 접속정보 등을 환경변수로 읽고 있었다면, 그 값이
배포 환경에 없을 때 **배포·헬스체크는 성공하지만 실제 질문에는 답하지 못하는**(백엔드
호출이 실패하는) 상태가 됩니다. 따라서 배포 시 아래를 **자동으로** 수행하세요:

1. **감지**: 에이전트 코드가 읽는 환경변수 이름을 스캔하세요(`process.env.X`,
   `os.environ[...]`, `os.getenv(...)` 등). 원본 프로젝트의 `.env.example`·`.env.local`·
   README도 교차 확인해 같은 이름을 찾습니다. **`AGENT_SECRET_KEY`는 여기서 제외** —
   그건 아래에서 따로 다루는 인증 키이며 절대 자동 설정하지 않습니다.
2. **값 확보**: 값은 지어내지 말고 프로젝트가 이미 가진 곳에서만 가져옵니다 —
   우선순위 `.env.local` → `.env` → 기존 배포 환경(예: `vercel env pull`).
3. **등록·재적용**: 찾은 값을 배포 환경에 등록하고(Vercel이면 `vercel env add <NAME>
   production`) **재배포**해 적용하세요(배포 문서의 해당 절 참고).
4. **없으면 물어보기**: 필수 값을 어디서도 못 찾으면 지어내거나 비워둔 채 넘어가지 말고
   사용자에게 값을 요청하세요(규칙 0이 허용하는 질문). "이건 팀이 가진 값이라 내가 만들 수
   없다"고 밝히고, 로컬 `.env.local`에서 찾아 알려달라고 안내합니다.
5. **보고**: 완료 보고에 **등록한 기능용 환경변수 이름만**(값은 절대 쓰지 않음) 나열하고,
   아직 사용자에게 받아야 하는 값이 있으면 명시하세요.

**플랫폼 불문 공통 원칙**:

1. 배포 로그인 등 브라우저 인증은 사용자만 할 수 있습니다 — 필요하면 직접 실행해달라고
   요청하고 기다리세요.
2. API 키(`AGENT_SECRET_KEY`)는 **AI가 값을 정하지 않습니다.** 키를 넣을지 말지는
   개인의 선택이므로, AI가 키 값을 물어보지도 말고, 임의로 생성해 넣지도 마세요.
   단, **사용자가 키 포함 배포를 명시적으로 요청하면**(예: "API 키를 포함해서 배포해줘")
   배포 과정에서 키 등록 명령(Vercel이면 `vercel env add AGENT_SECRET_KEY production`)
   실행을 안내하고, 값 입력 프롬프트에는 **사용자가 직접 입력**하게 하세요
   (배포 문서의 "API 키 설정" 절 참고. 등록 후 재배포까지 진행).
   키 요청이 없었던 배포라면 키를 건드리지 말고, 완료 보고에
   ① 현재 키가 없어 URL을 아는 누구나 호출 가능한 상태라는 것,
   ② 원하면 `CLIMATEPOD.md`의 설정 단계대로 본인이 직접 넣을 수 있다는 것만 알리세요.
3. 클라이밋팟이 접근할 수 있는 **공개 HTTPS URL**이어야 합니다 (비밀번호 보호·프리뷰 전용
   URL 금지).
4. 배포된 URL로 헬스체크·정상 SSE를 curl로 재확인하세요
   (키를 설정한 배포라면 인증 없는 요청이 401이 되는 것도 확인).

배포가 성공하면 — 그때 **한 번에** — 에이전트 폴더에 `CLIMATEPOD.md`를 작성하세요.
자리표시자 없이 전부 실제 값이어야 하고, **항목 순서는 아래 표의 순서 그대로** 씁니다
(URL·API 키 안내는 문서 맨 아래에 오게 합니다):

| 항목 | 기준 |
|------|------|
| 에이전트 이름 | 프로젝트/서비스 이름 기반, 간결하게 |
| 한 줄 설명 | 무엇을 물으면 무엇을 답하는지 한 문장 |
| 상세 설명 | 무엇을 어떻게 답하는 에이전트인지 2~3문장. **연동 프로젝트 없이 아이디어로 만든 에이전트라면, 답변의 기준값이 어디서 온 것인지 한 문장으로 밝히세요** — 예: "배출계수는 일반적으로 통용되는 표준값을 코드에 넣어 계산한 추정치입니다." 채팅 사용자가 공식·실시간 데이터로 오해하지 않게 하는 것이 목적입니다. 근거 미확정 항목(규칙 4.5)이 남아 있으면 그 사실도 이 문장에 포함하세요 |
| 태그 | 프로젝트에서 뽑을 수 있는 관련 키워드 **전부** (쉼표 구분, 개수 제한 없음) |
| 샘플 질문 3개 | **실제로 호출해 좋은 답이 나오는 것을 확인한 질문만** |
| 외부 에이전트 URL | 배포로 확정된 실제 주소 + `/chat` |
| API 키 | 값은 적지 않습니다. 맨 앞에 **이 배포의 현재 상태**를 명시하세요 — 키가 설정되지 않았으면 "현재 키 미설정: 인증 없이 동작하며 URL을 아는 누구나 호출 가능(무단 사용·과금 위험)", 사용자가 배포 중 키를 설정했으면 "현재 키 설정됨: 등록 시 입력한 그 값을 어드민에 입력할 것"이라고 씁니다. 이어서 공통 안내: 키는 배포하는 사람이 배포 환경의 환경변수 `AGENT_SECRET_KEY`에 직접 정해 넣는 값이라는 것과, 어드민에는 그 값을 `Bearer` 접두사 없이 그대로 입력한다는 것을 안내하세요. 키가 필수가 아니라는 점(미설정 시 인증 없이 동작)과, 그 경우 URL을 아는 누구나 호출할 수 있어 무단 사용·과금 위험이 있다는 경고를 함께 적으세요. 사용 중인 배포 플랫폼에서 환경변수를 설정·적용(재배포/재시작 포함)하는 구체적 단계를 적으세요 — Vercel이면 배포 문서의 "API 키 설정" 절을 그대로 옮깁니다. 등록한 키 값은 따로 보관하라는 안내와, 키 형식 권장사항(영문·숫자 20자 이상, 한글·공백·특수문자 금지 — HTTP 헤더에서 깨짐)도 적으세요 |

사용자가 배포를 원하지 않거나 로그인이 불가하면 `CLIMATEPOD.md`를 만들지 말고,
등록 정보를 완료 보고(채팅)에만 포함한 뒤 "배포 후 이 파일을 만들어달라"고 안내하세요.

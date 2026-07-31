"""클라이밋팟 외부 에이전트 — AI 대화 탄소·토큰 분석"""

import asyncio
import json
import os
import re
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .pipeline import analyze_conversation_text

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


async def generate_answer(message: str, history: Optional[list[HistoryItem]]) -> str:
    return await analyze_conversation_text(message)


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

    answer = sanitize_output(await generate_answer(req.message, req.conversation_history))

    async def stream():
        chunk_size = 12
        for i in range(0, len(answer), chunk_size):
            payload = json.dumps({"content": answer[i : i + chunk_size]}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
            await asyncio.sleep(0.02)
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

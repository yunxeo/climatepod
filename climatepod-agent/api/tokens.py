"""토큰 추정 — 프로바이더별 문자 기반 근사"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from constants import TOKEN_ESTIMATION
from parser import ParsedConversation, Turn

_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")
_LATIN_RE = re.compile(r"[A-Za-z0-9\s.,!?;:'\"()\[\]{}]")


@dataclass
class TokenEstimate:
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def _count_char_types(text: str) -> tuple[int, int, int]:
    cjk = len(_CJK_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    other = max(0, len(text) - cjk - latin)
    return cjk, latin, other


def estimate_tokens_for_text(text: str, provider: str) -> int:
    cfg = TOKEN_ESTIMATION.get(provider, TOKEN_ESTIMATION["openai"])
    cjk, latin, other = _count_char_types(text)
    raw = (
        cjk / cfg["cjk_chars_per_token"]
        + latin / cfg["latin_chars_per_token"]
        + other / cfg["other_chars_per_token"]
    )
    return max(1, math.ceil(raw)) if text.strip() else 0


def estimate_conversation_tokens(
    conversation: ParsedConversation, provider: str
) -> tuple[TokenEstimate, list[tuple[Turn, int]]]:
    per_turn: list[tuple[Turn, int]] = []
    input_tokens = 0
    output_tokens = 0

    for turn in conversation.turns:
        count = estimate_tokens_for_text(turn.content, provider)
        per_turn.append((turn, count))
        if turn.role == "user":
            input_tokens += count
        else:
            output_tokens += count

    return TokenEstimate(input_tokens=input_tokens, output_tokens=output_tokens), per_turn

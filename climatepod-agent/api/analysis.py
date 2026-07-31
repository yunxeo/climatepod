"""프롬프트 분석 휴리스틱 — 추후 효율성 로직 확장 지점"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parser import ParsedConversation
from .provider import ProviderInfo
from .tokens import TokenEstimate


@dataclass
class PromptAnalysis:
    task_type: str
    complexity: str
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


_TASK_KEYWORDS: list[tuple[str, re.Pattern[str]]] = [
    ("코드 작성·디버깅", re.compile(r"code|코드|python|javascript|bug|함수|api|sql", re.I)),
    ("글쓰기·편집", re.compile(r"글|작성|에세이|번역|translate|rewrite|요약", re.I)),
    ("학습·설명", re.compile(r"설명|알려|what is|왜|how|개념|학습", re.I)),
    ("기획·아이디어", re.compile(r"아이디어|기획|전략|plan|brainstorm", re.I)),
]


def _detect_task_type(text: str) -> str:
    for label, pattern in _TASK_KEYWORDS:
        if pattern.search(text):
            return label
    return "일반 질의·대화"


def _detect_complexity(conversation: ParsedConversation, tokens: TokenEstimate) -> str:
    if tokens.total_tokens >= 8000 or conversation.total_turns >= 20:
        return "높음"
    if tokens.total_tokens >= 2000 or conversation.total_turns >= 8:
        return "중간"
    return "낮음"


def _longest_user_message(conversation: ParsedConversation) -> int:
    return max(
        (len(t.content) for t in conversation.turns if t.role == "user"),
        default=0,
    )


def _has_repetition(text: str) -> bool:
    sentences = [s.strip() for s in re.split(r"[.!?\n]", text) if len(s.strip()) > 20]
    return len(sentences) != len(set(sentences))


def analyze_prompt(
    conversation: ParsedConversation,
    tokens: TokenEstimate,
    provider_info: ProviderInfo,
) -> PromptAnalysis:
    """규칙 기반 1차 분석. 추후 LLM/점수 모델로 교체 가능."""
    full_text = "\n".join(
        t.content for t in conversation.turns if t.role in ("user", "assistant")
    )
    user_text = "\n".join(t.content for t in conversation.turns if t.role == "user")
    task_type = _detect_task_type(full_text)
    complexity = _detect_complexity(conversation, tokens)

    strengths: list[str] = []
    improvements: list[str] = []
    suggestions: list[str] = []

    if conversation.user_turn_count >= 1:
        strengths.append("대화 형식으로 맥락이 단계적으로 전달되고 있어요.")

    if _longest_user_message(conversation) > 1500:
        improvements.append("사용자 발화 중 배경 설명이 긴 구간이 있어요.")
        suggestions.append("핵심 조건만 bullet로 정리하면 입력 토큰을 줄일 수 있어요.")

    if _has_repetition(full_text):
        improvements.append("비슷한 문장이 반복되는 부분이 보여요.")
        suggestions.append("중복 표현을 정리하면 약 5~15% 정도 토큰을 줄일 수 있어요.")

    if conversation.total_turns >= 10:
        improvements.append("턴 수가 많아 누적 토큰이 커질 수 있어요.")
        suggestions.append("새 주제는 새 대화로 시작하면 효율적이에요.")

    if not improvements:
        strengths.append("지금 상태도 충분히 읽기 좋은 구조예요.")

    has_output_contract = re.search(
        r"표|목록|불릿|JSON|Markdown|마크다운|문단|문장|글자|분량|형식|구성|"
        r"한국어|영어|존댓말|말투|코드|파일",
        user_text,
        re.I,
    )
    if not suggestions and not has_output_contract:
        suggestions.append("원하는 출력 형식(표, 목록, 분량)을 한 줄로 명시하면 답변 품질이 올라가요.")

    return PromptAnalysis(
        task_type=task_type,
        complexity=complexity,
        strengths=strengths,
        improvements=improvements,
        suggestions=suggestions,
    )

"""대화 텍스트 파싱 — 사용자/AI 발화 구분"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["user", "assistant"]

# 역할 라벨 패턴 (export 형식·한/영 혼용)
_ROLE_PATTERNS: list[tuple[Role, re.Pattern[str]]] = [
    ("user", re.compile(r"^(?:You|User|Human|나|사용자|질문|Question)\s*[:：]\s*", re.I)),
    (
        "assistant",
        re.compile(
            r"^(?:ChatGPT|GPT|Assistant|AI|Claude|Gemini|"
            r"어시스턴트|챗GPT|챗지피티|클로드|제미니|답변|Answer|Bot)\s*[:：]\s*",
            re.I,
        ),
    ),
]

# 마크다운/볼드 헤더 형식: **User**, ### Assistant 등
_MD_ROLE_PATTERNS: list[tuple[Role, re.Pattern[str]]] = [
    ("user", re.compile(r"^(?:#{1,4}\s*)?(?:\*\*)?(?:You|User|Human|사용자|나)(?:\*\*)?\s*$", re.I)),
    (
        "assistant",
        re.compile(
            r"^(?:#{1,4}\s*)?(?:\*\*)?(?:ChatGPT|Assistant|AI|Claude|Gemini|어시스턴트|답변)(?:\*\*)?\s*$",
            re.I,
        ),
    ),
]


@dataclass
class Turn:
    role: Role
    content: str


@dataclass
class ParsedConversation:
    turns: list[Turn] = field(default_factory=list)

    @property
    def total_turns(self) -> int:
        return len(self.turns)

    @property
    def user_turn_count(self) -> int:
        return sum(1 for t in self.turns if t.role == "user")

    @property
    def assistant_turn_count(self) -> int:
        return sum(1 for t in self.turns if t.role == "assistant")


def _strip_role_prefix(line: str) -> tuple[Role | None, str]:
    for role, pattern in _ROLE_PATTERNS:
        m = pattern.match(line)
        if m:
            return role, line[m.end() :].strip()
    return None, line


def _match_md_role(line: str) -> Role | None:
    stripped = line.strip()
    for role, pattern in _MD_ROLE_PATTERNS:
        if pattern.match(stripped):
            return role
    return None


def parse_conversation(text: str) -> ParsedConversation:
    """붙여넣은 대화 텍스트를 턴 단위로 파싱합니다."""
    text = text.strip()
    if not text:
        return ParsedConversation()

    lines = text.splitlines()
    turns: list[Turn] = []
    current_role: Role | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_role, current_lines
        if current_role and current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                turns.append(Turn(role=current_role, content=content))
        current_lines = []

    for line in lines:
        md_role = _match_md_role(line)
        if md_role:
            flush()
            current_role = md_role
            continue

        inline_role, remainder = _strip_role_prefix(line)
        if inline_role:
            flush()
            current_role = inline_role
            if remainder:
                current_lines.append(remainder)
            continue

        if current_role is None:
            # 라벨 없이 시작 — 첫 블록은 사용자로 가정
            current_role = "user"

        current_lines.append(line)

    flush()

    if turns:
        return ParsedConversation(turns=turns)

    # 라벨 없음: 빈 줄 기준 교대(user → assistant) 휴리스틱
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) >= 2:
        alt_turns = [
            Turn(role="user" if i % 2 == 0 else "assistant", content=block)
            for i, block in enumerate(blocks)
        ]
        return ParsedConversation(turns=alt_turns)

    return ParsedConversation(turns=[Turn(role="user", content=text)])

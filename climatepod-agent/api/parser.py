"""대화 텍스트 파싱 — 사용자/AI/UI 발화 구분과 신뢰도 기록."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["user", "assistant", "ui", "unknown"]
Confidence = Literal["high", "medium", "low"]

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

_UI_LINE = re.compile(
    r"^(?:복사|편집|다시\s*생성|좋아요|싫어요|공유|더\s*보기|"
    r"copy|edit|regenerate|share|good\s+response|bad\s+response)$",
    re.I,
)


@dataclass
class Turn:
    role: Role
    content: str
    turn_id: str = ""


@dataclass
class ParsedConversation:
    turns: list[Turn] = field(default_factory=list)
    segmentation_confidence: Confidence = "low"
    warnings: list[str] = field(default_factory=list)

    @property
    def total_turns(self) -> int:
        return sum(1 for t in self.turns if t.role in ("user", "assistant"))

    @property
    def total_segments(self) -> int:
        return len(self.turns)

    @property
    def user_turn_count(self) -> int:
        return sum(1 for t in self.turns if t.role == "user")

    @property
    def assistant_turn_count(self) -> int:
        return sum(1 for t in self.turns if t.role == "assistant")

    @property
    def unknown_turn_count(self) -> int:
        return sum(1 for t in self.turns if t.role == "unknown")

    @property
    def ui_turn_count(self) -> int:
        return sum(1 for t in self.turns if t.role == "ui")


def _with_turn_ids(turns: list[Turn]) -> list[Turn]:
    for index, turn in enumerate(turns, start=1):
        turn.turn_id = f"T{index}"
    return turns


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
    explicit_boundaries = 0
    in_fenced_code = False

    def flush() -> None:
        nonlocal current_role, current_lines
        if current_role and current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                turns.append(Turn(role=current_role, content=content))
        current_lines = []

    for line in lines:
        fence_marker = re.match(r"^\s*(?:```|~~~)", line)
        if in_fenced_code:
            if current_role is None:
                current_role = "unknown"
            current_lines.append(line)
            if fence_marker:
                in_fenced_code = False
            continue
        if fence_marker:
            if current_role is None:
                current_role = "unknown"
            current_lines.append(line)
            in_fenced_code = True
            continue

        if _UI_LINE.match(line.strip()):
            flush()
            turns.append(Turn(role="ui", content=line.strip()))
            current_role = None
            continue

        md_role = _match_md_role(line)
        if md_role:
            flush()
            current_role = md_role
            explicit_boundaries += 1
            continue

        inline_role, remainder = _strip_role_prefix(line)
        if inline_role:
            flush()
            current_role = inline_role
            explicit_boundaries += 1
            if remainder:
                current_lines.append(remainder)
            continue

        if current_role is None:
            # 명시적 화자가 아직 없으면 강제로 user로 확정하지 않는다.
            current_role = "unknown"

        current_lines.append(line)

    flush()

    if explicit_boundaries:
        confidence: Confidence = "high"
        warnings: list[str] = []
        if turns and turns[0].role == "unknown":
            confidence = "medium"
            warnings.append("첫 화자 라벨 앞의 구간은 역할을 확정하지 않았습니다.")
        return ParsedConversation(
            turns=_with_turn_ids(turns),
            segmentation_confidence=confidence,
            warnings=warnings,
        )

    # 라벨 없음: 빈 줄 기준 교대는 구조 추정일 뿐이므로 낮은 신뢰도로 표시한다.
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) >= 2:
        alt_turns = [
            Turn(role="user" if i % 2 == 0 else "assistant", content=block)
            for i, block in enumerate(blocks)
        ]
        return ParsedConversation(
            turns=_with_turn_ids(alt_turns),
            segmentation_confidence="low",
            warnings=["화자 라벨이 없어 빈 줄 기준 교대 대화로 추정했습니다."],
        )

    return ParsedConversation(
        turns=_with_turn_ids([Turn(role="user", content=text)]),
        segmentation_confidence="low",
        warnings=["화자 라벨이 없어 전체 입력을 사용자 발화로 추정했습니다."],
    )

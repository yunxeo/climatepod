"""Grooo v0.1 기준·가중치와 보수적 규칙 기반 fallback 평가.

Claude·Gemini 구조화 평가기도 이 모듈의 기준과 점수 계산 함수를 공유한다.
외부 평가기가 설정되지 않았거나 호출·검증에 실패하면 이 모듈의 규칙 기반
예비 평가를 사용한다.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Literal

from .parser import ParsedConversation, Turn
from .tokens import TokenEstimate

CategoryId = Literal[
    "prompt_readiness",
    "response_effectiveness",
    "interaction_efficiency",
]


@dataclass(frozen=True)
class CriterionDefinition:
    criterion_id: str
    category: CategoryId
    label: str
    weight: int
    question: str


CRITERIA_VERSION = "0.1"

CRITERIA: tuple[CriterionDefinition, ...] = (
    CriterionDefinition("P1", "prompt_readiness", "목표 명확성", 7, "무엇을 만들어야 하는지 분명한가"),
    CriterionDefinition("P2", "prompt_readiness", "문맥 충분성", 6, "필요한 자료, 배경, 대상이 제공됐는가"),
    CriterionDefinition("P3", "prompt_readiness", "범위와 제약", 5, "포함, 제외, 분량, 우선순위가 필요한 만큼 명확한가"),
    CriterionDefinition("P4", "prompt_readiness", "출력 명세", 5, "형식, 구성, 언어, 문체가 필요한 만큼 정의됐는가"),
    CriterionDefinition("P5", "prompt_readiness", "지시 일관성", 4, "지시끼리 또는 지시와 예시가 충돌하지 않는가"),
    CriterionDefinition("P6", "prompt_readiness", "입력 간결성", 3, "의미를 잃지 않고 제거할 중복이나 무관한 내용이 적은가"),
    CriterionDefinition("R1", "response_effectiveness", "목표 충족", 12, "사용자가 실제로 요청한 핵심 결과를 만들었는가"),
    CriterionDefinition("R2", "response_effectiveness", "관련성", 7, "요청과 직접 관련 없는 내용이 적은가"),
    CriterionDefinition("R3", "response_effectiveness", "완전성", 7, "요청한 필수 항목을 빠뜨리지 않았는가"),
    CriterionDefinition("R4", "response_effectiveness", "정확성·근거성", 7, "제공된 자료와 일치하며 확인 불가 내용을 단정하지 않는가"),
    CriterionDefinition("R5", "response_effectiveness", "형식 준수", 5, "요청한 길이, 형식, 언어, 문체를 지켰는가"),
    CriterionDefinition("R6", "response_effectiveness", "실행 가능성", 4, "사용자가 결과를 바로 활용하거나 다음 행동을 할 수 있는가"),
    CriterionDefinition("R7", "response_effectiveness", "출력 간결성", 3, "목표 달성에 필요하지 않은 반복과 장황함이 적은가"),
    CriterionDefinition("I1", "interaction_efficiency", "첫 응답 해결도", 8, "최초 응답이 핵심 목표를 어느 정도 해결했는가"),
    CriterionDefinition("I2", "interaction_efficiency", "후속 대화 필요성", 6, "추가 턴이 오류나 누락 때문에 발생했는가, 자연스러운 확장인가"),
    CriterionDefinition("I3", "interaction_efficiency", "입력 토큰 경제성", 4, "입력 중 결과에 기여하지 않는 부분이 많은가"),
    CriterionDefinition("I4", "interaction_efficiency", "출력 토큰 경제성", 4, "출력 중 사용자가 활용하지 않을 부분이 많은가"),
    CriterionDefinition("I5", "interaction_efficiency", "수정·회복 효율", 3, "지적 후 빠르게 바로잡았는가, 같은 오류를 반복했는가"),
)

CATEGORY_WEIGHTS: dict[CategoryId, int] = {
    "prompt_readiness": 30,
    "response_effectiveness": 45,
    "interaction_efficiency": 25,
}

CATEGORY_LABELS: dict[CategoryId, str] = {
    "prompt_readiness": "프롬프트 준비도",
    "response_effectiveness": "응답 효과성",
    "interaction_efficiency": "상호작용 효율",
}

_GOAL_MARKERS = re.compile(
    r"(?:해\s*줘|해주세요|작성|만들|분석|설명|요약|번역|수정|추천|찾아|알려|"
    r"구현|검토|비교|정리|계산|평가|원해|바라|\?)",
    re.I,
)
_CONTEXT_MARKERS = re.compile(
    r"(?:배경|맥락|대상|목적|자료|원문|아래|다음|기준|현재|사용자|상황|참고)",
    re.I,
)
_CONSTRAINT_MARKERS = re.compile(
    r"(?:포함|제외|이내|이상|이하|최대|최소|우선|금지|반드시|유지|제약|조건)",
    re.I,
)
_OUTPUT_MARKERS = re.compile(
    r"(?:표|목록|불릿|JSON|Markdown|마크다운|문단|문장|글자|분량|형식|구성|"
    r"한국어|영어|존댓말|말투|코드|파일)",
    re.I,
)
_CORRECTION_MARKERS = re.compile(
    r"(?:아니|틀렸|오류|잘못|빠졌|누락|다시|수정|고쳐|지켜|반영\s*안)",
    re.I,
)
_ACCEPT_MARKERS = re.compile(
    r"^(?:좋아|좋아요|네|응|확인|고마워|감사|완벽|됐어|됐습니다)[.! ]*$",
    re.I,
)
_WORD = re.compile(r"[A-Za-z0-9가-힣]{2,}")


@dataclass
class CriterionRating:
    criterion_id: str
    category: CategoryId
    label: str
    weight: int
    rating: int | None
    status: Literal["rated", "not_applicable"]
    evidence_turn_ids: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class EfficiencyEvaluation:
    schema_version: str
    criteria_version: str
    method: str
    analysis_confidence: Literal["high", "medium", "low"]
    limitations: list[str]
    ratings: list[CriterionRating]
    category_scores: dict[CategoryId, float | None]
    overall_score: float | None
    evaluator_model: str | None = None
    one_sentence_summary: str = ""
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _turn_ids(turns: list[Turn]) -> list[str]:
    return [turn.turn_id for turn in turns if turn.turn_id]


def _rated(
    definition: CriterionDefinition,
    rating: int,
    turns: list[Turn],
    reason: str,
) -> CriterionRating:
    return CriterionRating(
        criterion_id=definition.criterion_id,
        category=definition.category,
        label=definition.label,
        weight=definition.weight,
        rating=max(0, min(4, rating)),
        status="rated",
        evidence_turn_ids=_turn_ids(turns),
        reason=reason,
    )


def _not_applicable(
    definition: CriterionDefinition,
    reason: str,
    turns: list[Turn] | None = None,
) -> CriterionRating:
    return CriterionRating(
        criterion_id=definition.criterion_id,
        category=definition.category,
        label=definition.label,
        weight=definition.weight,
        rating=None,
        status="not_applicable",
        evidence_turn_ids=_turn_ids(turns or []),
        reason=reason,
    )


def _has_repetition(text: str) -> bool:
    chunks = [
        chunk.strip().lower()
        for chunk in re.split(r"[.!?\n]", text)
        if len(chunk.strip()) >= 20
    ]
    return len(chunks) >= 2 and len(chunks) != len(set(chunks))


def _content_overlap(user_text: str, assistant_text: str) -> float:
    user_words = set(_WORD.findall(user_text.lower()))
    assistant_words = set(_WORD.findall(assistant_text.lower()))
    if not user_words:
        return 0.0
    return len(user_words & assistant_words) / len(user_words)


def _is_simple_request(user_turns: list[Turn]) -> bool:
    text = "\n".join(turn.content for turn in user_turns)
    return len(user_turns) == 1 and len(text) <= 180


def _definitions() -> dict[str, CriterionDefinition]:
    return {definition.criterion_id: definition for definition in CRITERIA}


def _evaluate_ratings(
    conversation: ParsedConversation,
    tokens: TokenEstimate,
) -> list[CriterionRating]:
    definitions = _definitions()
    user_turns = [turn for turn in conversation.turns if turn.role == "user"]
    assistant_turns = [turn for turn in conversation.turns if turn.role == "assistant"]
    user_text = "\n".join(turn.content for turn in user_turns)
    assistant_text = "\n".join(turn.content for turn in assistant_turns)
    simple_request = _is_simple_request(user_turns)
    has_constraints = bool(_CONSTRAINT_MARKERS.search(user_text))
    has_output_contract = bool(_OUTPUT_MARKERS.search(user_text))
    correction_turns = [
        turn for turn in user_turns[1:] if _CORRECTION_MARKERS.search(turn.content)
    ]
    accepted_turns = [
        turn for turn in user_turns[1:] if _ACCEPT_MARKERS.match(turn.content.strip())
    ]

    ratings: list[CriterionRating] = []

    if not user_turns:
        for criterion_id in ("P1", "P2", "P3", "P4", "P5", "P6"):
            ratings.append(
                _not_applicable(
                    definitions[criterion_id],
                    "사용자 요청이 없어 프롬프트를 평가할 수 없습니다.",
                )
            )
    else:
        goal_rating = 4 if _GOAL_MARKERS.search(user_text) else 2
        ratings.append(
            _rated(
                definitions["P1"],
                goal_rating,
                [user_turns[0]],
                "요청 동작과 원하는 결과가 명시되어 있습니다."
                if goal_rating == 4
                else "요청의 대상은 보이지만 원하는 결과가 암시적으로 표현되어 있습니다.",
            )
        )

        if simple_request:
            context_rating = 4
            context_reason = "단순 요청을 수행하는 데 추가 배경이 필요하지 않습니다."
        elif _CONTEXT_MARKERS.search(user_text) or len(user_text) >= 300:
            context_rating = 3
            context_reason = "작업에 사용할 배경이나 자료가 포함되어 있습니다."
        else:
            context_rating = 2
            context_reason = "복합 요청에 필요한 대상이나 배경을 조금 더 구체화할 수 있습니다."
        ratings.append(
            _rated(definitions["P2"], context_rating, user_turns, context_reason)
        )

        if has_constraints:
            ratings.append(
                _rated(
                    definitions["P3"],
                    4,
                    user_turns,
                    "범위 또는 제약 조건이 명시되어 있습니다.",
                )
            )
        elif simple_request:
            ratings.append(
                _not_applicable(
                    definitions["P3"],
                    "단순 요청이라 별도 범위나 제약이 필요하지 않습니다.",
                    user_turns,
                )
            )
        else:
            ratings.append(
                _rated(
                    definitions["P3"],
                    2,
                    user_turns,
                    "복합 요청의 포함 범위나 우선순위가 명시적이지 않습니다.",
                )
            )

        if has_output_contract:
            ratings.append(
                _rated(
                    definitions["P4"],
                    4,
                    user_turns,
                    "결과의 형식, 분량, 언어 또는 파일 형태가 명시되어 있습니다.",
                )
            )
        elif simple_request:
            ratings.append(
                _not_applicable(
                    definitions["P4"],
                    "단순 요청이라 별도 출력 계약이 필요하지 않습니다.",
                    user_turns,
                )
            )
        else:
            ratings.append(
                _rated(
                    definitions["P4"],
                    2,
                    user_turns,
                    "바로 사용할 결과물의 형식이나 구성을 더 명확히 지정할 수 있습니다.",
                )
            )

        ratings.append(
            _rated(
                definitions["P5"],
                3,
                user_turns,
                "규칙 기반 검사에서 명시적인 지시 충돌은 발견되지 않았습니다.",
            )
        )

        if _has_repetition(user_text) or len(user_text) >= 3000:
            p6_rating = 2
            p6_reason = "중복되거나 매우 긴 입력 구간을 정리할 여지가 있습니다."
        else:
            p6_rating = 4 if len(user_text) <= 1000 else 3
            p6_reason = "결과에 직접 기여하지 않는 뚜렷한 반복이 발견되지 않았습니다."
        ratings.append(
            _rated(definitions["P6"], p6_rating, user_turns, p6_reason)
        )

    if not assistant_turns:
        for criterion_id in ("R1", "R2", "R3", "R4", "R5", "R6", "R7"):
            ratings.append(
                _not_applicable(
                    definitions[criterion_id],
                    "AI 응답이 없어 응답 효과성을 평가할 수 없습니다.",
                )
            )
    else:
        first_answer = assistant_turns[0]
        if len(first_answer.content.strip()) < 20 and len(user_text) > 80:
            r1_rating = 2
            r1_reason = "요청에 비해 첫 응답이 매우 짧아 핵심 결과의 충족 여부가 제한적입니다."
        else:
            r1_rating = 3
            r1_reason = "첫 응답이 요청에 대응하는 결과를 제공하고 있습니다."
        ratings.append(
            _rated(definitions["R1"], r1_rating, user_turns[:1] + [first_answer], r1_reason)
        )

        overlap = _content_overlap(user_text, assistant_text)
        if overlap >= 0.15 or simple_request:
            r2_rating = 3
            r2_reason = "응답이 요청의 주요 대상과 직접 연결되어 있습니다."
        else:
            r2_rating = 2
            r2_reason = "응답과 요청의 핵심 표현 연결이 약해 관련성을 추가 확인해야 합니다."
        ratings.append(
            _rated(definitions["R2"], r2_rating, user_turns + assistant_turns, r2_reason)
        )

        r3_rating = 2 if len(assistant_text) < 60 and len(user_text) > 300 else 3
        ratings.append(
            _rated(
                definitions["R3"],
                r3_rating,
                user_turns + assistant_turns,
                "요청 대비 응답 분량을 기준으로 주요 결과가 제공되었습니다."
                if r3_rating == 3
                else "복합 요청에 비해 응답이 짧아 필수 항목 누락 가능성이 있습니다.",
            )
        )

        ratings.append(
            _not_applicable(
                definitions["R4"],
                "정답, 원자료 또는 외부 검증 결과가 없어 사실 정확성을 추정하지 않습니다.",
                user_turns + assistant_turns,
            )
        )

        if has_output_contract:
            requested_table = bool(re.search(r"표|table", user_text, re.I))
            table_present = "|" in assistant_text
            format_ok = not requested_table or table_present
            ratings.append(
                _rated(
                    definitions["R5"],
                    4 if format_ok else 2,
                    user_turns + assistant_turns,
                    "확인 가능한 출력 형식 요구를 지켰습니다."
                    if format_ok
                    else "요청한 표 형식이 응답에서 확인되지 않습니다.",
                )
            )
        else:
            ratings.append(
                _not_applicable(
                    definitions["R5"],
                    "명시된 출력 형식이 없어 형식 준수를 평가하지 않습니다.",
                    user_turns,
                )
            )

        ratings.append(
            _rated(
                definitions["R6"],
                3,
                assistant_turns,
                "사용자가 읽거나 후속 작업에 활용할 수 있는 응답이 제공되었습니다.",
            )
        )

        output_ratio = tokens.output_tokens / max(1, tokens.input_tokens)
        if _has_repetition(assistant_text) or (
            tokens.output_tokens >= 1200 and output_ratio >= 8
        ):
            r7_rating = 2
            r7_reason = "반복 또는 입력 대비 큰 출력량을 정리할 여지가 있습니다."
        else:
            r7_rating = 3
            r7_reason = "뚜렷한 반복이나 과도한 출력 구간이 발견되지 않았습니다."
        ratings.append(
            _rated(definitions["R7"], r7_rating, assistant_turns, r7_reason)
        )

    if not assistant_turns:
        ratings.append(
            _not_applicable(
                definitions["I1"],
                "첫 AI 응답이 없어 해결도를 평가할 수 없습니다.",
            )
        )
    else:
        ratings.append(
            _rated(
                definitions["I1"],
                2 if correction_turns else 3,
                [user_turns[0], assistant_turns[0]] if user_turns else assistant_turns[:1],
                "후속 오류 수정 요청이 있어 첫 응답 해결도를 보수적으로 평가했습니다."
                if correction_turns
                else "첫 응답이 핵심 요청에 대응했지만 후속 발화 부재를 성공 증거로 사용하지 않았습니다.",
            )
        )

    if len(user_turns) <= 1:
        ratings.append(
            _not_applicable(
                definitions["I2"],
                "후속 사용자 발화가 없어 추가 대화의 필요성을 판단할 수 없습니다.",
                user_turns,
            )
        )
    elif correction_turns:
        ratings.append(
            _rated(
                definitions["I2"],
                2,
                correction_turns,
                "오류·누락 수정으로 보이는 후속 발화가 확인됩니다.",
            )
        )
    else:
        ratings.append(
            _rated(
                definitions["I2"],
                3,
                user_turns[1:],
                "후속 발화가 확인되지만 규칙 기반 분석으로는 응답 실패라고 단정하지 않습니다.",
            )
        )

    p6 = next(rating for rating in ratings if rating.criterion_id == "P6")
    ratings.append(
        CriterionRating(
            criterion_id="I3",
            category=definitions["I3"].category,
            label=definitions["I3"].label,
            weight=definitions["I3"].weight,
            rating=p6.rating,
            status=p6.status,
            evidence_turn_ids=p6.evidence_turn_ids,
            reason="입력 간결성의 코드 측정 결과를 토큰 경제성에 동일하게 반영했습니다.",
        )
    )

    if not assistant_turns:
        ratings.append(
            _not_applicable(
                definitions["I4"],
                "AI 출력이 없어 출력 토큰 경제성을 평가할 수 없습니다.",
            )
        )
    else:
        r7 = next(rating for rating in ratings if rating.criterion_id == "R7")
        ratings.append(
            CriterionRating(
                criterion_id="I4",
                category=definitions["I4"].category,
                label=definitions["I4"].label,
                weight=definitions["I4"].weight,
                rating=r7.rating,
                status=r7.status,
                evidence_turn_ids=r7.evidence_turn_ids,
                reason="출력 간결성의 코드 측정 결과를 토큰 경제성에 동일하게 반영했습니다.",
            )
        )

    if not correction_turns:
        ratings.append(
            _not_applicable(
                definitions["I5"],
                "명시적인 오류 수정 발화가 없어 회복 효율을 평가하지 않습니다.",
                accepted_turns,
            )
        )
    else:
        ratings.append(
            _rated(
                definitions["I5"],
                3 if len(assistant_turns) >= 2 else 2,
                correction_turns + assistant_turns[1:],
                "수정 요청 이후 응답 여부를 기준으로 회복 과정을 평가했습니다.",
            )
        )

    return ratings


def compute_weighted_scores(
    ratings: list[CriterionRating],
) -> dict[CategoryId, float | None]:
    """적용 가능한 항목만 사용해 영역별 가중치를 재정규화한다."""
    scores: dict[CategoryId, float | None] = {}
    for category in CATEGORY_WEIGHTS:
        applicable = [
            rating
            for rating in ratings
            if rating.category == category
            and rating.status == "rated"
            and rating.rating is not None
        ]
        weight_sum = sum(rating.weight for rating in applicable)
        if not weight_sum:
            scores[category] = None
            continue
        weighted = sum(
            rating.weight * (rating.rating or 0) / 4 for rating in applicable
        )
        scores[category] = round(100 * weighted / weight_sum, 1)
    return scores


def compute_overall_score(
    category_scores: dict[CategoryId, float | None],
    *,
    allow_single_score: bool,
) -> float | None:
    """평가 가능한 영역만 재정규화하며, 신뢰도가 낮으면 단일 점수를 보류한다."""
    if not allow_single_score:
        return None
    applicable = {
        category: score
        for category, score in category_scores.items()
        if score is not None
    }
    denominator = sum(CATEGORY_WEIGHTS[category] for category in applicable)
    if not denominator:
        return None
    numerator = sum(
        CATEGORY_WEIGHTS[category] * score
        for category, score in applicable.items()
        if score is not None
    )
    return round(numerator / denominator, 1)


def evaluate_efficiency(
    conversation: ParsedConversation,
    tokens: TokenEstimate,
) -> EfficiencyEvaluation:
    ratings = _evaluate_ratings(conversation, tokens)
    category_scores = compute_weighted_scores(ratings)
    low_segmentation = conversation.segmentation_confidence == "low"
    overall_score = compute_overall_score(
        category_scores,
        allow_single_score=not low_segmentation,
    )

    limitations = [
        "규칙 기반 예비 평가이며 의미 판단용 LLM 평가를 아직 사용하지 않았습니다.",
        "외부 정답이나 원자료가 없으면 정확성·근거성은 평가하지 않습니다.",
    ]
    if low_segmentation:
        limitations.append(
            "화자 구분 신뢰도가 낮아 단일 종합 점수를 표시하지 않습니다."
        )

    return EfficiencyEvaluation(
        schema_version="0.1",
        criteria_version=CRITERIA_VERSION,
        method="deterministic_heuristic",
        analysis_confidence="low" if low_segmentation else "medium",
        limitations=limitations,
        ratings=ratings,
        category_scores=category_scores,
        overall_score=overall_score,
    )

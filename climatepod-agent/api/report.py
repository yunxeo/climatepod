"""마크다운 리포트 섹션 빌더 — 섹션 추가·순서 변경이 쉬운 구조"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from .analysis import PromptAnalysis
from .constants import TREE_KG_CO2_PER_DAY
from .ecologits import CarbonImpact
from .evaluation import (
    CATEGORY_LABELS,
    CategoryId,
    EfficiencyEvaluation,
)
from .parser import ParsedConversation
from .provider import ProviderInfo, provider_display_name
from .tokens import TokenEstimate


@dataclass
class AnalysisContext:
    conversation: ParsedConversation
    provider_info: ProviderInfo
    tokens: TokenEstimate
    prompt_analysis: PromptAnalysis
    efficiency_evaluation: EfficiencyEvaluation
    carbon: Optional[CarbonImpact] = None
    carbon_error: bool = False


class ReportSection(ABC):
    @abstractmethod
    def render(self, ctx: AnalysisContext) -> str:
        ...


def _fmt_num(value: float, digits: int = 2) -> str:
    if value >= 100:
        return f"{value:,.{digits}f}"
    if value >= 1:
        return f"{value:.{digits}f}"
    if value >= 0.01:
        return f"{value:.{digits}f}"
    return f"{value:.4f}"


def _table_cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\r\n", "<br>").replace("\n", "<br>")


_STRUCTURED_EVALUATORS = {
    "anthropic_structured": "Claude 구조화 평가",
    "gemini_structured": "Gemini 구조화 평가",
}


def _is_structured_evaluation(method: str) -> bool:
    return method in _STRUCTURED_EVALUATORS


class EnvironmentReportSection(ReportSection):
    """1. 환경 영향 리포트 (최우선)"""

    def render(self, ctx: AnalysisContext) -> str:
        if ctx.carbon_error or ctx.carbon is None:
            return (
                "## 🌱 환경 영향 리포트\n\n"
                "탄소 계산을 일시적으로 불러올 수 없어요. 잠시 후 다시 시도해주세요."
            )

        c = ctx.carbon
        energy_wh = c.energy_kwh_mid * 1000
        gwp_g = c.gwp_kg_mid * 1000
        water_ml = c.water_l_mid * 1000
        tree_days = c.gwp_kg_mid / TREE_KG_CO2_PER_DAY if TREE_KG_CO2_PER_DAY else 0
        if tree_days >= 0.01:
            tree_label = f"약 {_fmt_num(tree_days, 2)}그루"
        elif tree_days > 0:
            tree_label = f"약 {_fmt_num(tree_days, 4)}그루"
        else:
            tree_label = "미미한 수준"

        confidence = "중간"
        if ctx.provider_info.detected_from == "model_name":
            confidence = "중~높음"
        elif ctx.provider_info.detected_from == "default":
            confidence = "낮~중간"

        lines = [
            "## 🌱 환경 영향 리포트",
            "",
            "> 이번 대화의 예상 환경 영향이에요.",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| ⚡ 예상 전력 사용량 | {_fmt_num(energy_wh)} Wh |",
            f"| 🌍 예상 탄소 배출량 | {_fmt_num(gwp_g)} gCO₂e |",
            f"| 💧 예상 물 사용량 | {_fmt_num(water_ml)} mL |",
            f"| 🌳 나무 흡수량 환산 | {tree_label}가 하루 동안 흡수하는 양 |",
            "",
            f"📊 추정 신뢰도: {confidence} (토큰 추정치 + EcoLogits 모델 `{ctx.provider_info.model}` 기반)",
            "",
            "*EcoLogits 기반 추정치(Estimate)입니다. 실제 값은 조건에 따라 달라질 수 있어요.*",
        ]

        if c.warnings:
            lines.append("")
            lines.append("참고: EcoLogits 경고 — " + "; ".join(c.warnings[:2]))

        return "\n".join(lines)


class ConversationStatsSection(ReportSection):
    """대화 파싱 요약"""

    def render(self, ctx: AnalysisContext) -> str:
        conv = ctx.conversation
        lines = [
            "## 🔍 프롬프트 분석",
            "",
            "### 대화 구조",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| 총 턴 수 | {conv.total_turns} |",
            f"| 전체 분리 구간 | {conv.total_segments} |",
            f"| 사용자 발화 수 | {conv.user_turn_count} |",
            f"| AI 발화 수 | {conv.assistant_turn_count} |",
            f"| UI 제외 구간 | {conv.ui_turn_count} |",
            f"| 역할 미확정 구간 | {conv.unknown_turn_count} |",
            f"| 화자 분리 신뢰도 | {conv.segmentation_confidence} |",
            f"| 탐지된 AI | {provider_display_name(ctx.provider_info.provider)} |",
            f"| 사용 모델 (추정) | {ctx.provider_info.model} |",
        ]
        if conv.warnings:
            lines.extend(["", "참고: " + " ".join(conv.warnings)])
        return "\n".join(lines)


class TokenAnalysisSection(ReportSection):
    """토큰 추정 결과"""

    def render(self, ctx: AnalysisContext) -> str:
        t = ctx.tokens
        pa = ctx.prompt_analysis
        lines = [
            "### 토큰 추정",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| 입력 토큰 (사용자) | {t.input_tokens:,} |",
            f"| 출력 토큰 (AI) | {t.output_tokens:,} |",
            f"| 역할 미확정 토큰 | {t.unattributed_tokens:,} |",
            f"| 전체 토큰 | {t.total_tokens:,} |",
            f"| 측정 품질 | `{t.measurement_quality}` |",
            f"| 작업 유형 | {pa.task_type} |",
            f"| 복잡도 | {pa.complexity} |",
            "",
            "토큰은 문자 기반 근사치예요. 보이는 대화 텍스트만 계산하며 숨겨진 시스템·추론 토큰은 포함하지 않아요.",
        ]
        return "\n".join(lines)


class EfficiencyScoreSection(ReportSection):
    """Grooo v0.1 평가 기준의 영역 점수와 항목별 근거."""

    _CATEGORY_ORDER: tuple[CategoryId, ...] = (
        "prompt_readiness",
        "response_effectiveness",
        "interaction_efficiency",
    )

    def render(self, ctx: AnalysisContext) -> str:
        evaluation = ctx.efficiency_evaluation
        is_structured = _is_structured_evaluation(evaluation.method)
        heading = "### AI 효율성 평가" if is_structured else "### AI 효율성 예비 평가"
        lines = [heading, ""]

        if evaluation.overall_score is None:
            lines.extend(
                [
                    "화자 분리 신뢰도가 낮아 단일 종합 점수는 표시하지 않아요.",
                    "",
                ]
            )
        else:
            score_label = "AI 효율성 점수" if is_structured else "AI 효율성 예비 점수"
            lines.extend(
                [
                    f"이번 대화의 {score_label}는 **{evaluation.overall_score:.1f}점**이에요.",
                    "",
                ]
            )
        if evaluation.one_sentence_summary:
            lines.extend([evaluation.one_sentence_summary, ""])

        lines.extend(["| 영역 | 점수 |", "|------|----:|"])
        for category in self._CATEGORY_ORDER:
            score = evaluation.category_scores[category]
            score_label = "평가 불가" if score is None else f"{score:.1f}"
            lines.append(f"| {CATEGORY_LABELS[category]} | {score_label} |")

        method_label = "규칙 기반 예비 평가"
        if is_structured:
            method_label = _STRUCTURED_EVALUATORS[evaluation.method]
            if evaluation.evaluator_model:
                method_label += f" (`{evaluation.evaluator_model}`)"

        lines.extend(
            [
                "",
                f"*분석 신뢰도: {evaluation.analysis_confidence}, 평가 방식: {method_label}*",
                "",
                "| 기준 | 평점 | 근거 발화 | 판단 |",
                "|------|----:|-----------|------|",
            ]
        )
        for rating in evaluation.ratings:
            rating_label = (
                "N/A" if rating.rating is None else f"{rating.rating}/4"
            )
            evidence = ", ".join(rating.evidence_turn_ids) or "-"
            lines.append(
                f"| {rating.criterion_id} {rating.label} | {rating_label} | "
                f"{evidence} | {_table_cell(rating.reason)} |"
            )

        lines.extend(
            [
                "",
                "정확성·근거성처럼 원자료 없이 판단할 수 없는 항목은 점수에서 제외하고, "
                "남은 항목의 가중치를 다시 계산했어요.",
            ]
        )
        if evaluation.limitations:
            lines.extend(
                [
                    "",
                    "제한사항: " + " ".join(evaluation.limitations[:2]),
                ]
            )
        return "\n".join(lines)


class PromptInsightsSection(ReportSection):
    """장점·개선점·제안"""

    def render(self, ctx: AnalysisContext) -> str:
        pa = ctx.prompt_analysis
        evaluation = ctx.efficiency_evaluation
        lines = ["### 분석 코멘트", ""]

        strengths = (
            evaluation.strengths
            if _is_structured_evaluation(evaluation.method) and evaluation.strengths
            else pa.strengths
        )
        improvements = (
            evaluation.improvements
            if _is_structured_evaluation(evaluation.method) and evaluation.improvements
            else pa.improvements
        )

        if strengths:
            lines.append("**장점**")
            for s in strengths:
                lines.append(f"- {s}")
            lines.append("")

        if improvements:
            lines.append("**개선 가능한 부분**")
            for s in improvements:
                lines.append(f"- {s}")

        return "\n".join(lines).rstrip()


class SuggestionsSection(ReportSection):
    """개선 제안 — 추후 최적화 엔진과 연동"""

    def render(self, ctx: AnalysisContext) -> str:
        pa = ctx.prompt_analysis
        if _is_structured_evaluation(ctx.efficiency_evaluation.method):
            return ""
        if not pa.suggestions:
            return ""

        lines = ["## ✨ 개선 제안", ""]
        for s in pa.suggestions:
            lines.append(f"- {s}")
        return "\n".join(lines)


class OptimizationSection(ReportSection):
    """최적화 Before/After — 추후 구현 예정"""

    def render(self, ctx: AnalysisContext) -> str:
        # 프롬프트 최적화 로직 추가 시 이 섹션에서 Before/After 비교 출력
        return ""


# 섹션 등록 순서 = 출력 순서. 항목 추가 시 이 리스트에 append.
REPORT_SECTIONS: list[ReportSection] = [
    EnvironmentReportSection(),
    ConversationStatsSection(),
    TokenAnalysisSection(),
    EfficiencyScoreSection(),
    PromptInsightsSection(),
    SuggestionsSection(),
    OptimizationSection(),
]


def build_report(ctx: AnalysisContext) -> str:
    parts: list[str] = []
    for section in REPORT_SECTIONS:
        rendered = section.render(ctx).strip()
        if rendered:
            parts.append(rendered)
    return "\n\n".join(parts)


def build_usage_guide() -> str:
    return (
        "AI 대화 내용을 **그대로 붙여넣어** 주시면 분석해 드릴게요.\n\n"
        "지원 형식 예시:\n"
        "- `User:` / `Assistant:` 라벨\n"
        "- `You:` / `ChatGPT:` (ChatGPT 내보내기)\n"
        "- `Human:` / `Claude:`\n"
        "- `사용자:` / `AI:`\n"
        "- 빈 줄로 구분된 교대 대화\n\n"
        "분석 항목: 대화 구조, 프롬프트 준비도, 응답 효과성, 상호작용 효율, "
        "토큰 추정, EcoLogits 기반 탄소발자국(한국 전력 믹스 기준)이에요."
    )

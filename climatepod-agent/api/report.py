"""마크다운 리포트 섹션 빌더 — 섹션 추가·순서 변경이 쉬운 구조"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from analysis import PromptAnalysis
from constants import TREE_KG_CO2_PER_DAY
from ecologits import CarbonImpact, EcoLogitsError
from parser import ParsedConversation
from provider import ProviderInfo, provider_display_name
from tokens import TokenEstimate


@dataclass
class AnalysisContext:
    conversation: ParsedConversation
    provider_info: ProviderInfo
    tokens: TokenEstimate
    prompt_analysis: PromptAnalysis
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
            f"| 사용자 발화 수 | {conv.user_turn_count} |",
            f"| AI 발화 수 | {conv.assistant_turn_count} |",
            f"| 탐지된 AI | {provider_display_name(ctx.provider_info.provider)} |",
            f"| 사용 모델 (추정) | {ctx.provider_info.model} |",
        ]
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
            f"| 전체 토큰 | {t.total_tokens:,} |",
            f"| 작업 유형 | {pa.task_type} |",
            f"| 복잡도 | {pa.complexity} |",
            "",
            "토큰은 OpenAI·Anthropic·Gemini 프롬프트 가이드의 문자 기반 근사 방식으로 추정했어요.",
        ]
        return "\n".join(lines)


class PromptInsightsSection(ReportSection):
    """장점·개선점·제안"""

    def render(self, ctx: AnalysisContext) -> str:
        pa = ctx.prompt_analysis
        lines = ["### 분석 코멘트", ""]

        if pa.strengths:
            lines.append("**장점**")
            for s in pa.strengths:
                lines.append(f"- {s}")
            lines.append("")

        if pa.improvements:
            lines.append("**개선 가능한 부분**")
            for s in pa.improvements:
                lines.append(f"- {s}")

        return "\n".join(lines).rstrip()


class SuggestionsSection(ReportSection):
    """개선 제안 — 추후 최적화 엔진과 연동"""

    def render(self, ctx: AnalysisContext) -> str:
        pa = ctx.prompt_analysis
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
        "분석 항목: 대화 구조, 토큰 추정, EcoLogits 기반 탄소발자국(한국 전력 믹스 기준)이에요."
    )

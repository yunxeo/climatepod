"""대화 분석 파이프라인 — 단계별 확장 지점"""

from __future__ import annotations

import logging
import os

from .analysis import analyze_prompt
from .anthropic_evaluator import (
    AnthropicEvaluationError,
    evaluate_efficiency_with_anthropic,
    is_anthropic_configured,
)
from .ecologits import EcoLogitsError, fetch_carbon_impact
from .evaluation import evaluate_efficiency
from .gemini_evaluator import (
    GeminiEvaluationError,
    evaluate_efficiency_with_gemini,
    is_gemini_configured,
)
from .parser import parse_conversation
from .provider import detect_provider
from .report import AnalysisContext, build_report, build_usage_guide
from .tokens import estimate_conversation_tokens

logger = logging.getLogger(__name__)

_EVALUATOR_PROVIDERS = {"auto", "anthropic", "gemini", "rules"}


def selected_evaluator_provider() -> str:
    """Return the configured evaluator without exposing any secret values.

    ``auto`` prefers the platform-funded Anthropic key, then an existing Gemini
    key, and finally the local deterministic evaluator.
    """

    requested = os.environ.get("EVALUATOR_PROVIDER", "auto").strip().lower() or "auto"
    if requested not in _EVALUATOR_PROVIDERS:
        logger.warning(
            "Unknown EVALUATOR_PROVIDER=%s; using rules evaluator.",
            requested,
        )
        return "rules"
    if requested != "auto":
        return requested
    if is_anthropic_configured():
        return "anthropic"
    if is_gemini_configured():
        return "gemini"
    return "rules"


def _fallback_evaluation(conversation, tokens, message: str):
    evaluation = evaluate_efficiency(conversation, tokens)
    evaluation.limitations.insert(0, message)
    return evaluation


async def analyze_conversation_text(text: str) -> str:
    conversation = parse_conversation(text)

    if not conversation.turns or (
        conversation.total_turns == 1
        and conversation.turns[0].role == "user"
        and len(conversation.turns[0].content) < 80
        and not any(
            label in text.lower()
            for label in ("user:", "assistant:", "you:", "chatgpt:", "claude:")
        )
        and "사용자" not in text
    ):
        return build_usage_guide()

    provider_info = detect_provider(text)
    tokens, _ = estimate_conversation_tokens(conversation, provider_info.provider)
    prompt_analysis = analyze_prompt(conversation, tokens, provider_info)
    evaluator_provider = selected_evaluator_provider()
    if evaluator_provider == "anthropic":
        try:
            efficiency_evaluation = await evaluate_efficiency_with_anthropic(
                conversation,
                tokens,
                provider_info,
            )
        except AnthropicEvaluationError as exc:
            logger.warning("Anthropic evaluation failed; using fallback: %s", exc)
            efficiency_evaluation = _fallback_evaluation(
                conversation,
                tokens,
                "Claude API 평가를 완료하지 못해 규칙 기반 예비 평가로 전환했습니다.",
            )
    elif evaluator_provider == "gemini":
        try:
            efficiency_evaluation = await evaluate_efficiency_with_gemini(
                conversation,
                tokens,
                provider_info,
            )
        except GeminiEvaluationError as exc:
            logger.warning("Gemini evaluation failed; using fallback: %s", exc)
            efficiency_evaluation = _fallback_evaluation(
                conversation,
                tokens,
                "Gemini API 평가를 완료하지 못해 규칙 기반 예비 평가로 전환했습니다.",
            )
    else:
        efficiency_evaluation = evaluate_efficiency(conversation, tokens)

    carbon = None
    carbon_error = False
    try:
        carbon = await fetch_carbon_impact(
            provider=provider_info.provider,
            model_name=provider_info.model,
            output_token_count=tokens.output_tokens,
        )
    except EcoLogitsError:
        carbon_error = True

    ctx = AnalysisContext(
        conversation=conversation,
        provider_info=provider_info,
        tokens=tokens,
        prompt_analysis=prompt_analysis,
        efficiency_evaluation=efficiency_evaluation,
        carbon=carbon,
        carbon_error=carbon_error,
    )
    return build_report(ctx)

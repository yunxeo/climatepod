"""대화 분석 파이프라인 — 단계별 확장 지점"""

from __future__ import annotations

from analysis import analyze_prompt
from ecologits import EcoLogitsError, fetch_carbon_impact
from parser import ParsedConversation, parse_conversation
from provider import detect_provider
from report import AnalysisContext, build_report, build_usage_guide
from tokens import estimate_conversation_tokens


async def analyze_conversation_text(text: str) -> str:
    conversation = parse_conversation(text)

    if not conversation.turns or (
        conversation.total_turns == 1
        and conversation.turns[0].role == "user"
        and len(conversation.turns[0].content) < 80
        and not any(label in text.lower() for label in ("user:", "assistant:", "you:", "chatgpt:", "claude:"))
        and "사용자" not in text
    ):
        return build_usage_guide()

    provider_info = detect_provider(text)
    tokens, _ = estimate_conversation_tokens(conversation, provider_info.provider)
    prompt_analysis = analyze_prompt(conversation, tokens, provider_info)

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
        carbon=carbon,
        carbon_error=carbon_error,
    )
    return build_report(ctx)

"""AI 프로바이더·모델 탐지"""

from __future__ import annotations

import re
from dataclasses import dataclass

from constants import DEFAULT_MODEL_BY_PROVIDER

# EcoLogits provider 식별자
ProviderId = str

_MODEL_PATTERNS: list[tuple[re.Pattern[str], ProviderId, str]] = [
    (re.compile(r"gpt-4o-mini", re.I), "openai", "gpt-4o-mini"),
    (re.compile(r"gpt-4o", re.I), "openai", "gpt-4o"),
    (re.compile(r"gpt-4-turbo", re.I), "openai", "gpt-4-turbo"),
    (re.compile(r"gpt-4(?!o)", re.I), "openai", "gpt-4"),
    (re.compile(r"gpt-3\.5-turbo", re.I), "openai", "gpt-3.5-turbo"),
    (re.compile(r"o1-mini", re.I), "openai", "o1-mini"),
    (re.compile(r"o1-preview", re.I), "openai", "o1-preview"),
    (re.compile(r"claude-opus-4-6", re.I), "anthropic", "claude-opus-4-6"),
    (re.compile(r"claude-sonnet-4-6", re.I), "anthropic", "claude-sonnet-4-6"),
    (re.compile(r"claude-sonnet-4-5", re.I), "anthropic", "claude-sonnet-4-5"),
    (re.compile(r"claude-sonnet-4", re.I), "anthropic", "claude-sonnet-4-20250514"),
    (re.compile(r"claude-opus-4", re.I), "anthropic", "claude-opus-4-20250514"),
    (re.compile(r"claude-3-5-sonnet", re.I), "anthropic", "claude-sonnet-4-20250514"),
    (re.compile(r"claude-3-5-haiku", re.I), "anthropic", "claude-haiku-4-5-20251001"),
    (re.compile(r"claude-3-opus", re.I), "anthropic", "claude-opus-4-20250514"),
    (re.compile(r"gemini-2\.5-pro", re.I), "google_genai", "gemini-2.5-pro"),
    (re.compile(r"gemini-2\.5-flash", re.I), "google_genai", "gemini-2.5-flash"),
    (re.compile(r"gemini-2\.0-flash", re.I), "google_genai", "gemini-2.0-flash"),
    (re.compile(r"gemini-1\.5-pro", re.I), "google_genai", "gemini-2.5-pro"),
    (re.compile(r"gemini-1\.5-flash", re.I), "google_genai", "gemini-2.0-flash"),
]

_PROVIDER_HINTS: list[tuple[re.Pattern[str], ProviderId]] = [
    (re.compile(r"chatgpt|openai|gpt\b", re.I), "openai"),
    (re.compile(r"claude|anthropic", re.I), "anthropic"),
    (re.compile(r"gemini|google\s*ai|bard", re.I), "google_genai"),
]


@dataclass
class ProviderInfo:
    provider: ProviderId
    model: str
    detected_from: str  # "model_name" | "provider_hint" | "default"


def detect_provider(text: str) -> ProviderInfo:
    for pattern, provider, model in _MODEL_PATTERNS:
        if pattern.search(text):
            return ProviderInfo(provider=provider, model=model, detected_from="model_name")

    for pattern, provider in _PROVIDER_HINTS:
        if pattern.search(text):
            return ProviderInfo(
                provider=provider,
                model=DEFAULT_MODEL_BY_PROVIDER[provider],
                detected_from="provider_hint",
            )

    return ProviderInfo(
        provider="openai",
        model=DEFAULT_MODEL_BY_PROVIDER["openai"],
        detected_from="default",
    )


def provider_display_name(provider: ProviderId) -> str:
    return {
        "openai": "OpenAI (ChatGPT)",
        "anthropic": "Anthropic (Claude)",
        "google_genai": "Google (Gemini)",
    }.get(provider, provider)

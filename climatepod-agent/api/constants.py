"""클라이밋팟 대화 분석 에이전트 — 상수 (팀 검수·수정용 단일 출처)"""

# --- EcoLogits API ---
ECOLOGITS_API_URL = "https://api.ecologits.ai/v1beta/estimations"
DEFAULT_REQUEST_LATENCY_SEC = 1.0  # 대화 내보내기에 지연 정보 없을 때 기본값
ELECTRICITY_MIX_ZONE = "KOR"  # ISO 3166-1 alpha-3, 한국 전력 믹스

# --- 탄소 흡수 환산 ---
TREE_KG_CO2_PER_DAY = 0.06  # 나무 1그루 하루 CO₂ 흡수량(kg) — 통용 권고 근사값

# --- 프로바이더별 EcoLogits 기본 모델 (대화에서 모델명 미탐지 시) ---
DEFAULT_MODEL_BY_PROVIDER = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "google_genai": "gemini-2.0-flash",
}

# --- 토큰 추정 계수 (프롬프트 엔지니어링 가이드 기반 근사) ---
# OpenAI: https://developers.openai.com/api/docs/guides/prompt-engineering — 영어 ~4자/토큰
# Anthropic: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview — 유사 토큰화
# Google Gemini: https://ai.google.dev/gemini-api/docs/prompting-strategies — 유사 토큰화
TOKEN_ESTIMATION = {
    "openai": {
        "latin_chars_per_token": 4.0,
        "cjk_chars_per_token": 1.8,
        "other_chars_per_token": 3.0,
    },
    "anthropic": {
        "latin_chars_per_token": 3.8,
        "cjk_chars_per_token": 1.7,
        "other_chars_per_token": 3.0,
    },
    "google_genai": {
        "latin_chars_per_token": 4.0,
        "cjk_chars_per_token": 1.9,
        "other_chars_per_token": 3.0,
    },
}

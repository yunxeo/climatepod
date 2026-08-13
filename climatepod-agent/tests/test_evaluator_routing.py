import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

from api.anthropic_evaluator import AnthropicEvaluationError
from api.evaluation import evaluate_efficiency
from api.pipeline import analyze_conversation_text, selected_evaluator_provider


class EvaluatorRoutingTests(unittest.TestCase):
    conversation = (
        "User: 아래 대화를 분석하고 효율성을 평가해주세요. 목표와 제약, 출력 형식을 모두 확인해주세요.\n"
        "Assistant: 요청한 목표와 제약, 출력 형식을 확인해 분석 결과를 제공합니다."
    )

    def test_auto_prefers_anthropic_then_gemini_then_rules(self):
        scenarios = [
            (
                {"ANTHROPIC_API_KEY": "claude-key", "GEMINI_API_KEY": "gemini-key"},
                "anthropic",
            ),
            ({"GEMINI_API_KEY": "gemini-key"}, "gemini"),
            ({}, "rules"),
        ]

        for environment, expected in scenarios:
            with (
                self.subTest(expected=expected),
                patch.dict(
                    os.environ,
                    environment,
                    clear=True,
                ),
            ):
                self.assertEqual(expected, selected_evaluator_provider())

    def test_explicit_provider_overrides_auto_detection(self):
        with patch.dict(
            os.environ,
            {
                "EVALUATOR_PROVIDER": "rules",
                "ANTHROPIC_API_KEY": "claude-key",
                "GEMINI_API_KEY": "gemini-key",
            },
            clear=True,
        ):
            self.assertEqual("rules", selected_evaluator_provider())

    def test_invalid_provider_fails_safe_to_rules(self):
        with patch.dict(
            os.environ,
            {"EVALUATOR_PROVIDER": "unknown-provider"},
            clear=True,
        ):
            self.assertEqual("rules", selected_evaluator_provider())

    def test_anthropic_failure_falls_back_to_local_evaluation(self):
        with (
            patch.dict(
                os.environ,
                {"EVALUATOR_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "test-key"},
                clear=True,
            ),
            patch(
                "api.pipeline.evaluate_efficiency_with_anthropic",
                new=AsyncMock(side_effect=AnthropicEvaluationError("test failure")),
            ),
            patch("api.pipeline.fetch_carbon_impact", new=AsyncMock(return_value=None)),
        ):
            report = asyncio.run(analyze_conversation_text(self.conversation))

        self.assertIn(
            "Claude API 평가를 완료하지 못해 규칙 기반 예비 평가로 전환했습니다.",
            report,
        )
        self.assertIn("AI 효율성 예비 평가", report)

    def test_anthropic_success_is_rendered_as_structured_evaluation(self):
        async def structured_evaluation(conversation, tokens, provider_info):
            evaluation = evaluate_efficiency(conversation, tokens)
            evaluation.method = "anthropic_structured"
            evaluation.evaluator_model = "claude-test"
            evaluation.strengths = ["목표가 명확합니다."]
            evaluation.improvements = ["출력 형식을 더 구체화할 수 있습니다."]
            return evaluation

        with (
            patch.dict(
                os.environ,
                {"EVALUATOR_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "test-key"},
                clear=True,
            ),
            patch(
                "api.pipeline.evaluate_efficiency_with_anthropic",
                new=AsyncMock(side_effect=structured_evaluation),
            ),
            patch("api.pipeline.fetch_carbon_impact", new=AsyncMock(return_value=None)),
        ):
            report = asyncio.run(analyze_conversation_text(self.conversation))

        self.assertIn("### AI 효율성 평가", report)
        self.assertNotIn("### AI 효율성 예비 평가", report)
        self.assertIn("Claude 구조화 평가 (`claude-test`)", report)


if __name__ == "__main__":
    unittest.main()

import asyncio
import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from api.anthropic_evaluator import (
    DEFAULT_ANTHROPIC_MODEL,
    AnthropicCriterionRating,
    AnthropicEvaluationError,
    AnthropicEvaluationPayload,
    _build_prompt,
    _call_anthropic,
    _create_anthropic_client,
    _model_validate_json,
    _validate_and_convert,
    configured_anthropic_model,
    is_anthropic_configured,
)
from api.evaluation import CRITERIA
from api.parser import parse_conversation
from api.provider import detect_provider
from api.tokens import estimate_conversation_tokens


class _FakeMessages:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.kwargs = None

    async def parse(self, **kwargs):
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.response


class _FakeClient:
    def __init__(self, messages):
        self.messages = messages
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.closed = True


class AnthropicEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.conversation = parse_conversation(
            "User: 세 문장으로 요약해주세요.\nAssistant: 요약 결과입니다."
        )
        self.tokens, _ = estimate_conversation_tokens(self.conversation, "openai")

    def _payload(self) -> AnthropicEvaluationPayload:
        ratings = []
        for criterion in CRITERIA:
            if criterion.criterion_id == "R4":
                ratings.append(
                    AnthropicCriterionRating(
                        criterion_id="R4",
                        rating=None,
                        status="not_applicable",
                        evidence_turn_ids=["T1", "T2"],
                        reason="외부 정답이 없습니다.",
                    )
                )
            else:
                ratings.append(
                    AnthropicCriterionRating(
                        criterion_id=criterion.criterion_id,
                        rating=3,
                        status="rated",
                        evidence_turn_ids=["T1"],
                        reason="근거가 확인됩니다.",
                    )
                )
        return AnthropicEvaluationPayload(
            analysis_confidence="medium",
            ratings=ratings,
            one_sentence_summary="요청과 응답이 대체로 연결되어 있습니다.",
            strengths=["목표가 명확합니다."],
            improvements=["출력 형식을 더 구체화할 수 있습니다."],
            limitations=["외부 사실은 검증하지 않았습니다."],
        )

    def test_environment_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(is_anthropic_configured())
            self.assertEqual(DEFAULT_ANTHROPIC_MODEL, configured_anthropic_model())

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "   "}, clear=True):
            self.assertFalse(is_anthropic_configured())

        with patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "test-key", "ANTHROPIC_MODEL": " custom-model "},
            clear=True,
        ):
            self.assertTrue(is_anthropic_configured())
            self.assertEqual("custom-model", configured_anthropic_model())

    def test_client_has_bounded_timeout_and_retries(self):
        captured = {}

        class FakeAsyncAnthropic:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        fake_module = types.ModuleType("anthropic")
        fake_module.AsyncAnthropic = FakeAsyncAnthropic
        with patch.dict(sys.modules, {"anthropic": fake_module}):
            _create_anthropic_client("test-key")

        self.assertEqual(
            {"api_key": "test-key", "timeout": 30.0, "max_retries": 1},
            captured,
        )

    def test_structured_payload_is_validated_and_scored(self):
        evaluation = _validate_and_convert(
            self._payload(),
            self.conversation,
            model="claude-test",
        )

        self.assertEqual("anthropic_structured", evaluation.method)
        self.assertEqual("claude-test", evaluation.evaluator_model)
        self.assertIsNotNone(evaluation.overall_score)
        self.assertEqual(18, len(evaluation.ratings))
        self.assertEqual(1, len(evaluation.improvements))

    def test_invalid_evidence_turn_is_rejected(self):
        payload = self._payload()
        payload.ratings[0].evidence_turn_ids = ["T999"]

        with self.assertRaises(AnthropicEvaluationError):
            _validate_and_convert(payload, self.conversation, model="claude-test")

    def test_contradictory_status_and_rating_are_normalized(self):
        payload = self._payload()
        payload.ratings[0].status = "rated"
        payload.ratings[0].rating = None
        payload.ratings[1].status = "not_applicable"
        payload.ratings[1].rating = 3
        payload.ratings[1].evidence_turn_ids = ["T1"]

        evaluation = _validate_and_convert(
            payload, self.conversation, model="claude-test"
        )

        self.assertEqual("not_applicable", evaluation.ratings[0].status)
        self.assertIsNone(evaluation.ratings[0].rating)
        self.assertEqual("rated", evaluation.ratings[1].status)
        self.assertEqual(3, evaluation.ratings[1].rating)

    def test_duplicate_and_missing_criteria_are_rejected(self):
        duplicate = self._payload()
        duplicate.ratings[-1].criterion_id = duplicate.ratings[0].criterion_id
        with self.assertRaises(AnthropicEvaluationError):
            _validate_and_convert(duplicate, self.conversation, model="claude-test")

        missing = self._payload()
        missing.ratings.pop()
        with self.assertRaises(AnthropicEvaluationError):
            _validate_and_convert(missing, self.conversation, model="claude-test")

    def test_invalid_json_is_wrapped_in_anthropic_error(self):
        with self.assertRaises(AnthropicEvaluationError):
            _model_validate_json("not-json")

    def test_prompt_contains_criteria_measurements_and_untrusted_transcript(self):
        prompt = _build_prompt(
            self.conversation,
            self.tokens,
            detect_provider("ChatGPT"),
        )

        self.assertIn('"criterion_id": "P1"', prompt)
        self.assertIn('"measurement_quality": "generic_estimate"', prompt)
        self.assertIn("<normalized_transcript_untrusted>", prompt)
        self.assertNotIn("ANTHROPIC_API_KEY", prompt)

    def test_call_uses_structured_output_without_network(self):
        messages = _FakeMessages(
            response=SimpleNamespace(
                parsed_output=self._payload(),
                stop_reason="end_turn",
            )
        )
        client = _FakeClient(messages)
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True),
            patch(
                "api.anthropic_evaluator._create_anthropic_client",
                return_value=client,
            ),
        ):
            result = asyncio.run(
                _call_anthropic(model="claude-test", prompt="test prompt")
            )

        self.assertIsInstance(result, AnthropicEvaluationPayload)
        self.assertEqual("claude-test", messages.kwargs["model"])
        self.assertEqual(8192, messages.kwargs["max_tokens"])
        self.assertIs(
            AnthropicEvaluationPayload,
            messages.kwargs["output_format"],
        )
        self.assertTrue(client.closed)

    def test_api_and_response_failures_are_wrapped(self):
        scenarios = [
            _FakeMessages(error=ValueError("network failure")),
            _FakeMessages(
                response=SimpleNamespace(parsed_output=None, stop_reason="refusal")
            ),
            _FakeMessages(
                response=SimpleNamespace(parsed_output=None, stop_reason="max_tokens")
            ),
            _FakeMessages(
                response=SimpleNamespace(parsed_output=None, stop_reason="end_turn")
            ),
            _FakeMessages(
                response=SimpleNamespace(
                    parsed_output={"analysis_confidence": "invalid"},
                    stop_reason="end_turn",
                )
            ),
        ]

        for messages in scenarios:
            with (
                self.subTest(messages=messages),
                patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True),
                patch(
                    "api.anthropic_evaluator._create_anthropic_client",
                    return_value=_FakeClient(messages),
                ),
                self.assertRaises(AnthropicEvaluationError),
            ):
                asyncio.run(_call_anthropic(model="claude-test", prompt="test prompt"))


if __name__ == "__main__":
    unittest.main()

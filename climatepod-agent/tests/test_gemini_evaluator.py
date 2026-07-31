import unittest

from api.evaluation import CRITERIA
from api.gemini_evaluator import (
    GeminiCriterionRating,
    GeminiEvaluationError,
    GeminiEvaluationPayload,
    _build_prompt,
    _validate_and_convert,
)
from api.parser import parse_conversation
from api.provider import detect_provider
from api.tokens import estimate_conversation_tokens


class GeminiEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.conversation = parse_conversation(
            "User: 세 문장으로 요약해주세요.\nAssistant: 요약 결과입니다."
        )
        self.tokens, _ = estimate_conversation_tokens(self.conversation, "openai")

    def _payload(self) -> GeminiEvaluationPayload:
        ratings = []
        for criterion in CRITERIA:
            if criterion.criterion_id == "R4":
                ratings.append(
                    GeminiCriterionRating(
                        criterion_id="R4",
                        rating=None,
                        status="not_applicable",
                        evidence_turn_ids=["T1", "T2"],
                        reason="외부 정답이 없습니다.",
                    )
                )
            else:
                ratings.append(
                    GeminiCriterionRating(
                        criterion_id=criterion.criterion_id,
                        rating=3,
                        status="rated",
                        evidence_turn_ids=["T1"],
                        reason="근거가 확인됩니다.",
                    )
                )
        return GeminiEvaluationPayload(
            analysis_confidence="medium",
            ratings=ratings,
            one_sentence_summary="요청과 응답이 대체로 연결되어 있습니다.",
            strengths=["목표가 명확합니다."],
            improvements=["출력 형식을 더 구체화할 수 있습니다."],
            limitations=["외부 사실은 검증하지 않았습니다."],
        )

    def test_structured_payload_is_validated_and_scored(self):
        evaluation = _validate_and_convert(
            self._payload(),
            self.conversation,
            model="gemini-test",
        )

        self.assertEqual("gemini_structured", evaluation.method)
        self.assertEqual("gemini-test", evaluation.evaluator_model)
        self.assertIsNotNone(evaluation.overall_score)
        self.assertEqual(18, len(evaluation.ratings))
        self.assertEqual(1, len(evaluation.improvements))

    def test_invalid_evidence_turn_is_rejected(self):
        payload = self._payload()
        payload.ratings[0].evidence_turn_ids = ["T999"]

        with self.assertRaises(GeminiEvaluationError):
            _validate_and_convert(payload, self.conversation, model="gemini-test")

    def test_prompt_contains_criteria_measurements_and_untrusted_transcript(self):
        prompt = _build_prompt(
            self.conversation,
            self.tokens,
            detect_provider("ChatGPT"),
        )

        self.assertIn('"criterion_id": "P1"', prompt)
        self.assertIn('"measurement_quality": "generic_estimate"', prompt)
        self.assertIn("<normalized_transcript_untrusted>", prompt)
        self.assertNotIn("GEMINI_API_KEY", prompt)


if __name__ == "__main__":
    unittest.main()

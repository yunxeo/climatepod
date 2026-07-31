import unittest

from api.evaluation import CRITERIA, evaluate_efficiency
from api.parser import parse_conversation
from api.tokens import estimate_conversation_tokens


class EvaluationTests(unittest.TestCase):
    def _evaluate(self, text: str):
        conversation = parse_conversation(text)
        tokens, _ = estimate_conversation_tokens(conversation, "openai")
        return evaluate_efficiency(conversation, tokens)

    def test_all_criteria_are_returned_with_evidence_status(self):
        evaluation = self._evaluate(
            "User: 아래 자료를 세 문장 표로 요약해주세요.\n"
            "Assistant: | 요약 |\n|---|\n| 첫 번째 내용입니다. |"
        )

        self.assertEqual(len(CRITERIA), len(evaluation.ratings))
        self.assertIsNotNone(evaluation.overall_score)
        self.assertTrue(
            all(
                rating.status == "not_applicable" or rating.evidence_turn_ids
                for rating in evaluation.ratings
            )
        )

    def test_correctness_is_not_scored_without_reference_evidence(self):
        evaluation = self._evaluate(
            "User: 한국의 수도는 어디인가요?\nAssistant: 서울입니다."
        )
        r4 = next(rating for rating in evaluation.ratings if rating.criterion_id == "R4")

        self.assertEqual("not_applicable", r4.status)
        self.assertIsNone(r4.rating)

    def test_low_segmentation_confidence_withholds_overall_score(self):
        evaluation = self._evaluate("세 문장으로 요약해줘\n\n요약 결과입니다.")

        self.assertIsNone(evaluation.overall_score)
        self.assertEqual("low", evaluation.analysis_confidence)

    def test_prompt_only_excludes_response_categories(self):
        evaluation = self._evaluate("User: 이 문서를 세 문장으로 요약해주세요.")

        self.assertIsNotNone(evaluation.category_scores["prompt_readiness"])
        self.assertIsNone(evaluation.category_scores["response_effectiveness"])


if __name__ == "__main__":
    unittest.main()

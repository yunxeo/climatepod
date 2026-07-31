import unittest

from api.parser import parse_conversation


class ParserTests(unittest.TestCase):
    def test_explicit_labels_create_evidence_ids_and_high_confidence(self):
        conversation = parse_conversation(
            "User: 아래 내용을 표로 정리해주세요.\n"
            "Assistant: | 항목 | 값 |\n|---|---|\n| A | 1 |"
        )

        self.assertEqual(["user", "assistant"], [turn.role for turn in conversation.turns])
        self.assertEqual(["T1", "T2"], [turn.turn_id for turn in conversation.turns])
        self.assertEqual("high", conversation.segmentation_confidence)

    def test_unlabeled_blocks_are_low_confidence(self):
        conversation = parse_conversation("요약해줘\n\n요약 결과입니다.")

        self.assertEqual(["user", "assistant"], [turn.role for turn in conversation.turns])
        self.assertEqual("low", conversation.segmentation_confidence)
        self.assertTrue(conversation.warnings)

    def test_ui_line_is_excluded_as_its_own_turn(self):
        conversation = parse_conversation(
            "User: 요약해줘\nAssistant: 요약입니다.\n복사\nUser: 고마워"
        )

        self.assertEqual(
            ["user", "assistant", "ui", "user"],
            [turn.role for turn in conversation.turns],
        )
        self.assertEqual(1, conversation.ui_turn_count)

    def test_role_labels_inside_code_fence_do_not_create_turns(self):
        conversation = parse_conversation(
            "User: 다음 코드 예시를 검토해줘.\n"
            "```text\nUser: example\nAssistant: example answer\n```\n"
            "Assistant: 검토 결과입니다."
        )

        self.assertEqual(["user", "assistant"], [turn.role for turn in conversation.turns])
        self.assertIn("Assistant: example answer", conversation.turns[0].content)


if __name__ == "__main__":
    unittest.main()

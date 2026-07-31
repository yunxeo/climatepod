import unittest

from api.parser import parse_conversation
from api.tokens import estimate_conversation_tokens


class TokenTests(unittest.TestCase):
    def test_ui_tokens_are_excluded_and_quality_is_explicit(self):
        conversation = parse_conversation(
            "User: 요약해줘\nAssistant: 요약입니다.\n복사"
        )
        tokens, per_turn = estimate_conversation_tokens(conversation, "openai")

        self.assertEqual(2, len(per_turn))
        self.assertGreater(tokens.input_tokens, 0)
        self.assertGreater(tokens.output_tokens, 0)
        self.assertEqual("generic_estimate", tokens.measurement_quality)
        self.assertFalse(tokens.hidden_or_system_tokens_included)


if __name__ == "__main__":
    unittest.main()

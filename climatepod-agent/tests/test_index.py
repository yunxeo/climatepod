import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from api.index import ChatRequest, chat, sanitize_output


class IndexTests(unittest.TestCase):
    def test_sanitize_output_removes_disallowed_markup(self):
        cleaned = sanitize_output(
            "앞 ![image](data:image/png;base64,abc) <b>내용</b> [로컬](file.txt) 뒤"
        )

        self.assertNotIn("data:", cleaned)
        self.assertNotIn("<b>", cleaned)
        self.assertNotIn("file.txt", cleaned)
        self.assertIn("로컬", cleaned)

    def test_chat_keeps_sse_contract(self):
        async def run_chat() -> str:
            with patch(
                "api.index.generate_answer",
                new=AsyncMock(return_value="<b>분석 결과</b>"),
            ):
                response = await chat(
                    ChatRequest(message="테스트"),
                    authorization=None,
                    x_api_key=None,
                )
                chunks = []
                async for chunk in response.body_iterator:
                    chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
                return "".join(chunks)

        body = asyncio.run(run_chat())
        self.assertIn('data: {"content": "분석 결과"}', body)
        self.assertTrue(body.endswith("data: [DONE]\n\n"))


if __name__ == "__main__":
    unittest.main()

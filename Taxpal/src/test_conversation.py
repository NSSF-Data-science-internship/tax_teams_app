import unittest
from unittest.mock import patch

from conversation import run_conversation_turn


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_greeting_does_not_retrieve(self):
        result = await run_conversation_turn("Hello", history=[])

        self.assertFalse(result["retrieval_used"])
        self.assertEqual(result["documents"], [])
        self.assertIn("TaxPal", result["answer"])

    async def test_explanation_reuses_previous_evidence(self):
        documents = [
            {
                "text": "VAT is charged at 18%.",
                "metadata": {"title": "VAT Act"},
            }
        ]
        history = [
            {"role": "user", "content": "What is the VAT rate?"},
            {
                "role": "assistant",
                "content": "The standard rate is 18%.",
                "documents": documents,
            },
        ]

        with patch(
            "conversation.answer_tax_question",
            return_value="VAT is 18% in simpler terms.",
        ):
            result = await run_conversation_turn(
                "Explain that more simply",
                history=history,
            )

        self.assertTrue(result["retrieval_reused"])
        self.assertFalse(result["retrieval_used"])
        self.assertEqual(result["documents"], documents)
        async def test_calculation_request_is_detected(self):
                with patch(
                    "conversation.answer_tax_question",
                    return_value="Calculation test",
                ):
                    with patch(
                        "conversation.search_tax_law",
                        return_value=[],
                    ):
                        result = await run_conversation_turn(
                            "Calculate VAT on 1,000,000",
                            history=[],
                        )
        
                self.assertTrue(
                    result["calculation_requested"]
                )


if __name__ == "__main__":
    unittest.main()

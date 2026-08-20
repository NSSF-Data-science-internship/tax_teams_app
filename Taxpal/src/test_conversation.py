import unittest
from unittest.mock import AsyncMock, patch

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

    async def test_vat_calculation_does_not_retrieve_or_call_llm(self):
        with patch("conversation.search_tax_law") as search, patch(
            "conversation.answer_tax_question"
        ) as answer:
            result = await run_conversation_turn(
                "Calculate VAT on UGX 1,000,000",
                history=[],
            )

        search.assert_not_called()
        answer.assert_not_called()
        self.assertTrue(result["calculator_used"])
        self.assertEqual(result["calculation"]["vat_amount"], "180000.00")

    async def test_standard_vat_rate_does_not_require_services(self):
        with patch("conversation.search_tax_law") as search, patch(
            "conversation.answer_tax_question"
        ) as answer:
            result = await run_conversation_turn(
                "What is the standard VAT rate in Uganda?", history=[]
            )
        search.assert_not_called()
        answer.assert_not_called()
        self.assertIn("18%", result["answer"])

    async def test_custom_percentage_does_not_retrieve_or_call_llm(self):
        with patch("conversation.search_tax_law") as search, patch(
            "conversation.answer_tax_question"
        ) as answer:
            result = await run_conversation_turn(
                "Calculate 6% withholding tax on UGX 500,000",
                history=[],
            )

        search.assert_not_called()
        answer.assert_not_called()
        self.assertEqual(result["calculation"]["kind"], "percentage")
        self.assertEqual(result["calculation"]["tax_amount"], "30000.00")

    async def test_paye_does_not_retrieve_or_call_llm(self):
        with patch("conversation.search_tax_law") as search, patch(
            "conversation.answer_tax_question"
        ) as answer:
            result = await run_conversation_turn(
                "Calculate PAYE for Resident on monthly chargeable income UGX 1,000,000",
                history=[],
            )

        search.assert_not_called()
        answer.assert_not_called()
        self.assertEqual(result["calculation"]["kind"], "paye")
        self.assertEqual(result["calculation"]["tax_amount"], "202000.00")

    async def test_rag_answer_has_validated_structured_citations(self):
        documents = [{
            "text": "The standard rate is 18 percent.",
            "metadata": {
                "title": "VAT guidance", "section": "Standard rate",
                "source": "URA", "url": "https://ura.go.ug/vat",
                "evidence_type": "local_document", "publication_date": "2026-01-01",
                "relevance_score": 0.9,
            },
        }]
        with patch("conversation.rewrite_question_for_retrieval", return_value="VAT rate"), patch(
            "conversation.search_tax_law", new=AsyncMock(return_value=documents)
        ), patch("conversation.answer_tax_question", return_value="The rate is 18% [S1]."):
            result = await run_conversation_turn("Explain VAT registration rules", history=[])

        self.assertEqual(result["citations"][0]["id"], "S1")
        self.assertEqual(result["evidence_assessment"]["confidence"], "high")
        self.assertIn("**Based on**", result["answer"])
        self.assertNotIn("[S1]", result["answer"])

    async def test_consented_profile_is_passed_to_generation(self):
        documents = [{"text": "Evidence", "metadata": {"title": "Guide", "relevance_score": 0.9}}]
        with patch("conversation.rewrite_question_for_retrieval", return_value="tax query"), patch(
            "conversation.search_tax_law", new=AsyncMock(return_value=documents)
        ), patch("conversation.answer_tax_question", return_value="Answer [S1].") as answer:
            await run_conversation_turn(
                "Explain this tax", history=[], user_profile={"residency": "resident"}
            )

        self.assertEqual(answer.call_args.args[3], {"residency": "resident"})


if __name__ == "__main__":
    unittest.main()

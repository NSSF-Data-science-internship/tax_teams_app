import unittest
from unittest.mock import patch

import httpx

import graph_rag_client


class GraphRagRoutingTests(unittest.TestCase):
    def test_graph_is_disabled_by_default(self):
        with patch.object(graph_rag_client, "GRAPH_RAG_ENABLED", False):
            self.assertIsNone(
                graph_rag_client.choose_graph_search_method(
                    "How does the VAT amendment affect input tax credits?"
                )
            )

    def test_relationship_question_uses_local_search(self):
        with patch.object(graph_rag_client, "GRAPH_RAG_ENABLED", True), patch.object(
            graph_rag_client, "GRAPH_RAG_MODE", "auto"
        ):
            method = graph_rag_client.choose_graph_search_method(
                "How does the VAT amendment affect input tax credits?"
            )
        self.assertEqual(method, "local")

    def test_corpus_wide_question_uses_global_search(self):
        with patch.object(graph_rag_client, "GRAPH_RAG_ENABLED", True), patch.object(
            graph_rag_client, "GRAPH_RAG_MODE", "auto"
        ):
            method = graph_rag_client.choose_graph_search_method(
                "Summarize the main changes across all Uganda tax laws"
            )
        self.assertEqual(method, "global")

    def test_direct_fact_question_stays_on_vector_search(self):
        with patch.object(graph_rag_client, "GRAPH_RAG_ENABLED", True), patch.object(
            graph_rag_client, "GRAPH_RAG_MODE", "auto"
        ):
            method = graph_rag_client.choose_graph_search_method("What is the VAT rate?")
        self.assertIsNone(method)


class GraphRagClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_service_results_use_standard_document_shape(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/search-graph")
            return httpx.Response(
                200,
                json={"results": [{"text": "Graph evidence", "metadata": {"evidence_type": "graph_rag"}}]},
            )

        results = await graph_rag_client.search_graph_rag(
            "How do the Acts relate?",
            "local",
            transport=httpx.MockTransport(handler),
        )
        self.assertEqual(results[0]["metadata"]["evidence_type"], "graph_rag")

    async def test_unavailable_index_has_a_vector_safe_error(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(503, json={"detail": "Index missing"})
        )
        with patch.object(graph_rag_client, "GRAPH_RAG_RETRIES", 1):
            with self.assertRaises(graph_rag_client.GraphRagUnavailable):
                await graph_rag_client.search_graph_rag(
                    "How do the Acts relate?", "local", transport=transport
                )


if __name__ == "__main__":
    unittest.main()

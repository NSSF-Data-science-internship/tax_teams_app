import httpx


class LangflowClient:
    """
    Handles communication between the Teams bot
    and the Langflow RAG pipeline.

    If no Flow ID is configured, the client
    automatically runs in mock mode.
    """

    def __init__(
        self,
        base_url: str,
        flow_id: str
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.flow_id = flow_id or ""

    async def ask(self, question: str) -> dict:
        """
        Send a question to Langflow.

        If the Flow ID is missing, return a mock
        development response instead.
        """

        # ---------------------------------------
        # DEVELOPMENT / MOCK MODE
        # ---------------------------------------

        if not self.flow_id:
            return self._mock_response(question)

        # ---------------------------------------
        # REAL LANGFLOW MODE
        # ---------------------------------------

        url = (
            f"{self.base_url}/api/v1/run/"
            f"{self.flow_id}"
        )

        payload = {
            "input_value": question,
            "input_type": "chat",
            "output_type": "chat",
        }

        try:
            async with httpx.AsyncClient(
                timeout=60.0
            ) as client:

                response = await client.post(
                    url,
                    json=payload
                )

                response.raise_for_status()

                data = response.json()

                return self._parse_response(data)

        except httpx.TimeoutException:
            return {
                "answer": (
                    "The tax information service "
                    "took too long to respond."
                ),
                "sources": []
            }

        except httpx.HTTPStatusError as error:
            print(
                "Langflow HTTP error:",
                error.response.status_code,
                error.response.text
            )

            return {
                "answer": (
                    "The tax information service "
                    "is currently unavailable."
                ),
                "sources": []
            }

        except Exception as error:
            print(
                "Langflow connection error:",
                error
            )

            return {
                "answer": (
                    "An unexpected error occurred "
                    "while retrieving tax information."
                ),
                "sources": []
            }

    def _mock_response(
        self,
        question: str
    ) -> dict:
        """
        Temporary response used while Person C's
        Langflow pipeline is not connected.
        """

        return {
            "answer": (
                "TaxPal is currently running in "
                "development mode.\n\n"
                f"You asked: {question}\n\n"
                "The Teams bot is working correctly. "
                "The verified tax-law answer will be "
                "provided by the Langflow RAG system "
                "once it is connected."
            ),
            "sources": [
                {
                    "title": (
                        "Mock Uganda Tax Law Source"
                    ),
                    "section": (
                        "Development Test"
                    )
                }
            ]
        }

    def _parse_response(
        self,
        data: dict
    ) -> dict:
        """
        Convert Langflow's response into the
        standard format used by app.py.
        """

        try:
            message = (
                data["outputs"][0]
                ["outputs"][0]
                ["results"]
                ["message"]
            )

            if isinstance(message, dict):

                answer = (
                    message.get("text")
                    or message.get("message")
                    or "No answer was returned."
                )

                sources = (
                    message.get("source_documents")
                    or message.get("sources")
                    or []
                )

            else:
                answer = str(message)
                sources = []

            return {
                "answer": answer,
                "sources": sources
            }

        except (
            KeyError,
            IndexError,
            TypeError
        ) as error:

            print(
                "Unable to parse Langflow response:",
                error
            )

            print(
                "Raw response:",
                data
            )

            return {
                "answer": (
                    "A response was received, "
                    "but TaxPal could not process it."
                ),
                "sources": []
            }
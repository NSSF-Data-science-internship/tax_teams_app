import asyncio

from microsoft_teams.apps import (
    App,
    ActivityContext
)

from microsoft_teams.api import (
    MessageActivity,
    MessageActivityInput
)

from config import Config
from langflow_client import LangflowClient


config = Config()


def create_token_factory():

    def get_token(
        scopes,
        tenant_id=None
    ):
        from azure.identity import (
            ManagedIdentityCredential
        )

        credential = (
            ManagedIdentityCredential(
                client_id=config.APP_ID
            )
        )

        if isinstance(scopes, str):
            scopes_list = [scopes]
        else:
            scopes_list = scopes

        token = credential.get_token(
            *scopes_list
        )

        return token.token

    return get_token


app = App(
    token=(
        create_token_factory()
        if config.APP_TYPE == "UserAssignedMsi"
        else None
    ),
    skip_auth=not config.APP_ID,
)


langflow_client = LangflowClient(
    base_url=config.LANGFLOW_BASE_URL,
    flow_id=config.LANGFLOW_FLOW_ID,
)


@app.on_message
async def handle_message(
    ctx: ActivityContext[MessageActivity]
):
    """
    Handle a message received from Microsoft Teams.
    """

    question = (
        ctx.activity.text or ""
    ).strip()

    if not question:

        await ctx.send(
            MessageActivityInput(
                text=(
                    "Please enter a tax question."
                )
            )
        )

        return

    print(
        f"Question received: {question}"
    )

    try:

        result = await langflow_client.ask(
            question
        )

        answer = result.get(
            "answer",
            "I could not generate an answer."
        )

        sources = result.get(
            "sources",
            []
        )

        response = answer

        if sources:

            response += "\n\nSources:"

            for source in sources:

                if isinstance(source, dict):

                    title = source.get(
                        "title",
                        "Unknown source"
                    )

                    section = source.get(
                        "section",
                        ""
                    )

                    if section:

                        response += (
                            f"\n• {title}"
                            f" — {section}"
                        )

                    else:

                        response += (
                            f"\n• {title}"
                        )

                else:

                    response += (
                        f"\n• {source}"
                    )

        response += (
            "\n\n"
            "TaxPal provides information for "
            "informational purposes and should "
            "not be treated as professional "
            "tax or legal advice."
        )

        await ctx.send(
            MessageActivityInput(
                text=response
            )
        )

    except Exception as error:

        print(
            "Error processing message:",
            error
        )

        await ctx.send(
            MessageActivityInput(
                text=(
                    "Sorry, I couldn't process "
                    "your question right now."
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(app.start())
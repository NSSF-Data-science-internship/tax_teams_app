import asyncio
import httpx

from microsoft_teams.apps import (
    App,
    ActivityContext
)

from microsoft_teams.api import (
    MessageActivity,
    MessageActivityInput
)

from config import Config
#from langflow_client import LangflowClient
from tax_search_client import search_tax_law
from llm_client import answer_tax_question

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


#langflow_client = LangflowClient(
    #base_url=config.LANGFLOW_BASE_URL,
    #flow_id=config.LANGFLOW_FLOW_ID,
#)


@app.on_message
async def handle_message(
    ctx: ActivityContext[MessageActivity]
):
    """Handle TaxPal questions."""

    question = (
        ctx.activity.text or ""
    ).strip()

    if not question:
        await ctx.send(
            MessageActivityInput(
                text="Please enter a tax question."
            )
        )
        return

    try:
        # 1. Retrieve relevant Ugandan tax-law chunks
        documents = await search_tax_law(
            question,
            k=4,
        )

        # 2. Ask Azure OpenAI to answer
        #    using only those retrieved documents
        answer = await asyncio.to_thread(
            answer_tax_question,
            question,
            documents,
        )

        await ctx.send(
            MessageActivityInput(
                text=answer
            )
        )

    except httpx.HTTPError as exc:
        print(
            f"Tax search error: {exc}"
        )

        await ctx.send(
            MessageActivityInput(
                text=(
                    "I couldn't access the tax-law "
                    "knowledge base right now."
                )
            )
        )

    except Exception as exc:
        print(
            f"TaxPal error: {exc}"
        )

        await ctx.send(
            MessageActivityInput(
                text=(
                    "Sorry, I couldn't process that "
                    "tax question right now."
                )
            )
        )
"""  
@app.on_members_added
async def handle_new_members(ctx: ActivityContext):
    await ctx.send(
        MessageActivityInput(
            text=(
                "👋 Hi! I'm TaxPal, your Ugandan tax law assistant.\n\n"
                "Ask me questions like:\n"
                "• What is the VAT rate on imported electronics?\n"
                "• Is rental income subject to withholding tax?\n"
                "• What exemptions exist for small businesses?\n\n"
                "I'll cite the specific act and section in my answer."
            )
        )
    )        
"""

if __name__ == "__main__":
    asyncio.run(app.start())
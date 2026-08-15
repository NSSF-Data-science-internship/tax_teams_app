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
from conversation import run_conversation_turn
from conversation_store import clear_history, load_history, save_turn

config = Config()

# Development-stage memory keyed by Teams conversation ID. This survives
# ordinary turns but is cleared whenever the bot process restarts.
conversation_histories: dict[str, list[dict]] = {}
MAX_HISTORY_MESSAGES = 12


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

    conversation = getattr(ctx.activity, "conversation", None)
    conversation_id = (
        getattr(conversation, "id", None)
        or getattr(ctx.activity, "conversation_id", None)
        or "default"
    )

    if question.lower() in {"clear conversation", "reset conversation"}:
        conversation_histories.pop(conversation_id, None)
        try:
            await asyncio.to_thread(clear_history, conversation_id)
        except Exception as exc:
            print(f"Persistent history clear failed: {exc}")
        await ctx.send(
            MessageActivityInput(
                text="Conversation cleared. What tax question can I help with?"
            )
        )
        return

    sender = getattr(ctx.activity, "from_", None)
    user_id = getattr(sender, "id", None) or "unknown-teams-user"

    try:
        history = await asyncio.to_thread(load_history, conversation_id)
    except Exception as exc:
        print(f"Persistent history load failed: {exc}")
        history = conversation_histories.setdefault(conversation_id, [])

    try:
        result = await run_conversation_turn(
            question,
            history=history,
            k=4,
        )

        history.extend(
            [
                {"role": "user", "content": question},
                {
                    "role": "assistant",
                    "content": result["answer"],
                    "documents": result["documents"],
                },
            ]
        )
        del history[:-MAX_HISTORY_MESSAGES]
        conversation_histories[conversation_id] = history

        try:
            await asyncio.to_thread(
                save_turn,
                conversation_id,
                user_id,
                "teams",
                question,
                result,
            )
        except Exception as exc:
            print(f"Persistent history save failed: {exc}")

        await ctx.send(
            MessageActivityInput(
                text=result["answer"]
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

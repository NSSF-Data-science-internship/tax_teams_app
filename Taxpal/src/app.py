import asyncio
import hashlib
import logging
import os

logging.basicConfig(level=logging.INFO)

from microsoft_teams.apps import (
    App,
    ActivityContext
)

from microsoft_teams.api import (
    MessageActivity,
    MessageActivityInput
)

from config import Config
from cards import build_taxpal_card_message
from conversation import run_conversation_turn
from tax_search_client import TaxSearchUnavailable
from conversation_store import (
    clear_history, delete_user_memory, load_history, load_user_memory,
    save_turn, set_memory_consent, update_user_memory,
)
from user_memory import extract_explicit_preferences, format_profile, memory_command

config = Config()

if config.ENVIRONMENT == "production" and not config.APP_ID:
    raise RuntimeError(
        "CLIENT_ID is required when TAXPAL_ENV=production; refusing to start without Teams authentication."
    )
if config.ENVIRONMENT == "production" and config.PLAYGROUND_MODE:
    raise RuntimeError(
        "TAXPAL_PLAYGROUND cannot be enabled when TAXPAL_ENV=production."
    )

# The Playground sends unsigned mock activities and hosts its callback service
# locally.  If real Teams credentials remain in the environment, the SDK tries
# to acquire an Entra token before replying and the mock turn fails.  Ignore
# those credentials only for explicit local Playground runs; production keeps
# the configured identity unchanged.
if config.PLAYGROUND_MODE:
    os.environ["CLIENT_ID"] = ""
    os.environ["CLIENT_SECRET"] = ""
    config.APP_ID = ""
    config.APP_PASSWORD = ""

# Development-stage memory keyed by Teams conversation ID. This survives
# ordinary turns but is cleared whenever the bot process restarts.
conversation_histories: dict[str, list[dict]] = {}
MAX_HISTORY_MESSAGES = 12


def _teams_identity(activity) -> tuple[str, str]:
    sender = getattr(activity, "from_", None)
    user_id = getattr(sender, "aad_object_id", None) or getattr(sender, "id", None)
    if not user_id:
        raise PermissionError("Teams did not provide an authenticated user identity.")
    conversation = getattr(activity, "conversation", None)
    conversation_id = getattr(conversation, "id", None) or getattr(activity, "conversation_id", None)
    if not conversation_id:
        raise PermissionError("Teams did not provide a conversation identity.")
    tenant_id = getattr(conversation, "tenant_id", None)
    channel_data = getattr(activity, "channel_data", None)
    if not tenant_id and isinstance(channel_data, dict):
        tenant = channel_data.get("tenant") or {}
        tenant_id = tenant.get("id") if isinstance(tenant, dict) else None
    tenant_id = tenant_id or "teams-tenant-unavailable"
    owner_id = f"{tenant_id}:{user_id}"
    session_material = f"teams\0{owner_id}\0{conversation_id}".encode("utf-8")
    session_id = "teams:" + hashlib.sha256(session_material).hexdigest()
    return owner_id, session_id


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
    dangerously_allow_unauthenticated_requests=(
        config.PLAYGROUND_MODE or not config.APP_ID
    ),
)


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
        user_id, conversation_id = _teams_identity(ctx.activity)
    except PermissionError:
        await ctx.send(MessageActivityInput(text="I couldn't verify your Teams identity, so I won't access conversation history."))
        return

    try:
        memory = await asyncio.to_thread(load_user_memory, user_id, "teams")
    except Exception as exc:
        print(f"User memory load failed: {exc}")
        memory = {"consented": False, "preferences": {}}

    command = memory_command(question)
    if command == "enable":
        try:
            await asyncio.to_thread(set_memory_consent, user_id, "teams", True)
            details = extract_explicit_preferences(question)
            if details:
                await asyncio.to_thread(update_user_memory, user_id, "teams", details)
            await ctx.send(MessageActivityInput(text="Memory is on. I will remember only profile details you explicitly state. You can say ‘show my profile’ or ‘forget my profile’ at any time."))
        except Exception as exc:
            print(f"User memory enable failed: {exc}")
            await ctx.send(MessageActivityInput(text="I couldn't enable profile memory right now."))
        return
    if command == "delete":
        try:
            await asyncio.to_thread(delete_user_memory, user_id, "teams")
            await ctx.send(MessageActivityInput(text="Your remembered tax profile and memory consent have been deleted. Your conversation history was not deleted."))
        except Exception as exc:
            print(f"User memory delete failed: {exc}")
            await ctx.send(MessageActivityInput(text="I couldn't delete your remembered profile right now."))
        return
    if command == "view":
        text = format_profile(memory.get("preferences", {})) if memory.get("consented") else "Memory is off. Say ‘remember my tax profile’ if you want to opt in."
        await ctx.send(MessageActivityInput(text=text))
        return

    remembered_updates = extract_explicit_preferences(question)
    if remembered_updates and memory.get("consented"):
        try:
            preferences = await asyncio.to_thread(update_user_memory, user_id, "teams", remembered_updates)
            await ctx.send(MessageActivityInput(text="I’ve updated your remembered profile.\n\n" + format_profile(preferences)))
        except Exception as exc:
            print(f"User memory update failed: {exc}")
            await ctx.send(MessageActivityInput(text="I understood the profile detail, but couldn't save it right now."))
        return

    if question.lower() in {"clear conversation", "reset conversation"}:
        conversation_histories.pop(conversation_id, None)
        try:
            await asyncio.to_thread(clear_history, conversation_id, user_id, "teams")
        except Exception as exc:
            print(f"Persistent history clear failed: {exc}")
        await ctx.send(
            MessageActivityInput(
                text="Conversation cleared. What tax question can I help with?"
            )
        )
        return

    try:
        history = await asyncio.to_thread(load_history, conversation_id, user_id, "teams")
    except Exception as exc:
        print(f"Persistent history load failed: {exc}")
        history = conversation_histories.setdefault(conversation_id, [])

    try:
        result = await run_conversation_turn(
            question,
            history=history,
            k=4,
            user_profile=memory.get("preferences", {}) if memory.get("consented") else {},
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

        try:
            response = build_taxpal_card_message(result)
        except Exception as exc:
            print(f"Adaptive Card build failed; sending text fallback: {exc}")
            response = MessageActivityInput(text=result["answer"])
        await ctx.send(response)

    except TaxSearchUnavailable as exc:
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

        error_text = str(exc).lower()
        if "resource_exhausted" in error_text or "quota" in error_text or "429" in error_text:
            user_message = (
                "I received your question, but the Gemini API quota is currently "
                "exhausted. Please check the Gemini project's quota/billing or use "
                "another configured LLM provider, then try again."
            )
        elif "tax-law search service" in error_text or "localhost:8001" in error_text:
            user_message = (
                "I received your question, but the local tax knowledge service is "
                "offline. Start the tax-search service and try again."
            )
        else:
            user_message = "Sorry, I couldn't process that tax question right now."

        await ctx.send(
            MessageActivityInput(
                text=user_message
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

import asyncio

import pandas as pd
import streamlit as st

from conversation import run_conversation_turn
from llm_client import GEMINI_MODEL, LLM_PROVIDER


st.set_page_config(
    page_title="TaxPal conversational tester",
    page_icon=":material/account_balance:",
    layout="wide",
)

st.session_state.setdefault("messages", [])
st.session_state.setdefault("result_count", 4)

with st.sidebar:
    st.header("Flow settings")
    st.metric("LLM provider", LLM_PROVIDER.title(), border=True)
    st.metric("Model", GEMINI_MODEL, border=True)
    st.slider(
        "Documents to retrieve",
        1,
        10,
        key="result_count",
    )
    if st.button("Clear conversation", icon=":material/delete:"):
        st.session_state.messages = []
        st.rerun()

st.title("TaxPal conversational tester")
st.caption(
    "Ask follow-up questions while inspecting rewritten searches, evidence, "
    "and timing for every answer."
)


def render_diagnostics(message: dict) -> None:
    documents = message.get("documents", [])
    diagnostics = message.get("diagnostics", {})

    with st.expander("Flow details and evidence"):
        if diagnostics.get("search_query"):
            st.markdown("**Standalone retrieval query**")
            st.code(diagnostics["search_query"], language=None)
        elif diagnostics.get("retrieval_reused"):
            st.info("Reused evidence from the previous answer; no new search ran.")
        else:
            st.info("No retrieval was needed for this conversational response.")

        with st.container(horizontal=True):
            st.metric("Sources", len(documents), border=True)
            st.metric(
                "Rewrite",
                f"{diagnostics.get('rewrite_seconds', 0):.2f}s",
                border=True,
            )
            st.metric(
                "Search",
                f"{diagnostics.get('search_seconds', 0):.2f}s",
                border=True,
            )
            st.metric(
                "Generation",
                f"{diagnostics.get('generation_seconds', 0):.2f}s",
                border=True,
            )

        if documents:
            source_rows = []
            for index, document in enumerate(documents, start=1):
                metadata = document.get("metadata", {})
                source_rows.append(
                    {
                        "Rank": index,
                        "Title": metadata.get("title", "Unknown document"),
                        "Section": metadata.get("section", ""),
                        "Source": metadata.get("source", ""),
                        "URL": metadata.get("url", ""),
                    }
                )
            st.dataframe(
                pd.DataFrame(source_rows),
                hide_index=True,
                column_config={"URL": st.column_config.LinkColumn("URL")},
            )

            for index, document in enumerate(documents, start=1):
                metadata = document.get("metadata", {})
                title = metadata.get("title", "Unknown document")
                with st.expander(f"Source {index}: {title}"):
                    st.json(metadata)
                    st.markdown(document.get("text", "No text returned."))


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_diagnostics(message)

suggestions = {
    "VAT rate": "What is the standard VAT rate in Uganda?",
    "Rental income": "How is rental income taxed in Uganda?",
    "Small business": "What tax rules apply to small businesses in Uganda?",
}

pending_prompt = None
if not st.session_state.messages:
    selected = st.pills(
        "Try asking",
        list(suggestions),
        label_visibility="collapsed",
    )
    if selected:
        pending_prompt = suggestions[selected]

prompt = pending_prompt or st.chat_input(
    "Ask TaxPal a Ugandan tax question",
    submit_mode="disable",
)

if prompt:
    user_message = {"role": "user", "content": prompt}
    st.session_state.messages.append(user_message)
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.status("Thinking with tax-law evidence…", expanded=True):
                result = asyncio.run(
                    run_conversation_turn(
                        prompt,
                        history=st.session_state.messages[:-1],
                        k=st.session_state.result_count,
                    )
                )

            assistant_message = {
                "role": "assistant",
                "content": result["answer"],
                "documents": result["documents"],
                "diagnostics": result,
            }
            st.markdown(result["answer"])
            render_diagnostics(assistant_message)
            st.session_state.messages.append(assistant_message)
        except Exception as exc:
            st.error("TaxPal could not complete this turn.")
            st.exception(exc)

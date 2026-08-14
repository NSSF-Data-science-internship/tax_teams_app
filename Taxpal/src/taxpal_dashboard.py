import asyncio
import time

import pandas as pd
import streamlit as st

from llm_client import GEMINI_MODEL, LLM_PROVIDER, answer_tax_question
from tax_search_client import search_tax_law


st.set_page_config(
    page_title="TaxPal flow tester",
    page_icon=":material/account_balance:",
    layout="wide",
)

st.title("TaxPal flow tester")
st.caption(
    "Inspect retrieval results, source metadata, timings, and the grounded answer."
)

with st.container(horizontal=True):
    st.metric("LLM provider", LLM_PROVIDER.title(), border=True)
    st.metric("Model", GEMINI_MODEL, border=True)
    st.metric("Search endpoint", "localhost:8001", border=True)

with st.form("taxpal_test"):
    question = st.text_area(
        "Tax question",
        value="What is the standard VAT rate in Uganda?",
        height=100,
    )
    result_count = st.slider("Documents to retrieve", 1, 10, 4)
    submitted = st.form_submit_button(
        "Run TaxPal flow",
        type="primary",
        icon=":material/play_arrow:",
    )

if submitted:
    if not question.strip():
        st.warning("Enter a tax question before running the flow.")
        st.stop()

    try:
        started = time.perf_counter()
        with st.status("Running TaxPal flow…", expanded=True) as status:
            st.write("1. Searching the tax-law vector store")
            search_started = time.perf_counter()
            documents = asyncio.run(
                search_tax_law(question.strip(), k=result_count)
            )
            search_seconds = time.perf_counter() - search_started
            st.write(f"2. Retrieved {len(documents)} source documents")

            generation_started = time.perf_counter()
            answer = answer_tax_question(question.strip(), documents)
            generation_seconds = time.perf_counter() - generation_started
            st.write(f"3. Generated an answer with {LLM_PROVIDER.title()}")
            status.update(label="TaxPal flow completed", state="complete")

        total_seconds = time.perf_counter() - started

        with st.container(horizontal=True):
            st.metric(
                "Documents retrieved", str(len(documents)), border=True
            )
            st.metric(
                "Retrieval time", f"{search_seconds:.2f}s", border=True
            )
            st.metric(
                "Generation time", f"{generation_seconds:.2f}s", border=True
            )
            st.metric("Total time", f"{total_seconds:.2f}s", border=True)

        with st.container(border=True):
            st.subheader("Grounded answer")
            st.markdown(answer)

        st.subheader("Retrieved evidence")
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
            column_config={
                "URL": st.column_config.LinkColumn("URL"),
            },
        )

        for index, document in enumerate(documents, start=1):
            metadata = document.get("metadata", {})
            title = metadata.get("title", "Unknown document")
            with st.expander(f"Source {index}: {title}"):
                st.json(metadata)
                st.markdown(document.get("text", "No text returned."))

    except Exception as exc:
        st.error("The TaxPal flow failed.")
        st.exception(exc)

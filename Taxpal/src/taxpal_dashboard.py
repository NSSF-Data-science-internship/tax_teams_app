import asyncio
import uuid
from decimal import Decimal

import pandas as pd
import streamlit as st

from conversation import run_conversation_turn
from conversation_store import (
    clear_history, delete_user_memory, load_history, load_user_memory,
    save_turn, set_memory_consent, update_user_memory,
)
from evidence import build_citations
from llm_client import GEMINI_MODEL, LLM_PROVIDER
from tax_search_client import TaxSearchUnavailable
from tax_rules import DEFAULT_TAX_YEAR, available_tax_years, load_tax_rules


st.set_page_config(
    page_title="TaxPal conversational tester",
    page_icon=":material/account_balance:",
    layout="wide",
)

st.session_state.setdefault("local_user_id", f"streamlit-user:{uuid.uuid4()}")
st.session_state.setdefault("session_id", f"streamlit:{uuid.uuid4()}")
local_user_id = st.session_state.local_user_id
session_id = st.session_state.session_id

if "messages" not in st.session_state:
    try:
        st.session_state.messages = load_history(session_id, local_user_id, "streamlit")
        st.session_state.history_status = "Connected"
    except Exception as exc:
        st.session_state.messages = []
        st.session_state.history_status = f"Unavailable: {exc}"

st.session_state.setdefault("result_count", 4)
if "user_memory" not in st.session_state:
    try:
        st.session_state.user_memory = load_user_memory(local_user_id, "streamlit")
    except Exception:
        st.session_state.user_memory = {"consented": False, "preferences": {}}


@st.dialog("Delete remembered profile")
def confirm_profile_deletion():
    st.write("This deletes memory consent and all remembered profile details. Conversation history is kept.")
    if st.button("Delete profile", type="primary", icon=":material/delete_forever:"):
        try:
            delete_user_memory(local_user_id, "streamlit")
            st.session_state.user_memory = {"consented": False, "preferences": {}}
            st.rerun()
        except Exception as exc:
            st.error(f"Could not delete the profile: {exc}")

with st.sidebar:
    st.header("Flow settings")
    st.metric("LLM provider", LLM_PROVIDER.title(), border=True)
    st.metric("Model", GEMINI_MODEL, border=True)
    st.caption(f"History: {st.session_state.history_status}")
    st.caption(f"Session: `{session_id}`")
    tax_year = st.selectbox(
        "Tax year",
        available_tax_years(),
        index=available_tax_years().index(DEFAULT_TAX_YEAR),
        key="tax_year",
        help="Applied to statutory calculator results. Typed requests can override it by naming a tax year.",
    )
    selected_rules = load_tax_rules(tax_year)
    st.caption(
        f"Rules: `{selected_rules['version']}` · effective "
        f"{selected_rules['effective_from']} to {selected_rules['effective_to']}"
    )
    st.slider(
        "Documents to retrieve",
        1,
        10,
        key="result_count",
    )
    with st.expander("Remembered profile"):
        memory = st.session_state.user_memory
        preferences = memory.get("preferences", {})
        st.caption("TaxPal stores profile details only after you opt in. Calculator inputs still require confirmation.")
        with st.form("memory_profile"):
            consented = st.checkbox("Allow TaxPal to remember my profile", value=bool(memory.get("consented")))
            residency_options = ["Not set", "resident", "non-resident"]
            current_residency = preferences.get("residency", "Not set")
            residency = st.selectbox("Residency", residency_options, index=residency_options.index(current_residency) if current_residency in residency_options else 0)
            taxpayer_options = ["Not set", "individual", "company"]
            current_taxpayer = preferences.get("taxpayer_type", "Not set")
            taxpayer_type = st.selectbox("Taxpayer type", taxpayer_options, index=taxpayer_options.index(current_taxpayer) if current_taxpayer in taxpayer_options else 0)
            year_options = ["Not set"] + available_tax_years()
            current_year = preferences.get("preferred_tax_year", "Not set")
            preferred_year = st.selectbox("Preferred tax year", year_options, index=year_options.index(current_year) if current_year in year_options else 0)
            frequent_options = ["Not set", "paye", "vat", "rental income", "withholding tax", "corporate income", "individual business income"]
            current_frequent = preferences.get("frequent_tax", "Not set")
            frequent_tax = st.selectbox("Frequent tax", frequent_options, index=frequent_options.index(current_frequent) if current_frequent in frequent_options else 0)
            business_sector = st.text_input("Business sector", value=preferences.get("business_sector", ""), max_chars=120)
            save_profile = st.form_submit_button("Save profile", icon=":material/save:")
        if save_profile:
            try:
                set_memory_consent(local_user_id, "streamlit", consented)
                saved = {}
                if consented:
                    values = {"residency": residency, "taxpayer_type": taxpayer_type, "preferred_tax_year": preferred_year, "frequent_tax": frequent_tax, "business_sector": business_sector}
                    saved = update_user_memory(local_user_id, "streamlit", {key: value for key, value in values.items() if value != "Not set" and value})
                st.session_state.user_memory = {"consented": consented, "preferences": saved}
                st.success("Profile preferences saved." if consented else "Memory is off and remembered profile details were cleared.")
            except Exception as exc:
                st.error(f"Could not save the profile: {exc}")
        if memory.get("consented") and st.button("Forget profile", icon=":material/delete:"):
            confirm_profile_deletion()
    if st.button("Clear conversation", icon=":material/delete:"):
        try:
            clear_history(session_id, local_user_id, "streamlit")
            st.session_state.history_status = "Connected"
        except Exception as exc:
            st.session_state.history_status = f"Unavailable: {exc}"
        st.session_state.messages = []
        st.rerun()

st.title("TaxPal conversational tester")
st.caption(
    "Ask follow-up questions while inspecting rewritten searches, evidence, "
    "and timing for every answer."
)

calculator_prompt = None
with st.container(border=True):
    st.subheader("Quick tax calculator")
    st.caption(
        "Estimate common Uganda taxes using verified URA rules, or supply your own flat rate."
    )
    calculator_mode = st.selectbox(
        "Calculation type",
        ["VAT", "PAYE", "Rental income", "Withholding tax", "Corporate income", "Individual business income", "Custom percentage"],
        index=0,
        key="calculator_mode",
    )
    with st.form("quick_tax_calculator"):
        amount = st.text_input(
            "Income or payment amount (UGX)",
            placeholder="1,000,000",
        )
        rate = 18.0
        taxpayer_status = "Resident"
        expenses = "0"
        wht_category = "Resident goods/services above UGX 1m"
        if calculator_mode == "VAT":
            rate = st.number_input("Rate (%)", min_value=0.0, max_value=100.0, value=18.0, step=0.5)
            treatment = st.segmented_control(
                "Amount treatment",
                ["VAT exclusive", "VAT inclusive"],
                default="VAT exclusive",
            )
            tax_label = "VAT"
        elif calculator_mode in {"PAYE", "Individual business income"}:
            taxpayer_status = st.segmented_control("Taxpayer status", ["Resident", "Non-resident"], default="Resident")
        elif calculator_mode == "Rental income":
            taxpayer_status = st.selectbox("Taxpayer type", ["Resident individual", "Non-resident individual", "Company"])
            if taxpayer_status == "Company":
                expenses = st.text_input("Allowable rental expenses (UGX)", value="0", help="The calculator caps allowable company expenses at 50% of annual gross rent.")
        elif calculator_mode == "Withholding tax":
            wht_category = st.selectbox(
                "Payment category",
                ["Resident goods/services above UGX 1m", "Rent above UGX 1m", "Non-resident services", "Non-resident dividend/interest/royalty"],
            )
            st.caption("Use this only where the payer has a legal obligation to withhold and the payee is not exempt.")
        elif calculator_mode == "Custom percentage":
            rate = st.number_input("Rate (%)", min_value=0.0, max_value=100.0, value=6.0, step=0.5)
            treatment = "VAT exclusive"
            tax_label = st.text_input(
                "Tax label",
                value="Custom tax",
                help="For example: withholding tax. The supplied rate is not legally verified.",
            )

        calculate_clicked = st.form_submit_button(
            "Calculate",
            type="primary",
            icon=":material/calculate:",
        )

    if calculate_clicked:
        if calculator_mode == "VAT":
            inclusion = "inclusive" if treatment == "VAT inclusive" else "exclusive"
            calculator_prompt = (
                f"Calculate VAT on UGX {amount} at {rate:g}% {inclusion} for tax year {tax_year}"
            )
        elif calculator_mode == "PAYE":
            calculator_prompt = f"Calculate PAYE for {taxpayer_status} on monthly chargeable income UGX {amount} for tax year {tax_year}"
        elif calculator_mode == "Individual business income":
            calculator_prompt = f"Calculate {taxpayer_status} individual annual business income tax on chargeable income UGX {amount} for tax year {tax_year}"
        elif calculator_mode == "Rental income":
            calculator_prompt = f"Calculate rental income tax for {taxpayer_status} on annual gross rent UGX {amount} with expenses UGX {expenses} for tax year {tax_year}"
        elif calculator_mode == "Corporate income":
            calculator_prompt = f"Calculate corporate income tax on annual chargeable income UGX {amount} for tax year {tax_year}"
        elif calculator_mode == "Withholding tax":
            calculator_prompt = f"Calculate withholding tax for {wht_category} on gross payment UGX {amount} for tax year {tax_year}"
        else:
            calculator_prompt = (
                f"Calculate {rate:g}% {tax_label} on UGX {amount}"
            )


def render_diagnostics(message: dict) -> None:
    documents = message.get("documents", [])
    diagnostics = message.get("diagnostics", {})
    citations = diagnostics.get("citations") or build_citations(documents)
    assessment = diagnostics.get("evidence_assessment") or {}

    with st.expander("Flow details and evidence"):
        calculation = diagnostics.get("calculation")
        if calculation:
            st.success("Used deterministic decimal arithmetic; no LLM arithmetic ran.")
            with st.container(horizontal=True):
                if calculation["kind"] == "vat_rate_fact":
                    st.metric("Standard VAT rate", f"{calculation['rate']}%", border=True)
                elif calculation["kind"] == "vat":
                    st.metric(
                        "Net amount",
                        f"UGX {Decimal(calculation['net_amount']):,.2f}",
                        border=True,
                    )
                    st.metric(
                        "VAT",
                        f"UGX {Decimal(calculation['vat_amount']):,.2f}",
                        border=True,
                    )
                    st.metric(
                        "Total",
                        f"UGX {Decimal(calculation['gross_amount']):,.2f}",
                        border=True,
                    )
                elif calculation["kind"] == "percentage":
                    st.metric(
                        "Taxable amount",
                        f"UGX {Decimal(calculation['input_amount']):,.2f}",
                        border=True,
                    )
                    st.metric(
                        calculation["label"],
                        f"UGX {Decimal(calculation['tax_amount']):,.2f}",
                        border=True,
                    )
                    st.metric(
                        "Rate",
                        f"{calculation['rate']}%",
                        border=True,
                    )
                else:
                    st.metric(
                        "Input amount",
                        f"UGX {Decimal(calculation['input_amount']):,.2f}",
                        border=True,
                    )
                    st.metric(
                        "Estimated tax",
                        f"UGX {Decimal(calculation['tax_amount']):,.2f}",
                        border=True,
                    )
                    detail_amount = calculation.get("net_amount") or calculation.get("chargeable_income")
                    detail_label = "After tax" if calculation.get("net_amount") else "Chargeable income"
                    st.metric(
                        detail_label,
                        f"UGX {Decimal(detail_amount):,.2f}",
                        border=True,
                    )
            if calculation.get("rule_version"):
                st.caption(
                    f"Tax year {calculation['tax_year']} · {calculation['rule_version']} · "
                    f"effective {calculation['effective_from']} to {calculation['effective_to']} · "
                    f"verified {calculation['verified_on']}"
                )
        elif diagnostics.get("search_query"):
            st.markdown("**Standalone retrieval query**")
            st.code(diagnostics["search_query"], language=None)
        elif diagnostics.get("retrieval_reused"):
            st.info("Reused evidence from the previous answer; no new search ran.")
        else:
            st.info("No retrieval was needed for this conversational response.")

        with st.container(horizontal=True):
            st.metric("Sources", len(citations), border=True)
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
            st.metric(
                "Official web",
                f"{diagnostics.get('web_seconds', 0):.2f}s",
                border=True,
            )

        if diagnostics.get("web_fallback_used"):
            st.success("Included evidence from approved official websites.")
        elif diagnostics.get("web_error"):
            st.warning(
                "Official web fallback was unavailable; the answer used local "
                f"evidence only. Details: {diagnostics['web_error']}"
            )

        confidence = assessment.get("confidence")
        if confidence == "high":
            st.success("Evidence confidence: High")
        elif confidence == "moderate":
            st.warning("Evidence confidence: Moderate")
        elif confidence == "low":
            st.error("Evidence confidence: Low — verify before relying on this answer.")
        for warning in assessment.get("warnings", []):
            st.warning(warning)

        if citations:
            source_rows = []
            for citation in citations:
                source_rows.append(
                    {
                        "Citation": citation["id"],
                        "Title": citation["title"],
                        "Section": citation["section"],
                        "Publisher": citation["publisher"],
                        "Origin": citation["evidence_type"],
                        "Published": citation["publication_date"],
                        "Effective from": citation["effective_from"],
                        "Effective to": citation["effective_to"],
                        "Accessed": citation["accessed_at"],
                        "URL": citation["url"],
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
    "VAT calculator": "Calculate VAT on UGX 1,000,000",
    "Rental income": "How is rental income taxed in Uganda?",
    "Small business": "What tax rules apply to small businesses in Uganda?",
}

pending_prompt = calculator_prompt
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
                        user_profile=(st.session_state.user_memory.get("preferences", {}) if st.session_state.user_memory.get("consented") else {}),
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
            try:
                save_turn(
                    session_id,
                    local_user_id,
                    "streamlit",
                    prompt,
                    result,
                )
                st.session_state.history_status = "Connected"
            except Exception as exc:
                st.session_state.history_status = f"Unavailable: {exc}"
                st.warning("The answer worked, but persistent history was not saved.")
        except TaxSearchUnavailable as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error("TaxPal could not complete this turn.")
            st.exception(exc)

"""PlaybookIQ Streamlit frontend — IBM Carbon theme, calls the FastAPI backend over HTTP.

Run alongside `uv run uvicorn app.main:app --port 8000`:
    uv run streamlit run app/ui.py
"""

import os
import sys
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from styles import get_carbon_css  # noqa: E402

load_dotenv()

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="PlaybookIQ | Sports Intelligence Platform",
    layout="wide",
)
st.markdown(get_carbon_css(), unsafe_allow_html=True)

st.title("PlaybookIQ Analytics Platform")
st.markdown(
    '<div class="subtitle">AWS Bedrock &bull; OpenSearch Serverless &bull; Claude 3.5 Sonnet</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## Configuration")
    model_choice = st.selectbox("Model Endpoint", ["Claude 3.5 Sonnet", "Claude 3 Haiku"])
    rag_enabled = st.checkbox("Enable RAG Context (Vector Store)", value=True)
    guardrails_enabled = st.checkbox("Enforce Bedrock Guardrails", value=True)

    st.markdown("## Filters")
    document_type = st.selectbox(
        "Document Type",
        ["All", "scouting_report", "game_transcript", "injury_log", "player_profile", "playbook"],
    )
    similarity_threshold = st.slider("Min Similarity Score", 0.0, 1.0, 0.5)

    st.markdown("## Backend")
    try:
        health = requests.get(f"{API_BASE_URL}/health", timeout=3)
        status_ok = health.status_code == 200
    except requests.RequestException:
        status_ok = False
    dot_class = "dot-ok" if status_ok else "dot-err"
    status_text = "Connected" if status_ok else "Unreachable"
    st.markdown(
        f'<div class="health-indicator"><span class="{dot_class}">&#9679;</span> API: {status_text}</div>',
        unsafe_allow_html=True,
    )

st.markdown("### Query Workspace")

with st.form("query_form"):
    user_query = st.text_input(
        "Input Tactical Query or Scouting Request",
        placeholder="e.g., Extract third-down blitz pass coverage vulnerabilities from the past games.",
    )
    submitted = st.form_submit_button("Execute Intelligence Query")

if submitted and user_query:
    payload = {
        "query": user_query,
        "use_fast_model": model_choice == "Claude 3 Haiku",
        "enable_rag": rag_enabled,
        "enable_guardrails": guardrails_enabled,
        "document_type": None if document_type == "All" else document_type,
        "similarity_threshold": similarity_threshold,
    }

    with st.spinner("Executing hybrid retrieval and Claude inference..."):
        try:
            response = requests.post(f"{API_BASE_URL}/query", json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as exc:
            st.error(f"Query failed: {exc}")
            result = None

    if result:
        st.markdown("### System Synthesis")
        st.markdown(result["answer"])

        if rag_enabled and result["retrieved_chunks"]:
            with st.expander("Retrieved Context Chunks"):
                for idx, chunk in enumerate(result["retrieved_chunks"], 1):
                    st.markdown(
                        f"**[{idx}]** score={chunk['score']:.3f} "
                        f"type={chunk['document_type']} player_id={chunk['player_id']}"
                    )
                    st.code(chunk["content"], language="text")
elif submitted:
    st.warning("Enter a query before executing.")
else:
    st.markdown(
        """
        <div class="empty-state">
          <div class="empty-title">No query executed yet</div>
          <div class="empty-desc">Try one of the example queries below</div>
          <div class="example-query">What is Isaiah Whitfield's current injury status?</div>
          <div class="example-query">Extract third-down blitz pass coverage vulnerabilities</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

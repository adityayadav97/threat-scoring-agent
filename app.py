"""Streamlit dashboard for the Threat Intelligence agents.

Flow:
    Upload Document -> Threat Scoring Agent -> Threat Report
        -> Recommendation Agent -> Recommendations -> Download Report

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import streamlit as st

from agents._common import LLMError, build_client
from agents.recommendation_agent import RecommendationAgent
from agents.threat_scoring_agent import ThreatScoringAgent
from utils.document_loader import SUPPORTED_EXTENSIONS, extract_text

SEVERITY_COLORS = {
    "Low": "#2e7d32",
    "Medium": "#f9a825",
    "High": "#ef6c00",
    "Critical": "#c62828",
}

st.set_page_config(page_title="Threat Intelligence Dashboard", page_icon="🛡️", layout="wide")


# --------------------------------------------------------------------------- #
# Session state helpers
# --------------------------------------------------------------------------- #
def _init_state() -> None:
    defaults = {
        "document_text": None,
        "document_name": None,
        "threat_report": None,
        "recommendations": None,
        "chat_history": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _secret(name: str) -> str | None:
    """Read a value from Streamlit secrets (cloud) or env/.env (local)."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # noqa: BLE001 - no secrets file configured locally
        pass
    return os.getenv(name)


@st.cache_resource(show_spinner=False)
def get_client():
    """Create the LLM client, preferring Groq, falling back to Gemini."""
    groq_key = _secret("GROQ_API_KEY")
    if groq_key:
        return build_client(
            api_key=groq_key, model=_secret("GROQ_MODEL"), provider="groq"
        )

    gemini_key = _secret("GEMINI_API_KEY")
    if gemini_key:
        return build_client(
            api_key=gemini_key, model=_secret("GEMINI_MODEL"), provider="gemini"
        )

    raise LLMError(
        "No API key found. Add GROQ_API_KEY (recommended, free at "
        "https://console.groq.com/keys) or GEMINI_API_KEY to the app secrets."
    )


def build_full_report() -> dict:
    return {
        "document_name": st.session_state.document_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "threat_report": st.session_state.threat_report,
        "recommendations": st.session_state.recommendations,
    }


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #
def render_threat_report(report: dict) -> None:
    score = report.get("threat_score", 0)
    severity = report.get("severity_level", "Low")
    color = SEVERITY_COLORS.get(severity, "#555")

    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("Threat Score", f"{score} / 10")
        st.markdown(
            f"<div style='padding:0.5rem 1rem;border-radius:8px;background:{color};"
            f"color:white;font-weight:600;text-align:center;'>Severity: {severity}</div>",
            unsafe_allow_html=True,
        )
        st.progress(min(1.0, float(score) / 10.0))
    with c2:
        st.markdown("**Summary**")
        st.write(report.get("summary") or "_No summary provided._")

    if report.get("input_truncated"):
        st.warning("Document was large and truncated before analysis.")

    entities = report.get("key_entities", [])
    if entities:
        st.markdown("#### 🧩 Key Entities")
        st.table(
            [
                {
                    "Name": e.get("name", ""),
                    "Type": e.get("type", ""),
                    "Role": e.get("role", ""),
                }
                for e in entities
            ]
        )

    indicators = report.get("threat_indicators", [])
    if indicators:
        st.markdown("#### 🚩 Threat Indicators")
        st.table(
            [
                {
                    "Indicator": i.get("indicator", ""),
                    "Category": i.get("category", ""),
                    "Confidence": i.get("confidence", ""),
                }
                for i in indicators
            ]
        )


def render_evidence(report: dict) -> None:
    evidence = report.get("evidence", [])
    if not evidence:
        st.info("No evidence items were returned.")
        return
    for idx, item in enumerate(evidence, start=1):
        with st.expander(f"Evidence #{idx}: {item.get('finding', 'Finding')}"):
            st.markdown(f"**Reasoning:** {item.get('reasoning', '')}")
            quote = item.get("quote")
            if quote:
                st.markdown("**Supporting excerpt:**")
                st.markdown(f"> {quote}")


def render_recommendations(plan: dict) -> None:
    st.markdown("#### ⚡ Immediate Actions")
    for action in plan.get("immediate_actions", []) or ["_None_"]:
        st.markdown(f"- {action}")

    st.markdown("#### 👁️ Monitoring Tasks")
    for task in plan.get("monitoring_tasks", []) or ["_None_"]:
        st.markdown(f"- {task}")

    esc = plan.get("escalation", {})
    st.markdown("#### 🚨 Escalation Decision")
    if esc.get("should_escalate"):
        st.error(
            f"**Escalate to:** {esc.get('escalate_to', 'N/A')}  \n"
            f"**Urgency:** {esc.get('urgency', 'N/A')}  \n"
            f"**Reason:** {esc.get('reason', '')}"
        )
    else:
        st.success(f"No escalation needed. {esc.get('reason', '')}")

    st.markdown("#### 🛠️ Risk Mitigation")
    for item in plan.get("risk_mitigation", []) or ["_None_"]:
        st.markdown(f"- {item}")


# --------------------------------------------------------------------------- #
# Main app
# --------------------------------------------------------------------------- #
def main() -> None:
    _init_state()

    st.title("🛡️ Threat Intelligence Dashboard")
    st.caption("Upload a document → score the threat → get recommendations → download the report.")

    # --- Sidebar: upload + analyze ---------------------------------------- #
    with st.sidebar:
        st.header("📂 Upload Document")
        uploaded = st.file_uploader(
            "Choose a document",
            type=[ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS],
            help="Supported: " + ", ".join(SUPPORTED_EXTENSIONS),
        )

        if uploaded is not None:
            try:
                text = extract_text(uploaded.name, uploaded.getvalue())
                st.session_state.document_text = text
                st.session_state.document_name = uploaded.name
                st.success(f"Loaded **{uploaded.name}** ({len(text):,} chars)")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not read document: {exc}")

        analyze = st.button(
            "🔬 Analyze Threat",
            type="primary",
            disabled=st.session_state.document_text is None,
            use_container_width=True,
        )

        if analyze:
            _run_analysis()

    if st.session_state.document_text is None:
        st.info("👈 Upload a document in the sidebar to begin.")
        return

    with st.expander("📄 Document preview", expanded=False):
        st.text(st.session_state.document_text[:3000])

    tab_report, tab_evidence, tab_reco, tab_ask, tab_download = st.tabs(
        ["📊 Threat Report", "🔍 Evidence", "✅ Recommendations", "💬 Ask Questions", "⬇️ Download"]
    )

    with tab_report:
        if st.session_state.threat_report:
            render_threat_report(st.session_state.threat_report)
            with st.expander("Raw threat report (JSON)"):
                st.json(st.session_state.threat_report)
        else:
            st.info("Run **Analyze Threat** to generate the report.")

    with tab_evidence:
        if st.session_state.threat_report:
            render_evidence(st.session_state.threat_report)
        else:
            st.info("Run **Analyze Threat** to see evidence.")

    with tab_reco:
        if st.session_state.recommendations:
            render_recommendations(st.session_state.recommendations)
            with st.expander("Raw recommendations (JSON)"):
                st.json(st.session_state.recommendations)
        else:
            st.info("Run **Analyze Threat** to generate recommendations.")

    with tab_ask:
        _render_ask_tab()

    with tab_download:
        _render_download_tab()


def _run_analysis() -> None:
    try:
        client = get_client()
    except LLMError as exc:
        st.error(str(exc))
        return

    try:
        with st.spinner("Scoring threats..."):
            report = ThreatScoringAgent(client).analyze(st.session_state.document_text)
        st.session_state.threat_report = report

        with st.spinner("Generating recommendations..."):
            plan = RecommendationAgent(client).recommend(report)
        st.session_state.recommendations = plan

        st.session_state.chat_history = []
        st.success("Analysis complete. See the tabs on the right.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Analysis failed: {exc}")


def _render_ask_tab() -> None:
    st.markdown("Ask a question about the uploaded document.")
    if st.session_state.document_text is None:
        st.info("Upload a document first.")
        return

    for q, a in st.session_state.chat_history:
        st.markdown(f"**You:** {q}")
        st.markdown(f"**Assistant:** {a}")
        st.divider()

    question = st.text_input("Your question", key="question_input")
    if st.button("Ask", disabled=not question):
        try:
            client = get_client()
            context = st.session_state.document_text[:30_000]
            report = st.session_state.threat_report or {}
            prompt = (
                "You are a threat-analysis assistant. Answer the question using ONLY "
                "the document and threat report below. If the answer is not present, "
                "say so.\n\n"
                f"THREAT REPORT:\n{json.dumps(report, indent=2)[:4000]}\n\n"
                f"DOCUMENT:\n\"\"\"\n{context}\n\"\"\"\n\n"
                f"QUESTION: {question}"
            )
            with st.spinner("Thinking..."):
                answer = client.generate_text(prompt)
            st.session_state.chat_history.append((question, answer))
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not answer: {exc}")


def _render_download_tab() -> None:
    if not st.session_state.threat_report:
        st.info("Run an analysis first to download a report.")
        return

    full_report = build_full_report()
    payload = json.dumps(full_report, indent=2)
    safe_name = (st.session_state.document_name or "document").rsplit(".", 1)[0]

    st.download_button(
        "⬇️ Download full report (JSON)",
        data=payload,
        file_name=f"threat_report_{safe_name}.json",
        mime="application/json",
        use_container_width=True,
    )
    st.json(full_report)


if __name__ == "__main__":
    main()

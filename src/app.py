import streamlit as st
import json
from datetime import datetime
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.models.input import SessionLog
from src.engine import ReviewEngine

@st.cache_resource
def get_engine():
    return ReviewEngine()

def save_decision(session_id: str, decision: str):
    """Zapisuje decyzję audytora do lokalnego pliku tekstowego."""
    timestamp = datetime.now().isoformat()
    with open("human_decisions_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{timestamp} | Session: {session_id} | Final Decision: {decision}\n")

def main():
    st.set_page_config(page_title="SAP Firefighter AI Reviewer", layout="wide")
    
    st.title("🛡️ SAP Firefighter Log Reviewer")
    st.markdown("Upload a session JSON file to run the AI compliance check and provide human validation.")

    engine = get_engine()

    uploaded_file = st.file_uploader("Choose a session JSON file", type=["json"])

    if uploaded_file is not None:
        raw_data = json.load(uploaded_file)
        session = SessionLog(**raw_data)
        
        with st.spinner("AI is analyzing the logs (checking rules & invoking LLM)..."):
            verdict = engine.review_session(session)

        st.divider()

        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader(f"System Verdict: `{verdict.verdict}`")
            
            if verdict.findings:
                st.error(f"Found {len(verdict.findings)} compliance violations.")
                for f in verdict.findings:
                    with st.expander(f"[{f.severity.upper()}] {f.rule_id}: {f.description}"):
                        st.write(f"**Location:** `{f.location}`")
                        st.write(f"**Evidence:** {f.evidence}")
            else:
                st.success("No compliance violations detected. Session appears clean.")

            st.divider()
            
            st.subheader("Human Controller Decision")
            st.write("Review the AI findings and log your final decision:")
            
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            if btn_col1.button("✅ PASS", use_container_width=True):
                save_decision(session.session_id, "PASS")
                st.success(f"Decision 'PASS' recorded for {session.session_id}.")
                
            if btn_col2.button("🚫 REJECT", use_container_width=True):
                save_decision(session.session_id, "REJECT")
                st.warning(f"Decision 'REJECT' recorded for {session.session_id}.")
                
            if btn_col3.button("↩️ SEND-BACK", use_container_width=True):
                save_decision(session.session_id, "SEND-BACK")
                st.info(f"Decision 'SEND-BACK' recorded for {session.session_id}.")

        with col2:
            st.subheader("Original Log Details")
            st.json(raw_data)

if __name__ == "__main__":
    main()
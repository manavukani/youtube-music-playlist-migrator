import streamlit as st
from ui.queue_manager import QueueManager

def get_queue_manager() -> QueueManager:
    """Get or create the singleton QueueManager from session state."""
    if "queue_manager" not in st.session_state:
        st.session_state["queue_manager"] = QueueManager()
    return st.session_state["queue_manager"]

import os
import streamlit as st
import pandas as pd
from playlistmigrator.state import StateManager

st.title("🔧 Status & Diagnostics")

st_manager = StateManager()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Current CSV", st_manager.get('current_csv', 'None'))
with col2:
    st.metric("Current Row", st_manager.get('current_row', 0))
with col3:
    st.metric("Completed Playlists", len(st_manager.get('completed_csvs', [])))

with st.expander("Raw state.json"):
    st.json(st_manager.state)

st.markdown("---")
st.subheader("Unmatched Tracks")

unmatched_file = 'unmatched_tracks.csv'
if os.path.exists(unmatched_file):
    try:
        df = pd.read_csv(unmatched_file)
        st.dataframe(df, use_container_width=True)

        with open(unmatched_file, 'rb') as f:
            st.download_button("⬇ Download unmatched_tracks.csv", data=f, file_name="unmatched_tracks.csv", mime="text/csv")
    except Exception as e:
        st.error(f"Failed to read `{unmatched_file}`: {e}")
else:
    st.info("No unmatched tracks file found.")

st.markdown("---")
st.subheader("⚠️ Danger Zone")

if st.button("🔄 Reset State"):
    st.session_state["show_reset_confirm"] = True

if st.session_state.get("show_reset_confirm", False):
    st.warning("This will delete state.json and reset all progress.")
    confirm = st.checkbox("I understand this cannot be undone")

    if st.button("Confirm Reset", disabled=not confirm):
        if os.path.exists('state.json'):
            os.remove('state.json')
            st.success("✅ State has been reset.")
        else:
            st.info("No `state.json` found to reset.")
        st.session_state["show_reset_confirm"] = False
        st.rerun()

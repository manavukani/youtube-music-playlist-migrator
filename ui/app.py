import streamlit as st

st.set_page_config(
    page_title="Playlist Migrator",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject global CSS (job card styles, etc.)
st.markdown("""
<style>
.job-running  { border-left: 4px solid #1f77b4; padding-left: 12px; margin-bottom: 8px; }
.job-pending  { border-left: 4px solid #aaaaaa; padding-left: 12px; margin-bottom: 8px; }
.job-done     { border-left: 4px solid #2ca02c; padding-left: 12px; margin-bottom: 8px; }
.job-error    { border-left: 4px solid #d62728; padding-left: 12px; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# Sidebar: show queue summary badge if jobs are running
from ui.session import get_queue_manager
qm = get_queue_manager()

if qm.is_busy:
    st.sidebar.success(f"▶ Transfer running — {qm.pending_count} pending")
elif qm.pending_count > 0:
    st.sidebar.info(f"⏳ {qm.pending_count} job(s) pending")

st.sidebar.markdown("---")
st.sidebar.markdown("**playlistmigrator** v1.0")

# Home page content
st.title("🎵 Playlist Migrator")
st.markdown("""
Welcome! Use the sidebar to navigate.

| Page | Purpose |
|------|---------|
| 🔐 Auth | Set up YouTube Music credentials |
| 📂 Load CSV | Convert Spotify CSV exports to playlists.json |
| 📋 Playlists | Browse source and YTMusic playlists |
| 🎵 Transfer Queue | Queue and run playlist transfers |
| 🔧 Status | View migration state and unmatched tracks |
""")

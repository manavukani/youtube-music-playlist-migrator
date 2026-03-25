import os
import uuid
from datetime import datetime
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from playlistmigrator import backend, auth as auth_module
from playlistmigrator.state import StateManager
from ui.session import get_queue_manager
from ui.queue_manager import TransferJob, STATUS_PENDING, STATUS_RUNNING, STATUS_DONE, STATUS_ERROR, STATUS_SKIPPED

st.set_page_config(
    page_title="Transfer Queue - Playlist Migrator",
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

st.title("🎵 Transfer Queue")

qm = get_queue_manager()
st_manager = StateManager()

st.info("Note: The queue runs in the background for this browser session. If you restart the Streamlit server, the queue will be lost, but in-progress jobs can be resumed.")

current_csv = st_manager.get('current_csv')
if current_csv:
    st.warning(f"⚠️ A previous transfer was in progress for playlist ID `{current_csv}`. It will be resumed if you re-add it to the queue.")

# Auto-refresh
if st.toggle("Auto-refresh (2s)", value=True):
    st_autorefresh(interval=2000, key="queue_refresh")

st.markdown("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
st.subheader("SECTION A: Submit a New Job")
st.markdown("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

col1, col2 = st.columns(2)

selected_source_id = None
playlists = []

with col1:
    st.markdown("**Source Playlist**")
    try:
        spotify_pls = backend.load_playlists_json()
        playlists = spotify_pls.get("playlists", [])

        source_options = {}
        for pl in playlists:
            label = f"{pl.get('name')} ({len(pl.get('tracks', []))} tracks)"
            source_options[label] = pl.get('id')

        selected_source_label = st.selectbox("Select source playlist", list(source_options.keys()))
        selected_source_id = source_options.get(selected_source_label) if selected_source_label else None

    except FileNotFoundError:
        st.warning("`playlists.json` not found. [Load CSV](/2_load_csv) first.")
        st.button("➕ Add to Queue", disabled=True) # disable button if not found

target_options = {}
selected_target_id = None

with col2:
    st.markdown("**Target YTMusic Playlist**")
    target_mode = st.radio("Target Option", ["Auto-create new", "Use existing"], label_visibility="collapsed")

    if target_mode == "Use existing":
        try:
            yt = auth_module.get_ytmusic()
            yt_playlists = yt.get_library_playlists(limit=5000)
            target_options = {f"{pl.get('title')} ({pl.get('count')} tracks)": pl.get('playlistId') for pl in yt_playlists}
            selected_target_label = st.selectbox("Select YTMusic playlist", list(target_options.keys()))
            selected_target_id = target_options.get(selected_target_label) if selected_target_label else None
        except Exception as e:
            st.error(f"Error fetching YTMusic playlists: {e}")
            selected_target_id = None
    else:
        st.info("(will be created with same name)")
        selected_target_id = None
        selected_target_label = None

with st.expander("Advanced Options"):
    track_sleep = st.slider("Track Sleep (seconds)", 0.0, 2.0, 0.1)
    algo_option = st.radio("Search Algorithm", ["0 — Exact", "1 — Extended", "2 — Approximate"])
    algo = int(algo_option[0])
    dry_run = st.checkbox("Dry Run (don't write any changes)")
    privacy = st.selectbox("Privacy", ["PRIVATE", "PUBLIC", "UNLISTED"])

# Only show button if playlists.json was loaded
if playlists:
    # Check if already in queue
    existing_jobs = qm.get_jobs()
    is_duplicate = any(j.src_playlist_id == selected_source_id and j.status in (STATUS_PENDING, STATUS_RUNNING) for j in existing_jobs)

    allow_override = False
    if is_duplicate:
        st.warning("This playlist is already pending or running in the queue.")
        allow_override = st.checkbox("I know, add it anyway")

    if st.button("➕ Add to Queue", disabled=is_duplicate and not allow_override):
        if not os.path.exists("creds.json"):
            st.error("Not authenticated. Go to Auth page.")
        elif not selected_source_id:
            st.error("Please select a source playlist.")
        else:
            source_name = next((p.get("name") for p in playlists if p.get("id") == selected_source_id), "Unknown")
            target_name = None
            if selected_target_id:
                # we got title from earlier fetch, this is a bit hacky but avoids refetching
                try:
                   target_name = selected_target_label.split(" (")[0]
                except:
                   target_name = "Unknown target"

            job = TransferJob(
                job_id=str(uuid.uuid4()),
                src_playlist_id=selected_source_id,
                src_playlist_name=source_name,
                dst_playlist_id=selected_target_id,
                dst_playlist_name=target_name,
                algo=algo,
                dry_run=dry_run,
                track_sleep=track_sleep,
                privacy=privacy,
                status=STATUS_PENDING,
                progress=0,
                total_tracks=0,
                tracks_done=0,
                tracks_added=0,
                tracks_errored=0,
                tracks_skipped=0,
                log_lines=[],
                submitted_at=datetime.utcnow().isoformat()
            )

            was_busy = qm.is_busy
            qm.submit(job)

            st.success(f"✅ Added '{source_name}' to queue.")
            if not was_busy:
                st.info("▶️ Transfer started immediately.")
            else:
                st.info(f"⏳ Queued — position {qm.pending_count} in queue.")

            st.rerun()

st.markdown("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
st.subheader("SECTION B: Queue Status")
st.markdown("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

jobs = qm.get_jobs()
running_count = sum(1 for j in jobs if j.status == STATUS_RUNNING)
pending_count = sum(1 for j in jobs if j.status == STATUS_PENDING)
done_count = sum(1 for j in jobs if j.status == STATUS_DONE)
error_count = sum(1 for j in jobs if j.status == STATUS_ERROR)

st.markdown(f"**| ▶ Running: {running_count} | ⏳ Pending: {pending_count} | ✅ Done: {done_count} | ❌ Errors: {error_count} |**")

if jobs:
    for job in reversed(jobs):
        with st.container():
            target_display = job.dst_playlist_name if job.dst_playlist_name else "[Auto-create]"
            dry_run_badge = " (DRY RUN)" if job.dry_run else ""

            if job.status == STATUS_RUNNING:
                st.markdown(f"<div class='job-running'>", unsafe_allow_html=True)
                st.markdown(f"**▶ RUNNING** `{job.src_playlist_name}` → `{target_display}`{dry_run_badge}")
                st.markdown(f"Submitted: {job.submitted_at} | Started: {job.started_at}")
                st.progress(job.progress / 100)
                st.markdown(f"**{job.progress}%** ({job.tracks_done}/{job.total_tracks} tracks) — Added: {job.tracks_added} | Errors: {job.tracks_errored} | Duplicates: {job.tracks_skipped}")

            elif job.status == STATUS_PENDING:
                st.markdown(f"<div class='job-pending'>", unsafe_allow_html=True)
                cols = st.columns([4, 1])
                with cols[0]:
                    st.markdown(f"**⏳ PENDING** `{job.src_playlist_name}` → `{target_display}`{dry_run_badge}")
                    st.markdown(f"Submitted: {job.submitted_at}")
                with cols[1]:
                    if st.button("✕ Cancel", key=f"cancel_{job.job_id}"):
                        qm.cancel_pending(job.job_id)
                        st.rerun()

            elif job.status == STATUS_DONE:
                st.markdown(f"<div class='job-done'>", unsafe_allow_html=True)
                st.markdown(f"**✅ DONE** `{job.src_playlist_name}` → `{target_display}`{dry_run_badge}")
                duration = "Unknown"
                if job.started_at and job.finished_at:
                    try:
                        start_time = datetime.fromisoformat(job.started_at)
                        end_time = datetime.fromisoformat(job.finished_at)
                        duration = str(end_time - start_time).split('.')[0]
                    except:
                        pass
                st.markdown(f"Finished: {job.finished_at} | Duration: {duration}")
                st.markdown(f"Added: {job.tracks_added} | Errors: {job.tracks_errored} | Duplicates: {job.tracks_skipped}")

            elif job.status == STATUS_ERROR:
                st.markdown(f"<div class='job-error'>", unsafe_allow_html=True)
                st.markdown(f"**❌ ERROR** `{job.src_playlist_name}` → `{target_display}`{dry_run_badge}")
                st.error(job.error_message)

            with st.expander("▼ Show Log" if job.status in (STATUS_DONE, STATUS_ERROR) else "▼ Show Live Log"):
                if job.log_lines:
                    st.code("\n".join(job.log_lines), language="text")
                else:
                    st.info("No log output yet.")
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("---")
else:
    st.info("The queue is currently empty.")

if st.button("🗑 Clear Finished Jobs"):
    qm.clear_finished()
    st.rerun()

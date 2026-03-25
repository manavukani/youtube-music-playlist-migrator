1. **Create `ui/app.py`**
   - Streamlit entry point.
   - Sidebar with queue summary badge.
   - Home page content explaining the tool.

2. **Create `ui/session.py`**
   - Manage the singleton `QueueManager` in `st.session_state`.

3. **Create `ui/queue_manager.py`**
   - Core job queue engine.
   - `TransferJob` dataclass for job state.
   - `QueueManager` class with background daemon thread.
   - `_execute_job` handles patching `sys.stdout` to capture logs and updating progress.

4. **Create `ui/pages/1_auth.py`**
   - Authentication status.
   - Button to run OAuth setup (`auth_module.setup_oauth()`).
   - Expander for advanced setup via request headers.

5. **Create `ui/pages/2_load_csv.py`**
   - Load CSVs from a directory and convert to `playlists.json`.
   - Preview CSV files.
   - Validation before conversion.

6. **Create `ui/components/playlist_table.py`**
   - Reusable `render_playlist_table` component for filtering and sorting playlists.

7. **Create `ui/pages/3_playlists.py`**
   - Browse source playlists (`playlists.json`) and YTMusic playlists side-by-side.
   - Uses `render_playlist_table`.
   - Inspect source playlist contents.

8. **Create `ui/pages/4_queue.py`**
   - Main job queue UI.
   - Submit new jobs (source playlist, target YTMusic playlist, options).
   - Queue status with auto-refresh (`streamlit-autorefresh`).
   - Summary row and colored job cards.

9. **Create `ui/pages/5_status.py`**
   - View `state.json`.
   - View unmatched tracks (`unmatched_tracks.csv`).
   - Reset state.

10. **Update `requirements.txt`**
    - Add `streamlit>=1.35.0`, `streamlit-autorefresh>=0.0.1`, `pandas>=2.0.0`.

11. **Run Pre-commit Checks**
    - Run `pre_commit_instructions` to ensure proper testing, verification, review, and reflection are done.

12. **Submit Changes**
    - Commit and push changes.

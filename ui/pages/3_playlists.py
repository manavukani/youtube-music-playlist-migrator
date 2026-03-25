import streamlit as st
import pandas as pd
from playlistmigrator import backend, auth as auth_module
from ui.components.playlist_table import render_playlist_table

st.title("📋 Playlists")

playlists = []

tab_source, tab_yt = st.tabs(["Source Playlists", "YTMusic Playlists"])

# --- Source Playlists tab ---
with tab_source:
    try:
        spotify_pls = backend.load_playlists_json()
        playlists = spotify_pls.get("playlists", [])

        formatted_playlists = [
            {
                "id": pl.get("id"),
                "name": pl.get("name"),
                "count": len(pl.get("tracks", [])),
            }
            for pl in playlists
        ]

        st.caption(f"{len(formatted_playlists)} playlists loaded from `playlists.json`")
        render_playlist_table(
            formatted_playlists, "id", "name", "count", "Search source playlists", show_id=True
        )

    except FileNotFoundError:
        st.warning("`playlists.json` not found. Run **Load CSV** first.")

    st.divider()

    with st.expander("Inspect a Source Playlist"):
        if playlists:
            playlist_names = [pl.get("name") for pl in playlists]
            selected_name = st.selectbox("Select a playlist to inspect:", playlist_names)

            if selected_name:
                selected_pl = next(
                    (p for p in playlists if p.get("name") == selected_name), None
                )
                if selected_pl:
                    tracks = selected_pl.get("tracks", [])
                    track_data = []
                    for t in tracks:
                        track_info = t.get("track", {})
                        if track_info:
                            name = track_info.get("name", "Unknown")
                            artists = ", ".join(
                                a.get("name", "Unknown")
                                for a in track_info.get("artists", [])
                            )
                            album = track_info.get("album", {}).get("name", "Unknown")
                            track_data.append(
                                {"Track": name, "Artist": artists, "Album": album}
                            )

                    st.dataframe(
                        pd.DataFrame(track_data),
                        width='stretch',
                        hide_index=True,
                    )
        else:
            st.info("No source playlists loaded.")

# --- YTMusic Playlists tab ---
with tab_yt:

    @st.cache_data(ttl=300)
    def fetch_yt_playlists():
        try:
            yt = auth_module.get_ytmusic()
            return yt.get_library_playlists(limit=5000)
        except Exception as e:
            st.error(f"Check authentication on the Auth page: {e}")
            return []

    if st.button("🔄 Refresh", help="Re-fetch playlists from YTMusic"):
        st.cache_data.clear()

    yt_playlists = fetch_yt_playlists()

    if yt_playlists:
        st.caption(f"{len(yt_playlists)} playlists found on YTMusic")
        render_playlist_table(
            yt_playlists, "playlistId", "title", "count", "Search YTMusic playlists"
        )

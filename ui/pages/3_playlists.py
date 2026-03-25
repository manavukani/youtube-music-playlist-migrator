import os
import streamlit as st
import pandas as pd
from playlistmigrator import backend, auth as auth_module
from ui.components.playlist_table import render_playlist_table

st.title("📋 Playlists")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Source Playlists (playlists.json)")
    try:
        spotify_pls = backend.load_playlists_json()
        playlists = spotify_pls.get("playlists", [])

        # Adjust data format for the component
        formatted_playlists = []
        for pl in playlists:
            formatted_playlists.append({
                "id": pl.get("id"),
                "name": pl.get("name"),
                "count": len(pl.get("tracks", []))
            })

        render_playlist_table(formatted_playlists, "id", "name", "count", "Filter Source")

    except FileNotFoundError:
        st.warning("`playlists.json` not found. Run Load CSV first.")
        playlists = []

with col2:
    st.subheader("YTMusic Playlists")

    @st.cache_data(ttl=300)
    def fetch_yt_playlists():
        try:
            yt = auth_module.get_ytmusic()
            return yt.get_library_playlists(limit=5000)
        except Exception as e:
            st.error(f"Check authentication on the Auth page: {e}")
            return []

    if st.button("🔄 Refresh"):
        st.cache_data.clear()

    yt_playlists = fetch_yt_playlists()

    if yt_playlists:
        render_playlist_table(yt_playlists, "playlistId", "title", "count", "Filter YTMusic")


st.markdown("---")

with st.expander("Inspect a Source Playlist"):
    if playlists:
        playlist_names = [pl.get("name") for pl in playlists]
        selected_name = st.selectbox("Select a playlist to inspect:", playlist_names)

        if selected_name:
            selected_pl = next((p for p in playlists if p.get("name") == selected_name), None)
            if selected_pl:
                tracks = selected_pl.get("tracks", [])

                track_data = []
                for t in tracks:
                    track_info = t.get("track", {})
                    if track_info:
                        name = track_info.get("name", "Unknown")
                        artists = ", ".join([a.get("name", "Unknown") for a in track_info.get("artists", [])])
                        album = track_info.get("album", {}).get("name", "Unknown")

                        track_data.append({
                            "Track Name": name,
                            "Artist": artists,
                            "Album": album
                        })

                st.dataframe(pd.DataFrame(track_data), use_container_width=True)
    else:
        st.info("No source playlists loaded.")

import streamlit as st
import pandas as pd

def render_playlist_table(playlists: list, id_key: str, name_key: str, count_key: str, search_label: str = "Filter"):
    """
    Renders a filterable, sortable dataframe of playlists.
    Returns the list of currently displayed rows (after filter).
    """
    query = st.text_input(search_label, key=f"search_{id_key}")
    rows = [
        {
            "ID": pl.get(id_key, ""),
            "Name": pl.get(name_key, ""),
            "Tracks": pl.get(count_key, "?"),
        }
        for pl in playlists
    ]
    df = pd.DataFrame(rows)
    if query:
        df = df[df["Name"].str.contains(query, case=False, na=False)]
    st.dataframe(df, use_container_width=True, hide_index=True)
    return df

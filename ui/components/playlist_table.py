import streamlit as st
import pandas as pd


def render_playlist_table(
    playlists: list,
    id_key: str,
    name_key: str,
    count_key: str,
    search_label: str = "Filter",
    show_id: bool = False,
):
    """
    Renders a filterable, sortable dataframe of playlists.
    Returns the filtered DataFrame.
    """
    query = st.text_input(search_label, key=f"search_{id_key}")
    rows = [
        {
            "Name": pl.get(name_key, ""),
            "Tracks": pl.get(count_key, "?"),
            "_id": pl.get(id_key, ""),
        }
        for pl in playlists
    ]
    df = pd.DataFrame(rows)
    if query:
        df = df[df["Name"].str.contains(query, case=False, na=False)]

    display_cols = ["Name", "Tracks"]
    if show_id:
        display_cols = ["Name", "Tracks", "_id"]

    column_config = {
        "Name": st.column_config.TextColumn("Name", width="large"),
        "Tracks": st.column_config.NumberColumn("Tracks", width="small"),
        "_id": st.column_config.TextColumn("ID", width="medium"),
    }

    st.dataframe(
        df[display_cols],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
    )
    return df

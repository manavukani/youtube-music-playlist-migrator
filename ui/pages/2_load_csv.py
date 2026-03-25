import os
import streamlit as st
import pandas as pd
from playlistmigrator import backend

st.title("📂 Load CSV Files")

csv_dir = st.text_input("CSV Directory path", value="./csvs")
output_file = "playlists.json"

st.markdown("---")

if st.button("Scan Directory"):
    if not os.path.exists(csv_dir):
        st.error(f"Directory `{csv_dir}` not found.")
    else:
        files = [f for f in os.listdir(csv_dir) if f.endswith('.csv')]

        if not files:
            st.warning(f"No CSV files found in `{csv_dir}`.")
        else:
            table_data = []

            for file in files:
                filepath = os.path.join(csv_dir, file)
                try:
                    df = pd.read_csv(filepath)
                    cols = df.columns.tolist()

                    has_track = 'Track Name' in cols
                    has_artist = any(c in cols for c in ['Artist Name(s)', 'Artist Name'])

                    if not has_track or not has_artist:
                        status = "❌ Missing Columns"
                    else:
                        status = "✅ Valid"

                    table_data.append({
                        "Filename": file,
                        "Detected Tracks": len(df),
                        "Status": status
                    })
                except Exception as e:
                    table_data.append({
                        "Filename": file,
                        "Detected Tracks": "Error",
                        "Status": f"❌ {str(e)}"
                    })

            st.dataframe(pd.DataFrame(table_data), width='stretch')

if st.button("Convert to playlists.json"):
    with st.spinner("Converting CSVs..."):
        try:
            backend.csv_to_json(csv_dir, output_file)
            st.success(f"✅ Conversion successful! Written to `{output_file}`.")
        except Exception as e:
            st.error(f"Error during conversion: {e}")

st.markdown("---")

with st.expander("Current playlists.json contents"):
    if os.path.exists(output_file):
        try:
            import json
            with open(output_file, 'r') as f:
                data = json.load(f)
            st.json(data)
        except Exception as e:
            st.error(f"Failed to read `{output_file}`: {e}")
    else:
        st.info("Not found. Run conversion first.")

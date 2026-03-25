import os
import json
import streamlit as st
from playlistmigrator import auth as auth_module
from playlistmigrator import creds_generator

st.title("🔐 Authentication")

# Status card
if os.path.exists("creds.json"):
    try:
        with open("creds.json", "r") as f:
            json.load(f)
        st.success("✅ Authenticated (creds.json found and valid)")
    except json.JSONDecodeError:
        st.error("❌ Corrupted credentials (creds.json is not valid JSON)")
else:
    st.error("❌ Not authenticated (creds.json missing)")

st.markdown("---")

with st.expander("Advanced — Setup via request headers"):
    st.markdown("""
    1. Log in to YouTube Music in your browser.
    2. Open Inspection Tool (F12) -> Network tab.
    3. Filter by `/browse` and copy the request as cURL.
    4. Paste it below.
    """)
    headers_input = st.text_area("Paste cURL or raw headers here:", height=150)

    if st.button("Generate creds.json from headers"):
        if headers_input:
            with st.spinner("Generating credentials..."):
                try:
                    with open("request_headers.txt", "w") as f:
                        f.write(headers_input)

                    creds_generator.setup_ytmusic_with_request_headers()
                    st.success("Credentials generated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate credentials: {e}")
        else:
            st.warning("Please paste the headers first.")

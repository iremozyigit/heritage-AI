import streamlit as st
import pandas as pd
import random
import time
import os
import io
import requests
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from textwrap import wrap
from PIL import Image as PILImage
import gspread
from google.oauth2.service_account import Credentials
import json
import uuid

# --- Set up connection to Google Sheets ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials_dict = st.secrets["gspread"]
credentials = Credentials.from_service_account_info(credentials_dict, scopes=scope)
client = gspread.authorize(credentials)

# --- Load Data ---
base_path = os.path.dirname(__file__)
file_path = os.path.join(base_path, 'data', 'real_museum_metadata_with_ai.json')

if os.path.exists(file_path):
    data = pd.read_json(file_path)
else:
    st.error(f"Metadata file not found at {file_path}. Please check your data folder.")
    st.stop()

# --- Setup Session State ---
if "group" not in st.session_state:
    st.session_state.group = random.choice(["curator", "ai"])
if "start_times" not in st.session_state:
    st.session_state.start_times = {}
if "viewed_items" not in st.session_state:
    st.session_state.viewed_items = []
if "index" not in st.session_state:
    st.session_state.index = 0
if "selected_indices" not in st.session_state:
    st.session_state.selected_indices = random.sample(range(len(data)), 20)
if "exhibition_title" not in st.session_state:
    st.session_state.exhibition_title = ""
if "exhibition_description" not in st.session_state:
    st.session_state.exhibition_description = ""
if "preferences" not in st.session_state:
    st.session_state.preferences = {}
if "exhibition_stage" not in st.session_state:
    st.session_state.exhibition_stage = "select_artworks"
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# --- Main App Logic ---
if st.session_state.index < len(st.session_state.selected_indices):
    artwork = data.iloc[st.session_state.selected_indices[st.session_state.index]]

    st.image(artwork['image_url'], use_container_width=True)
    st.subheader(artwork['title'])
    st.caption(f"Artist: {artwork.get('artist', 'Unknown')}")

    description_text = artwork['description'] if st.session_state.group == "curator" else artwork.get('ai_story', None)
    st.write(description_text if description_text else "No description available for this artwork.")

    if artwork['id'] not in st.session_state.start_times:
        st.session_state.start_times[artwork['id']] = time.time()

    if st.button("Next", key=f"next_{artwork['id']}"):
        end_time = time.time()
        time_spent = end_time - st.session_state.start_times[artwork['id']]

        st.session_state.viewed_items.append({
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": st.session_state.session_id,
            "artwork_id": artwork['id'],
            "title": artwork['title'],
            "time_spent_seconds": round(time_spent, 2),
            "group": st.session_state.group
        })

        st.session_state.index += 1
        st.rerun()

else:
    st.title("Thank you for participating!")
    st.write("You have completed the main session.")

    # --- Write interaction data to Google Sheets ---
    try:
        sheet = client.open("Digital Museum Streamlit Data Sheet").sheet1
        df_views = pd.DataFrame(st.session_state.viewed_items)
        if not df_views.empty:
            sheet.append_rows([df_views.columns.tolist()] + df_views.values.tolist())
            st.success("Your viewing data has been saved.")
    except Exception as e:
        st.error(f"❌ Failed to write viewing data to Google Sheets: {e}")

    st.markdown("### ➡️ [Proceed to Post-Experience Survey](https://docs.google.com/forms/d/e/1FAIpQLSfMmbXk8-9qoEygXBqcBY2gAqiGrzDms48tcf0j_ax-px56pg/viewform?usp=header)")

    st.markdown("---")
    st.subheader("Curator Mode: Build Your Own Exhibition")

    st.write("Would you like to create your own mini-exhibition from the artworks you just saw? (Optional)")
    proceed = st.radio("Choose an option:", ["Yes, I want to build an exhibition", "No, I want to skip this step"], key="curator_choice")

    if proceed == "Yes, I want to build an exhibition":
        st.rerun()
    else:
        st.info("You chose to skip Curator Mode. Thank you for participating!")

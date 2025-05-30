import streamlit as st
import pandas as pd
import random
import time
import os
import io
import requests
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
    st.markdown("[Go to Survey](https://docs.google.com/forms/d/e/1FAIpQLSfMmbXk8-9qoEygXBqcBY2gAqiGrzDms48tcf0j_ax-px56pg/viewform?usp=header)")

    st.markdown("---")
    st.subheader("Curator Mode: Build Your Own Exhibition")

    st.write("Would you like to create your own mini-exhibition from the artworks you just saw? (Optional)")
    proceed = st.radio("Choose an option:", ["Yes, I want to build an exhibition", "No, I want to skip this step"], key="curator_choice")

    if proceed == "Yes, I want to build an exhibition":
        viewed_df = pd.DataFrame(st.session_state.viewed_items)
        selected_titles = []

        if st.session_state.exhibition_stage == "select_artworks":
            st.markdown("#### Select artworks to include in your exhibition:")
            col_left, col_right = st.columns(2)
            for i, row in enumerate(viewed_df.itertuples()):
                col = col_left if i % 2 == 0 else col_right
                with col:
                    st.markdown("**Select**")
                    if st.checkbox("", key=f"select_{row.artwork_id}_{i}"):
                        selected_titles.append(row.artwork_id)
                    st.image(data[data['id'] == row.artwork_id].iloc[0]['image_url'], width=160)
                    st.caption(row.title)

            if st.button("Save My Exhibition and Pick Descriptions for Artworks", key="save_exhibition"):
                if not selected_titles:
                    st.error("Please select at least 1 artwork to proceed.")
                else:
                    st.session_state.exhibition_stage = "pick_descriptions"
                    st.session_state.selected_titles = selected_titles
                    st.rerun()

        elif st.session_state.exhibition_stage == "pick_descriptions":
            selected_titles = st.session_state.selected_titles
            st.success("Artworks selected. Now select which description you'd include for each artwork.")
            for artwork_id in selected_titles:
                artwork_row = data[data['id'] == artwork_id].iloc[0]
                title = artwork_row['title']
                curator_desc = artwork_row['description'] or "No curator description available."
                ai_desc = artwork_row['ai_story'] or "No AI-generated description available."

                desc_key = f"description_order_{artwork_id}"

                if desc_key not in st.session_state:
                    descriptions = [("A", curator_desc, "curator"), ("B", ai_desc, "ai")]
                    random.shuffle(descriptions)
                    st.session_state[desc_key] = descriptions
                else:
                    descriptions = st.session_state[desc_key]

                st.markdown(f"### {title}")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Description A**")
                    st.write(descriptions[0][1])
                with col2:
                    st.markdown("**Description B**")
                    st.write(descriptions[1][1])

                choice = st.radio(
                    f"Which description would you include for '{title}'?",
                    ["Description A", "Description B"],
                    key=f"preference_{artwork_id}"
                )

                st.session_state.preferences[artwork_id] = {
                    "artwork_title": title,
                    "user_choice": choice,
                    "description_A_source": descriptions[0][2],
                    "description_B_source": descriptions[1][2]
                }

            st.markdown("---")
            st.subheader("Finalize Your Exhibition")

            st.session_state.exhibition_title = st.text_input("Give your exhibition a title:", value=st.session_state.exhibition_title, key="exhibition_title_input")
            st.session_state.exhibition_description = st.text_area("Describe your theme in 1–2 sentences:", value=st.session_state.exhibition_description, key="exhibition_description_input")

            if st.button("Save My Exhibition", key="finalize_exhibition"):
                if not st.session_state.exhibition_title or not st.session_state.exhibition_description:
                    st.error("Please provide a title and description to save your exhibition.")
                else:
                    st.session_state.curated_exhibition = {
                        "selected_ids": selected_titles,
                        "exhibition_title": st.session_state.exhibition_title,
                        "exhibition_description": st.session_state.exhibition_description,
                        "preferences": st.session_state.preferences
                    }
                    st.success("Your exhibition has been saved!")

                    # Write session data to Google Sheets
                    try:
                        sheet = client.open("Digital Museum Streamlit Data Sheet").sheet1
                        df_views = pd.DataFrame(st.session_state.viewed_items)
                        view_rows = df_views.values.tolist()
                        sheet.append_rows([["Artwork ID", "Title", "Time Spent (s)", "Group"]] + view_rows)

                        summary_row = [
                            "EXHIBITION SUMMARY",
                            st.session_state.exhibition_title,
                            st.session_state.exhibition_description,
                            ", ".join(selected_titles),
                            json.dumps(st.session_state.preferences)
                        ]
                        sheet.append_row(summary_row)
                    except Exception as e:
                        st.error(f"❌ Failed to write session data to Google Sheets: {e}")

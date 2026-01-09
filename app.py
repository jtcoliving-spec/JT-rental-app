import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import cloudinary
import cloudinary.uploader

# --- CLOUDINARY DIRECT CONFIG (Safety Backup) ---
# This ensures even if the Secrets vault is acting up, the app has the keys
CLOUDINARY_NAME = st.secrets.get("cloud_name", "dtjnolrto")
CLOUDINARY_API_KEY = st.secrets.get("api_key", "222527173245397")
CLOUDINARY_API_SECRET = st.secrets.get("api_secret", "fRtbmFO5zaBJie3Jdi82wPsxKTw")

cloudinary.config( 
  cloud_name = CLOUDINARY_NAME, 
  api_key = CLOUDINARY_API_KEY, 
  api_secret = CLOUDINARY_API_SECRET 
)

# --- GOOGLE SHEETS CONFIG ---
RATE_PER_UNIT = 0.60
ADMIN_PASSWORD = "admin123" 
SHEET_URL = "https://docs.google.com/spreadsheets/d/1UGG66jyHsNoPwAINcdsgg6oXyEq4WslAOnxLmiTJ7Z0/edit?usp=sharing"

st.set_page_config(page_title="Rental Management Pro", layout="wide", page_icon="🏠")
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name):
    return conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0)

def save_data(df, sheet_name):
    conn.update(spreadsheet=SHEET_URL, worksheet=sheet_name, data=df)
    st.cache_data.clear()

UNITS = ["5-7", "12-1", "13-1", "16-7", "19-1", "20-7", "21-8"]
ROOM_TYPES = ["Master bedroom M", "Living studio L", "Medium room M1", "Medium room M2", "Single room S"]

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

menu = st.sidebar.radio("Navigation", ["Tenant Portal", "Owner Admin"])

# --- OWNER ADMIN ---
if menu == "Owner Admin":
    st.header("🔑 Owner Management")
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        tab1, tab2 = st.tabs(["Manage Tenants", "Records History"])
        
        with tab1:
            t_db = load_data("tenants")
            edited_t = st.data_editor(t_db, num_rows="dynamic")
            if st.button("Save Tenant Changes"):
                save_data(edited_t, "tenants")
                st.success("Updated!")
        
        with tab2:
            r_db = load_data("records")
            st.dataframe(r_db)

# --- TENANT PORTAL ---
else:
    st.header("📱 Tenant Portal")
    try:
        t_db = load_data("tenants")
        
        if not st.session_state.logged_in:
            name = st.selectbox("Select Name", [""] + t_db['Name'].tolist())
            pw = st.text_input("Password", type="password")
            if st.button("Login"):
                user = t_db[(t_db['Name'] == name) & (t_db['Password'] == str(pw))]
                if not user.empty:
                    st.session_state.logged_in = True
                    st.session_state.user = user.iloc[0]
                    st.rerun()
                else:
                    st.error("Invalid Login")
        else:
            info = st.session_state.user
            st.success(f"Welcome {info['Name']}")
            
            # Submission Form
            curr = st.number_input("New AC Reading", min_value=0.0)
            rent = st.number_input("Rent Amount (RM)", min_value=0.0)
            
            img_pay = st.file_uploader("Upload Receipt")
            img_ac = st.file_uploader("Upload Meter Photo")
            
            if st.button("Submit"):
                if img_pay and img_ac:
                    with st.spinner("Uploading..."):
                        res_p = cloudinary.uploader.upload(img_pay)
                        res_a = cloudinary.uploader.upload(img_ac)
                        
                        # Save to Sheet
                        history = load_data("records")
                        new_row = pd.DataFrame([{
                            "Date": datetime.now().strftime("%Y-%m-%d"),
                            "Unit": info['Unit'], "Tenant": info['Name'],
                            "AC_Reading": curr, "Total_Paid": rent,
                            "Receipt_URL": res_p['secure_url'],
                            "AC_Photo_URL": res_a['secure_url']
                        }])
                        save_data(pd.concat([history, new_row], ignore_index=True), "records")
                        st.balloons()
                        st.success("Submitted!")
    except Exception as e:
        st.error(f"Waiting for database connection... If this persists, check your Google Sheet tabs. Error: {e}")

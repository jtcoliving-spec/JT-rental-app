import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import cloudinary
import cloudinary.uploader

# --- CONFIGURATION ---
RATE_PER_UNIT = 0.60
ADMIN_PASSWORD = "admin123"  # <--- SET YOUR NEW ADMIN PASSWORD HERE
SHEET_URL = "https://docs.google.com/spreadsheets/d/1UGG66jyHsNoPwAINcdsgg6oXyEq4WslAOnxLmiTJ7Z0/edit?usp=sharing"

# --- CLOUDINARY SETUP ---
# Ensure these are in your Streamlit Secrets
try:
    cloudinary.config( 
      cloud_name = st.secrets["cloud_name"], 
      api_key = st.secrets["api_key"], 
      api_secret = st.secrets["api_secret"] 
    )
except Exception:
    st.error("Cloudinary secrets are missing. Please add them to Streamlit Secrets.")

st.set_page_config(page_title="Rental Management Pro", layout="wide", page_icon="🏠")
conn = st.connection("gsheets", type=GSheetsConnection)

# Helper functions
def load_data(sheet_name):
    return conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0)

def save_data(df, sheet_name):
    conn.update(spreadsheet=SHEET_URL, worksheet=sheet_name, data=df)
    st.cache_data.clear()

UNITS = ["5-7", "12-1", "13-1", "16-7", "19-1", "20-7", "21-8"]
ROOM_TYPES = ["Master bedroom M", "Living studio L", "Medium room M1", "Medium room M2", "Single room S"]

# Initialize Login Session State
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_info' not in st.session_state:
    st.session_state.user_info = None

menu = st.sidebar.radio("Navigation", ["Tenant Portal", "Owner Admin"])

# --- OWNER ADMIN (Edit, Delete, Register) ---
if menu == "Owner Admin":
    st.header("🔑 Owner Management")
    if st.text_input("Admin Password", type="password") == ADMIN_PASSWORD:
        
        tab1, tab2, tab3 = st.tabs(["Register Tenant", "Manage/Delete Tenants", "Edit AC History"])
        
        with tab1:
            st.subheader("Add New Tenant")
            with st.form("reg"):
                t_name = st.text_input("Tenant Full Name")
                t_unit = st.selectbox("Unit", UNITS)
                t_room = st.selectbox("Room Type", ROOM_TYPES)
                t_pw = st.text_input("Set Password", type="password")
                t_initial_ac = st.number_input("Starting AC Meter Reading", min_value=0.0)
                
                if st.form_submit_button("Save Tenant"):
                    t_df = load_data("tenants")
                    new_t = pd.DataFrame([{"Name": t_name, "Unit": t_unit, "Room": t_room, "Password": t_pw}])
                    save_data(pd.concat([t_df, new_t], ignore_index=True), "tenants")
                    
                    r_df = load_data("records")
                    init_log = pd.DataFrame([{
                        "Date": "INIT", "Unit": t_unit, "Room": t_room, "Tenant": t_name, 
                        "Prev_Reading": 0, "AC_Reading": t_initial_ac, "Units_Used": 0, 
                        "AC_Cost": 0, "Rent_Paid": 0, "Total_Paid": 0,
                        "Receipt_URL": "N/A", "AC_Photo_URL": "N/A"
                    }])
                    save_data(pd.concat([r_df, init_log], ignore_index=True), "records")
                    st.success("Tenant Saved!")

        with tab2:
            st.subheader("Current Tenants")
            t_db = load_data("tenants")
            if not t_db.empty:
                edited_df = st.data_editor(t_db, num_rows="dynamic", key="tenant_editor")
                if st.button("Save Changes to Tenant List"):
                    save_data(edited_df, "tenants")
                    st.success("Tenant database updated!")
                st.info("Mobile Users: Tap a cell to edit. To delete, use the 'trash' icon or delete the row text.")

        with tab3:
            st.subheader("Edit/Correct AC Records")
            r_db = load_data("records")
            if not r_db.empty:
                edited_r = st.data_editor(r_db, key="record_editor")
                if st.button("Update All Records"):
                    save_data(edited_r, "records")
                    st.success("Billing records corrected!")

# --- TENANT PORTAL (Login & Submission) ---
else:
    st.header("📱 Tenant Portal")
    t_db = load_data("tenants")

    if not st.session_state.logged_in:
        with st.container(border=True):
            st.subheader("Sign In")
            name_input = st.selectbox("Select Your Name", [""] + t_db['Name'].tolist())
            pw_input = st.text_input("Enter Your Password", type="password")
            if st.button("Login"):
                user = t_db[(t_db['Name'] == name_input) & (t_db['Password'] == str(pw_input))]
                if not user.empty:
                    st.session_state.logged_in = True
                    st.session_state.user_info = user.iloc[0]
                    st.rerun()
                else:
                    st.error("Invalid name or password.")
    else:
        info = st.session_state.user_info
        st.success(f"Logged in: {info['Name']} | Unit {info['Unit']}")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

        # Submission Logic
        history = load_data("records")
        my_hist = history[(history['Unit'] == info['Unit']) & (history['Room'] == info['Room'])]
        prev = my_hist.iloc[-1]['AC_Reading'] if not my_hist.empty else 0.0
        
        st.write(f"**Previous Reading:** {prev} units")
        curr = st.number_input("Current Meter Reading", min_value=float(prev), step=0.1)
        rent = st.number_input("Monthly Rent Amount (RM)", min_value=0.0)
        
        used = curr - prev
        ac_cost = used * RATE_PER_UNIT
        total = rent + ac_cost
        
        st.metric("Total to Pay", f"RM {total:.2f}", delta=f"AC: RM {ac_cost:.2f}")

        img_pay = st.file_uploader("Upload Payment Slip", type=['png', 'jpg', 'jpeg'])
        img_ac = st.file_uploader("Upload AC Meter Photo", type=['png', 'jpg', 'jpeg'])
        
        if st.button("Submit My Record"):
            if img_pay and img_ac:
                with st.spinner("Uploading and saving..."):
                    res_pay = cloudinary.uploader.upload(img_pay)
                    res_ac = cloudinary.uploader.upload(img_ac)
                    
                    new_rec = pd.DataFrame([{
                        "Date": datetime.now().strftime("%Y-%m-%d"),
                        "Unit": info['Unit'], "Room": info['Room'], "Tenant": info['Name'],
                        "Prev_Reading": prev, "AC_Reading": curr, "Units_Used": used,
                        "AC_Cost": ac_cost, "Rent_Paid": rent, "Total_Paid": total,
                        "Receipt_URL": res_pay['secure_url'], "AC_Photo_URL": res_ac['secure_url']
                    }])
                    save_data(pd.concat([history, new_rec], ignore_index=True), "records")
                    st.balloons()
                    st.success("Submitted successfully! Your landlord will see the record.")
            else:
                st.error("Please upload both the payment slip and the AC meter photo.")

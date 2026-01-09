import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
RATE_PER_UNIT = 0.60
SHEET_URL = "YOUR_GOOGLE_SHEET_URL_HERE" # Ensure this is your link

st.set_page_config(page_title="Rental Management Pro", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# Helper functions
def load_data(sheet_name):
    return conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0)

def save_data(df, sheet_name):
    conn.update(spreadsheet=SHEET_URL, worksheet=sheet_name, data=df)
    st.cache_data.clear()

# Custom Lists
UNITS = ["5-7", "12-1", "13-1", "16-7", "19-1", "20-7", "21-8"]
ROOM_TYPES = ["Master bedroom M", "Living studio L", "Medium room M1", "Medium room M2", "Single room S"]

menu = st.sidebar.radio("Navigation", ["Tenant Login", "Owner Admin"])

# --- OWNER ADMIN (For Registering & Pre-setting AC) ---
if menu == "Owner Admin":
    st.header("🔑 Owner Management")
    if st.text_input("Admin Password", type="password") == "admin123":
        st.subheader("Register New Tenant")
        with st.form("reg"):
            t_name = st.text_input("Tenant Full Name")
            t_unit = st.selectbox("Unit", UNITS)
            t_room = st.selectbox("Room Type", ROOM_TYPES)
            t_pw = st.text_input("Create Tenant Password", type="password")
            # This is where you pre-set the starting AC reading
            t_initial_ac = st.number_input("Starting AC Meter Reading", min_value=0.0, step=0.1)
            
            if st.form_submit_button("Register & Save"):
                # 1. Add to Tenant List
                t_df = load_data("tenants")
                new_t = pd.DataFrame([{"Name": t_name, "Unit": t_unit, "Room": t_room, "Password": t_pw}])
                save_data(pd.concat([t_df, new_t], ignore_index=True), "tenants")
                
                # 2. Log Initial Reading into Records so the app has a "Previous" value
                r_df = load_data("records")
                init_log = pd.DataFrame([{
                    "Date": "INITIAL SETUP", "Unit": t_unit, "Room": t_room, "Tenant": t_name,
                    "Prev_Reading": 0, "AC_Reading": t_initial_ac, "Units_Used": 0, 
                    "AC_Cost": 0, "Rent_Paid": 0, "Total_Paid": 0
                }])
                save_data(pd.concat([r_df, init_log], ignore_index=True), "records")
                st.success("Tenant registered and AC starting point set!")

# --- TENANT LOGIN & PORTAL ---
else:
    st.header("📱 Tenant Portal")
    tenant_db = load_data("tenants")
    
    # Login Logic
    name_input = st.selectbox("Select Your Name", [""] + tenant_db['Name'].tolist())
    pw_input = st.text_input("Enter Your Password", type="password")
    
    if name_input and pw_input:
        user_row = tenant_db[(tenant_db['Name'] == name_input) & (tenant_db['Password'] == str(pw_input))]
        
        if not user_row.empty:
            info = user_row.iloc[0]
            st.success(f"Logged in: {info['Unit']} - {info['Room']}")
            
            # Get Last Reading
            history = load_data("records")
            my_hist = history[(history['Unit'] == info['Unit']) & (history['Room'] == info['Room'])]
            prev = my_hist.iloc[-1]['AC_Reading'] if not my_hist.empty else 0.0
            
            st.metric("Previous Meter Reading", f"{prev} units")
            curr = st.number_input("Enter New AC Meter Reading", min_value=float(prev), step=0.1)
            
            used = curr - prev
            ac_cost = used * RATE_PER_UNIT
            rent = st.number_input("Monthly Rent (RM)", min_value=0.0)
            
            st.subheader(f"Total Amount to Pay: RM {rent + ac_cost:.2f}")
            
            # Photo Uploaders
            img_pay = st.file_uploader("Upload Payment Slip", type=['png', 'jpg', 'jpeg'])
            img_ac = st.file_uploader("Upload AC Meter Photo", type=['png', 'jpg', 'jpeg'])
            
            if st.button("Submit Monthly Record"):
                if img_pay and img_ac:
                    # NOTE: Since we are using Google Sheets, we save the status here. 
                    # Real image hosting requires extra setup, so for now we log that they were uploaded.
                    new_rec = pd.DataFrame([{
                        "Date": datetime.now().strftime("%Y-%m-%d"),
                        "Unit": info['Unit'], "Room": info['Room'], "Tenant": name_input,
                        "Prev_Reading": prev, "AC_Reading": curr, "Units_Used": used,
                        "AC_Cost": ac_cost, "Rent_Paid": rent, "Total_Paid": rent + ac_cost,
                        "Receipt_URL": "Uploaded", "AC_Photo_URL": "Uploaded"
                    }])
                    save_data(pd.concat([history, new_rec], ignore_index=True), "records")
                    st.balloons()
                    st.success("Submission Successful!")
                else:
                    st.error("Please upload both photos before submitting.")
        else:
            st.error("Incorrect password.")

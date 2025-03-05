import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import psycopg2
from passlib.hash import bcrypt
from dotenv import load_dotenv
import os
import urllib.parse as urlparse

#load_dotenv()

# Database connection
def get_conn():
    try:
        url = urlparse.urlparse(st.secrets["DATABASE_URL"])
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        return conn
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return None

# # Initialize session state
# if 'authenticated' not in st.session_state:
#     st.session_state.authenticated = False
# if 'user' not in st.session_state:
#     st.session_state.user = None
# if 'current_batch' not in st.session_state:
#     st.session_state.current_batch = None

# Session state initialization
if 'authenticated' not in st.session_state:
    st.session_state.update({
        'authenticated': False,
        'user': None,
        'current_batch': None,
        'edit_mode': False,
        'edited_slabs': pd.DataFrame()
    })

# # Authentication functions
# def verify_credentials(username, password):
#     conn = get_conn()
#     cur = conn.cursor()
#     cur.execute("SELECT id, password_hash, role FROM users WHERE username = %s", (username,))
#     result = cur.fetchone()
    
#     cur.close()
#     conn.close()
    
#     if result and bcrypt.verify(password, result[1]):
#         return {"id": result[0], "role": result[2]}
#     return None

# Authentication functions
def verify_user(username, password):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id,password_hash, role 
                FROM users 
                WHERE username = %s
            """, (username,))
            result = cur.fetchone()
            if result and bcrypt.verify(password, result[1]):
                return {'id': result[0], 'role': result[2]}
    finally:
        conn.close()
    return None

# Login Form
def login_form():
    st.title("Slab Measurement System Login")
    with st.form("Login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.form_submit_button("Login"):
            user = verify_user(username, password)
            if user:
                st.session_state.update({
                    'authenticated': True,
                    'user': user
                })
                st.rerun()
            else:
                st.error("Invalid credentials")


# Admin User Management
def admin_panel():
    st.sidebar.header("Admin Panel")
    with st.sidebar.expander("Create New User"):
        with st.form("New User"):
            new_user = st.text_input("Username")
            new_pass = st.text_input("Password", type="password")
            user_role = st.selectbox("Role", ["marker", "admin"])
            if st.form_submit_button("Create User"):
                conn = get_conn()
                try:
                    with conn.cursor() as cur:
                        hash_pw = bcrypt.hash(new_pass)
                        cur.execute("""
                            INSERT INTO users (username, password_hash, role)
                            VALUES (%s, %s, %s)
                        """, (new_user, hash_pw, user_role))
                        conn.commit()
                        st.success("User created successfully")
                except psycopg2.Error as e:
                    st.error(f"Error: {e}")
                finally:
                    conn.close()

# Main App
# if not st.session_state.authenticated:
#     st.title("Slab Measurement System Login")
#     login_form()
#     st.stop()

# # Admin Section
# if st.session_state.user['role'] == 'admin':
#     admin_panel()

# # Logout button
# if st.sidebar.button("Logout"):                     ## change the posistion of logout
#     st.session_state.authenticated = False
#     st.session_state.user = None
#     st.rerun()

def slab_correction_interface(batch_number):
    conn = get_conn()
    try:
        slabs_df = pd.read_sql(f"""
            SELECT slab_number, length, width, grade 
            FROM slabs 
            WHERE batch_number = '{batch_number}'
            ORDER BY slab_number
        """, conn)

        # Add a temporary unique identifier for each row (e.g., row index)
        slabs_df['row_key'] = range(len(slabs_df))
        
        # Make the key unique by incorporating the batch_number
        edited_df = st.data_editor(
            slabs_df,
            key=f"slab_editor_{batch_number}",  # Unique key for each batch
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "row_key": None  # Hide the row_key column from the user
            }
        )
        
        if not edited_df.equals(slabs_df):
            # Check for duplicate slab_numbers in the edited DataFrame
            if edited_df['slab_number'].duplicated().any():
                st.error("Duplicate slab numbers detected. Please ensure each slab number is unique.")
                return
            
            with conn.cursor() as cur:
                # Delete removed rows
                original_numbers = set(slabs_df['slab_number'])
                current_numbers = set(edited_df['slab_number'])
                deleted = original_numbers - current_numbers
                if deleted:
                    cur.execute(f"""
                        DELETE FROM slabs 
                        WHERE batch_number = %s 
                        AND slab_number IN %s
                    """, (batch_number, tuple(deleted)))
                
                # Update/insert modified rows
                for _, row in edited_df.iterrows():
                    cur.execute("""
                        INSERT INTO slabs 
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (slab_number) 
                        DO UPDATE SET
                            length = EXCLUDED.length,
                            width = EXCLUDED.width,
                            sq_ft = EXCLUDED.length * EXCLUDED.width,
                            grade = EXCLUDED.grade
                    """, (                        
                        row['slab_number'],
                        row['length'],
                        row['width'],
                        row['length'] * row['width'],
                        row['grade'],
                        batch_number
                    ))
                conn.commit()
                st.success("Changes saved successfully!")
    finally:
        conn.close()

# Main Application
def main_app():
    st.title("Slab Measurements Entry")
    
    # Section 1: Batch Creation
    with st.expander("Create New Batch", expanded=True):
        
        supplier_name = st.text_input("Supplier Name")
        batch_no = st.text_input("Batch Number")
        color = st.text_input("Color")
        thickness = st.text_input("Thickness")
        date = st.date_input("Date", value=datetime.today())
        if st.button("Enter Measurement"):
            if supplier_name and batch_no and color and thickness:
                conn = get_conn()
                
                try:
                    with conn.cursor() as cur:
                        cur.execute("INSERT INTO batches (supplier_name, batch_number, color, user_id, date, thickness) VALUES (%s, %s, %s, %s, %s, %s)",
                        (supplier_name, batch_no, color, st.session_state.user['id'], date, thickness))
                        conn.commit()
                        st.session_state.current_batch = batch_no
                        st.success("Batch created successfully!")
                except psycopg2.IntegrityError:
                    st.error("Batch number already exists!")
                    conn.rollback()
                finally:
                    conn.close()
            else:
                st.error("Please fill all required fields")

    # Section 2: Slab Entry
    if st.session_state.current_batch:
        with st.expander("Add New Slabs", expanded=True):
            slab_no = st.number_input("Slab Number", min_value=0)
            length = st.number_input("Length", min_value=0)
            width = st.number_input("Width", min_value=0)
            grade = st.selectbox("Grade", ["A", "B", "C", "D", "Other"])
            
            if st.button("Add Slab"):
                conn = get_conn()
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO slabs 
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (                        
                            slab_no,
                            length,
                            width,
                            length * width,
                            grade,
                            st.session_state.current_batch,
                        ))
                        conn.commit()
                        st.success("Slab added successfully!")
                except psycopg2.IntegrityError:
                    st.error("Slab number already exists in this batch!")
                    conn.rollback()
                finally:
                    conn.close()
    
    # Section 3: Data Correction
    st.header("Slab Review & Correction")
    slab_correction_interface(st.session_state.current_batch)
    
    # Excel Export
    if st.button("Generate Excel Report"):
        conn = get_conn()
        try:
            batch_df = pd.read_sql(f"""
                SELECT * FROM batches 
                WHERE batch_number = '{st.session_state.current_batch}'
            """, conn)
            
            slabs_df = pd.read_sql(f"""
                SELECT * FROM slabs 
                WHERE batch_number = '{st.session_state.current_batch}'
                ORDER BY slab_number
            """, conn)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                batch_df.to_excel(writer, index=False, sheet_name="Batch")
                slabs_df.to_excel(writer, index=False, sheet_name="Slabs")
            
            st.download_button(
                label="Download Excel Report",
                data=output.getvalue(),
                file_name=f"{st.session_state.current_batch}_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        finally:
            conn.close()


# App Flow Control
if not st.session_state.authenticated:
    
    login_form()
else:
    if st.session_state.user['role'] == 'admin':
        admin_panel()
    main_app()

    # Create an empty placeholder to push the logout button to the bottom
    spacer = st.sidebar.empty()

    # Place the logout button inside the empty container
    with spacer:
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()
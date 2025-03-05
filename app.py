# code added to select existing batches

import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import psycopg2
from passlib.hash import bcrypt
from dotenv import load_dotenv
import os
import urllib.parse as urlparse

import warnings
warnings.filterwarnings("ignore", category=UserWarning, message="pandas only supports SQLAlchemy connectable.*")
# Ignore all warnings related to bcrypt
warnings.simplefilter("ignore", category=UserWarning)
#load_dotenv()

# Database connection
# Function to create a SQLAlchemy engine
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


# Session state initialization
if 'authenticated' not in st.session_state:
    st.session_state.update({
        'authenticated': False,
        'user': None,
        'current_batch': None,
        'edit_mode': False,
        'edited_slabs': pd.DataFrame()
    })


# Function to verify user credentials
def verify_user(username, password):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id,password_hash, role, username 
                FROM users 
                WHERE username = %s
            """, (username,))
            result = cur.fetchone()
            if result and bcrypt.verify(password, result[1]):
                return {'id': result[0], 'role': result[2], 'username': result[3]}
    finally:
        conn.close()
    return None

# Login Form
def login_page():
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

# Function to fetch slabs for a batch
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

# Function to fetch user batches
def get_user_batches(id):
    conn = get_conn()
    try:
        return pd.read_sql(f"""
            SELECT batch_number, supplier_name, color, date
            FROM batches 
            WHERE user_id = %s
            ORDER BY date DESC
        """, conn, params=(id,))
    finally:
        conn.close()

# Modified Main Application
def main_app():
    st.title("Slab Measurements Entry")
    
    # Batch Selection Interface
    if 'selected_batch' not in st.session_state:
        st.session_state.selected_batch = None
    if 'show_create_batch' not in st.session_state:
        st.session_state.show_create_batch = False  # Controls visibility of the expander
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Create New Batch"):
            st.session_state.selected_batch = None
            st.session_state.current_batch = None
            st.session_state.show_create_batch = True
            
    
    with col2:
        user_batches = get_user_batches(st.session_state.user['id'])
        if not user_batches.empty:
            selected = st.selectbox(
                "📂 Open Existing Batch",
                options=["Select a batch"] + user_batches['batch_number'].tolist()
            )
            if selected and selected != "Select a batch":
                st.session_state.selected_batch = selected
                st.session_state.current_batch = selected
                

    # Batch Creation Section
    if st.session_state.show_create_batch:
        with st.expander("Create New Batch", expanded=True):
            with st.form("Batch Details"):
                supplier = st.text_input("Supplier Name")
                batch_no = st.text_input("Batch Number")
                color = st.text_input("Color")
                thickness = st.text_input("Thickness")
                batch_date = st.date_input("Date", value=datetime.today())
                
                if st.form_submit_button("Save Batch"):
                    if supplier and batch_no and color:
                        conn = get_conn()
                        try:
                            with conn.cursor() as cur:
                                cur.execute("""
                                    INSERT INTO batches 
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (
                                    supplier,
                                    batch_no,                            
                                    color,
                                    st.session_state.user['id'],
                                    batch_date,
                                    thickness
                                ))
                                conn.commit()
                                st.session_state.selected_batch = batch_no
                                st.session_state.current_batch = batch_no
                                st.success("Batch created successfully!")
                                st.session_state.show_create_batch = False 
                                
                        except psycopg2.IntegrityError:
                            st.error("Batch number already exists!")
                            conn.rollback()
                        finally:
                            conn.close()
                    else:
                        st.error("Please fill all required fields")

    if st.session_state.selected_batch:
        # Fetch batch information
        user_batches = get_user_batches(st.session_state.user['id'])
        
        # Filter the DataFrame for the selected batch
        batch_info_df = user_batches[user_batches['batch_number'] == st.session_state.selected_batch]
        
        # Check if the filtered DataFrame is not empty
        if not batch_info_df.empty:
            batch_info = batch_info_df.iloc[0]  # Access the first row
            
            # Display Batch Information
            st.header(f"Batch: {st.session_state.selected_batch}")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Supplier", batch_info['supplier_name'])
            with col2:
                st.metric("Color", batch_info['color'])
            with col3:
                st.metric("Created On", batch_info['date'].strftime('%Y-%m-%d'))
        else:
            st.error("No batch information found for the selected batch.")
    else:
        st.info("Please select or create a batch to view details.")
        
    if st.session_state.selected_batch:
        # Section 2: Slab Entry
        with st.expander("Add New Slabs", expanded=True):
                  
            slab_no = st.number_input("Slab Number", min_value=0, format="%d")
            length = st.number_input("Length", min_value=0, format="%d")        
            width = st.number_input("Height", min_value=0, format="%d")
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
                            st.session_state.selected_batch
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
        slab_correction_interface(st.session_state.selected_batch)
        
        # Excel Export
        if st.button("Generate Excel Report"):
            conn = get_conn()
            try:
                batch_df = pd.read_sql(f"""
                    SELECT b.supplier_name, b.batch_number, u.username, b.color, b.thickness, b.date
                    FROM batches b, users u
                    WHERE u.id = b.user_id AND b.batch_number = '{st.session_state.selected_batch}'
                """, conn)
                
                slabs_df = pd.read_sql(f"""
                    SELECT slab_number, length, width, sq_ft, grade 
                    FROM slabs 
                    WHERE batch_number = '{st.session_state.selected_batch}'
                    ORDER BY slab_number
                """, conn)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    batch_df.to_excel(writer, index=False, sheet_name="Batch")
                    slabs_df.to_excel(writer, index=False, sheet_name="Slabs")
                
                st.download_button(
                    label="Download Excel Report",
                    data=output.getvalue(),
                    file_name=f"{st.session_state.selected_batch}_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            finally:
                conn.close()

# App Flow Control
if not st.session_state.authenticated:
    login_page()
else:

    # Set page layout to wide
    st.set_page_config(layout="wide")
    # Create a horizontal layout with a logout button on the right
    col1, col2 = st.columns([8, 1])  # Adjust proportions to push button to the right
    with col2:
        logout = st.button("🚪 Logout")
    
    with col1:
        if st.session_state.user['role'] == 'admin':
            admin_panel()
        main_app()

    if logout:
        st.success("Logged out successfully!")
        st.session_state.clear()
        st.rerun()
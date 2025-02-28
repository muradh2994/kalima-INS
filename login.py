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
                SELECT password_hash, role 
                FROM users 
                WHERE username = %s
            """, (username,))
            result = cur.fetchone()
            if result and bcrypt.verify(password, result[0]):
                return {'username': username, 'role': result[1]}
    finally:
        conn.close()
    return None

# Login Form
def login_form():
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
if not st.session_state.authenticated:
    st.title("Slab Measurement System Login")
    login_form()
    st.stop()

# Admin Section
if st.session_state.user['role'] == 'admin':
    admin_panel()

# Logout button
if st.sidebar.button("Logout"):                     ## change the posistion of logout
    st.session_state.authenticated = False
    st.session_state.user = None
    st.rerun()

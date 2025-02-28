from passlib.hash import bcrypt
from dotenv import load_dotenv
import os
import psycopg2
import urllib.parse as urlparse

load_dotenv()

def get_db_connection():
    try:
        url = urlparse.urlparse(os.environ["DATABASE_URL"])
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def hash_and_update_password(username, new_password):
    hashed_password = bcrypt.hash(new_password)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = %s WHERE username = %s", (hashed_password, username))
        conn.commit()
        conn.close()
        print(f"Password for {username} updated successfully.")
    except Exception as e:
        print(f"Error updating password: {e}")

#Example usage, run this once, then remove the code.
hash_and_update_password("anwar", os.environ.get("admin_pwd"))
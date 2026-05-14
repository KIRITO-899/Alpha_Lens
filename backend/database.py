"""
User database helpers. Authentication HTTP routes are defined in app.py.
Secrets must come from environment variables (see project .env).
"""
import os
import sqlite3
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DB_PATH = os.path.join(_BACKEND_DIR, 'users.db')


def init_db():
    conn = sqlite3.connect(USERS_DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

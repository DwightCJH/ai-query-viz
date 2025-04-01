import sqlite3
import os

DATABASE = 'history.db'

def init_db():
    # Check if DB exists, connect or create
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Create table with updated schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prompt_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT NOT NULL,
            dataset_name TEXT,
            response_type TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            feedback TEXT CHECK(feedback IN ('useful', 'not_useful', NULL))
        )
    ''')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    # This allows running `python database.py` to initialize the DB
    print(f"Initializing database '{DATABASE}'...")
    init_db()
    print("Database initialized successfully.")
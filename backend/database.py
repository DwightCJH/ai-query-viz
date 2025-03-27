import sqlite3

def init_db():
    with sqlite3.connect('history.db') as conn:
        # Create a table for prompt history
        conn.execute('''
            CREATE TABLE IF NOT EXISTS prompt_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                response TEXT,
                timestamp TEXT
            )
        ''')
        conn.commit()

if __name__ == '__main__':
    init_db()
    print("Database initialized.")
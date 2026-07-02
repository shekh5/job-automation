import sqlite3
import os

DB_PATH = "/Users/bhawanisingh/.openclaw/workspace/stealth_applier/job_state.db"

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_jobs (
            job_url TEXT PRIMARY KEY
        )
    ''')
    conn.commit()
    conn.close()

def is_job_processed(job_url: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM processed_jobs WHERE job_url = ?', (job_url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_job_completed(job_url: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO processed_jobs (job_url)
        VALUES (?)
    ''', (job_url,))
    conn.commit()
    conn.close()
